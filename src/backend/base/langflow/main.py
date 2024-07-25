import os
import asyncio
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import nest_asyncio  # type: ignore
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from http import HTTPStatus
from loguru import logger
from pydantic import PydanticDeprecatedSince20
from rich import print as rprint
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from langflow.api import router, health_check_router, log_router
from langflow.initial_setup.setup import (
    create_or_update_starter_projects,
    initialize_super_user_if_needed,
    load_flows_from_directory,
)
from langflow.interface.types import get_and_cache_all_types_dict
from langflow.interface.utils import setup_llm_caching
from langflow.services.deps import get_cache_service, get_settings_service, get_telemetry_service
from langflow.services.plugins.langfuse_plugin import LangfuseInstance
from langflow.services.utils import initialize_services, teardown_services
from langflow.utils.logger import configure

# AgentOps import
import agentops
from dotenv import load_dotenv

# Ignore Pydantic deprecation warnings from Langchain
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)

# Load environment variables and initialize AgentOps
load_dotenv()
agentops.init(os.getenv("AGENTOPS_API_KEY"))


class RequestCancelledMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
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
            agentops.record_event("request_cancelled", {"path": request.url.path})
            return Response("Request was cancelled", status_code=499)
        else:
            return await handler_task


class JavaScriptMIMETypeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(exc)
            agentops.record_event("middleware_error", {"error": str(exc)})
            raise exc
        if "files/" not in request.url.path and request.url.path.endswith(".js") and response.status_code == 200:
            response.headers["Content-Type"] = "text/javascript"
        return response


@agentops.record_function("lifespan")
def get_lifespan(fix_migration=False, socketio_server=None, version=None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nest_asyncio.apply()
        # Startup message
        if version:
            rprint(f"[bold green]Starting Langflow v{version}...[/bold green]")
        else:
            rprint("[bold green]Starting Langflow...[/bold green]")
        try:
            initialize_services(fix_migration=fix_migration, socketio_server=socketio_server)
            setup_llm_caching()
            LangfuseInstance.update()
            initialize_super_user_if_needed()
            task = asyncio.create_task(get_and_cache_all_types_dict(get_settings_service(), get_cache_service()))
            await create_or_update_starter_projects(task)
            asyncio.create_task(get_telemetry_service().start())
            load_flows_from_directory()
            agentops.record_event("langflow_started", {"version": version})
            yield
        except Exception as exc:
            if "langflow migration --fix" not in str(exc):
                logger.error(exc)
            agentops.record_event("langflow_startup_error", {"error": str(exc)})
            raise
        # Shutdown message
        rprint("[bold red]Shutting down Langflow...[/bold red]")
        await teardown_services()
        agentops.record_event("langflow_shutdown")

    return lifespan


@agentops.record_function("create_app")
def create_app():
    """Create the FastAPI app and include the router."""
    try:
        from langflow.version import __version__  # type: ignore
    except ImportError:
        from importlib.metadata import version

        __version__ = version("langflow-base")

    configure()
    lifespan = get_lifespan(version=__version__)
    app = FastAPI(lifespan=lifespan, title="Langflow", version=__version__)
    setup_sentry(app)
    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(JavaScriptMIMETypeMiddleware)
    # ! Deactivating this until we find a better solution
    # app.add_middleware(RequestCancelledMiddleware)

    @app.middleware("http")
    async def flatten_query_string_lists(request: Request, call_next):
        flattened: list[tuple[str, str]] = []
        for key, value in request.query_params.multi_items():
            flattened.extend((key, entry) for entry in value.split(","))

        request.scope["query_string"] = urlencode(flattened, doseq=True).encode("utf-8")

        return await call_next(request)

    settings = get_settings_service().settings
    if prome_port_str := os.environ.get("LANGFLOW_PROMETHEUS_PORT"):
        # set here for create_app() entry point
        prome_port = int(prome_port_str)
        if prome_port > 0 or prome_port < 65535:
            rprint(f"[bold green]Starting Prometheus server on port {prome_port}...[/bold green]")
            settings.prometheus_enabled = True
            settings.prometheus_port = prome_port
        else:
            raise ValueError(f"Invalid port number {prome_port_str}")

    if settings.prometheus_enabled:
        from prometheus_client import start_http_server

        start_http_server(settings.prometheus_port)

    app.include_router(router)
    app.include_router(health_check_router)
    app.include_router(log_router)

    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            logger.error(f"HTTPException: {exc.detail}")
            agentops.record_event("http_exception", {"status_code": exc.status_code, "detail": exc.detail})
            return JSONResponse(
                status_code=exc.status_code,
                content={"message": str(exc.detail)},
            )
        else:
            logger.error(f"unhandled error: {exc}")
            agentops.record_event("unhandled_exception", {"error": str(exc)})
            return JSONResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content={"message": str(exc)},
            )

    FastAPIInstrumentor.instrument_app(app)

    return app


@agentops.record_function("setup_sentry")
def setup_sentry(app: FastAPI):
    settings = get_settings_service().settings
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
        )
        app.add_middleware(SentryAsgiMiddleware)
        agentops.record_event("sentry_initialized")


@agentops.record_function("setup_static_files")
def setup_static_files(app: FastAPI, static_files_dir: Path):
    """
    Setup the static files directory.
    Args:
        app (FastAPI): FastAPI app.
        path (str): Path to the static files directory.
    """
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )

    @app.exception_handler(404)
    async def custom_404_handler(request, __):
        path = static_files_dir / "index.html"

        if not path.exists():
            agentops.record_event("static_file_not_found", {"path": str(path)})
            raise RuntimeError(f"File at path {path} does not exist.")
        return FileResponse(path)


@agentops.record_function("get_static_files_dir")
def get_static_files_dir():
    """Get the static files directory relative to Langflow's main.py file."""
    frontend_path = Path(__file__).parent
    return frontend_path / "frontend"


@agentops.record_function("setup_app")
def setup_app(static_files_dir: Optional[Path] = None, backend_only: bool = False) -> FastAPI:
    """Setup the FastAPI app."""
    # get the directory of the current file
    logger.info(f"Setting up app with static files directory {static_files_dir}")
    if not static_files_dir:
        static_files_dir = get_static_files_dir()

    if not backend_only and (not static_files_dir or not static_files_dir.exists()):
        agentops.record_event("static_files_dir_not_found", {"path": str(static_files_dir)})
        raise RuntimeError(f"Static files directory {static_files_dir} does not exist.")
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
        host="127.0.0.1",
        port=7860,
        workers=get_number_of_workers(),
        log_level="error",
        reload=True,
        loop="asyncio",
    )

# End the session when the program exits
import atexit


def end_session():
    agentops.end_session("Success")


atexit.register(end_session)
