"""Gunicorn master preload hook for Langflow.

When ``LANGFLOW_GUNICORN_PRELOAD=true`` (which flips gunicorn's
``preload_app`` option), this module runs the fork-safe parts of
Langflow's startup in the master process so that worker processes
inherit the result via copy-on-write. The dominant memory wins are:

- Python modules imported from custom-component bundles.
- The component types dict (``lfx.interface.components.component_cache``),
  which is typically tens of MB per worker.
- Starter-project graphs and related in-process state.

Fork-unsafe resources must not survive across ``fork`` (live DB connection
pools, cache-service sockets, prometheus HTTP servers, telemetry threads, MCP
composer asyncio tasks, queue service, per-worker background tasks, etc.).
Preload may open the SQLAlchemy engine transiently to run migrations and
seeding, then ``dispose()`` it before workers are forked; it does not leave a
pool open for request serving in the master. Other services are torn down or
never started here. Each worker continues to set up its own pools and services
in its own FastAPI ``lifespan`` after fork, so workers remain fully independent
and can each serve any request on their own.

Failure contract:
    Fork-safety-critical steps (DB engine disposal, cache service teardown)
    that fail will propagate their exception and abort preload. Best-effort
    steps (profile pictures, starter projects, agentic globals, agentic MCP,
    flows) that fail will log the exception with traceback, clear their
    completion flag, and allow preload to continue so workers inherit partial
    progress. Workers re-run any incomplete step during their lifespan.

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
from enum import Enum
from typing import TYPE_CHECKING, Final

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from tempfile import TemporaryDirectory


class PreloadStep(Enum):
    """Ordered preload phases; completion flags must advance via ``mark_step_complete`` only."""

    PROFILE_PICTURES = "profile_pictures"
    BUNDLES = "bundles"
    TYPES_CACHED = "types_cached"
    STARTER_PROJECTS = "starter_projects"
    AGENTIC_GLOBALS = "agentic_globals"
    AGENTIC_MCP = "agentic_mcp"
    FLOWS = "flows"


_STEP_ATTR: Final[dict[PreloadStep, str]] = {
    PreloadStep.PROFILE_PICTURES: "profile_pictures_copied",
    PreloadStep.BUNDLES: "bundles_loaded",
    PreloadStep.TYPES_CACHED: "types_cached",
    PreloadStep.STARTER_PROJECTS: "starter_projects_created",
    PreloadStep.AGENTIC_GLOBALS: "agentic_globals_initialized",
    PreloadStep.AGENTIC_MCP: "agentic_mcp_configured",
    PreloadStep.FLOWS: "flows_loaded",
}

# Explicit prerequisite DAG matching ``_run_master_preload`` ordering (comments + pipeline).
_STEP_PREREQUISITES: Final[dict[PreloadStep, tuple[PreloadStep, ...]]] = {
    PreloadStep.PROFILE_PICTURES: (),
    PreloadStep.BUNDLES: (),
    PreloadStep.TYPES_CACHED: (PreloadStep.BUNDLES,),
    PreloadStep.STARTER_PROJECTS: (PreloadStep.TYPES_CACHED,),
    PreloadStep.AGENTIC_GLOBALS: (PreloadStep.TYPES_CACHED,),
    # MCP config may succeed even when globals failed (separate try/except in preload).
    PreloadStep.AGENTIC_MCP: (PreloadStep.TYPES_CACHED,),
    PreloadStep.FLOWS: (PreloadStep.TYPES_CACHED,),
}


def is_step_complete(step: PreloadStep) -> bool:
    """Return True if *step* finished successfully during preload (workers inherit via fork)."""
    attr = _STEP_ATTR[step]
    return bool(getattr(_STATE, attr))


def mark_step_complete(step: PreloadStep) -> None:
    """Record successful completion of *step*, enforcing declared prerequisite ordering."""
    missing = [p for p in _STEP_PREREQUISITES[step] if not is_step_complete(p)]
    if missing:
        msg = f"Cannot complete preload step {step.value!r}: incomplete prerequisites {[m.value for m in missing]}"
        raise RuntimeError(msg)
    setattr(_STATE, _STEP_ATTR[step], True)


@dataclass
class _PreloadState:
    preloaded: bool = False
    master_pid: int | None = None
    temp_dirs: list[TemporaryDirectory] = field(default_factory=list)
    bundles_components_paths: list[str] = field(default_factory=list)
    # Per-step completion flags to prevent silent data loss
    profile_pictures_copied: bool = False
    bundles_loaded: bool = False
    types_cached: bool = False
    starter_projects_created: bool = False
    agentic_globals_initialized: bool = False
    agentic_mcp_configured: bool = False
    flows_loaded: bool = False

    def reset(self) -> None:
        """Restore all fields to their default values.

        Called from the outer failure handler in ``preload_master()`` so that
        a partially-completed preload never leaves inconsistent state behind
        (e.g. ``master_pid`` set while ``preloaded`` is False, or best-effort
        completion flags set for steps that ran before the failure point).
        Cleans up bundle ``TemporaryDirectory`` instances before clearing
        ``temp_dirs`` so failed preloads do not leak on-disk directories.
        After reset, workers take the full non-preload code path.
        """
        self.preloaded = False
        self.master_pid = None
        for tmp_dir in self.temp_dirs:
            try:
                tmp_dir.cleanup()
            except Exception:  # noqa: BLE001
                logger.exception("[preload] failed to cleanup preload temporary directory")
        self.temp_dirs = []
        self.bundles_components_paths = []
        self.profile_pictures_copied = False
        self.bundles_loaded = False
        self.types_cached = False
        self.starter_projects_created = False
        self.agentic_globals_initialized = False
        self.agentic_mcp_configured = False
        self.flows_loaded = False


_STATE = _PreloadState()


async def _best_effort(step: PreloadStep, log_suffix: str, awaitable: Awaitable[None]) -> None:
    """Run *awaitable* and mark *step* complete on success; log and continue on failure."""
    try:
        await awaitable
        mark_step_complete(step)
    except Exception:  # noqa: BLE001
        await logger.aexception(f"[preload] {log_suffix}")


def is_preloaded() -> bool:
    """Return True iff the master ran the preload hook.

    Workers inherit ``_STATE`` via fork, so this returns True in any
    process forked from a master that completed ``preload_master()``.
    """
    return _STATE.preloaded


def is_master() -> bool:
    """Return True if the current process is the gunicorn master that ran preload."""
    return _STATE.master_pid is not None and os.getpid() == _STATE.master_pid


def get_owned_temp_dirs() -> list[TemporaryDirectory]:
    """Return temp_dirs that the current process owns and should clean up.

    When preloaded:
      - Master returns the preloaded temp_dirs (it owns them)
      - Workers return an empty list (they must NOT clean up master's temp_dirs)
    When not preloaded:
      - Returns an empty list (will be populated by load_bundles later)

    This encodes the master-only ownership rule so callers don't need
    to check is_master() themselves.
    """
    if _STATE.preloaded and is_master():
        return _STATE.temp_dirs
    return []


async def _run_master_preload() -> None:
    """Run fork-safe one-time initialization inside an asyncio event loop.

    This function opens the DB engine (for migrations and seeding) and
    always disposes it before returning — including on failure paths — so
    no connections / file descriptors leak into forked workers.
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

    # Wrap all post-initialization work in try/finally so the DB engine and
    # cache service are always torn down before returning, even on failure.
    # Without this, any exception raised between here and the dispose() calls
    # would leave an open connection pool in the master process, and that pool
    # would be inherited (fork-unsafe) by every worker.
    try:
        await logger.adebug("[preload] copying profile pictures")
        await _best_effort(
            PreloadStep.PROFILE_PICTURES,
            "copy_profile_pictures failed",
            copy_profile_pictures(),
        )

        await logger.ainfo("[preload] loading bundles")
        temp_dirs, bundles_components_paths = await load_bundles_with_error_handling()
        _STATE.temp_dirs = list(temp_dirs)
        _STATE.bundles_components_paths = list(bundles_components_paths)
        settings_service.settings.components_path.extend(bundles_components_paths)
        mark_step_complete(PreloadStep.BUNDLES)

        await logger.ainfo("[preload] building component types cache")
        await get_and_cache_all_types_dict(settings_service, get_telemetry_service())
        mark_step_complete(PreloadStep.TYPES_CACHED)

        all_types_dict = component_cache.all_types_dict
        if all_types_dict is not None:
            await logger.adebug("[preload] creating/updating starter projects")
            await _best_effort(
                PreloadStep.STARTER_PROJECTS,
                "starter projects init failed",
                create_or_update_starter_projects(all_types_dict),
            )

        if settings_service.settings.agentic_experience:
            from langflow.api.utils.mcp.agentic_mcp import (
                auto_configure_agentic_mcp_server,
                initialize_agentic_global_variables,
            )

            await logger.adebug("[preload] initializing agentic global variables")

            async def _run_agentic_globals() -> None:
                async with session_scope() as session:
                    await initialize_agentic_global_variables(session)

            await _best_effort(
                PreloadStep.AGENTIC_GLOBALS,
                "initialize agentic global variables failed",
                _run_agentic_globals(),
            )

            await logger.adebug("[preload] auto-configuring agentic MCP server")

            async def _run_agentic_mcp() -> None:
                async with session_scope() as session:
                    await auto_configure_agentic_mcp_server(session)

            await _best_effort(
                PreloadStep.AGENTIC_MCP,
                "auto-configure agentic MCP server failed",
                _run_agentic_mcp(),
            )

        await logger.adebug("[preload] loading flows from directory")
        await _best_effort(
            PreloadStep.FLOWS,
            "load_flows_from_directory failed",
            load_flows_from_directory(),
        )

    finally:
        # CRITICAL: dispose the DB engine before the master returns control to
        # gunicorn regardless of whether the steps above succeeded or failed.
        # Forking with an open connection pool causes workers to inherit the
        # same TCP / file descriptors, making SQLAlchemy / the DB driver
        # behave unpredictably. After dispose(), the engine object is still
        # usable: on first access in a worker it opens a fresh pool for that
        # process.
        await logger.adebug("[preload] disposing master DB engine before fork")
        await get_db_service().engine.dispose()

        # Close cache service socket (e.g. Redis) to prevent sharing across fork.
        # ExternalAsyncBaseCacheService declares teardown() abstract, so any
        # concrete implementation is guaranteed to have it. A failure here is
        # fork-safety-critical and must propagate (no try/except).
        from langflow.services.cache.base import ExternalAsyncBaseCacheService
        from langflow.services.deps import get_service
        from langflow.services.schema import ServiceType

        cache_service = get_service(ServiceType.CACHE_SERVICE)
        if isinstance(cache_service, ExternalAsyncBaseCacheService):
            await cache_service.teardown()


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
        # Clear any partial state so workers take the full non-preload path
        # and is_master() / is_preloaded() stay mutually consistent.
        _STATE.reset()
        return

    # Help COW: move preload-allocated objects into the permanent generation
    # so the cyclic GC won't touch (and unshare) their pages in workers.
    try:
        gc.collect()
        gc.freeze()
    except Exception:
        logger.exception(
            "[preload] gc.collect()/gc.freeze() failed after async preload; resetting state and re-raising"
        )
        _STATE.reset()
        raise

    _STATE.preloaded = True
    logger.info("[preload] master preload complete; workers will inherit shared state via COW")
