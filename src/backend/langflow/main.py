from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from langflow.api import router


from langflow.interface.utils import setup_llm_caching
from langflow.services.utils import initialize_services
from langflow.services.plugins.langfuse import LangfuseInstance
from langflow.services.utils import (
    teardown_services,
)
from langflow.utils.logger import configure


def create_app():
    """Create the FastAPI app and include the router."""

    configure()

    app = FastAPI()

    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(router)

    app.on_event("startup")(initialize_services)
    app.on_event("startup")(setup_llm_caching)
    app.on_event("startup")(LangfuseInstance.update)

    app.on_event("shutdown")(teardown_services)
    app.on_event("shutdown")(LangfuseInstance.teardown)

    return app


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


def setup_app(
    static_files_dir: Optional[Path] = None, backend_only: bool = False
) -> FastAPI:
    """Setup the FastAPI app."""
    # get the directory of the current file
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
        create_app,
        host="127.0.0.1",
        port=7860,
        workers=get_number_of_workers(),
        log_level="debug",
        reload=True,
    )
