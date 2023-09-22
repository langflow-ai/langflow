from pathlib import Path
from tempfile import tempdir
from langflow.__main__ import app
import pytest

from langflow.services import getters


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
        ["run", "--components-path", str(temp_dir), *default_settings],
    )
    assert result.exit_code == 0, result.stdout
    settings_service = getters.get_settings_service()
    assert str(temp_dir) in settings_service.settings.COMPONENTS_PATH


def test_superuser(runner, client, session):
    result = runner.invoke(app, ["superuser"], input="admin\nadmin\n")
    assert result.exit_code == 0, result.stdout
    assert "Superuser created successfully." in result.stdout
