from pathlib import Path
from tempfile import tempdir
from langflow.__main__ import app
import pytest

from langflow.services import utils


@pytest.fixture(scope="module")
def default_settings():
    return [
        "--backend-only",
        "--no-open-browser",
    ]


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
