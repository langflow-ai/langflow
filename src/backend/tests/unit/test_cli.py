from pathlib import Path
from tempfile import tempdir

import pytest
from langflow.__main__ import app
from langflow.services import deps


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
    settings_service = deps.get_settings_service()
    assert str(temp_dir) in settings_service.settings.components_path


def test_superuser(runner, client, session):
    result = runner.invoke(app, ["superuser"], input="admin\nadmin\n")
    assert result.exit_code == 0, result.stdout
    assert "Superuser created successfully." in result.stdout
