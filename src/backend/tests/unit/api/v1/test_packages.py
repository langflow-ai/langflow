"""Tests for the packages API endpoints."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langflow.api.v1.packages import (
    PackageInstallRequest,
    get_installation_status,
    install_package_background,
)


class TestPackageInstallRequest:
    """Test the PackageInstallRequest model."""

    def test_package_install_request_valid(self):
        """Test valid package install request."""
        request = PackageInstallRequest(package_name="requests")
        assert request.package_name == "requests"

    def test_package_install_request_empty_string(self):
        """Test package install request with empty string."""
        request = PackageInstallRequest(package_name="")
        assert request.package_name == ""

    def test_package_install_request_with_spaces(self):
        """Test package install request with spaces."""
        request = PackageInstallRequest(package_name="  numpy  ")
        assert request.package_name == "  numpy  "


class TestInstallPackageBackground:
    """Test the background package installation function."""

    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Reset global state before each test."""
        # Import and reset globals
        import langflow.api.v1.packages as pkg_module

        pkg_module._installation_in_progress = False
        pkg_module._last_installation_result = None
        yield
        # Clean up after test
        pkg_module._installation_in_progress = False
        pkg_module._last_installation_result = None

    @patch("langflow.api.v1.packages.asyncio.create_task")
    @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
    async def test_install_package_background_success(self, mock_subprocess, mock_create_task):
        """Test successful package installation."""
        # Mock successful subprocess
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(b"Successfully installed numpy", b""))
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Mock the restart task
        mock_create_task.return_value = None

        await install_package_background("numpy")

        # Verify subprocess was called correctly
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0]
        assert args == ("uv", "add", "numpy")

        # Verify global state
        import langflow.api.v1.packages as pkg_module

        assert not pkg_module._installation_in_progress
        assert pkg_module._last_installation_result["status"] == "success"
        assert pkg_module._last_installation_result["package_name"] == "numpy"

    @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
    async def test_install_package_background_failure(self, mock_subprocess):
        """Test failed package installation."""
        # Mock failed subprocess
        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"ERROR: No matching distribution found for nonexistent-package")
        )
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        await install_package_background("nonexistent-package")

        # Verify global state
        import langflow.api.v1.packages as pkg_module

        assert not pkg_module._installation_in_progress
        assert pkg_module._last_installation_result["status"] == "error"
        assert pkg_module._last_installation_result["package_name"] == "nonexistent-package"

    @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
    async def test_install_package_background_exception(self, mock_subprocess):
        """Test package installation with exception."""
        # Mock subprocess that raises an exception
        mock_subprocess.side_effect = Exception("Subprocess failed")

        await install_package_background("test-package")

        # Verify global state
        import langflow.api.v1.packages as pkg_module

        assert not pkg_module._installation_in_progress
        assert pkg_module._last_installation_result["status"] == "error"
        assert pkg_module._last_installation_result["package_name"] == "test-package"

    @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
    async def test_installation_in_progress_flag(self, mock_subprocess):
        """Test that installation_in_progress flag is properly managed."""
        # Mock a process that we can control
        mock_process = Mock()

        # Create an event to control when communicate() completes
        communicate_event = asyncio.Event()

        async def mock_communicate():
            await communicate_event.wait()
            return (b"Successfully installed test-package", b"")

        mock_process.communicate = mock_communicate
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Start installation in background without awaiting
        task = asyncio.create_task(install_package_background("test-package"))

        # Give it a moment to start
        await asyncio.sleep(0.01)

        # Installation should be in progress
        import langflow.api.v1.packages as pkg_module

        assert pkg_module._installation_in_progress

        # Allow installation to complete
        communicate_event.set()
        await task

        # Installation should be complete
        assert not pkg_module._installation_in_progress


class TestGetInstallationStatus:
    """Test the get_installation_status endpoint."""

    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Reset global state before each test."""
        import langflow.api.v1.packages as pkg_module

        pkg_module._installation_in_progress = False
        pkg_module._last_installation_result = None

    async def test_get_installation_status_no_installation(self):
        """Test getting status when no installation has occurred."""
        mock_user = Mock()

        result = await get_installation_status(mock_user)

        assert result["installation_in_progress"] is False
        assert result["last_result"] is None

    async def test_get_installation_status_in_progress(self):
        """Test getting status when installation is in progress."""
        import langflow.api.v1.packages as pkg_module

        pkg_module._installation_in_progress = True

        mock_user = Mock()

        result = await get_installation_status(mock_user)

        assert result["installation_in_progress"] is True
        assert result["last_result"] is None

    async def test_get_installation_status_with_result(self):
        """Test getting status with installation result."""
        import langflow.api.v1.packages as pkg_module

        pkg_module._last_installation_result = {
            "status": "success",
            "package_name": "requests",
            "message": "Package 'requests' installed successfully",
        }

        mock_user = Mock()

        result = await get_installation_status(mock_user)

        assert result["installation_in_progress"] is False
        assert result["last_result"]["status"] == "success"
        assert result["last_result"]["package_name"] == "requests"

    async def test_get_installation_status_with_error(self):
        """Test getting status with installation error."""
        import langflow.api.v1.packages as pkg_module

        pkg_module._last_installation_result = {
            "status": "error",
            "package_name": "nonexistent",
            "message": "Failed to install package 'nonexistent': Package not found",
        }

        mock_user = Mock()

        result = await get_installation_status(mock_user)

        assert result["installation_in_progress"] is False
        assert result["last_result"]["status"] == "error"
        assert result["last_result"]["package_name"] == "nonexistent"

    async def test_clear_installation_status(self):
        """Test clearing installation status."""
        import langflow.api.v1.packages as pkg_module
        from langflow.api.v1.packages import clear_installation_status

        # Set some state first
        pkg_module._installation_in_progress = True
        pkg_module._last_installation_result = {"status": "error", "package_name": "test", "message": "Test error"}

        mock_user = Mock()
        result = await clear_installation_status(mock_user)

        # Verify state is cleared
        assert not pkg_module._installation_in_progress
        assert pkg_module._last_installation_result is None
        assert result["message"] == "Installation status cleared"


class TestRestartApplication:
    """Test the _restart_application function."""

    @patch("langflow.api.v1.packages.os._exit")
    @patch("langflow.api.v1.packages.os.kill")
    @patch("langflow.api.v1.packages.os.getpid")
    @patch("langflow.api.v1.packages.asyncio.sleep")
    async def test_restart_application_force_exit(self, mock_sleep, mock_getpid, mock_kill, mock_exit):
        """Test application restart with force exit when all other methods fail."""
        from langflow.api.v1.packages import _restart_application

        # Mock getpid for signal handling
        mock_getpid.return_value = 12345

        # Mock signal to fail
        mock_kill.side_effect = Exception("Signal failed")

        # Mock both pathlib.Path imports to ensure all path operations fail
        with patch("pathlib.Path") as mock_pathlib_path, patch("langflow.api.v1.packages.Path") as mock_local_path:
            # Create mock files that don't exist
            mock_main_file = Mock()
            mock_main_file.exists.return_value = False
            mock_init_file = Mock()
            mock_init_file.exists.return_value = False

            # Mock the path navigation chain for both imports
            for mock_path_class in [mock_pathlib_path, mock_local_path]:
                mock_path_instance = Mock()
                mock_path_class.return_value = mock_path_instance

                # Mock the parent chain: __file__ -> parent -> parent -> parent -> / "main.py" or / "__init__.py"
                mock_parent3 = Mock()
                mock_parent3.__truediv__ = Mock(side_effect=[mock_main_file, mock_init_file])

                mock_parent2 = Mock()
                mock_parent2.parent = mock_parent3

                mock_parent1 = Mock()
                mock_parent1.parent = mock_parent2

                mock_path_instance.parent = mock_parent1

            await _restart_application()

            # Verify sleep was called for initial delay
            assert mock_sleep.call_count >= 1
            # Verify force exit was called as last resort
            mock_exit.assert_called_with(0)

    @patch("langflow.api.v1.packages.os._exit")
    @patch("langflow.api.v1.packages.asyncio.sleep")
    async def test_restart_application_calls_sleep_and_completes(self, mock_sleep):
        """Test that restart application function executes and handles completion."""
        from langflow.api.v1.packages import _restart_application

        # Mock all file operations to prevent actual file system access
        with patch("langflow.api.v1.packages.Path"):
            await _restart_application()

            # Verify sleep was called for delay
            mock_sleep.assert_called_with(2)
            # Function should complete successfully (either by touching files, signals, or exit)
            assert True  # Test passes if no exception was raised

    @patch("langflow.api.v1.packages.os._exit")
    @patch("langflow.api.v1.packages.asyncio.sleep")
    async def test_restart_application_handles_exceptions(self, mock_sleep, mock_exit):
        """Test that restart application handles exceptions gracefully."""
        from langflow.api.v1.packages import _restart_application

        # Mock the initial sleep to raise an exception
        mock_sleep.side_effect = Exception("Test exception")

        # Should not raise an exception - should exit as fallback
        await _restart_application()

        # Should call exit as emergency fallback
        mock_exit.assert_called_with(1)

    @patch("langflow.api.v1.packages.asyncio.sleep")
    async def test_restart_application_basic_execution(self, mock_sleep):
        """Test basic execution path of restart application."""
        from langflow.api.v1.packages import _restart_application

        # Mock Path to avoid file system operations
        with patch("langflow.api.v1.packages.Path"):
            await _restart_application()

            # Should call sleep for delay
            mock_sleep.assert_called_with(2)
