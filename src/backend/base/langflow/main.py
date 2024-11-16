import asyncio
import json
import os
import re
import warnings
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import PydanticDeprecatedSince20
from pydantic_core import PydanticSerializationError
from rich import print as rprint
from starlette.middleware.base import BaseHTTPMiddleware

from langflow.api import health_check_router, log_router, router
from langflow.initial_setup.setup import (
    create_or_update_starter_projects,
    initialize_super_user_if_needed,
    load_flows_from_directory,
)
from langflow.interface.types import get_and_cache_all_types_dict
from langflow.interface.utils import setup_llm_caching
from langflow.logging.logger import configure
from langflow.services.deps import get_settings_service, get_telemetry_service
from langflow.services.utils import initialize_services, teardown_services

# Ignore Pydantic deprecation warnings from Langchain
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)


MAX_PORT = 65535


class RequestCancelledMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
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
            return Response("Request was cancelled", status_code=499)
        return await handler_task


class JavaScriptMIMETypeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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


def get_lifespan(*, fix_migration=False, version=None):
    telemetry_service = get_telemetry_service()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        configure(async_file=True)

        # Startup message
        if version:
            rprint(f"[bold green]Starting Langflow v{version}...[/bold green]")
        else:
            rprint("[bold green]Starting Langflow...[/bold green]")
        try:
            await initialize_services(fix_migration=fix_migration)
            await asyncio.to_thread(setup_llm_caching)
            await initialize_super_user_if_needed()
            all_types_dict = await get_and_cache_all_types_dict(get_settings_service())
            await asyncio.to_thread(create_or_update_starter_projects, all_types_dict)
            telemetry_service.start()
            await load_flows_from_directory()
            yield

        except Exception as exc:
            if "langflow migration --fix" not in str(exc):
                logger.exception(exc)
            raise
        finally:
            # Clean shutdown
            logger.info("Cleaning up resources...")
            await teardown_services()
            await logger.complete()
            # Final message
            rprint("[bold red]Langflow shutdown complete[/bold red]")

    return lifespan


def create_app():
    """Create the FastAPI app and include the router."""
    from langflow.utils.version import get_version_info

    __version__ = get_version_info()["version"]

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
            boundary_end = f"--{boundary}--\r\n".encode()

            if not body.startswith(boundary_start) or not body.endswith(boundary_end):
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Invalid multipart formatting"},
                )

        return await call_next(request)

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
        if prome_port > 0 or prome_port < MAX_PORT:
            rprint(f"[bold green]Starting Prometheus server on port {prome_port}...[/bold green]")
            settings.prometheus_enabled = True
            settings.prometheus_port = prome_port
        else:
            msg = f"Invalid port number {prome_port_str}"
            raise ValueError(msg)

    if settings.prometheus_enabled:
        from prometheus_client import start_http_server

        start_http_server(settings.prometheus_port)

    app.include_router(router)
    app.include_router(health_check_router)
    app.include_router(log_router)

    @app.exception_handler(Exception)
    async def exception_handler(_request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            logger.error(f"HTTPException: {exc}", exc_info=exc)
            return JSONResponse(
                status_code=exc.status_code,
                content={"message": str(exc.detail)},
            )
        logger.error(f"unhandled error: {exc}", exc_info=exc)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={"message": str(exc)},
        )

    FastAPIInstrumentor.instrument_app(app)

    return app


def setup_sentry(app: FastAPI) -> None:
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
        path = static_files_dir / "index.html"

        if not path.exists():
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
    logger.info(f"Setting up app with static files directory {static_files_dir}")
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
        host="127.0.0.1",
        port=7860,
        workers=get_number_of_workers(),
        log_level="error",
        reload=True,
        loop="asyncio",
    )
