from pathlib import Path
from tempfile import tempdir
from langflow.__main__ import app
import pytest

import requests
import multiprocessing
import time
from langflow.services import utils


@pytest.fixture(scope="module")
def default_settings():
    return [
        "--backend-only",
        "--no-open-browser",
    ]


def test_server(default_settings):
    p = multiprocessing.Process(
        target=app,
        args=(["--host", "localhost", "--port", "8982", *default_settings],),
    )
    p.start()
    time.sleep(5)  # allow some time for the server to start

    response = requests.get(
        "http://localhost:8982/health"
    )  # assuming a /health endpoint exists
    assert response.status_code == 200

    p.terminate()


def test_database_url(runner):
    result = runner.invoke(app, ["--database-url", "sqlite:///test.db"])
    assert result.exit_code == 2, result.stdout
    assert "No such option: --database-url" in result.output


def test_components_path(runner, client, default_settings):
    # Create a foldr in the tmp directory
    temp_dir = Path(tempdir)
    # create a "components" folder
    temp_dir = temp_dir / "components"
    temp_dir.mkdir(exist_ok=True)

    result = runner.invoke(
        app,
        ["--components-path", str(temp_dir), *default_settings],
    )
    assert result.exit_code == 0, result.stdout
    settings_manager = utils.get_settings_manager()
    assert temp_dir in settings_manager.settings.COMPONENTS_PATH
