import socket
import threading
import time
from unittest.mock import patch

import pytest
import typer
from langflow.__main__ import _create_superuser, app
from lfx.services import deps


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


@pytest.mark.xdist_group(name="serial-superuser-tests")
class TestSuperuserCommand:
    """Deterministic tests for the superuser CLI command."""

    @pytest.mark.asyncio
    async def test_additional_superuser_requires_auth_production(self, client, active_super_user):  # noqa: ARG002
        """Test additional superuser creation requires authentication in production."""
        # We already have active_super_user from the fixture, so we're not in first setup
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            # Configure settings for production mode (AUTO_LOGIN=False)
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": False, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser without auth - should fail
            with pytest.raises(typer.Exit) as exc_info:
                await _create_superuser("newuser", "newpass", None)

            assert exc_info.value.exit_code == 1

    @pytest.mark.asyncio
    async def test_additional_superuser_blocked_in_auto_login_mode(self, client, active_super_user):  # noqa: ARG002
        """Test additional superuser creation blocked when AUTO_LOGIN=true."""
        # We already have active_super_user from the fixture, so we're not in first setup
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            # Configure settings for AUTO_LOGIN mode
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": True, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser - should fail
            with pytest.raises(typer.Exit) as exc_info:
                await _create_superuser("newuser", "newpass", None)

            assert exc_info.value.exit_code == 1

    @pytest.mark.asyncio
    async def test_cli_disabled_blocks_creation(self, client):  # noqa: ARG002
        """Test ENABLE_SUPERUSER_CLI=false blocks superuser creation."""
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": True, "ENABLE_SUPERUSER_CLI": False})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser - should fail
            with pytest.raises(typer.Exit) as exc_info:
                await _create_superuser("admin", "password", None)

            assert exc_info.value.exit_code == 1

    @pytest.mark.skip(reason="Skip -- default superuser is created by initialize_services() function")
    @pytest.mark.asyncio
    async def test_auto_login_forces_default_credentials(self, client):
        """Test AUTO_LOGIN=true forces default credentials."""
        # Since client fixture already creates default user, we need to test in a clean DB scenario
        # But that's why this test is skipped - the behavior is already handled by initialize_services

    @pytest.mark.asyncio
    async def test_failed_auth_token_validation(self, client, active_super_user):  # noqa: ARG002
        """Test failed superuser creation with invalid auth token."""
        # We already have active_super_user from the fixture, so we're not in first setup
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
            patch("langflow.__main__.get_current_user_by_jwt", side_effect=Exception("Invalid token")),
            patch("langflow.__main__.check_key", return_value=None),
        ):
            # Configure settings for production mode (AUTO_LOGIN=False)
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": False, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser with invalid token - should fail
            with pytest.raises(typer.Exit) as exc_info:
                await _create_superuser("newuser", "newpass", "invalid-token")

            assert exc_info.value.exit_code == 1
