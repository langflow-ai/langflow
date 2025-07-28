import socket
import threading
import time
from unittest.mock import patch

import pytest
from langflow.__main__ import app
from langflow.services import deps


@pytest.fixture(scope="module")
def default_settings():
    return [
        "--backend-only",
        "--no-open-browser",
    ]


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def run_flow(runner, port, components_path, default_settings):
    args = [
        "run",
        "--port",
        str(port),
        "--components-path",
        str(components_path),
        *default_settings,
    ]
    result = runner.invoke(app, args)
    if result.exit_code != 0:
        msg = f"CLI failed with exit code {result.exit_code}: {result.output}"
        raise RuntimeError(msg)


def test_components_path(runner, default_settings, tmp_path):
    # create a "components" folder
    temp_dir = tmp_path / "components"
    temp_dir.mkdir(exist_ok=True)

    port = get_free_port()

    thread = threading.Thread(
        target=run_flow,
        args=(runner, port, temp_dir, default_settings),
        daemon=True,
    )
    thread.start()

    # Give the server some time to start
    time.sleep(5)

    settings_service = deps.get_settings_service()
    assert str(temp_dir) in settings_service.settings.components_path


def test_superuser(runner):
    result = runner.invoke(app, ["superuser"], input="admin\nadmin\n")
    assert result.exit_code == 0, result.stdout
    assert "Superuser created successfully." in result.stdout


class TestSuperuserCommand:
    """Deterministic tests for the superuser CLI command."""

    def test_additional_superuser_requires_auth_production(self, runner):
        """Test additional superuser creation requires authentication in production."""
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            # Configure settings for production mode (AUTO_LOGIN=False)
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": False, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser without auth - should fail
            result = runner.invoke(app, ["superuser"], input="newuser\nnewpass\n")

            assert result.exit_code == 1
            assert "Error: Creating a superuser requires authentication." in result.stdout
            assert "Please provide --auth-token" in result.stdout

    def test_additional_superuser_blocked_in_auto_login_mode(self, runner):
        """Test additional superuser creation blocked when AUTO_LOGIN=true."""
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            # Configure settings for AUTO_LOGIN mode
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": True, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser - should fail
            result = runner.invoke(app, ["superuser"], input="newuser\nnewpass\n")

            assert result.exit_code == 1
            assert "Error: Cannot create additional superusers when AUTO_LOGIN is enabled." in result.stdout
            assert "AUTO_LOGIN mode is for development with only the default superuser." in result.stdout

    def test_cli_disabled_blocks_creation(self, runner):
        """Test ENABLE_SUPERUSER_CLI=false blocks superuser creation."""
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": True, "ENABLE_SUPERUSER_CLI": False})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            result = runner.invoke(app, ["superuser"], input="admin\npassword\n")

            assert result.exit_code == 1
            assert "Error: Superuser creation via CLI is disabled." in result.stdout
            assert "Set LANGFLOW_ENABLE_SUPERUSER_CLI=true to enable this feature." in result.stdout

    @pytest.mark.skip(reason="Skip -- default superuser is created by initialize_services() function")
    def test_auto_login_forces_default_credentials(self, runner):
        """Test AUTO_LOGIN=true forces default credentials."""
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            # Configure settings for AUTO_LOGIN mode
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": True, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Even with custom CLI args, should use defaults in AUTO_LOGIN mode
            result = runner.invoke(app, ["superuser", "--username", "custom", "--password", "custom123"])

            assert result.exit_code == 0, f"Exit code: {result.exit_code}, Output: {result.stdout}"
            assert "AUTO_LOGIN enabled. Creating default superuser 'langflow'..." in result.stdout
            assert "Default credentials are langflow/langflow" in result.stdout


    def test_failed_auth_token_validation(self, runner):
        """Test failed superuser creation with invalid auth token."""
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            # Configure settings for production mode (AUTO_LOGIN=False)
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": False, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Tyy to create a superuser with invalid token - should fail
            result = runner.invoke(app, ["superuser", "--auth-token", "invalid-token", "--username", "newuser", "--password", "newpass"])

            assert result.exit_code == 1
            assert "Error: Invalid token or insufficient privileges. Only superusers can create other superusers." in result.stdout
