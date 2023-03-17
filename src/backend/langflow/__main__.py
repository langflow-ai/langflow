import multiprocessing
import platform
import re

from langflow.main import create_app

import typer
from fastapi.staticfiles import StaticFiles
from pathlib import Path


def get_number_of_workers(workers=None):
    if workers == -1:
        workers = (multiprocessing.cpu_count() * 2) + 1
    return workers


def replace_port(static_files_dir, host, port):
    # Load index.html from frontend directory
    # In it there is a script tag that sets the base url
    # like so setItem("port", "http://localhost:7860")
    # localhost could be anything so we need to verify for string
    # we need to set the base url to the port that the server is running on
    # so that the frontend can make requests to the backend
    # This is a hacky way to do it, but it works
    new_string = f'setItem("port","http://{host}:{port}")'
    with open(static_files_dir / "index.html", "r") as f:
        index_html = f.read()
        # using regex to replace the port
        index_html = re.sub(
            r"setItem\(\"port\",.*\)",
            new_string,
            index_html,
        )
    with open(static_files_dir / "index.html", "w") as f:
        f.write(index_html)
    # Verify that the port was replaced
    with open(static_files_dir / "index.html", "r") as f:
        index_html = f.read()
        if new_string not in index_html:
            raise ValueError(
                "The port was not replaced in index.html. "
                "Please check the regex in main.py"
            )


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

    # Replace the port in index.html
    replace_port(static_files_dir, host, port)

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
