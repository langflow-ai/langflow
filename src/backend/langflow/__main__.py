import multiprocessing
import platform
import re

from langflow.main import create_app

import typer
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def get_number_of_workers(workers=None):
    if workers == -1:
        workers = (multiprocessing.cpu_count() * 2) + 1
    return workers


def serve(
    host: str = "127.0.0.1", workers: int = 1, timeout: int = 60, port: int = 7860
):
    app = create_app()
    # get the directory of the current file
    path = Path(__file__).parent
    static_files_dir = path / "frontend"
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )
    options = {
        "bind": f"{host}:{port}",
        "workers": get_number_of_workers(workers),
        "worker_class": "uvicorn.workers.UvicornWorker",
        "timeout": timeout,
    }

    if platform.system() in ["Darwin", "Windows"]:
        # Run using uvicorn on MacOS and Windows
        # Windows doesn't support gunicorn
        # MacOS requires a env variable to be set to use gunicorn
        import uvicorn

        uvicorn.run(app, host=host, port=port, log_level="info")
    else:
        from langflow.server import LangflowApplication

        LangflowApplication(app, options).run()


def main():
    typer.run(serve)


if __name__ == "__main__":
    main()
