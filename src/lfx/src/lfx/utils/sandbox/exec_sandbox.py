"""The ``exec-sandbox`` backend: one local QEMU microVM per execution.

Event-loop ownership: ``exec_sandbox.Scheduler`` is asyncio-based and
loop-bound, while component code may run on any thread/loop (and
``run_until_complete`` creates throwaway loops when one is already running).
A shared scheduler on a throwaway loop would break, so this module owns a
single long-lived daemon thread running a private event loop; the scheduler
lives on that loop for the life of the process and calls are submitted with
``asyncio.run_coroutine_threadsafe``. This also amortizes Scheduler startup
(asset verification, VM image download) across executions.
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import os
import subprocess
import sys
import threading
from pathlib import Path

from lfx.log.logger import logger
from lfx.utils.sandbox.base import (
    Capabilities,
    SandboxExecutionError,
    SandboxResult,
    SandboxUnavailableError,
    _sandbox_settings,
)
from lfx.utils.sandbox.registry import register_sandbox_backend

SANDBOX_BACKEND_EXEC_SANDBOX = "exec-sandbox"

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


def _hardware_acceleration_available() -> bool:
    """Shallow preflight: whether a hardware hypervisor looks present at all.

    Fast fail before any loop/scheduler work when there is obviously no
    KVM/HVF. This is deliberately NOT the authoritative gate — exec-sandbox's
    own probe additionally verifies device permissions, KVM ioctls, and the
    QEMU binary's accelerator support, so the real decision is made on the
    sandbox loop via :func:`_assert_hardware_acceleration` right before the
    Scheduler is created.
    """
    if sys.platform.startswith("linux"):
        return Path("/dev/kvm").exists()
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["/usr/sbin/sysctl", "-n", "kern.hv_support"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return out.stdout.strip() == "1"
    # exec-sandbox supports only Linux and macOS.
    return False


def _emulation_forced_by_env() -> bool:
    """True when exec-sandbox is told to force TCG regardless of hardware.

    Upstream honors EXEC_SANDBOX_FORCE_EMULATION, which would silently select
    software emulation even on a KVM/HVF-capable host — so it must be treated
    exactly like a host without acceleration. The truthy set mirrors pydantic's
    bool coercion (upstream parses the env var with a pydantic ``bool`` field),
    so values like ``on`` or ``t`` cannot slip past this preflight while still
    forcing TCG upstream. This is only the fast preflight; the authoritative
    decision consumes upstream's own Settings in
    :func:`_assert_hardware_acceleration`.
    """
    return os.environ.get("EXEC_SANDBOX_FORCE_EMULATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "y",
        "t",
    }


_TCG_REFUSAL_MSG = (
    "LANGFLOW_SANDBOX_BACKEND=exec-sandbox is configured but QEMU would run under "
    "TCG software emulation instead of a hardware hypervisor (KVM on Linux requires "
    "a usable /dev/kvm; HVF on macOS), either because acceleration is unavailable "
    "or EXEC_SANDBOX_FORCE_EMULATION is set. exec-sandbox does not support TCG as "
    "a security boundary — and sandbox mode disables the in-process Python defenses "
    "on the assumption of hardware isolation. Enable hardware virtualization (or "
    "pass /dev/kvm through to the container), or set "
    "LANGFLOW_SANDBOX_ALLOW_SOFTWARE_EMULATION=true only for trusted/development "
    "workloads. Refusing to run the code."
)


async def _assert_hardware_acceleration() -> None:
    """Authoritative TCG gate, evaluated where exec_sandbox is importable.

    Reproduces upstream's own accelerator decision — ``detect_accel_type`` is
    exec-sandbox's documented single source of truth, fed with the
    ``force_emulation`` value parsed by exec-sandbox's *own* Settings (so
    every pydantic-truthy spelling of EXEC_SANDBOX_FORCE_EMULATION is honored
    identically) — and ALLOWLISTS the two hardware hypervisors: anything that
    is not exactly KVM or HVF is refused, so a future pre-1.0 exec-sandbox
    that renames TCG, adds another software accelerator, or changes the
    return shape fails closed instead of slipping past a TCG-only denylist.

    Also FAILS CLOSED if the decision cannot be obtained: the pinned
    dependency range guarantees this API today, and guessing about the
    isolation boundary when it moves would be exactly the fail-open this gate
    exists to prevent.
    """
    try:
        from exec_sandbox.settings import Settings as ExecSandboxSettings
        from exec_sandbox.system_probes import detect_accel_type
        from exec_sandbox.vm_types import AccelType

        force_emulation = ExecSandboxSettings().force_emulation
        accel = await detect_accel_type(force_emulation=force_emulation)
    except Exception as e:
        logger.debug("Could not obtain exec-sandbox accelerator decision", exc_info=True)
        msg = (
            "LANGFLOW_SANDBOX_BACKEND=exec-sandbox is configured but Langflow could not "
            "determine which QEMU accelerator exec-sandbox would select "
            f"({type(e).__name__}: {e}). Refusing to run rather than risk TCG software "
            "emulation, which is not a supported security boundary. If this exec-sandbox "
            "version changed its probe API, this Langflow version does not support it; "
            "LANGFLOW_SANDBOX_ALLOW_SOFTWARE_EMULATION=true bypasses this gate for "
            "trusted/development workloads only."
        )
        raise SandboxUnavailableError(msg) from e
    if accel not in (AccelType.KVM, AccelType.HVF):
        msg = f"{_TCG_REFUSAL_MSG} (exec-sandbox accelerator decision: {accel!r})"
        raise SandboxUnavailableError(msg)


class _ExecSandboxExecutor:
    """Owns the private event-loop thread and the lazily-created Scheduler."""

    name = SANDBOX_BACKEND_EXEC_SANDBOX

    @staticmethod
    def capabilities() -> Capabilities:
        """exec-sandbox runs a QEMU guest with an in-guest DNS filter.

        ``isolation`` reports what the backend provides, not what the current
        settings ask for: LANGFLOW_SANDBOX_ALLOW_SOFTWARE_EMULATION is an
        operator opt-out that :meth:`run` enforces itself, and reporting it
        here would make the dispatcher refuse a run the operator deliberately
        allowed.
        """
        return Capabilities(
            isolation="hardware-virtualized",
            supports_deny_all_egress=True,
            supports_domain_allowlist=True,
        )

    def __init__(self) -> None:
        """Initialize empty loop, thread, and scheduler state."""
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._scheduler = None
        self._scheduler_lock: asyncio.Lock | None = None
        self._lock = threading.Lock()
        self._atexit_registered = False
        # True only after a first execution has fully completed: _scheduler
        # becomes non-None before the first scheduler.run() finishes its
        # base-image download / VM boot, so _scheduler alone cannot decide
        # whether a caller still needs the startup grace margin.
        self._startup_complete = False
        # Scheduler lifecycle generation: incremented whenever the scheduler
        # is closed or the loop restarts. Lets a run that overlaps a shutdown
        # detect that it belongs to a previous scheduler and refrain from
        # marking the NEW generation's startup complete.
        self._generation = 0

    def _ensure_loop_locked(self) -> asyncio.AbstractEventLoop:
        """Create/return the loop. Caller MUST hold ``self._lock``."""
        if self._loop is None or self._thread is None or not self._thread.is_alive():
            # A dead loop thread (first use, or a fork inheriting this
            # module-global) invalidates everything loop-affine: the
            # scheduler's VM transports and the asyncio lock lived on the
            # old loop, so drop them and start fresh rather than reuse
            # state bound to a loop that no longer runs.
            self._scheduler = None
            self._startup_complete = False
            self._generation += 1
            # Create the creation lock EAGERLY, together with the loop: it
            # must exist by the time run() releases self._lock, so a
            # subsequent shutdown() always finds it and queues the close
            # behind any submitted-but-not-yet-executed run instead of
            # returning early and leaving that run's scheduler open.
            # (asyncio.Lock binds to a loop only on first acquire, so
            # constructing it off-loop here is safe on Python 3.10+.)
            self._scheduler_lock = asyncio.Lock()
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

    def reset_after_fork(self) -> None:
        """Rebuild synchronization state in a freshly forked child.

        Called from an ``os.register_at_fork(after_in_child=...)`` hook, i.e.
        in the guaranteed single-threaded window right after fork() returns
        in the child, so replacing state without holding any lock is safe.

        The mutex must be REPLACED, not merely relied upon: if another parent
        thread held ``self._lock`` at fork time, the child inherits it locked
        with no surviving owner and run() would block forever before ever
        reaching the dead-loop recovery in _ensure_loop_locked. Loop-affine
        state is cleared outright — threads do not survive fork, so the
        inherited loop/scheduler/asyncio-lock are all unusable husks.
        """
        self._lock = threading.Lock()
        self._scheduler_lock = None
        self._scheduler = None
        self._loop = None
        self._thread = None
        self._startup_complete = False
        self._generation += 1

    async def _ensure_scheduler(self, *, allow_software_emulation: bool):
        """Create the exec-sandbox Scheduler on first use, and return it.

        Args:
            allow_software_emulation: When False, the hardware-acceleration
                check runs before any VM resources are created.

        Returns:
            The process-wide Scheduler instance.
        """
        # Runs ON the sandbox loop, so scheduler state is loop-affine by
        # construction. exec_sandbox import errors are translated into the
        # fail-closed SandboxUnavailableError contract by run().
        #
        # The lazy lock creation is atomic (no await between check and assign
        # on the single loop thread); the asyncio.Lock then serializes the
        # awaited Scheduler startup so two concurrent first calls cannot each
        # create a scheduler and leak one VM pool.
        #
        # The warm pool is deliberately NOT configured: upstream pre-boots N
        # VMs for EVERY language (python/javascript/raw) at a fixed default
        # memory size, ignoring per-run memory_mb on warm hits, and network-
        # enabled runs bypass the pool entirely. Langflow only runs Python
        # with an operator-tunable memory limit, so the upstream pool contract
        # does not fit; revisit if exec-sandbox grows a per-language,
        # memory-keyed pool.
        if self._scheduler_lock is None:
            self._scheduler_lock = asyncio.Lock()
        async with self._scheduler_lock:
            if self._scheduler is None:
                # The authoritative TCG gate runs here — on the loop, with
                # exec_sandbox importable, before any VM resources exist.
                if not allow_software_emulation:
                    await _assert_hardware_acceleration()
                from exec_sandbox import Scheduler, SchedulerConfig

                scheduler = Scheduler(SchedulerConfig())
                self._scheduler = await scheduler.__aenter__()
                if not self._atexit_registered:
                    atexit.register(self.shutdown)
                    self._atexit_registered = True
        return self._scheduler

    async def _close_scheduler(self) -> None:
        """Exit and CLEAR the scheduler under the creation lock.

        Acquiring the creation lock makes this a BARRIER for in-flight
        creation: a shutdown that overlaps ``Scheduler.__aenter__`` waits for
        it and then closes the freshly created scheduler instead of returning
        early and leaving it running. Clearing ``_scheduler`` makes shutdown
        restartable (a later execution creates a fresh Scheduler rather than
        calling into an exited one).

        Readiness/generation are NOT touched here: shutdown() transitions
        them synchronously under the thread mutex at submission time, because
        by the time this coroutine runs another run may already have captured
        its grace classification.
        """
        if self._scheduler_lock is None:
            return
        async with self._scheduler_lock:
            if self._scheduler is None:
                return
            scheduler, self._scheduler = self._scheduler, None
            await scheduler.__aexit__(None, None, None)

    def shutdown(self) -> None:
        """Best-effort Scheduler teardown (atexit + app-shutdown hook).

        The loop thread is a daemon, so without this the process would exit
        without ever running Scheduler.__aexit__ and guest VMs could outlive
        Langflow. atexit runs while daemon threads are still alive, so the
        coroutine can complete on the sandbox loop; a short timeout and
        blanket suppress keep a wedged VM from hanging process exit. Safe to
        call repeatedly and mid-process.

        The lifecycle transition happens SYNCHRONOUSLY under ``self._lock``
        at submission time — readiness is cleared and the generation bumped
        before the mutex is released, NOT inside the queued close coroutine.
        A run accepted after this point therefore always classifies itself as
        a cold start (startup grace) even though the close has not executed
        yet, and an in-flight run of the closing generation can no longer
        re-mark readiness (its completion guard sees the bumped generation).
        The close coroutine itself only performs the actual __aexit__ behind
        the creation lock: with the eagerly created creation lock, a run
        accepted before the shutdown has its coroutine queued ahead of the
        close, which then closes whatever that run creates. Only the wait
        happens outside the mutex, so a slow close never blocks new
        submissions; if it outlives the wait timeout it keeps running on the
        loop and still closes as soon as in-flight creation completes.
        """
        with self._lock:
            loop = self._loop
            if self._scheduler_lock is None or loop is None or loop.is_closed():
                return
            self._startup_complete = False
            self._generation += 1
            future = asyncio.run_coroutine_threadsafe(self._close_scheduler(), loop)
        with contextlib.suppress(Exception):
            future.result(timeout=10)

    async def _run_on_loop(
        self,
        code: str,
        *,
        timeout_seconds: int,
        memory_mb: int,
        allow_network: bool,
        allowed_domains: tuple[str, ...],
        allow_software_emulation: bool,
        generation: int,
        env: dict[str, str] | None,
    ) -> SandboxResult:
        """Run ``code`` on the sandbox loop and return its outcome.

        Must run on the private event loop: the Scheduler and its VM
        transports are loop-affine.
        """
        # ``generation`` is the lifecycle epoch captured at ACCEPTANCE time
        # (in run(), under the thread mutex). Capturing it here instead would
        # be too late: a shutdown that lands between acceptance and this
        # coroutine executing bumps the generation first, and a run of the
        # closing epoch would then adopt the new epoch and wrongly mark its
        # readiness below.
        scheduler = await self._ensure_scheduler(allow_software_emulation=allow_software_emulation)
        # NOTE: the keyword is env_vars (not env as the README suggests), and
        # timeouts do NOT raise — they surface as exit_code == -1. With
        # allow_network=True and no allowed_domains, exec-sandbox's DNS filter
        # defaults to package registries only (PyPI/files.pythonhosted.org);
        # broader egress requires an explicit domain list.
        result = await scheduler.run(
            code=code,
            language="python",
            timeout_seconds=timeout_seconds,
            memory_mb=memory_mb,
            env_vars=env or {},
            allow_network=allow_network,
            allowed_domains=list(allowed_domains) if allowed_domains else None,
        )
        # Any completed run (even a non-zero guest exit) proves the base image
        # is downloaded and a VM booted; only now do later callers stop
        # needing the startup grace margin. Left False on exceptions so a
        # failed cold start keeps the generous margin for the next attempt,
        # and skipped when a shutdown was requested after this run was
        # accepted — its scheduler is (being) closed, so its completion says
        # nothing about the current epoch's readiness.
        #
        # The comparison and the write must be one atomic step under the same
        # mutex shutdown() uses for its transition: unlocked, a shutdown can
        # land between a successful comparison and the assignment, leaving
        # startup_complete=True with no scheduler — the next cold start would
        # then run under the steady-state margin and can time out. Holding
        # the thread mutex briefly on the loop thread is deadlock-free: no
        # mutex holder ever blocks on the loop while holding it.
        with self._lock:
            if self._generation == generation:
                self._startup_complete = True
        return SandboxResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            execution_time_ms=getattr(result, "execution_time_ms", None),
        )

    def run(self, code: str, *, env: dict[str, str] | None = None) -> SandboxResult:
        """Run ``code`` to completion in a fresh exec-sandbox VM.

        Raises:
            SandboxUnavailableError: The 'exec-sandbox' package is missing,
                or the operator's policy cannot be honored.
            SandboxExecutionError: The infrastructure failed mid-run.
        """
        settings = _sandbox_settings()
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

        if not settings.allow_software_emulation and (
            _emulation_forced_by_env() or not _hardware_acceleration_available()
        ):
            # Shallow fast-fail; the authoritative deep gate (exec-sandbox's
            # own probe: device permissions, KVM ioctls, QEMU accelerator
            # support) runs on the loop in _ensure_scheduler.
            raise SandboxUnavailableError(_TCG_REFUSAL_MSG)

        # Loop acquisition, readiness capture, and submission form one
        # critical section under the executor's thread mutex, totally ordered
        # against shutdown() (which submits its close under the same mutex).
        # This closes two races: a shutdown can no longer slip between the
        # readiness read and the submission (stale steady-state grace for
        # what becomes a cold start), and a shutdown can no longer observe
        # partially initialized state for an already-accepted run — the loop
        # and its creation lock are created together, so an accepted run
        # always leaves something for the close to queue behind.
        #
        # The readiness flag is read here rather than _scheduler because the
        # scheduler becomes non-None before the first run finishes its
        # base-image download / VM boot; a second concurrent caller would
        # otherwise get the steady-state margin while startup work is still
        # in flight.
        with self._lock:
            loop = self._ensure_loop_locked()
            is_first_execution = not self._startup_complete
            future = asyncio.run_coroutine_threadsafe(
                self._run_on_loop(
                    code,
                    generation=self._generation,
                    timeout_seconds=settings.timeout_seconds,
                    memory_mb=settings.memory_mb,
                    allow_network=settings.allow_network,
                    allowed_domains=settings.allowed_domains,
                    allow_software_emulation=settings.allow_software_emulation,
                    env=env,
                ),
                loop,
            )
        # The VM enforces timeout_seconds internally (exit_code -1 on
        # timeout); the outer margin only guards against a wedged scheduler so
        # the component thread cannot hang forever. The first execution gets a
        # larger margin because Scheduler startup (image download, VM boot)
        # happens inside the same coroutine.
        grace = _STARTUP_GRACE_SECONDS if is_first_execution else _RUN_GRACE_SECONDS
        deadline = settings.timeout_seconds + grace
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


# Re-executing this module (importlib.reload, or a test that reimports it)
# must not raise. seal_builtins() has run by then, and re-registering a sealed
# built-in name is refused by design -- which is the correct refusal, just not
# a reason to break the import.
with contextlib.suppress(ValueError):
    register_sandbox_backend(SANDBOX_BACKEND_EXEC_SANDBOX, _ExecSandboxExecutor)
