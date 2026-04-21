"""Gunicorn master preload hook for Langflow.

When ``LANGFLOW_GUNICORN_PRELOAD=true`` (which flips gunicorn's
``preload_app`` option), this module runs the fork-safe parts of
Langflow's startup in the master process so that worker processes
inherit the result via copy-on-write. The dominant memory wins are:

- Python modules imported from custom-component bundles.
- The component types dict (``lfx.interface.components.component_cache``),
  which is typically tens of MB per worker.
- Starter-project graphs and related in-process state.

Fork-unsafe resources (DB connection pools, cache-service sockets,
prometheus HTTP servers, telemetry threads, MCP composer asyncio tasks,
queue service, per-worker background tasks, etc.) are deliberately NOT
started here. Each worker continues to set those up in its own FastAPI
``lifespan`` after fork, so workers remain fully independent and can
each serve any request on their own.

Notes on CPython and copy-on-write:
    CPython mutates ``ob_refcnt`` on every attribute access, which
    triggers 4 KB page copies even for "shared" objects. Preloading
    therefore does not eliminate per-worker memory entirely, but it
    significantly reduces the cold-start working set, and calling
    ``gc.freeze()`` after preload prevents the cyclic GC from touching
    long-lived objects and unsharing their pages.
"""

from __future__ import annotations

import asyncio
import gc
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from tempfile import TemporaryDirectory


@dataclass
class _PreloadState:
    preloaded: bool = False
    master_pid: int | None = None
    temp_dirs: list[TemporaryDirectory] = field(default_factory=list)
    bundles_components_paths: list[str] = field(default_factory=list)


_STATE = _PreloadState()


def is_preloaded() -> bool:
    """Return True iff the master ran the preload hook.

    Workers inherit ``_STATE`` via fork, so this returns True in any
    process forked from a master that completed ``preload_master()``.
    """
    return _STATE.preloaded


def is_master() -> bool:
    """Return True if the current process is the gunicorn master that ran preload."""
    return _STATE.master_pid is not None and os.getpid() == _STATE.master_pid


def get_preloaded_temp_dirs() -> list[TemporaryDirectory]:
    """Return the list of bundle ``TemporaryDirectory`` objects created during preload.

    Only the master should clean these up on shutdown; workers must not
    call ``.cleanup()`` on them or they would delete files the master
    still expects to own.
    """
    return _STATE.temp_dirs


async def _run_master_preload() -> None:
    """Run fork-safe one-time initialization inside an asyncio event loop.

    This function opens the DB engine (for migrations and seeding) and
    always disposes it before returning so no connections / file
    descriptors leak into forked workers.
    """
    from lfx.interface.components import component_cache, get_and_cache_all_types_dict

    from langflow.initial_setup.setup import (
        copy_profile_pictures,
        create_or_update_starter_projects,
        load_flows_from_directory,
    )
    from langflow.main import load_bundles_with_error_handling
    from langflow.services.deps import (
        get_db_service,
        get_settings_service,
        get_telemetry_service,
        session_scope,
    )
    from langflow.services.utils import initialize_services

    settings_service = get_settings_service()

    await logger.ainfo("[preload] initializing services in master")
    await initialize_services(fix_migration=False)

    await logger.adebug("[preload] copying profile pictures")
    try:
        await copy_profile_pictures()
    except Exception as e:  # noqa: BLE001
        await logger.awarning(f"[preload] copy_profile_pictures failed: {e}")

    await logger.ainfo("[preload] loading bundles")
    temp_dirs, bundles_components_paths = await load_bundles_with_error_handling()
    _STATE.temp_dirs = list(temp_dirs)
    _STATE.bundles_components_paths = list(bundles_components_paths)
    settings_service.settings.components_path.extend(bundles_components_paths)

    await logger.ainfo("[preload] building component types cache")
    await get_and_cache_all_types_dict(settings_service, get_telemetry_service())

    all_types_dict = component_cache.all_types_dict
    if all_types_dict is not None:
        await logger.adebug("[preload] creating/updating starter projects")
        try:
            await create_or_update_starter_projects(all_types_dict)
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"[preload] starter projects init failed: {e}")

    if settings_service.settings.agentic_experience:
        try:
            from langflow.api.utils.mcp.agentic_mcp import (
                auto_configure_agentic_mcp_server,
                initialize_agentic_global_variables,
            )

            await logger.adebug("[preload] initializing agentic global variables")
            async with session_scope() as session:
                await initialize_agentic_global_variables(session)
            await logger.adebug("[preload] auto-configuring agentic MCP server")
            async with session_scope() as session:
                await auto_configure_agentic_mcp_server(session)
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"[preload] agentic MCP init failed: {e}")

    await logger.adebug("[preload] loading flows from directory")
    try:
        await load_flows_from_directory()
    except Exception as e:  # noqa: BLE001
        await logger.awarning(f"[preload] load_flows_from_directory failed: {e}")

    # CRITICAL: dispose the DB engine before the master returns control to
    # gunicorn. If we fork with an open connection pool, child workers
    # inherit the same TCP / file descriptors and SQLAlchemy / the DB
    # driver will behave unpredictably. After dispose(), the engine object
    # is still usable: on first access in a worker it will open a fresh
    # connection pool for that process.
    await logger.adebug("[preload] disposing master DB engine before fork")
    await get_db_service().engine.dispose()

    # Close cache service socket (e.g. Redis) to prevent sharing across fork.
    from langflow.services.cache.base import ExternalAsyncBaseCacheService
    from langflow.services.deps import get_service
    from langflow.services.schema import ServiceType

    cache_service = get_service(ServiceType.CACHE_SERVICE)
    if isinstance(cache_service, ExternalAsyncBaseCacheService):
        teardown = getattr(cache_service, "teardown", None)
        if callable(teardown):
            result = teardown()
            if asyncio.iscoroutine(result):
                await result


def preload_master() -> None:
    """Run one-time Langflow initialization in the gunicorn master before workers are forked.

    Safe to call more than once: subsequent calls are no-ops.
    If preload fails for any reason, this function logs the failure and
    returns without setting the preloaded flag, so workers fall back to
    running the full lifespan as before (no behavior regression).
    """
    if _STATE.preloaded:
        return

    _STATE.master_pid = os.getpid()

    try:
        asyncio.run(_run_master_preload())
    except Exception:  # noqa: BLE001
        logger.exception("[preload] master preload failed; falling back to per-worker init")
        return

    _STATE.preloaded = True

    # Help COW: move preload-allocated objects into the permanent generation
    # so the cyclic GC won't touch (and unshare) their pages in workers.
    try:
        gc.collect()
        gc.freeze()
    except Exception:  # noqa: BLE001
        logger.exception("[preload] gc.freeze() failed")

    logger.info("[preload] master preload complete; workers will inherit shared state via COW")
