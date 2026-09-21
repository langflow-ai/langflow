"""``langflow listeners``: the process that holds Track B connections.

It is the same image and the same configuration as the API - the same database
URL, the same secret key, the same ``lfx.toml`` service discovery, so an
Enterprise override registered for the API is registered here too - with one
difference that the whole design rests on: there is no HTTP application. The
boot path marks the process and asserts it, and
:func:`langflow.main.create_app` refuses to build one afterwards.

What it deliberately does *not* do:

* **It does not migrate.** Schema is the API's job. A listener that ran Alembic
  would race every API replica during a rolling upgrade, so this process
  verifies that the trigger tables exist and exits with an actionable message
  when they do not.
* **It does not create a superuser, load bundles, or warm a component cache.**
  None of that is needed to hold a socket, and every one of them is a way for
  the listener to fail on something the API is responsible for.
* **It does not run the dispatcher or the schedule tick.** Those are API-process
  singletons (``decisions/process-model.md``). The two processes meet only at
  the ledger table.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from lfx.log.logger import logger

from langflow.services.triggers.listeners.adapters import register_builtin_adapters
from langflow.services.triggers.listeners.guard import assert_no_http_app, mark_listener_process
from langflow.services.triggers.listeners.health import ListenerHealthServer
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor


async def verify_schema() -> None:
    """Fail fast, and legibly, when the database has not been migrated yet.

    A listener started before its API (a Compose ``depends_on`` that only waits
    for the container, a Kubernetes Deployment that rolls first) would otherwise
    die on an opaque "no such table" once per restart.
    """
    from sqlmodel import select

    from langflow.services.database.models.trigger.model import Trigger
    from langflow.services.deps import session_scope

    try:
        async with session_scope() as session:
            await session.exec(select(Trigger).limit(1))
    except Exception as exc:
        msg = (
            "The trigger tables are missing or unreadable. The listener process never migrates: "
            "start (or upgrade) the Langflow API against this database first, then start the listeners."
        )
        raise RuntimeError(msg) from exc


async def boot_services() -> None:
    """Bring up exactly the services a listener needs, and nothing else."""
    from langflow.services.utils import initialize_settings_service, register_all_service_factories

    initialize_settings_service()
    register_all_service_factories()
    register_builtin_adapters()
    await verify_schema()


async def run_listeners(*, stop_event: asyncio.Event | None = None) -> None:
    """Boot, supervise, and shut down cleanly. Returns when stopped."""
    mark_listener_process()
    assert_no_http_app()
    await boot_services()

    stopping = stop_event or asyncio.Event()
    supervisor = ListenerSupervisor()
    health = ListenerHealthServer(supervisor)

    supervisor.start()
    await health.start()
    await logger.ainfo("Langflow listeners started (holder %s)", supervisor.holder)

    try:
        await stopping.wait()
    finally:
        await logger.ainfo("Langflow listeners stopping")
        with contextlib.suppress(Exception):
            await health.stop()
        with contextlib.suppress(Exception):
            await supervisor.stop()
        with contextlib.suppress(Exception):
            from langflow.services.utils import teardown_services

            await teardown_services()


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stopping: asyncio.Event) -> None:
    """SIGTERM and SIGINT stop the supervisor instead of killing the process.

    A hard kill leaves every lease to expire, which costs the next replica up to
    two TTLs. Handling the signal is what makes "stops cleanly on SIGTERM" - a
    container's normal shutdown - a promise rather than a hope. Windows has no
    ``add_signal_handler``; there ``KeyboardInterrupt`` is the path.
    """
    for signal_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, signal_name, None)
        if sig is None:  # pragma: no cover - platform dependent
            continue
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, stopping.set)


async def _main() -> None:
    stopping = asyncio.Event()
    _install_signal_handlers(asyncio.get_running_loop(), stopping)
    try:
        await run_listeners(stop_event=stopping)
    except KeyboardInterrupt:  # pragma: no cover - Windows / no signal handler
        stopping.set()


def main() -> None:
    """Console entry point for ``langflow listeners``."""
    # A second Ctrl-C during shutdown should end the process quietly, not print
    # a traceback over the clean-shutdown log lines.
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_main())


if __name__ == "__main__":  # pragma: no cover - ``python -m`` convenience
    main()
