import asyncio
import json
import os
import re
import sys
import tempfile
import warnings
from contextlib import asynccontextmanager, suppress
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import urlencode

import anyio
import httpx
import sqlalchemy
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from filelock import FileLock
from lfx.interface.utils import setup_llm_caching
from lfx.log.logger import configure, logger
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import PydanticDeprecatedSince20
from pydantic_core import PydanticSerializationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from langflow.api import health_check_router, log_router
from langflow.api.router import router
from langflow.api.v1.mcp_projects import init_mcp_servers
from langflow.initial_setup.setup import (
    copy_profile_pictures,
    create_or_update_starter_projects,
    load_bundles_from_urls,
    load_flows_from_directory,
    sync_flows_from_fs,
)
from langflow.middleware import ContentSizeLimitMiddleware
from langflow.plugin_routes import load_plugin_routes
from langflow.services.database.models.deployment.exceptions import DeploymentGuardError
from langflow.services.database.service import UnsupportedPostgreSQLVersionError
from langflow.services.deps import (
    get_queue_service,
    get_service,
    get_settings_service,
    get_telemetry_service,
    session_scope,
)
from langflow.services.schema import ServiceType
from langflow.services.utils import initialize_services, initialize_settings_service, teardown_services
from langflow.utils.mcp_cleanup import cleanup_mcp_sessions

if TYPE_CHECKING:
    from lfx.services.mcp_composer.service import MCPComposerService

# Ignore Pydantic deprecation warnings from Langchain
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)

# Suppress ResourceWarning from anyio streams (SSE connections)
warnings.filterwarnings("ignore", category=ResourceWarning, message=".*MemoryObjectReceiveStream.*")
warnings.filterwarnings("ignore", category=ResourceWarning, message=".*MemoryObjectSendStream.*")

_tasks: list[asyncio.Task] = []

MAX_PORT = 65535


async def log_exception_to_telemetry(exc: Exception, context: str) -> None:
    """Helper to safely log exceptions to telemetry without raising."""
    try:
        telemetry_service = get_telemetry_service()
        await telemetry_service.log_exception(exc, context)
    except (httpx.HTTPError, asyncio.QueueFull):
        await logger.awarning(f"Failed to log {context} exception to telemetry")


class RequestCancelledMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        sentinel = object()

        async def cancel_handler():
            while True:
                if await request.is_disconnected():
                    return sentinel
                await asyncio.sleep(0.1)

        handler_task = asyncio.create_task(call_next(request))
        cancel_task = asyncio.create_task(cancel_handler())

        done, pending = await asyncio.wait([handler_task, cancel_task], return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

        if cancel_task in done:
            return Response("Request was cancelled", status_code=499)
        return await handler_task


class JavaScriptMIMETypeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
        except Exception as exc:
            if isinstance(exc, PydanticSerializationError):
                message = (
                    "Something went wrong while serializing the response. "
                    "Please share this error on our GitHub repository."
                )
                error_messages = json.dumps([message, str(exc)])
                raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=error_messages) from exc
            raise
        if (
            "files/" not in request.url.path
            and request.url.path.endswith(".js")
            and response.status_code == HTTPStatus.OK
        ):
            response.headers["Content-Type"] = "text/javascript"
        return response


async def load_bundles_with_error_handling():
    try:
        return await load_bundles_from_urls()
    except (httpx.TimeoutException, httpx.HTTPError, httpx.RequestError) as exc:
        await logger.aerror(f"Error loading bundles from URLs: {exc}")
        return [], []


def warn_about_future_cors_changes(settings):
    """Warn users about upcoming CORS security changes in version 1.7."""
    # Check if using default (backward compatible) settings
    using_defaults = settings.cors_origins == "*" and settings.cors_allow_credentials is True

    if using_defaults:
        logger.warning(
            "CORS: Using permissive defaults (all origins + credentials). "
            "Set LANGFLOW_CORS_ORIGINS for production. Stricter defaults in v2.0."
        )


def get_lifespan(*, fix_migration=False, version=None):
    initialize_settings_service()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        from lfx.interface.components import component_cache, get_and_cache_all_types_dict

        from langflow.preload import PreloadStep, get_owned_temp_dirs, is_step_complete

        configure()

        # Startup message
        if version:
            await logger.adebug(f"Starting Langflow v{version}...")
        else:
            await logger.adebug("Starting Langflow...")

        sync_flows_from_fs_task = None
        mcp_init_task = None
        models_dev_refresh_task = None

        try:
            start_time = asyncio.get_event_loop().time()

            if get_settings_service().settings.sentry_dsn:
                try:
                    import sentry_sdk
                except ImportError:
                    await logger.awarning(
                        "LANGFLOW_SENTRY_DSN is set but sentry-sdk is not installed; "
                        "Sentry will not be initialized. Install it with: pip install sentry-sdk"
                    )
                else:
                    try:
                        sentry_settings = get_settings_service().settings
                        sentry_sdk.init(
                            dsn=sentry_settings.sentry_dsn,
                            traces_sample_rate=sentry_settings.sentry_traces_sample_rate,
                            profiles_sample_rate=sentry_settings.sentry_profiles_sample_rate,
                        )
                        await logger.adebug("Sentry SDK initialized in worker")
                    except Exception as e:  # noqa: BLE001
                        await logger.awarning(f"Failed to initialize Sentry SDK (check LANGFLOW_SENTRY_DSN): {e}")

            await logger.adebug("Initializing services")
            # When the master already ran preload, the service_manager (and the
            # DB service object) are inherited via fork. We still call
            # initialize_services() here so each worker rebuilds its own fresh
            # connection pool on first use (the master disposed its engine
            # before fork). The call is idempotent: factory registration and
            # migration application both no-op when already done.
            await initialize_services(fix_migration=fix_migration)
            await logger.adebug(f"Services initialized in {asyncio.get_event_loop().time() - start_time:.2f}s")

            # Start the telemetry writer (no-op when telemetry_writer_enabled is False).
            try:
                from langflow.services.deps import get_telemetry_writer_service

                telemetry_writer = get_telemetry_writer_service()
                if telemetry_writer is not None and telemetry_writer.is_enabled():
                    await telemetry_writer.start()
            except Exception as exc:  # noqa: BLE001
                # If the user explicitly opted in (telemetry_writer_enabled=True)
                # but startup failed, this is an error not a warning — every
                # subsequent write will silently fall back to the legacy direct-
                # write path that this feature was built to replace.
                await logger.aerror(
                    f"Failed to start telemetry writer; transactions and vertex_build "
                    f"writes will use the legacy direct-write path: {exc}"
                )

            current_time = asyncio.get_event_loop().time()
            await logger.adebug("Setting up LLM caching")
            setup_llm_caching()
            await logger.adebug(f"LLM caching setup in {asyncio.get_event_loop().time() - current_time:.2f}s")

            # Gate: Copy profile pictures
            if is_step_complete(PreloadStep.PROFILE_PICTURES):
                await logger.adebug("Skipping profile-picture copy: master already completed it during preload")
            else:
                current_time = asyncio.get_event_loop().time()
                await logger.adebug("Copying profile pictures")
                await copy_profile_pictures()
                await logger.adebug(f"Profile pictures copied in {asyncio.get_event_loop().time() - current_time:.2f}s")

            current_time = asyncio.get_event_loop().time()
            await logger.adebug("Reconciling knowledge base rows from disk")
            try:
                from langflow.api.utils import knowledge_base_service

                inserted = await knowledge_base_service.backfill_all_users_from_disk()
                elapsed = asyncio.get_event_loop().time() - current_time
                await logger.adebug(
                    f"Knowledge base reconciliation completed in {elapsed:.2f}s ({inserted} rows inserted)"
                )
            except Exception as exc:  # noqa: BLE001
                await logger.awarning("Knowledge base reconciliation skipped after startup error: %s", exc)

            if get_settings_service().settings.prometheus_enabled:
                try:
                    from prometheus_client import start_http_server

                    start_http_server(get_settings_service().settings.prometheus_port)
                    await logger.adebug(
                        f"Started Prometheus server on port {get_settings_service().settings.prometheus_port}"
                    )
                except ImportError:
                    await logger.aerror(
                        "prometheus_client is not installed. Install it with: pip install prometheus-client"
                    )
                except OSError as e:
                    import errno

                    if e.errno == errno.EADDRINUSE:
                        await logger.adebug(
                            f"Prometheus port {get_settings_service().settings.prometheus_port} already in use "
                            "(may be running in another worker)"
                        )
                    else:
                        await logger.awarning(f"Failed to start Prometheus server: {e}")

            telemetry_service = get_telemetry_service()

            # Gate: Load bundles
            if is_step_complete(PreloadStep.BUNDLES):
                # Inherit bundle paths from master via COW.
                # get_owned_temp_dirs() returns the preloaded dirs if this is
                # the master, or an empty list if this is a worker (workers
                # must NOT clean up the master's temp_dirs).
                temp_dirs = get_owned_temp_dirs()
                await logger.adebug("Skipping bundle load: inherited from master")
            else:
                current_time = asyncio.get_event_loop().time()
                await logger.adebug("Loading bundles")
                temp_dirs, bundles_components_paths = await load_bundles_with_error_handling()
                get_settings_service().settings.components_path.extend(bundles_components_paths)
                await logger.adebug(f"Bundles loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")

            # Locally-registered dev extensions (``lfx extension dev``) are
            # loaded later via :func:`import_extension_components` through the
            # @official-slot pathway alongside installed extensions, so they
            # share the BundleRegistry, palette decoration, and reload
            # endpoint with pip-installed bundles.  Nothing to wire here.

            # Gate: Cache component types
            # When types_cached is True, workers inherited the populated cache via COW; we still need a
            # local handle for create_or_update_starter_projects. starter_projects_created can remain False
            # if the master failed after caching types but before finishing starter projects.
            if is_step_complete(PreloadStep.TYPES_CACHED):
                await logger.adebug("Skipping types cache: inherited from master")
                all_types_dict = component_cache.all_types_dict
                if all_types_dict is None:
                    # Inconsistent inherited state (e.g. rare fork/COW edge cases): rebuild instead of
                    # skipping starter projects with an empty cache.
                    await logger.awarning(
                        "Component types cache is empty but preload marked types cached; "
                        "rebuilding cache in this worker."
                    )
                    all_types_dict = await get_and_cache_all_types_dict(get_settings_service(), telemetry_service)
            else:
                current_time = asyncio.get_event_loop().time()
                await logger.adebug("Caching types")
                all_types_dict = await get_and_cache_all_types_dict(get_settings_service(), telemetry_service)
                await logger.adebug(f"Types cached in {asyncio.get_event_loop().time() - current_time:.2f}s")

            # Gate: Create/update starter projects
            if is_step_complete(PreloadStep.STARTER_PROJECTS):
                await logger.adebug("Skipping starter projects: inherited from master")
            else:
                # Use file-based lock to prevent multiple workers from creating duplicate starter projects
                # concurrently. Note that it's still possible that one worker may complete this task, release
                # the lock, then another worker pick it up, but the operation is idempotent so worst case it
                # duplicates the initialization work.
                current_time = asyncio.get_event_loop().time()
                await logger.adebug("Creating/updating starter projects")

                if all_types_dict is None:
                    await logger.awarning(
                        "Skipping starter projects: component types cache is still empty after cache build. "
                        "Starter projects will not be created or updated."
                    )
                else:
                    lock_file = Path(tempfile.gettempdir()) / "langflow_starter_projects.lock"
                    lock = FileLock(lock_file, timeout=1)
                    try:
                        with lock:
                            await create_or_update_starter_projects(all_types_dict)
                            elapsed = asyncio.get_event_loop().time() - current_time
                            await logger.adebug(f"Starter projects created/updated in {elapsed:.2f}s")
                    except TimeoutError:
                        await logger.adebug("Another worker is creating starter projects, skipping")
                    except Exception as e:  # noqa: BLE001
                        await logger.awarning(
                            f"Failed to create or update starter projects: {e}. "
                            "Starter projects may not be created or updated."
                        )

            # Gate: Initialize agentic global variables (when agentic_experience enabled)
            if get_settings_service().settings.agentic_experience:
                if is_step_complete(PreloadStep.AGENTIC_GLOBALS):
                    await logger.adebug("Skipping agentic global variables: master already completed it during preload")
                else:
                    from langflow.api.utils.mcp.agentic_mcp import initialize_agentic_global_variables

                    current_time = asyncio.get_event_loop().time()
                    await logger.ainfo("Initializing agentic global variables...")
                    try:
                        async with session_scope() as session:
                            await initialize_agentic_global_variables(session)
                        elapsed = asyncio.get_event_loop().time() - current_time
                        await logger.adebug(f"Agentic global variables initialized in {elapsed:.2f}s")
                    except Exception as e:  # noqa: BLE001
                        await logger.awarning(f"Failed to initialize agentic global variables: {e}")

            current_time = asyncio.get_event_loop().time()
            await logger.adebug("Starting telemetry service")
            telemetry_service.start()
            await logger.adebug(f"started telemetry service in {asyncio.get_event_loop().time() - current_time:.2f}s")

            current_time = asyncio.get_event_loop().time()
            await logger.adebug("Starting MCP Composer service")
            mcp_composer_service = cast("MCPComposerService", get_service(ServiceType.MCP_COMPOSER_SERVICE))
            await mcp_composer_service.start()
            await logger.adebug(
                f"started MCP Composer service in {asyncio.get_event_loop().time() - current_time:.2f}s"
            )

            # Gate: Auto-configure agentic MCP server (when agentic_experience enabled)
            if get_settings_service().settings.agentic_experience:
                if is_step_complete(PreloadStep.AGENTIC_MCP):
                    await logger.adebug(
                        "Skipping agentic MCP server config: master already completed it during preload"
                    )
                else:
                    from langflow.api.utils.mcp.agentic_mcp import auto_configure_agentic_mcp_server

                    current_time = asyncio.get_event_loop().time()
                    await logger.ainfo("Configuring Agentic MCP server...")
                    try:
                        async with session_scope() as session:
                            await auto_configure_agentic_mcp_server(session)
                        elapsed = asyncio.get_event_loop().time() - current_time
                        await logger.adebug(f"Agentic MCP server configured in {elapsed:.2f}s")
                    except Exception as e:  # noqa: BLE001
                        await logger.awarning(f"Failed to configure agentic MCP server: {e}")

            # Gate: Load flows from directory
            current_time = asyncio.get_event_loop().time()
            if is_step_complete(PreloadStep.FLOWS):
                await logger.adebug("Skipping flows load: master already completed it during preload")
            else:
                await logger.adebug("Loading flows")
                await load_flows_from_directory()
                await logger.adebug(f"Flows loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")

            # Per-worker setup: sync_flows_from_fs and queue service
            # (MUST be started per-worker: they create asyncio tasks bound to this event loop)
            sync_flows_from_fs_task = asyncio.create_task(sync_flows_from_fs())
            queue_service = get_queue_service()
            if not queue_service.is_started():
                queue_service.start()

            total_time = asyncio.get_event_loop().time() - start_time
            await logger.adebug(f"Total initialization time: {total_time:.2f}s")

            async def delayed_init_mcp_servers():
                await asyncio.sleep(10.0)  # Increased delay to allow starter projects to be created
                current_time = asyncio.get_event_loop().time()
                await logger.adebug("Loading MCP servers for projects")
                try:
                    await init_mcp_servers()
                    await logger.adebug(f"MCP servers loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")
                except Exception as e:  # noqa: BLE001
                    await logger.awarning(f"First MCP server initialization attempt failed: {e}")
                    await asyncio.sleep(5.0)  # Increased retry delay
                    current_time = asyncio.get_event_loop().time()
                    await logger.adebug("Retrying MCP servers initialization")
                    try:
                        await init_mcp_servers()
                        await logger.adebug(
                            f"MCP servers loaded on retry in {asyncio.get_event_loop().time() - current_time:.2f}s"
                        )
                    except Exception as e2:  # noqa: BLE001
                        await logger.aexception(f"Failed to initialize MCP servers after retry: {e2}")

            # Start the delayed initialization as a background task
            # Allows the server to start first to avoid race conditions with MCP Server startup
            mcp_init_task = asyncio.create_task(delayed_init_mcp_servers())

            async def refresh_models_dev_periodically() -> None:
                """Hydrate the models.dev catalog at startup and refresh daily.

                Loads any disk snapshot first so the in-memory catalog reflects
                last-known-good metadata immediately, then attempts a live
                fetch. On failure the disk snapshot (or bundled static lists)
                stays in effect — startup is never blocked by models.dev
                availability.
                """
                from lfx.base.models.models_dev_catalog import (
                    fetch_models_dev_snapshot,
                    invalidate_catalog_cache,
                    load_models_dev_snapshot,
                    save_models_dev_snapshot,
                    set_active_snapshot,
                )

                refresh_interval_seconds = 24 * 60 * 60

                disk_snapshot = load_models_dev_snapshot()
                if disk_snapshot is not None:
                    set_active_snapshot(disk_snapshot)
                    invalidate_catalog_cache()
                    await logger.adebug("Loaded models.dev snapshot from disk")

                while True:
                    try:
                        fresh = await fetch_models_dev_snapshot()
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:  # noqa: BLE001
                        await logger.awarning(f"models.dev refresh failed: {e}")
                        fresh = None

                    if fresh is not None:
                        set_active_snapshot(fresh)
                        invalidate_catalog_cache()
                        try:
                            save_models_dev_snapshot(fresh)
                        except Exception as e:  # noqa: BLE001
                            await logger.awarning(f"models.dev snapshot save failed: {e}")
                        else:
                            await logger.adebug("models.dev snapshot refreshed")

                    await asyncio.sleep(refresh_interval_seconds)

            # LANGFLOW_MODELS_DEV_REFRESH=false disables the live models.dev
            # fetch. Tests set this: the startup fetch otherwise fires from a
            # background task during whatever test is running, hitting the
            # network and tripping event-loop-block detectors (pyleak).
            if os.getenv("LANGFLOW_MODELS_DEV_REFRESH", "true").lower() not in ("false", "0", "no"):
                models_dev_refresh_task = asyncio.create_task(refresh_models_dev_periodically())
            else:
                await logger.adebug("models.dev refresh disabled via LANGFLOW_MODELS_DEV_REFRESH")

            # v1 and project MCP server context managers
            from langflow.api.v1.mcp import start_streamable_http_manager
            from langflow.api.v1.mcp_projects import start_project_task_group

            await start_streamable_http_manager()
            await start_project_task_group()

            yield
        except asyncio.CancelledError:
            await logger.adebug("Lifespan received cancellation signal")
        except UnsupportedPostgreSQLVersionError:
            # Normally caught by the pre-flight check in __main__.py
            # before the server starts.  If we get here anyway (e.g.
            # direct uvicorn invocation via ``make backend``), exit
            # immediately and tell the parent (reloader) to stop.
            import signal

            sys.stdout.flush()
            sys.stderr.flush()
            with suppress(ProcessLookupError, PermissionError):
                os.kill(os.getppid(), signal.SIGTERM)
            os._exit(3)
        except Exception as exc:
            if "langflow migration --fix" not in str(exc):
                logger.exception(exc)

                await log_exception_to_telemetry(exc, "lifespan")
            raise
        finally:
            # CRITICAL: Cleanup MCP sessions FIRST, before any other shutdown logic.
            # This ensures MCP subprocesses are killed even if shutdown is interrupted.
            await cleanup_mcp_sessions()

            # Clean shutdown with progress indicator
            # Create shutdown progress (show verbose timing if log level is DEBUG)
            from langflow.__main__ import get_number_of_workers
            from langflow.cli.progress import create_langflow_shutdown_progress

            log_level = os.getenv("LANGFLOW_LOG_LEVEL", "info").lower()
            num_workers = get_number_of_workers(get_settings_service().settings.workers)
            shutdown_progress = create_langflow_shutdown_progress(
                verbose=log_level == "debug", multiple_workers=num_workers > 1
            )

            try:
                # Step 0: Stopping Server
                with shutdown_progress.step(0):
                    await logger.adebug("Stopping server gracefully...")
                    # The actual server stopping is handled by the lifespan context
                    await asyncio.sleep(0.1)  # Brief pause for visual effect

                # Step 1: Cancelling Background Tasks
                with shutdown_progress.step(1):
                    from langflow.api.v1.mcp import stop_streamable_http_manager
                    from langflow.api.v1.mcp_projects import stop_project_task_group

                    # Shutdown MCP project servers
                    try:
                        await stop_project_task_group()
                    except Exception as e:  # noqa: BLE001
                        await logger.aerror(f"Failed to stop MCP Project servers: {e}")
                    # Close MCP server streamable-http session manager .run() context manager
                    try:
                        await stop_streamable_http_manager()
                    except Exception as e:  # noqa: BLE001
                        await logger.aerror(f"Failed to stop MCP server streamable-http session manager: {e}")
                    # Cancel background tasks
                    tasks_to_cancel = []
                    if sync_flows_from_fs_task:
                        sync_flows_from_fs_task.cancel()
                        tasks_to_cancel.append(sync_flows_from_fs_task)
                    if mcp_init_task and not mcp_init_task.done():
                        mcp_init_task.cancel()
                        tasks_to_cancel.append(mcp_init_task)
                    if models_dev_refresh_task and not models_dev_refresh_task.done():
                        models_dev_refresh_task.cancel()
                        tasks_to_cancel.append(models_dev_refresh_task)
                    if tasks_to_cancel:
                        # Wait for all tasks to complete, capturing exceptions
                        results = await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
                        # Log any non-cancellation exceptions
                        for result in results:
                            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                                await logger.aerror(f"Error during task cleanup: {result}", exc_info=result)

                # Step 2: Cleaning Up Services
                with shutdown_progress.step(2):
                    # Drain pending audit writes before services tear down so
                    # rows scheduled mid-request still land in the DB. We do
                    # this here (not in teardown_services) because the DB
                    # session factory must still be alive.
                    try:
                        from langflow.services.authorization.utils import drain_pending_audit_writes

                        await drain_pending_audit_writes(timeout=5.0)
                    except Exception as drain_exc:  # noqa: BLE001 — never block shutdown on audit
                        await logger.awarning(f"drain_pending_audit_writes failed: {drain_exc}")
                    try:
                        await asyncio.wait_for(teardown_services(), timeout=30)
                    except asyncio.TimeoutError:
                        await logger.awarning("Teardown services timed out after 30s.")

                # Step 3: Clearing Temporary Files
                with shutdown_progress.step(3):
                    temp_dir_cleanups = [asyncio.to_thread(temp_dir.cleanup) for temp_dir in temp_dirs]
                    try:
                        await asyncio.wait_for(asyncio.gather(*temp_dir_cleanups), timeout=10)
                    except asyncio.TimeoutError:
                        await logger.awarning("Temporary file cleanup timed out after 10s.")

                # Step 4: Finalizing Shutdown
                with shutdown_progress.step(4):
                    await logger.adebug("Langflow shutdown complete")

                # Show completion summary and farewell
                shutdown_progress.print_shutdown_summary()

            except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.DBAPIError) as e:
                # Case where the database connection is closed during shutdown
                await logger.awarning(f"Database teardown failed due to closed connection: {e}")
            except asyncio.CancelledError:
                # Swallow this - it's normal during shutdown
                await logger.adebug("Teardown cancelled during shutdown.")
            except Exception as e:  # noqa: BLE001
                await logger.aexception(f"Unhandled error during cleanup: {e}")
                await log_exception_to_telemetry(e, "lifespan_cleanup")

    return lifespan


def create_app():
    """Create the FastAPI app and include the router."""
    from langflow.utils.version import get_version_info

    __version__ = get_version_info()["version"]
    configure()
    lifespan = get_lifespan(version=__version__)

    settings = get_settings_service().settings

    app = FastAPI(
        title="Langflow",
        version=__version__,
        lifespan=lifespan,
        root_path=settings.root_path,
    )
    app.add_middleware(
        ContentSizeLimitMiddleware,
    )

    add_sentry_middleware(app)

    # Warn about future CORS changes
    warn_about_future_cors_changes(settings)

    # Configure CORS using settings (with backward compatible defaults)
    origins = settings.cors_origins
    if isinstance(origins, str) and origins != "*":
        origins = [origins]

    # Apply current CORS configuration (maintains backward compatibility)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    app.add_middleware(JavaScriptMIMETypeMiddleware)

    @app.middleware("http")
    async def check_boundary(request: Request, call_next):
        if "/api/v1/files/upload" in request.url.path:
            content_type = request.headers.get("Content-Type")

            if not content_type or "multipart/form-data" not in content_type or "boundary=" not in content_type:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Content-Type header must be 'multipart/form-data' with a boundary parameter."},
                )

            boundary = content_type.split("boundary=")[-1].strip()

            if not re.match(r"^[\w\-]{1,70}$", boundary):
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Invalid boundary format"},
                )

            body = await request.body()

            boundary_start = f"--{boundary}".encode()
            # The multipart/form-data spec doesn't require a newline after the boundary, however many clients do
            # implement it that way
            boundary_end = f"--{boundary}--\r\n".encode()
            boundary_end_no_newline = f"--{boundary}--".encode()

            if not body.startswith(boundary_start) or not body.endswith((boundary_end, boundary_end_no_newline)):
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Invalid multipart formatting"},
                )

        return await call_next(request)

    @app.middleware("http")
    async def forwarded_prefix_middleware(request: Request, call_next):
        """Honour X-Forwarded-Prefix set by a reverse proxy.

        When a reverse proxy (e.g. Nginx) strips a URL prefix before forwarding
        the request, it can advertise the original prefix via X-Forwarded-Prefix.
        We propagate this into the ASGI ``root_path`` so that transports like
        MCP SSE include the prefix in the POST-back URLs they hand to clients.

        This middleware is only active when ``root_path`` is configured in
        settings (i.e. the operator has explicitly opted into reverse-proxy
        mode).  The header value takes precedence over the static setting
        because the proxy is the runtime source of truth for the prefix.
        """
        if not settings.root_path:
            return await call_next(request)

        prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
        if prefix and prefix.startswith("/") and "://" not in prefix and "?" not in prefix and "#" not in prefix:
            request.scope["root_path"] = prefix
        return await call_next(request)

    @app.middleware("http")
    async def flatten_query_string_lists(request: Request, call_next):
        flattened: list[tuple[str, str]] = []
        for key, value in request.query_params.multi_items():
            flattened.extend((key, entry) for entry in value.split(","))

        request.scope["query_string"] = urlencode(flattened, doseq=True).encode("utf-8")

        return await call_next(request)

    _supported_locales: frozenset[str] | None = None

    @app.middleware("http")
    async def set_locale(request: Request, call_next):
        """Parse Accept-Language header and store normalised locale in request.state.

        Handles quality values ("fr-FR,fr;q=0.9,en;q=0.8" → "fr") and preserves
        zh-Hans as a full tag. All other locales are reduced to the language code.
        Validates against the loaded locale files and falls back to "en" for unknown
        values — prevents client-supplied headers from polluting the per-locale cache.
        Result is available as request.state.locale in any endpoint.
        """
        nonlocal _supported_locales
        if _supported_locales is None:
            from langflow.utils.i18n import get_supported_locales

            _supported_locales = frozenset(get_supported_locales())

        accept_lang = request.headers.get("Accept-Language", "en")
        primary = accept_lang.split(",")[0].strip()
        locale = "zh-Hans" if primary.lower().startswith("zh-hans") else primary.split("-")[0]
        if locale not in _supported_locales:
            locale = "en"
        request.state.locale = locale
        return await call_next(request)

    if prome_port_str := os.environ.get("LANGFLOW_PROMETHEUS_PORT"):
        # set here for create_app() entry point
        prome_port = int(prome_port_str)
        if prome_port > 0 and prome_port < MAX_PORT:
            logger.debug(f"Prometheus server port configured as {prome_port}...")
            settings.prometheus_enabled = True
            settings.prometheus_port = prome_port
        else:
            msg = f"Invalid port number {prome_port_str}"
            raise ValueError(msg)

    if settings.mcp_server_enabled:
        from langflow.api.v1 import mcp_router

        router.include_router(mcp_router)

    app.include_router(router)
    app.include_router(health_check_router)
    app.include_router(log_router)

    # Discover and register additional routers from plugins (langflow.plugins entry-point)
    load_plugin_routes(app)

    @app.exception_handler(DeploymentGuardError)
    async def deployment_guard_exception_handler(_request: Request, exc: DeploymentGuardError):
        return JSONResponse(
            status_code=HTTPStatus.CONFLICT,
            content={"detail": exc.detail},
        )

    # Add rate limit exception handler
    from slowapi.errors import RateLimitExceeded

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exception_handler(request: Request, _exc: RateLimitExceeded):
        """Handle rate limit exceeded errors with structured logging."""
        from langflow.services.rate_limit.service import get_limiter_key

        # Default to 60 seconds for "/minute" window
        retry_after_seconds = "60"

        client_ip = get_limiter_key(request)
        logger.warning(
            "Rate limit exceeded",
            auth_event="rate_limit_exceeded",
            client_ip=client_ip,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            content={
                "detail": "Too many requests. Please try again later.",
                "retry_after": retry_after_seconds,
            },
            headers={
                "Retry-After": retry_after_seconds,
            },
        )

    @app.exception_handler(Exception)
    async def exception_handler(_request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            await logger.aerror(f"HTTPException: {exc}", exc_info=exc)
            return JSONResponse(
                status_code=exc.status_code,
                content={"message": str(exc.detail)},
            )
        await logger.aerror(f"unhandled error: {exc}", exc_info=exc)

        await log_exception_to_telemetry(exc, "handler")

        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={"message": str(exc)},
        )

    FastAPIInstrumentor.instrument_app(app)

    add_pagination(app)

    # Add SlowAPI state to app for rate limiting
    from langflow.services.rate_limit import get_rate_limiter

    limiter = get_rate_limiter()
    app.state.limiter = limiter

    return app


def add_sentry_middleware(app: FastAPI) -> None:
    """Attach SentryAsgiMiddleware to the app.

    Only the ASGI middleware is registered here so it is available at request time.
    The actual ``sentry_sdk.init()`` call is deferred to the worker lifespan
    (see ``get_lifespan``) to avoid ghost transactions across pre-fork workers.
    """
    settings = get_settings_service().settings
    if settings.sentry_dsn:
        try:
            from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
        except ImportError:
            logger.warning(
                "LANGFLOW_SENTRY_DSN is set but sentry-sdk is not installed; "
                "SentryAsgiMiddleware will not be added. Install it with: pip install sentry-sdk"
            )
            return
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to import SentryAsgiMiddleware: {e}")
            return

        app.add_middleware(SentryAsgiMiddleware)


def setup_static_files(app: FastAPI, static_files_dir: Path) -> None:
    """Setup the static files directory.

    Args:
        app (FastAPI): FastAPI app.
        static_files_dir (str): Path to the static files directory.
    """
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )

    @app.exception_handler(404)
    async def custom_404_handler(_request, _exc):
        # Return JSON for all API endpoints to prevent HTML responses
        if _request.url.path.startswith("/api"):
            # Extract detail from HTTPException if available
            detail = _exc.detail if isinstance(_exc, HTTPException) else "Not Found"
            return JSONResponse(
                status_code=404,
                content=detail if isinstance(detail, dict) else {"detail": detail},
            )

        path = anyio.Path(static_files_dir) / "index.html"

        if not await path.exists():
            msg = f"File at path {path} does not exist."
            raise RuntimeError(msg)
        return FileResponse(path)


def get_static_files_dir():
    """Get the static files directory relative to Langflow's main.py file."""
    frontend_path = Path(__file__).parent
    return frontend_path / "frontend"


def setup_app(static_files_dir: Path | None = None, *, backend_only: bool = False) -> FastAPI:
    """Setup the FastAPI app."""
    # get the directory of the current file
    if not static_files_dir:
        static_files_dir = get_static_files_dir()

    if not backend_only and (not static_files_dir or not static_files_dir.exists()):
        msg = f"Static files directory {static_files_dir} does not exist."
        raise RuntimeError(msg)
    app = create_app()

    if not backend_only and static_files_dir is not None:
        setup_static_files(app, static_files_dir)
    return app


if __name__ == "__main__":
    import uvicorn

    from langflow.__main__ import get_number_of_workers

    configure()
    uvicorn.run(
        "langflow.main:create_app",
        host="localhost",
        port=7860,
        workers=get_number_of_workers(),
        log_level="error",
        reload=True,
        loop="asyncio",
    )
