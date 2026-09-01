"""Optional hardware-isolated sandbox backend for user-authored code execution.

Issue #12029: the Python Interpreter / Python REPL components execute
user-supplied code with ``exec`` inside the server process. The Python-level
hardening in :mod:`lfx.utils.python_repl_security` is best-effort defense in
depth, not a security boundary. This package adds an opt-in execution backend
that routes that code into a dedicated microVM per execution, so a malicious
payload lands in a throwaway VM (read-only rootfs, no network by default)
instead of the Langflow server process.

Operator contract:

* ``LANGFLOW_SANDBOX_BACKEND=none`` (default) — existing in-process behavior,
  nothing in this package activates and no backend package need be installed.
* Any other value names a registered backend. If that backend cannot be used
  (package not installed, no hardware hypervisor, missing credential)
  execution FAILS CLOSED with :class:`SandboxUnavailableError`; it never
  silently falls back to in-process ``exec``, because the operator explicitly
  asked for isolation.

Layout:

* :mod:`lfx.utils.sandbox.base` — result and error types, operator settings,
  code normalization, and the :class:`SandboxBackend` protocol.
* :mod:`lfx.utils.sandbox.registry` — name to implementation, one source of
  truth for which names are accepted.
* :mod:`lfx.utils.sandbox.exec_sandbox` — local QEMU microVMs via the
  `exec-sandbox <https://github.com/dualeai/exec-sandbox>`_ package.
"""

from __future__ import annotations

import contextlib
import os

from lfx.utils.sandbox.base import (
    Capabilities,
    SandboxBackend,
    SandboxExecutionError,
    SandboxResult,
    SandboxUnavailableError,
    _compose_sandbox_code,
    _sandbox_settings,
    build_import_preamble,
    sanitize_code,
)
from lfx.utils.sandbox.registry import (
    SANDBOX_BACKEND_NONE,
    get_sandbox_backend,
    is_sandbox_enabled,
    known_sandbox_backends,
    live_sandbox_backends,
    register_sandbox_backend,
    reset_registry_after_fork,
    resolve_sandbox_backend,
)
from lfx.utils.sandbox.registry import seal_builtins as _seal_builtins

# Imported for their registration side effect. An in-tree backend is a plain
# import here; an out-of-tree one arrives through the lfx.sandbox_backends
# entry point instead and needs no edit to this file.
from lfx.utils.sandbox import exec_sandbox as _exec_sandbox  # noqa: F401  isort:skip

# Everything registered above is in-tree. Freezing the set here is what lets
# the registry refuse a plugin that tries to take one of those names.
_seal_builtins()

__all__ = [
    "SANDBOX_BACKEND_NONE",
    "Capabilities",
    "SandboxBackend",
    "SandboxExecutionError",
    "SandboxResult",
    "SandboxUnavailableError",
    "build_import_preamble",
    "get_sandbox_backend",
    "is_sandbox_enabled",
    "known_sandbox_backends",
    "register_sandbox_backend",
    "run_code_in_sandbox",
    "sanitize_code",
    "shutdown_sandbox",
]


def _reinit_backends_after_fork() -> None:
    """after_in_child fork hook: give every live backend fresh sync state.

    Resolves the instances at call time, so a backend registered later (or a
    test-injected one) is covered too. Runs in the child's single-threaded
    post-fork window; must never raise, because an exception here would
    surface inside unrelated fork calls.
    """
    # First, before anything reads the registry. The registry's own mutex was
    # inherited from the parent and may be locked with no owner, so
    # live_sandbox_backends() below would block here forever -- and a blocked
    # child cannot be rescued by the suppress() around the loop.
    reset_registry_after_fork()
    for backend in live_sandbox_backends():
        with contextlib.suppress(Exception):
            backend.reset_after_fork()


if hasattr(os, "register_at_fork"):
    # POSIX only. Registered once at import for the process lifetime; the hook
    # re-resolves the live backends when it fires, so it never pins a stale
    # instance.
    os.register_at_fork(after_in_child=_reinit_backends_after_fork)


def run_code_in_sandbox(
    code: str,
    *,
    global_imports: str | list[str] = "",
    env: dict[str, str] | None = None,
) -> SandboxResult:
    """Execute ``code`` in the configured sandbox backend and return the outcome.

    Synchronous by design: the code-execution components are synchronous and
    may be invoked from arbitrary threads/event loops, so any loop-affine work
    is the backend's problem, not the caller's.

    Raises:
        SandboxUnavailableError: A sandbox backend is configured but unusable
            (fail closed — never falls back to in-process execution).
        SandboxExecutionError: The sandbox infrastructure failed mid-run.
        ValueError: ``global_imports`` contains an invalid module name.
    """
    name = get_sandbox_backend()
    if name == SANDBOX_BACKEND_NONE:
        msg = "run_code_in_sandbox called while no sandbox backend is configured"
        raise SandboxExecutionError(msg)
    try:
        backend = resolve_sandbox_backend(name)
    except KeyError as exc:
        msg = (
            f"Unknown sandbox backend {name!r}. Supported values for "
            f"LANGFLOW_SANDBOX_BACKEND: {', '.join(known_sandbox_backends())}."
        )
        raise SandboxUnavailableError(msg) from exc

    if not code.strip():
        # Parity with the in-process interpreter, which returns an empty
        # result for blank code; exec-sandbox rejects empty code outright and
        # that rejection would otherwise surface as an infrastructure error.
        return SandboxResult(stdout="", stderr="", exit_code=0)

    _assert_backend_honours_policy(backend)
    preamble = build_import_preamble(global_imports)
    full_code = _compose_sandbox_code(preamble, code)
    return backend.run(full_code, env=env)


def _assert_backend_honours_policy(backend: SandboxBackend) -> None:
    """Refuse when the backend cannot deliver the isolation the operator configured.

    The backend DECLARES what it supports. This function DECIDES whether that
    is enough. Keeping the decision here rather than in each backend means a
    third-party backend cannot grant itself a policy exemption, and every
    branch fails closed.
    """
    settings = _sandbox_settings()
    capabilities = backend.capabilities()

    if capabilities.isolation != "hardware-virtualized":
        msg = (
            f"Sandbox backend {backend.name!r} reports {capabilities.isolation!r} isolation, "
            "not a hardware-virtualized boundary. Sandbox mode disables the in-process Python "
            "defenses on the assumption of hardware isolation. Refusing to run the code."
        )
        raise SandboxUnavailableError(msg)

    if not settings.allow_network and not capabilities.supports_deny_all_egress:
        msg = (
            f"LANGFLOW_SANDBOX_ALLOW_NETWORK is false but sandbox backend {backend.name!r} "
            "cannot block all egress. Refusing to run the code."
        )
        raise SandboxUnavailableError(msg)

    if settings.allowed_domains and not capabilities.supports_domain_allowlist:
        msg = (
            f"LANGFLOW_SANDBOX_ALLOWED_DOMAINS is set but sandbox backend {backend.name!r} "
            "cannot restrict egress by domain. Refusing to run the code."
        )
        raise SandboxUnavailableError(msg)

    if capabilities.max_timeout_seconds is not None and settings.timeout_seconds > capabilities.max_timeout_seconds:
        msg = (
            f"LANGFLOW_SANDBOX_TIMEOUT_SECONDS is {settings.timeout_seconds} but sandbox backend "
            f"{backend.name!r} caps one execution at {capabilities.max_timeout_seconds}s. "
            "Refusing to run the code."
        )
        raise SandboxUnavailableError(msg)


def shutdown_sandbox() -> None:
    """Best-effort teardown of every live backend and its VMs.

    Safe to call when the sandbox was never used. Wired into application
    shutdown in addition to each backend's own atexit hook, because a backend
    that relies on the host process reaping its guests (exec-sandbox only gets
    QEMU parent-death cleanup on QEMU 10.2+) could otherwise leave VMs running
    after an abrupt worker exit.
    """
    for backend in live_sandbox_backends():
        with contextlib.suppress(Exception):
            backend.shutdown()
