import typer
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from langflow.backend.app import create_app

# get the directory of the current file
path = Path(__file__).parent
static_files_dir = path / "frontend/build"
app = create_app()
app.mount(
    "/",
    StaticFiles(directory=static_files_dir, html=True),
    name="static",
)


def serve(port: int = 5003):
    import uvicorn

    uvicorn.run(app, host="localhost", port=port)


def main():
    typer.run(serve)


if __name__ == "__main__":
    main()
