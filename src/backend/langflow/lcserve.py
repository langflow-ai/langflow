# This file is used by lc-serve to load the mounted app and serve it.

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from langflow.main import create_app

app = create_app()
path = Path(__file__).parent
static_files_dir = path / "frontend"
app.mount(
    "/",
    StaticFiles(directory=static_files_dir, html=True),
    name="static",
)
