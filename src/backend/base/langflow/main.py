import asyncio
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import nest_asyncio  # type: ignore
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import PydanticDeprecatedSince20
from rich import print as rprint
from starlette.middleware.base import BaseHTTPMiddleware

from langflow.api import router
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

# Ignore Pydantic deprecation warnings from Langchain
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)


class RequestCancelledMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Let's make a shared queue for the request messages
        queue = asyncio.Queue()

        async def message_poller(sentinel, handler_task):
            nonlocal queue
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    handler_task.cancel()
                    return sentinel  # Break the loop

                # Puts the message in the queue
                await queue.put(message)

        sentinel = object()
        handler_task = asyncio.create_task(self.app(scope, queue.get, send))
        asyncio.create_task(message_poller(sentinel, handler_task))

        try:
            return await handler_task
        except asyncio.CancelledError:
            pass


class JavaScriptMIMETypeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(exc)
            raise exc
        if "files/" not in request.url.path and request.url.path.endswith(".js") and response.status_code == 200:
            response.headers["Content-Type"] = "text/javascript"
        return response


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
            yield
        except Exception as exc:
            if "langflow migration --fix" not in str(exc):
                logger.error(exc)
            raise
        # Shutdown message
        rprint("[bold red]Shutting down Langflow...[/bold red]")
        teardown_services()

    return lifespan


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
    app.add_middleware(RequestCancelledMiddleware)

    @app.middleware("http")
    async def flatten_query_string_lists(request: Request, call_next):
        flattened: list[tuple[str, str]] = []
        for key, value in request.query_params.multi_items():
            flattened.extend((key, entry) for entry in value.split(","))

        request.scope["query_string"] = urlencode(flattened, doseq=True).encode("utf-8")

        return await call_next(request)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(router)

    return app


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
            raise RuntimeError(f"File at path {path} does not exist.")
        return FileResponse(path)


def get_static_files_dir():
    """Get the static files directory relative to Langflow's main.py file."""
    frontend_path = Path(__file__).parent
    return frontend_path / "frontend"


def setup_app(static_files_dir: Optional[Path] = None, backend_only: bool = False) -> FastAPI:
    """Setup the FastAPI app."""
    # get the directory of the current file
    logger.info(f"Setting up app with static files directory {static_files_dir}")
    if not static_files_dir:
        static_files_dir = get_static_files_dir()

    if not backend_only and (not static_files_dir or not static_files_dir.exists()):
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
