from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from langflow.api import router
from langflow.database.base import create_db_and_tables
from langflow.interface.utils import setup_llm_caching


def create_app():
    """Create the FastAPI app and include the router."""

    app = FastAPI()

    origins = [
        "*",
    ]

    @app.get("/health")
    def get_health():
        return {"status": "OK"}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.on_event("startup")(create_db_and_tables)
    app.on_event("startup")(setup_llm_caching)
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


# app = create_app()
# setup_static_files(app, static_files_dir)
def setup_app(static_files_dir: Optional[Path] = None) -> FastAPI:
    """Setup the FastAPI app."""
    # get the directory of the current file
    if not static_files_dir:
        frontend_path = Path(__file__).parent
        static_files_dir = frontend_path / "frontend"

    app = create_app()
    setup_static_files(app, static_files_dir)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=7860)
