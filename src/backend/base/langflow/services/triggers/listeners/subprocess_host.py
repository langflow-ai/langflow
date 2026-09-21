"""The single-container and Desktop shape: the API supervises one child process.

``decisions/process-model.md`` selects both shapes. A separate service is the
supported deployment, but Desktop and a single container have no second process
to run, so ``LANGFLOW_LISTENERS_MODE=subprocess`` makes the API lifespan spawn
``langflow listeners`` as a child and stop it on shutdown.

The guard is the reason this module is more than ``subprocess.Popen``. The API
defaults to ``(cpu_count() * 2) + 1`` uvicorn workers, and every one of them
runs the lifespan. Without an election, enabling subprocess mode on a four-core
machine starts nine listener processes that fight over every connection lease
and exhaust the provider's connection budget between them. So one worker takes
the ``trigger_listener_host`` lease and only that worker spawns a child; if it
dies, another worker takes the lease within a TTL and spawns a replacement.

The child is a real process, not a thread or a task: it must be able to die -
of a leaked provider client, of its own memory - without taking the API with it.
That was the failure mode of both precedents.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import sys
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import leases
from langflow.services.triggers.constants import LISTENER_HOST_LEASE_NAME

if TYPE_CHECKING:
    from collections.abc import Sequence

#: How long a terminated child gets to release its leases and close its sockets
#: before it is killed.
GRACE_PERIOD_S = 15.0


def listener_command() -> Sequence[str]:
    """The command that becomes the child.

    ``sys.executable -m langflow`` rather than the ``langflow`` script so the
    child is guaranteed to be the same interpreter and virtual environment as
    the parent, including inside Desktop's bundled runtime where no console
    script is on ``PATH``.
    """
    return [sys.executable, "-m", "langflow", "listeners"]


class ListenerSubprocess:
    """Runs at most one ``langflow listeners`` child, while this worker is elected."""

    def __init__(self, *, owner: str | None = None) -> None:
        self.owner = owner or leases.new_owner_token("listener-host")
        self.process: subprocess.Popen | None = None
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self.holding = False

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.terminate_child()
        if self.holding:
            with contextlib.suppress(Exception):
                async with session_scope() as session:
                    await leases.release(session, name=LISTENER_HOST_LEASE_NAME, owner=self.owner)
            self.holding = False

    async def _loop(self) -> None:
        settings = get_settings_service().settings
        while not self._stopping.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - supervision must outlive one bad pass
                await logger.aerror("Listener subprocess supervision failed: %s", type(exc).__name__)
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=settings.listener_reconcile_interval_s)

    async def tick(self) -> bool:
        """One supervision pass. Returns True while this worker hosts the child."""
        settings = get_settings_service().settings
        async with session_scope() as session:
            held = await leases.acquire(
                session,
                name=LISTENER_HOST_LEASE_NAME,
                owner=self.owner,
                ttl_s=settings.listener_lease_ttl_s,
            )
        self.holding = held
        if not held:
            # Another worker hosts it. If we were the host and lost the lease,
            # stand down rather than running a second listener alongside it.
            await self.terminate_child()
            return False
        if not self.running:
            self.spawn_child()
        return True

    def spawn_child(self) -> None:
        """Start the child, inheriting this process's environment verbatim.

        Verbatim on purpose: the listener has to see the same database URL, the
        same secret key, and the same plugin configuration as the API, and any
        curated subset of the environment is a list that goes stale the first
        time someone adds a setting.
        """
        exit_code = None if self.process is None else self.process.poll()
        if exit_code is not None:
            logger.warning("Langflow listeners child exited with %s; restarting", exit_code)
        self.process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell, no user input
            listener_command(),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
        logger.info("Started langflow listeners subprocess (pid %s)", self.process.pid)

    async def terminate_child(self) -> None:
        """SIGTERM, wait out the grace period, then kill."""
        process, self.process = self.process, None
        if process is None or process.poll() is not None:
            return
        with contextlib.suppress(ProcessLookupError, OSError):
            process.terminate()
        try:
            await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=GRACE_PERIOD_S)
        except (TimeoutError, asyncio.TimeoutError):
            await logger.awarning("Langflow listeners child did not exit in %.0fs; killing it", GRACE_PERIOD_S)
            with contextlib.suppress(ProcessLookupError, OSError):
                process.kill()
            with contextlib.suppress(Exception):
                await asyncio.to_thread(process.wait)


def start_listener_subprocess_if_enabled() -> ListenerSubprocess | None:
    """Start the child supervisor, or return None when subprocess mode is off.

    Failures are swallowed for the same reason the dispatcher's are: a trigger
    listener that cannot start must never stop the API from booting. The caller
    gets ``None`` and has nothing to stop.
    """
    settings = get_settings_service().settings
    if settings.listeners_mode != "subprocess":
        return None
    try:
        host = ListenerSubprocess()
        host.start()
    except Exception as exc:  # noqa: BLE001 - boot must not depend on the listener child
        logger.warning("Langflow listeners subprocess did not start: %s", type(exc).__name__)
        return None
    return host
