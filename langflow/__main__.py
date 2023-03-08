import multiprocessing
from langflow_backend.main import create_app

import typer
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from langflow.server import LangflowApplication

def serve(
    workers: int = None,
    timeout: int = None,
):
    app = create_app()
    # get the directory of the current file
    path = Path(__file__).parent
    static_files_dir = path / "frontend/build"
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )
    if not workers:
        workers = 1
    elif workers == -1:
        workers = (multiprocessing.cpu_count() * 2) + 1

    if not timeout:
        timeout = 60


    options = {"bind": "0.0.0.0:5003", "workers": workers, "worker_class": "uvicorn.workers.UvicornWorker", "timeout": timeout}


    LangflowApplication(app, options).run()


def main():
    typer.run(serve)


if __name__ == "__main__":
    main()
