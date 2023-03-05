from langflow.backend.app import create_app

import typer
import uvicorn
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = create_app()


def serve(port: int = 5003):
    # get the directory of the current file
    path = Path(__file__).parent
    static_files_dir = path / "frontend/build"
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )
    uvicorn.run(app, port=port)


def main():
    typer.run(serve)


if __name__ == "__main__":
    main()
