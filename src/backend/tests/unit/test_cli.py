import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import typer
from langflow.__main__ import _create_superuser, api_key_banner, app, get_number_of_workers
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
            patch("langflow.__main__.get_current_user_from_access_token", side_effect=Exception("Invalid token")),
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


class TestApiKeyBanner:
    """Tests for api_key_banner clipboard fallback (headless environments)."""

    def _make_key(self, value: str = "sk-test-1234"):
        mock = MagicMock()
        mock.api_key = value
        return mock

    def test_clipboard_available_copies_key(self):
        """When pyperclip works, key is copied and clipboard hint is shown."""
        key = self._make_key()
        with (
            patch("pyperclip.copy") as mock_copy,
            patch("langflow.__main__.Console") as mock_console_cls,
        ):
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            api_key_banner(key)

            mock_copy.assert_called_once_with(key.api_key)
            printed = mock_console.print.call_args[0][0]
            assert "clipboard" in str(printed).lower()
            assert key.api_key in str(printed)

    def test_clipboard_unavailable_still_prints_key(self):
        """When pyperclip raises (headless/Docker), key is still displayed on stdout."""
        key = self._make_key()
        with (
            patch("pyperclip.copy", side_effect=Exception("No clipboard mechanism")),
            patch("langflow.__main__.Console") as mock_console_cls,
        ):
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            # Must NOT raise
            api_key_banner(key)

            mock_console.print.assert_called_once()
            printed = mock_console.print.call_args[0][0]
            assert key.api_key in str(printed)

    def test_clipboard_unavailable_shows_fallback_hint(self):
        """When clipboard is unavailable, hint text must not mention clipboard."""
        key = self._make_key()
        with (
            patch("pyperclip.copy", side_effect=Exception("No clipboard mechanism")),
            patch("langflow.__main__.Console") as mock_console_cls,
        ):
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            api_key_banner(key)

            printed = str(mock_console.print.call_args[0][0])
            assert "clipboard" not in printed.lower()
            assert "securely" in printed.lower()

    def test_unicode_error_fallback_with_clipboard(self):
        """On UnicodeEncodeError, logger fallback includes clipboard message when available."""
        key = self._make_key()
        with (
            patch("pyperclip.copy"),
            patch("langflow.__main__.Console") as mock_console_cls,
            patch("langflow.__main__.logger") as mock_logger,
        ):
            mock_console = MagicMock()
            mock_console.print.side_effect = UnicodeEncodeError("utf-8", b"", 0, 1, "reason")
            mock_console_cls.return_value = mock_console

            api_key_banner(key)

            logged_messages = " ".join(str(c) for c in mock_logger.info.call_args_list)
            assert key.api_key in logged_messages
            assert "clipboard" in logged_messages.lower()

    def test_unicode_error_fallback_without_clipboard(self):
        """On UnicodeEncodeError, logger fallback omits clipboard message when unavailable."""
        key = self._make_key()
        with (
            patch("pyperclip.copy", side_effect=Exception("No clipboard mechanism")),
            patch("langflow.__main__.Console") as mock_console_cls,
            patch("langflow.__main__.logger") as mock_logger,
        ):
            mock_console = MagicMock()
            mock_console.print.side_effect = UnicodeEncodeError("utf-8", b"", 0, 1, "reason")
            mock_console_cls.return_value = mock_console

            api_key_banner(key)

            logged_messages = " ".join(str(c) for c in mock_logger.info.call_args_list)
            assert key.api_key in logged_messages
            assert "clipboard" not in logged_messages.lower()


def test_get_number_of_workers():
    """Test that get_number_of_workers uses cpu_count on Linux."""
    with (
        patch("langflow.__main__.platform.system", return_value="Linux"),
        patch("langflow.__main__.cpu_count", return_value=4),
    ):
        # Test default behavior (None)
        workers = get_number_of_workers(None)
        assert workers == (4 * 2) + 1  # 9 workers

        # Test explicit value is respected
        workers = get_number_of_workers(2)
        assert workers == 2
