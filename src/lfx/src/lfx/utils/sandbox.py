"""Optional hardware-isolated sandbox backend for user-authored code execution.

Issue #12029: the Python Interpreter / Python REPL components execute
user-supplied code with ``exec`` inside the server process. The Python-level
hardening in :mod:`lfx.utils.python_repl_security` is best-effort defense in
depth, not a security boundary. This module adds an opt-in execution backend
that routes that code into a dedicated QEMU microVM per execution via the
`exec-sandbox <https://github.com/dualeai/exec-sandbox>`_ package, so a
malicious payload lands in a throwaway VM (read-only rootfs, no network by
default) instead of the Langflow server process.

Operator contract:

* ``LANGFLOW_SANDBOX_BACKEND=none`` (default) — existing in-process behavior,
  nothing in this module activates and ``exec-sandbox`` need not be installed.
* ``LANGFLOW_SANDBOX_BACKEND=exec-sandbox`` — code-execution components run
  user code through :func:`run_code_in_sandbox`. If the backend cannot be used
  (package not installed, Python < 3.12, QEMU missing) execution FAILS CLOSED
  with :class:`SandboxUnavailableError`; it never silently falls back to
  in-process ``exec``, because the operator explicitly asked for isolation.

Event-loop ownership: ``exec_sandbox.Scheduler`` is asyncio-based and
loop-bound, while component code may run on any thread/loop (and
``run_until_complete`` creates throwaway loops when one is already running).
A shared scheduler on a throwaway loop would break, so this module owns a
single long-lived daemon thread running a private event loop; the scheduler
lives on that loop for the life of the process and calls are submitted with
``asyncio.run_coroutine_threadsafe``. This also preserves exec-sandbox's warm
VM pool across executions.
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import re
import threading
from dataclasses import dataclass

from lfx.log.logger import logger

# Backend identifiers accepted by LANGFLOW_SANDBOX_BACKEND.
SANDBOX_BACKEND_NONE = "none"
SANDBOX_BACKEND_EXEC_SANDBOX = "exec-sandbox"
KNOWN_SANDBOX_BACKENDS = (SANDBOX_BACKEND_NONE, SANDBOX_BACKEND_EXEC_SANDBOX)

# Mirrors langchain_experimental's PythonREPL.sanitize_input, which the
# in-process path applies before exec: strip a leading markdown fence /
# "python" language tag / backticks and trailing backticks-whitespace. The
# sandbox path must normalize identically or fenced LLM-generated code that
# runs in-process today would become a guest SyntaxError. Replicated here
# (two small regexes) so the sandbox path does not depend on
# langchain_experimental being installed.
_FENCE_PREFIX_RE = re.compile(r"^(\s|`)*(?i:python)?\s*")
_FENCE_SUFFIX_RE = re.compile(r"(\s|`)*$")


def sanitize_code(code: str) -> str:
    """Strip markdown fences/backticks the way PythonREPL.sanitize_input does."""
    return _FENCE_SUFFIX_RE.sub("", _FENCE_PREFIX_RE.sub("", code))


class SandboxExecutionError(RuntimeError):
    """Raised when a sandboxed execution fails for infrastructure reasons.

    Infrastructure failures (VM boot timeout, guest communication loss) are
    distinct from the user code failing — the latter is reported through
    :attr:`SandboxResult.exit_code` / :attr:`SandboxResult.stderr`, not an
    exception.
    """


class SandboxUnavailableError(SandboxExecutionError):
    """Raised when a sandbox backend is configured but cannot be used.

    Deliberately NOT caught by the components' fallback paths: a configured
    sandbox that cannot start must block execution (fail closed), not degrade
    to in-process ``exec``.
    """


# exec-sandbox reports these outcomes through exit_code instead of raising:
# -1 is a wall-clock timeout, 137 is SIGKILL (usually the guest OOM killer).
_EXIT_CODE_TIMEOUT = -1
_EXIT_CODE_KILLED = 137

# Host-side grace added on top of the guest-enforced timeout when waiting for
# the loop-thread future. The guest timeout is authoritative (it surfaces as a
# graceful exit_code == -1 result); this margin exists only so a wedged
# scheduler cannot pin the component thread forever, and it must be generous
# enough that legitimate infrastructure work is never misclassified as a wedge:
# scheduling delay and result transport in the steady state, plus one-time
# Scheduler startup (VM image download ~75MB + warm-pool boot, or slow TCG
# boots on hosts without KVM/HVF) on the first execution.
_RUN_GRACE_SECONDS = 60
_STARTUP_GRACE_SECONDS = 300


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of one sandboxed execution."""

    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: int | None = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def error_message(self) -> str:
        """A user-facing message for a failed execution (non-zero exit code)."""
        if self.exit_code == _EXIT_CODE_TIMEOUT:
            return "Sandboxed execution timed out (see LANGFLOW_SANDBOX_TIMEOUT_SECONDS)."
        if self.exit_code == _EXIT_CODE_KILLED:
            return (
                "Sandboxed execution was killed (exit code 137), typically because it "
                "exceeded the VM memory limit (see LANGFLOW_SANDBOX_MEMORY_MB)."
            )
        return self.stderr.strip() or f"Sandboxed execution failed with exit code {self.exit_code}"


def get_sandbox_backend() -> str:
    """Return the configured sandbox backend name (``none`` when unset).

    An absent or unresolvable settings stack means the sandbox was never
    opted into, so the answer is ``none`` — unlike the
    ``allow_custom_components`` gate there is no fail-closed question here;
    the fail-closed behavior lives in :func:`run_code_in_sandbox` once a
    backend IS configured.
    """
    try:
        from lfx.services.deps import get_settings_service

        settings_service = get_settings_service()
    except ImportError:
        return SANDBOX_BACKEND_NONE
    if settings_service is None:
        return SANDBOX_BACKEND_NONE
    backend = getattr(settings_service.settings, "sandbox_backend", SANDBOX_BACKEND_NONE)
    return backend or SANDBOX_BACKEND_NONE


def is_sandbox_enabled() -> bool:
    """True when a non-default sandbox backend is configured."""
    return get_sandbox_backend() != SANDBOX_BACKEND_NONE


def _sandbox_settings() -> tuple[int, int, bool, int]:
    """Return (timeout_seconds, memory_mb, allow_network, warm_pool_size) from settings."""
    timeout_seconds, memory_mb, allow_network, warm_pool_size = 30, 192, False, 0
    try:
        from lfx.services.deps import get_settings_service

        settings_service = get_settings_service()
    except ImportError:
        return timeout_seconds, memory_mb, allow_network, warm_pool_size
    if settings_service is None:
        return timeout_seconds, memory_mb, allow_network, warm_pool_size
    settings = settings_service.settings
    return (
        getattr(settings, "sandbox_timeout_seconds", timeout_seconds),
        getattr(settings, "sandbox_memory_mb", memory_mb),
        getattr(settings, "sandbox_allow_network", allow_network),
        getattr(settings, "sandbox_warm_pool_size", warm_pool_size),
    )


class _ExecSandboxExecutor:
    """Owns the private event-loop thread and the lazily-created Scheduler."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._scheduler = None
        self._scheduler_lock: asyncio.Lock | None = None
        self._lock = threading.Lock()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or self._thread is None or not self._thread.is_alive():
                # A dead loop thread (first use, or a fork inheriting this
                # module-global) invalidates everything loop-affine: the
                # scheduler's VM transports and the asyncio lock lived on the
                # old loop, so drop them and start fresh rather than reuse
                # state bound to a loop that no longer runs.
                self._scheduler = None
                self._scheduler_lock = None
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever,
                    name="lfx-sandbox-loop",
                    daemon=True,
                )
                thread.start()
                self._loop = loop
                self._thread = thread
            return self._loop

    async def _ensure_scheduler(self, warm_pool_size: int):
        # Runs ON the sandbox loop, so scheduler state is loop-affine by
        # construction. exec_sandbox import errors are translated into the
        # fail-closed SandboxUnavailableError contract by run().
        #
        # The lazy lock creation is atomic (no await between check and assign
        # on the single loop thread); the asyncio.Lock then serializes the
        # awaited Scheduler startup so two concurrent first calls cannot each
        # create a scheduler and leak one VM pool.
        if self._scheduler_lock is None:
            self._scheduler_lock = asyncio.Lock()
        async with self._scheduler_lock:
            if self._scheduler is None:
                from exec_sandbox import Scheduler, SchedulerConfig

                scheduler = Scheduler(SchedulerConfig(warm_pool_size=warm_pool_size))
                self._scheduler = await scheduler.__aenter__()
                atexit.register(self._shutdown)
        return self._scheduler

    def _shutdown(self) -> None:
        """Best-effort Scheduler teardown at interpreter exit.

        The loop thread is a daemon, so without this the process would exit
        without ever running Scheduler.__aexit__ and warm-pool VMs could
        outlive Langflow. atexit runs while daemon threads are still alive,
        so the coroutine can complete on the sandbox loop; a short timeout
        and blanket suppress keep a wedged VM from hanging process exit.
        """
        scheduler, loop = self._scheduler, self._loop
        if scheduler is None or loop is None or loop.is_closed():
            return
        with contextlib.suppress(Exception):
            asyncio.run_coroutine_threadsafe(scheduler.__aexit__(None, None, None), loop).result(timeout=10)

    async def _run_on_loop(
        self,
        code: str,
        *,
        timeout_seconds: int,
        memory_mb: int,
        allow_network: bool,
        warm_pool_size: int,
        env: dict[str, str] | None,
    ) -> SandboxResult:
        scheduler = await self._ensure_scheduler(warm_pool_size)
        # NOTE: the keyword is env_vars (not env as the README suggests), and
        # timeouts do NOT raise — they surface as exit_code == -1.
        result = await scheduler.run(
            code=code,
            language="python",
            timeout_seconds=timeout_seconds,
            memory_mb=memory_mb,
            env_vars=env or {},
            allow_network=allow_network,
        )
        return SandboxResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            execution_time_ms=getattr(result, "execution_time_ms", None),
        )

    def run(self, code: str, *, env: dict[str, str] | None = None) -> SandboxResult:
        timeout_seconds, memory_mb, allow_network, warm_pool_size = _sandbox_settings()
        try:
            import exec_sandbox  # noqa: F401
        except ImportError as e:
            msg = (
                "LANGFLOW_SANDBOX_BACKEND=exec-sandbox is configured but the 'exec-sandbox' "
                "package is not installed. Install it with `pip install 'langflow[sandbox]'` "
                "(requires Python >= 3.12 and QEMU 8+ on the host), or set "
                "LANGFLOW_SANDBOX_BACKEND=none to run code in-process. Refusing to run the "
                "code outside the sandbox."
            )
            raise SandboxUnavailableError(msg) from e

        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(
            self._run_on_loop(
                code,
                timeout_seconds=timeout_seconds,
                memory_mb=memory_mb,
                allow_network=allow_network,
                warm_pool_size=warm_pool_size,
                env=env,
            ),
            loop,
        )
        # The VM enforces timeout_seconds internally (exit_code -1 on
        # timeout); the outer margin only guards against a wedged scheduler so
        # the component thread cannot hang forever. The first execution gets a
        # larger margin because Scheduler startup (image download, VM boot)
        # happens inside the same coroutine.
        grace = _RUN_GRACE_SECONDS if self._scheduler is not None else _STARTUP_GRACE_SECONDS
        deadline = timeout_seconds + grace
        try:
            return future.result(timeout=deadline)
        except SandboxExecutionError:
            raise
        except TimeoutError as e:
            future.cancel()
            msg = f"Sandboxed execution did not complete within {deadline}s (scheduler unresponsive)."
            raise SandboxExecutionError(msg) from e
        except Exception as e:
            # exec_sandbox raises its own exception hierarchy (SandboxError
            # subclasses) for VM/infrastructure failures; surface them under
            # this module's stable exception type so callers do not need to
            # import exec_sandbox to handle errors.
            logger.debug("Sandboxed execution failed", exc_info=True)
            msg = f"Sandboxed execution failed: {type(e).__name__}: {e}"
            raise SandboxExecutionError(msg) from e


_executor = _ExecSandboxExecutor()


def build_import_preamble(global_imports: str | list[str]) -> str:
    """Translate the components' ``Global Imports`` field into import statements.

    In-process execution imports these modules on the host and injects them
    into the exec globals; in sandbox mode the equivalent is a plain import
    preamble that runs inside the guest VM. A module missing from the guest
    image surfaces as an ImportError in the sandboxed stderr.
    """
    if isinstance(global_imports, str):
        modules = [module.strip() for module in global_imports.split(",") if module.strip()]
    elif isinstance(global_imports, list):
        modules = [str(module).strip() for module in global_imports if str(module).strip()]
    else:
        msg = "global_imports must be either a string or a list"
        raise TypeError(msg)
    for module in modules:
        # Modules become import statements in generated code, so restrict to
        # dotted-identifier names to keep code injection out of the preamble.
        if not all(part.isidentifier() for part in module.split(".")):
            msg = f"Invalid module name in Global Imports: {module!r}"
            raise ValueError(msg)
    return "\n".join(f"import {module}" for module in modules)


def run_code_in_sandbox(
    code: str, *, global_imports: str | list[str] = "", env: dict[str, str] | None = None
) -> SandboxResult:
    """Execute ``code`` in the configured sandbox backend and return the outcome.

    Synchronous by design: the code-execution components are synchronous and
    may be invoked from arbitrary threads/event loops, so the loop-affine
    scheduler work is delegated to the module's private loop thread.

    Raises:
        SandboxUnavailableError: A sandbox backend is configured but unusable
            (fail closed — never falls back to in-process execution).
        SandboxExecutionError: The sandbox infrastructure failed mid-run.
        ValueError: ``global_imports`` contains an invalid module name.
    """
    backend = get_sandbox_backend()
    if backend == SANDBOX_BACKEND_NONE:
        msg = "run_code_in_sandbox called while no sandbox backend is configured"
        raise SandboxExecutionError(msg)
    if backend != SANDBOX_BACKEND_EXEC_SANDBOX:
        msg = (
            f"Unknown sandbox backend {backend!r}. Supported values for "
            f"LANGFLOW_SANDBOX_BACKEND: {', '.join(KNOWN_SANDBOX_BACKENDS)}."
        )
        raise SandboxUnavailableError(msg)

    preamble = build_import_preamble(global_imports)
    full_code = f"{preamble}\n{code}" if preamble else code
    return _executor.run(full_code, env=env)
