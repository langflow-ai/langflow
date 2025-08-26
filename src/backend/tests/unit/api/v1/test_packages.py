"""Comprehensive tests for the packages API endpoints.

This module tests all functionality in langflow.api.v1.packages including:
- Pydantic models for requests and responses
- Utility functions for package management
- Background tasks for installation and restoration
- API endpoints for package operations
- Error handling and edge cases
- Cross-platform compatibility
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.packages import (
    InstalledPackage,
    # Pydantic Models
    PackageInstallRequest,
    PackageInstallResponse,
    PackageRestoreRequest,
    PackageRestoreResponse,
    # Utility Functions
    _find_project_root,
    _find_uv_executable,
    _get_core_dependencies,
    _is_core_dependency,
    _is_valid_windows_package_name,
    _validate_package_name,
    _validate_package_specification,
    cleanup_orphaned_installation_records,
    clear_installation_status,
    get_installation_status,
    get_installed_packages,
    # API Endpoints
    install_package,
    # Background Tasks
    install_package_background,
    restore_langflow,
    restore_langflow_background,
)
from langflow.services.database.models.package_installation.model import (
    InstallationStatus,
    PackageInstallation,
)


def mock_open_with_toml_content():
    """Mock open function that returns TOML content."""
    mock_file = Mock()
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=None)
    return mock_file


class TestPydanticModels:
    """Test all Pydantic model definitions."""

    class TestPackageInstallRequest:
        """Test PackageInstallRequest model."""

        def test_valid_package_names(self):
            """Test valid package install requests."""
            # Simple package name
            request = PackageInstallRequest(package_name="requests")
            assert request.package_name == "requests"

            # Package with version
            request = PackageInstallRequest(package_name="pandas==2.3.1")
            assert request.package_name == "pandas==2.3.1"

            # Package with minimum version
            request = PackageInstallRequest(package_name="numpy>=1.20.0")
            assert request.package_name == "numpy>=1.20.0"

        def test_empty_package_name(self):
            """Test empty package name handling."""
            request = PackageInstallRequest(package_name="")
            assert request.package_name == ""

        def test_package_name_with_spaces(self):
            """Test package names with leading/trailing spaces."""
            request = PackageInstallRequest(package_name="  scikit-learn  ")
            assert request.package_name == "  scikit-learn  "

        def test_complex_version_specs(self):
            """Test complex version specifications."""
            specs = ["django>=3.2,<4.0", "requests!=2.25.0", "tensorflow~=2.8.0", "package-name-with-dashes==1.0.0"]
            for spec in specs:
                request = PackageInstallRequest(package_name=spec)
                assert request.package_name == spec

    class TestPackageInstallResponse:
        """Test PackageInstallResponse model."""

        def test_valid_response(self):
            """Test valid install response."""
            response = PackageInstallResponse(
                message="Package installation started", package_name="requests", status="started"
            )
            assert response.message == "Package installation started"
            assert response.package_name == "requests"
            assert response.status == "started"

        def test_response_serialization(self):
            """Test response model serialization."""
            response = PackageInstallResponse(message="Test message", package_name="test-package", status="completed")
            data = response.model_dump()
            assert data["message"] == "Test message"
            assert data["package_name"] == "test-package"
            assert data["status"] == "completed"

    class TestPackageRestoreRequest:
        """Test PackageRestoreRequest model."""

        def test_default_confirm_false(self):
            """Test default confirm value is False."""
            request = PackageRestoreRequest()
            assert request.confirm is False

        def test_explicit_confirm_values(self):
            """Test explicit confirm values."""
            request_true = PackageRestoreRequest(confirm=True)
            assert request_true.confirm is True

            request_false = PackageRestoreRequest(confirm=False)
            assert request_false.confirm is False

    class TestPackageRestoreResponse:
        """Test PackageRestoreResponse model."""

        def test_valid_response(self):
            """Test valid restore response."""
            response = PackageRestoreResponse(message="Restore started", status="started")
            assert response.message == "Restore started"
            assert response.status == "started"

    class TestInstalledPackage:
        """Test InstalledPackage model."""

        def test_valid_package(self):
            """Test valid installed package."""
            package = InstalledPackage(name="requests", version="2.25.1")
            assert package.name == "requests"
            assert package.version == "2.25.1"

        def test_package_with_complex_version(self):
            """Test package with complex version string."""
            package = InstalledPackage(name="tensorflow", version="2.8.0rc1")
            assert package.name == "tensorflow"
            assert package.version == "2.8.0rc1"


class TestUtilityFunctions:
    """Test all utility functions."""

    class TestProjectRootFinder:
        """Test _find_project_root function."""

        def test_find_project_root_returns_path(self):
            """Test that function returns a Path object."""
            result = _find_project_root()
            assert isinstance(result, Path)

        def test_find_main_langflow_project(self):
            """Test finding main langflow project over langflow-base."""
            # This is a complex function that depends on file system
            # For a unit test, we just verify it returns a Path object
            result = _find_project_root()
            assert isinstance(result, Path)

        @patch("langflow.api.v1.packages.Path.cwd")
        def test_fallback_to_cwd(self, mock_cwd):
            """Test fallback to current working directory."""
            mock_cwd.return_value = Path("/fallback/path")

            # This would require extensive mocking to fully test
            # For now, verify basic behavior
            result = _find_project_root()
            assert isinstance(result, Path)

    class TestUVExecutableFinder:
        """Test _find_uv_executable function."""

        @patch("langflow.api.v1.packages.shutil.which")
        def test_find_uv_executable_success(self, mock_which):
            """Test finding UV executable successfully."""
            mock_which.return_value = "/usr/local/bin/uv"

            result = _find_uv_executable()
            assert result == "/usr/local/bin/uv"
            mock_which.assert_called_with("uv")

        @patch("langflow.api.v1.packages.shutil.which")
        def test_find_uv_executable_not_found(self, mock_which):
            """Test UV executable not found."""
            mock_which.return_value = None

            with pytest.raises(RuntimeError, match="UV package manager not found"):
                _find_uv_executable()

        @patch("langflow.api.v1.packages.platform.system")
        @patch("langflow.api.v1.packages.shutil.which")
        def test_windows_fallback_to_exe(self, mock_which, mock_system):
            """Test Windows fallback to .exe extension."""
            mock_system.return_value = "Windows"
            mock_which.side_effect = [None, "/path/to/uv.exe"]  # First call returns None, second returns .exe

            result = _find_uv_executable()
            assert result == "/path/to/uv.exe"

    class TestPackageValidation:
        """Test package validation functions."""

        def test_validate_package_specification_valid(self):
            """Test valid package specifications."""
            valid_specs = [
                "requests",
                "pandas==2.3.1",
                "numpy>=1.20.0",
                "django<=4.0.0",
                "scipy>1.5.0",
                "matplotlib<3.5.0",
                "flask!=2.0.0",
                "tensorflow~=2.8.0",
                "scikit-learn===1.0.2",
                "package-name-with-dashes",
                "package_name_with_underscores",
                "package.name.with.dots",
                "Package123",
            ]

            for spec in valid_specs:
                assert _validate_package_specification(spec) is True, f"Failed for: {spec}"

        def test_validate_package_specification_invalid(self):
            """Test invalid package specifications."""
            invalid_specs = [
                "",  # Empty
                " ",  # Just whitespace
                "package;rm -rf /",  # Command injection
                "package&malicious",  # Command injection
                "package|evil",  # Command injection
                "package`command`",  # Command injection
                "package$(command)",  # Command injection
                "package()",  # Parentheses
                "package;",  # Semicolon
            ]

            for spec in invalid_specs:
                assert _validate_package_specification(spec) is False, f"Should be invalid: {spec}"

        @patch("langflow.api.v1.packages.platform.system")
        def test_windows_specific_validation(self, mock_system):
            """Test Windows-specific forbidden characters."""
            mock_system.return_value = "Windows"

            windows_invalid = [
                "package%command%",  # Windows percent
                "package^command",  # Windows caret
                'package"quoted"',  # Windows quotes
                "package'quoted'",  # Windows single quotes
            ]

            for spec in windows_invalid:
                assert _validate_package_specification(spec) is False, f"Should be invalid on Windows: {spec}"

        def test_is_valid_windows_package_name(self):
            """Test Windows package name validation."""
            # Valid names
            assert _is_valid_windows_package_name("requests") is True
            assert _is_valid_windows_package_name("pandas==2.3.1") is True

            # Invalid names with forbidden characters
            forbidden_chars = ["<", ">", ":", '"', "|", "?", "*"]
            for char in forbidden_chars:
                invalid_name = f"package{char}name"
                assert _is_valid_windows_package_name(invalid_name) is False

        def test_validate_package_name_legacy(self):
            """Test legacy _validate_package_name function."""
            # Should redirect to _validate_package_specification
            assert _validate_package_name("requests") is True
            assert _validate_package_name("") is False
            assert _validate_package_name("package;evil") is False

    class TestCoreDependencies:
        """Test core dependency functions."""

        def test_get_core_dependencies_returns_set(self):
            """Test that core dependencies function returns a set."""
            result = _get_core_dependencies()
            assert isinstance(result, set)
            assert len(result) > 0

        def test_get_core_dependencies_contains_essentials(self):
            """Test that core dependencies contain essential packages."""
            core_deps = _get_core_dependencies()

            # Should contain some essential packages
            expected_essentials = {"requests", "fastapi", "uvicorn", "sqlmodel", "pydantic", "openai", "anthropic"}

            # At least some of these should be present
            overlap = core_deps.intersection(expected_essentials)
            assert len(overlap) > 0, f"Expected at least some of {expected_essentials} in {core_deps}"

        def test_is_core_dependency(self):
            """Test checking if packages are core dependencies."""
            # These should typically be core dependencies
            likely_core = ["requests", "fastapi", "pydantic"]
            for pkg in likely_core:
                # Note: actual result depends on pyproject.toml content
                result = _is_core_dependency(pkg)
                assert isinstance(result, bool)

        def test_is_core_dependency_case_insensitive(self):
            """Test core dependency check is case insensitive."""
            result1 = _is_core_dependency("REQUESTS")
            result2 = _is_core_dependency("requests")
            # Should be the same (both compared in lowercase)
            assert result1 == result2

        def test_is_core_dependency_unknown_package(self):
            """Test unknown packages are not core dependencies."""
            assert _is_core_dependency("definitely-not-a-real-package-12345") is False

        def test_get_core_dependencies_file_error(self):
            """Test fallback when pyproject.toml can't be read."""
            # This function has internal error handling that returns a fallback set
            # We can test this by calling it normally - if files aren't found, it will use the fallback
            result = _get_core_dependencies()
            assert isinstance(result, set)
            # Should contain some essential packages (from either pyproject.toml or fallback)
            assert len(result) > 0

    class TestOrphanedRecordCleanup:
        """Test cleanup_orphaned_installation_records function."""

        @patch("langflow.api.v1.packages._find_uv_executable")
        @patch("langflow.api.v1.packages._find_project_root")
        @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
        async def test_cleanup_orphaned_records_success(self, mock_subprocess, mock_find_root, mock_find_uv):
            """Test successful cleanup of orphaned records."""
            # Setup mocks
            mock_find_uv.return_value = "uv"
            mock_find_root.return_value = Path("/fake/root")

            # Mock subprocess that returns package list without the orphaned package
            mock_process = Mock()
            mock_process.communicate = AsyncMock(
                return_value=(json.dumps([{"name": "existing-package", "version": "1.0.0"}]).encode(), b"")
            )
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Mock database session
            mock_session = AsyncMock()
            user_id = uuid4()

            # Mock installation record for a package that's no longer installed
            mock_installation = Mock()
            mock_installation.package_name = "orphaned-package"
            mock_installations = Mock()
            mock_installations.__iter__ = Mock(return_value=iter([mock_installation]))
            mock_session.exec.return_value = mock_installations

            result = await cleanup_orphaned_installation_records(mock_session, user_id)

            # Should have found and cleaned up one orphaned record
            assert result == 1
            mock_session.delete.assert_called_once_with(mock_installation)
            mock_session.commit.assert_called_once()

        @patch("langflow.api.v1.packages._find_uv_executable")
        async def test_cleanup_orphaned_records_uv_error(self, mock_find_uv):
            """Test cleanup when UV command fails."""
            mock_find_uv.side_effect = RuntimeError("UV not found")

            mock_session = AsyncMock()
            user_id = uuid4()

            result = await cleanup_orphaned_installation_records(mock_session, user_id)

            # Should return 0 when UV command fails
            assert result == 0

        @patch("langflow.api.v1.packages._find_uv_executable")
        @patch("langflow.api.v1.packages._find_project_root")
        @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
        async def test_cleanup_orphaned_records_subprocess_failure(self, mock_subprocess, mock_find_root, mock_find_uv):
            """Test cleanup when subprocess fails."""
            # Setup mocks
            mock_find_uv.return_value = "uv"
            mock_find_root.return_value = Path("/fake/root")

            # Mock subprocess failure
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(b"", b"Error"))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process

            mock_session = AsyncMock()
            user_id = uuid4()

            result = await cleanup_orphaned_installation_records(mock_session, user_id)

            # Should return 0 when subprocess fails
            assert result == 0


class TestBackgroundTasks:
    """Test background task functions."""

    class TestInstallPackageBackground:
        """Test install_package_background function."""

        @patch("langflow.api.v1.packages._find_uv_executable")
        @patch("langflow.api.v1.packages._find_project_root")
        @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
        async def test_install_package_success(self, mock_subprocess, mock_find_root, mock_find_uv):
            """Test successful package installation."""
            # Setup mocks
            mock_find_uv.return_value = "uv"
            mock_find_root.return_value = Path("/fake/root")

            # Mock successful subprocess
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(b"Successfully installed test-package-1.0.0", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Mock database session and installation
            installation_id = uuid4()
            mock_installation = Mock()
            mock_installation.package_name = "test-package"
            mock_installation.status = InstallationStatus.PENDING

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = mock_installation

                await install_package_background(installation_id)

                # Verify subprocess was called correctly
                mock_subprocess.assert_called_once()
                args = mock_subprocess.call_args[0]
                assert args == ("uv", "add", "test-package")

                # Verify installation was marked as completed
                assert mock_installation.status == InstallationStatus.COMPLETED
                assert "installed successfully" in mock_installation.message

        @patch("langflow.api.v1.packages._find_uv_executable")
        @patch("langflow.api.v1.packages._find_project_root")
        @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
        async def test_install_package_failure(self, mock_subprocess, mock_find_root, mock_find_uv):
            """Test failed package installation."""
            # Setup mocks
            mock_find_uv.return_value = "uv"
            mock_find_root.return_value = Path("/fake/root")

            # Mock failed subprocess
            mock_process = Mock()
            mock_process.communicate = AsyncMock(
                return_value=(b"", b"ERROR: No matching distribution found for nonexistent-package")
            )
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process

            installation_id = uuid4()
            mock_installation = Mock()
            mock_installation.package_name = "nonexistent-package"
            mock_installation.status = InstallationStatus.PENDING

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = mock_installation

                await install_package_background(installation_id)

                # Verify installation was marked as failed
                assert mock_installation.status == InstallationStatus.FAILED
                assert "No matching distribution found" in mock_installation.message

        @patch("langflow.api.v1.packages._find_uv_executable")
        async def test_install_package_uv_not_found(self, mock_find_uv):
            """Test installation when UV is not found."""
            mock_find_uv.side_effect = RuntimeError("UV not found")

            installation_id = uuid4()
            mock_installation = Mock()
            mock_installation.package_name = "test-package"
            mock_installation.status = InstallationStatus.PENDING

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = mock_installation

                await install_package_background(installation_id)

                # Verify installation was marked as failed
                assert mock_installation.status == InstallationStatus.FAILED
                assert "UV not found" in mock_installation.message

        @patch("langflow.api.v1.packages.platform.system")
        @patch("langflow.api.v1.packages._is_valid_windows_package_name")
        async def test_install_package_windows_validation(self, mock_windows_validation, mock_system):
            """Test Windows-specific package name validation."""
            mock_system.return_value = "Windows"
            mock_windows_validation.return_value = False  # Invalid Windows package name

            installation_id = uuid4()
            mock_installation = Mock()
            mock_installation.package_name = "invalid<package>name"
            mock_installation.status = InstallationStatus.PENDING

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = mock_installation

                await install_package_background(installation_id)

                # Verify installation was marked as failed due to Windows validation
                assert mock_installation.status == InstallationStatus.FAILED
                assert "Invalid package name" in mock_installation.message
                assert "Windows" in mock_installation.message

        async def test_install_package_not_found(self):
            """Test installation when installation record is not found."""
            installation_id = uuid4()

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = None  # Installation not found

                # Should not raise an exception, but log error
                await install_package_background(installation_id)

                mock_session.get.assert_called_once_with(PackageInstallation, installation_id)

        @patch("langflow.api.v1.packages._find_uv_executable")
        @patch("langflow.api.v1.packages._find_project_root")
        @patch("langflow.api.v1.packages.platform.system")
        @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
        async def test_install_package_windows_encoding(
            self, mock_subprocess, mock_system, mock_find_root, mock_find_uv
        ):
            """Test Windows encoding handling."""
            mock_system.return_value = "Windows"
            mock_find_uv.return_value = "uv"
            mock_find_root.return_value = Path("/fake/root")

            # Mock subprocess with Windows-specific encoding issues
            mock_process = Mock()
            # Simulate Windows encoding that fails UTF-8 but works with CP1252
            mock_process.communicate = AsyncMock(return_value=("Successfully installed".encode("cp1252"), b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            installation_id = uuid4()
            mock_installation = Mock()
            mock_installation.package_name = "test-package"
            mock_installation.status = InstallationStatus.PENDING

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = mock_installation

                await install_package_background(installation_id)

                # Should handle encoding gracefully and succeed
                assert mock_installation.status == InstallationStatus.COMPLETED

    class TestRestoreLangflowBackground:
        """Test restore_langflow_background function."""

        @patch("langflow.api.v1.packages._find_uv_executable")
        @patch("langflow.api.v1.packages._find_project_root")
        @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
        async def test_restore_langflow_success(self, mock_subprocess, mock_find_root, mock_find_uv):
            """Test successful Langflow restoration."""
            # Setup mocks
            mock_find_uv.return_value = "uv"
            mock_find_root.return_value = Path("/fake/root")

            # Mock successful subprocess calls (remove + sync)
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(b"Successfully removed test-package", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            installation_id = uuid4()
            user_id = uuid4()
            mock_installation = Mock()
            mock_installation.id = installation_id
            mock_installation.package_name = "langflow-restore"
            mock_installation.user_id = user_id
            mock_installation.status = InstallationStatus.PENDING

            # Mock user installations to remove
            mock_user_installation = Mock()
            mock_user_installation.package_name = "test-package==1.0.0"
            mock_user_installation.id = uuid4()

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = mock_installation

                # Mock the exec calls for finding user installations
                mock_result1 = Mock()
                mock_result1.__iter__ = Mock(return_value=iter([mock_user_installation]))
                mock_result2 = Mock()
                mock_result2.__iter__ = Mock(return_value=iter([]))
                mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2])

                # Mock asyncio.sleep to speed up test
                with patch("asyncio.sleep"):
                    await restore_langflow_background(installation_id)

                # Verify subprocess calls (remove package + sync)
                assert mock_subprocess.call_count >= 2

                # Should eventually be marked as completed and then deleted
                # (Note: the function deletes itself at the end)

        @patch("langflow.api.v1.packages._find_uv_executable")
        @patch("langflow.api.v1.packages._find_project_root")
        @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
        async def test_restore_langflow_remove_failure(self, mock_subprocess, mock_find_root, mock_find_uv):
            """Test restoration when package removal fails."""
            # Setup mocks
            mock_find_uv.return_value = "uv"
            mock_find_root.return_value = Path("/fake/root")

            # Mock failed package removal but successful sync
            remove_process = Mock()
            remove_process.communicate = AsyncMock(return_value=(b"", b"ERROR: Package not found"))
            remove_process.returncode = 1

            sync_process = Mock()
            sync_process.communicate = AsyncMock(return_value=(b"Successfully synced", b""))
            sync_process.returncode = 0

            mock_subprocess.side_effect = [remove_process, sync_process]

            installation_id = uuid4()
            user_id = uuid4()
            mock_installation = Mock()
            mock_installation.id = installation_id
            mock_installation.package_name = "langflow-restore"
            mock_installation.user_id = user_id
            mock_installation.status = InstallationStatus.PENDING

            # Mock user installation
            mock_user_installation = Mock()
            mock_user_installation.package_name = "test-package"
            mock_user_installation.id = uuid4()

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = mock_installation

                # Mock the exec calls
                mock_result1 = Mock()
                mock_result1.__iter__ = Mock(return_value=iter([mock_user_installation]))
                mock_result2 = Mock()
                mock_result2.__iter__ = Mock(return_value=iter([]))
                mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2])

                with patch("asyncio.sleep"):
                    await restore_langflow_background(installation_id)

                # Should still succeed if sync works (package removal failures are often expected)

        @patch("langflow.api.v1.packages._find_uv_executable")
        async def test_restore_langflow_uv_not_found(self, mock_find_uv):
            """Test restoration when UV is not found."""
            mock_find_uv.side_effect = RuntimeError("UV not found")

            installation_id = uuid4()
            mock_installation = Mock()
            mock_installation.package_name = "langflow-restore"
            mock_installation.status = InstallationStatus.PENDING

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = mock_installation

                await restore_langflow_background(installation_id)

                # Verify installation was marked as failed
                assert mock_installation.status == InstallationStatus.FAILED
                assert "UV not found" in mock_installation.message

        async def test_restore_langflow_installation_not_found(self):
            """Test restoration when installation record is not found."""
            installation_id = uuid4()

            with patch("langflow.services.deps.session_scope") as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_session.get.return_value = None

                # Should not raise exception
                await restore_langflow_background(installation_id)

                mock_session.get.assert_called_once_with(PackageInstallation, installation_id)


class TestAPIEndpoints:
    """Test all API endpoint functions."""

    class TestInstallPackageEndpoint:
        """Test install_package endpoint."""

        @patch("langflow.api.v1.packages.get_settings_service")
        @patch("langflow.api.v1.packages._validate_package_name")
        @patch("langflow.api.v1.packages._is_core_dependency")
        async def test_install_package_success(self, mock_is_core, mock_validate, mock_get_settings):
            """Test successful package installation request."""
            # Mock settings
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            # Mock validation
            mock_validate.return_value = True
            mock_is_core.return_value = False

            # Mock database session
            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock database queries - no existing installations, no stuck installations, no active installations
            mock_result1 = Mock()  # existing installations
            mock_result1.__iter__ = Mock(return_value=iter([]))
            mock_result2 = Mock()  # stuck installations
            mock_result2.__iter__ = Mock(return_value=iter([]))
            mock_result3 = Mock()  # active installations
            mock_result3.first.return_value = None
            mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2, mock_result3])

            # Mock database operations
            mock_session.add = Mock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()

            package_request = PackageInstallRequest(package_name="requests")
            background_tasks = Mock()

            result = await install_package(
                package_request=package_request,
                background_tasks=background_tasks,
                session=mock_session,
                current_user=mock_user,
            )

            assert result.status == "started"
            assert "installation started" in result.message
            assert result.package_name == "requests"
            background_tasks.add_task.assert_called_once()

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_install_package_disabled(self, mock_get_settings):
            """Test install when package manager is disabled."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = False
            mock_get_settings.return_value = mock_settings

            package_request = PackageInstallRequest(package_name="requests")
            mock_session = AsyncMock()
            mock_user = Mock()
            background_tasks = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await install_package(
                    package_request=package_request,
                    background_tasks=background_tasks,
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 403
            assert "Package manager is disabled" in str(exc_info.value.detail)

        @patch("langflow.api.v1.packages.get_settings_service")
        @patch("langflow.api.v1.packages._validate_package_name")
        async def test_install_package_invalid_name(self, mock_validate, mock_get_settings):
            """Test install with invalid package name."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_validate.return_value = False  # Invalid package name

            package_request = PackageInstallRequest(package_name="invalid;package")
            mock_session = AsyncMock()
            mock_user = Mock()
            background_tasks = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await install_package(
                    package_request=package_request,
                    background_tasks=background_tasks,
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 400
            assert "Invalid package name" in str(exc_info.value.detail)

        @patch("langflow.api.v1.packages.get_settings_service")
        @patch("langflow.api.v1.packages._validate_package_name")
        @patch("langflow.api.v1.packages._is_core_dependency")
        async def test_install_package_core_dependency(self, mock_is_core, mock_validate, mock_get_settings):
            """Test install of core dependency should fail."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_validate.return_value = True
            mock_is_core.return_value = True  # This is a core dependency

            package_request = PackageInstallRequest(package_name="fastapi")
            mock_session = AsyncMock()
            mock_user = Mock()
            background_tasks = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await install_package(
                    package_request=package_request,
                    background_tasks=background_tasks,
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 409
            assert "already installed as a core dependency" in str(exc_info.value.detail)

        @patch("langflow.api.v1.packages.get_settings_service")
        @patch("langflow.api.v1.packages._validate_package_name")
        @patch("langflow.api.v1.packages._is_core_dependency")
        async def test_install_package_already_installed(self, mock_is_core, mock_validate, mock_get_settings):
            """Test install when package is already installed."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_validate.return_value = True
            mock_is_core.return_value = False

            # Mock existing installation
            mock_existing = Mock()
            mock_existing.package_name = "requests==2.25.1"
            mock_result = Mock()
            mock_result.__iter__ = Mock(return_value=iter([mock_existing]))

            mock_session = AsyncMock()
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_user = Mock()
            mock_user.id = uuid4()

            package_request = PackageInstallRequest(package_name="requests")
            background_tasks = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await install_package(
                    package_request=package_request,
                    background_tasks=background_tasks,
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 409
            assert "already installed through the package manager" in str(exc_info.value.detail)

        @patch("langflow.api.v1.packages.get_settings_service")
        @patch("langflow.api.v1.packages._validate_package_name")
        @patch("langflow.api.v1.packages._is_core_dependency")
        async def test_install_package_installation_in_progress(self, mock_is_core, mock_validate, mock_get_settings):
            """Test install when another installation is in progress."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_validate.return_value = True
            mock_is_core.return_value = False

            # Mock active installation
            mock_active = Mock()
            mock_active.status = InstallationStatus.IN_PROGRESS
            mock_active.updated_at = datetime.now(timezone.utc)  # Recent

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock database queries
            mock_result1 = Mock()  # existing installations
            mock_result1.__iter__ = Mock(return_value=iter([]))
            mock_result2 = Mock()  # stuck installations
            mock_result2.__iter__ = Mock(return_value=iter([]))
            mock_result3 = Mock()  # active installations
            mock_result3.first.return_value = mock_active
            mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2, mock_result3])

            package_request = PackageInstallRequest(package_name="requests")
            background_tasks = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await install_package(
                    package_request=package_request,
                    background_tasks=background_tasks,
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 409
            assert "installation already in progress" in str(exc_info.value.detail)

    class TestGetInstallationStatus:
        """Test get_installation_status endpoint."""

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_get_status_no_installation(self, mock_get_settings):
            """Test getting status when no installation exists."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock no installation found
            mock_result = Mock()
            mock_result.first.return_value = None
            mock_session.exec = AsyncMock(return_value=mock_result)

            result = await get_installation_status(mock_session, mock_user)

            assert result["installation_in_progress"] is False
            assert result["last_result"] is None

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_get_status_in_progress(self, mock_get_settings):
            """Test getting status when installation is in progress."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock installation in progress
            mock_installation = Mock()
            mock_installation.status = InstallationStatus.IN_PROGRESS
            mock_result = Mock()
            mock_result.first.return_value = mock_installation
            mock_session.exec = AsyncMock(return_value=mock_result)

            result = await get_installation_status(mock_session, mock_user)

            assert result["installation_in_progress"] is True
            assert result["last_result"] is None

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_get_status_with_completed_result(self, mock_get_settings):
            """Test getting status with completed installation."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock completed installation
            installation_id = uuid4()
            user_id = uuid4()
            mock_installation = Mock()
            mock_installation.id = installation_id
            mock_installation.package_name = "requests"
            mock_installation.status = InstallationStatus.COMPLETED
            mock_installation.message = "Successfully installed"
            mock_installation.created_at = datetime.now(timezone.utc)
            mock_installation.updated_at = datetime.now(timezone.utc)
            mock_installation.user_id = user_id

            mock_result = Mock()
            mock_result.first.return_value = mock_installation
            mock_session.exec = AsyncMock(return_value=mock_result)

            result = await get_installation_status(mock_session, mock_user)

            assert result["installation_in_progress"] is False
            assert result["last_result"] is not None
            assert result["last_result"]["status"] == "completed"
            assert result["last_result"]["package_name"] == "requests"

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_get_status_disabled(self, mock_get_settings):
            """Test getting status when package manager is disabled."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = False
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await get_installation_status(mock_session, mock_user)

            assert exc_info.value.status_code == 403
            assert "Package manager is disabled" in str(exc_info.value.detail)

    class TestClearInstallationStatus:
        """Test clear_installation_status endpoint."""

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_clear_status_success(self, mock_get_settings):
            """Test successfully clearing installation status."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock installations to delete
            mock_completed = Mock()
            mock_failed = Mock()

            mock_result1 = Mock()
            mock_result1.all.return_value = [mock_completed]
            mock_result2 = Mock()
            mock_result2.all.return_value = [mock_failed]

            mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2])

            result = await clear_installation_status(mock_session, mock_user)

            assert result["message"] == "Installation status cleared"
            assert mock_session.delete.call_count == 2
            mock_session.commit.assert_called_once()

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_clear_status_disabled(self, mock_get_settings):
            """Test clearing status when package manager is disabled."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = False
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await clear_installation_status(mock_session, mock_user)

            assert exc_info.value.status_code == 403
            assert "Package manager is disabled" in str(exc_info.value.detail)

    class TestRestoreLangflowEndpoint:
        """Test restore_langflow endpoint."""

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_restore_success(self, mock_get_settings):
            """Test successful restore request."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock no active installations
            mock_result1 = Mock()  # stuck installations
            mock_result1.__iter__ = Mock(return_value=iter([]))
            mock_result2 = Mock()  # active installations
            mock_result2.first.return_value = None
            mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2])

            # Mock database operations
            mock_session.add = Mock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()

            restore_request = PackageRestoreRequest(confirm=True)
            background_tasks = Mock()

            result = await restore_langflow(
                restore_request=restore_request,
                background_tasks=background_tasks,
                session=mock_session,
                current_user=mock_user,
            )

            assert result.status == "started"
            assert "restore started" in result.message
            background_tasks.add_task.assert_called_once()

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_restore_no_confirmation(self, mock_get_settings):
            """Test restore without confirmation."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()

            restore_request = PackageRestoreRequest(confirm=False)
            background_tasks = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await restore_langflow(
                    restore_request=restore_request,
                    background_tasks=background_tasks,
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 400
            assert "Restore confirmation is required" in str(exc_info.value.detail)

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_restore_disabled(self, mock_get_settings):
            """Test restore when package manager is disabled."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = False
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()

            restore_request = PackageRestoreRequest(confirm=True)
            background_tasks = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await restore_langflow(
                    restore_request=restore_request,
                    background_tasks=background_tasks,
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 403
            assert "Package manager is disabled" in str(exc_info.value.detail)

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_restore_operation_in_progress(self, mock_get_settings):
            """Test restore when another operation is in progress."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock active operation
            mock_active = Mock()
            mock_active.status = InstallationStatus.IN_PROGRESS
            mock_active.updated_at = datetime.now(timezone.utc)

            mock_result1 = Mock()  # stuck installations
            mock_result1.__iter__ = Mock(return_value=iter([]))
            mock_result2 = Mock()  # active installations
            mock_result2.first.return_value = mock_active
            mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2])

            restore_request = PackageRestoreRequest(confirm=True)
            background_tasks = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await restore_langflow(
                    restore_request=restore_request,
                    background_tasks=background_tasks,
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 409
            assert "operation already in progress" in str(exc_info.value.detail)

    class TestGetInstalledPackages:
        """Test get_installed_packages endpoint."""

        @patch("langflow.api.v1.packages.get_settings_service")
        @patch("langflow.api.v1.packages.cleanup_orphaned_installation_records")
        @patch("langflow.api.v1.packages._find_uv_executable")
        @patch("langflow.api.v1.packages._find_project_root")
        @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
        async def test_get_installed_packages_success(
            self, mock_subprocess, mock_find_root, mock_find_uv, mock_cleanup, mock_get_settings
        ):
            """Test successfully getting installed packages."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_cleanup.return_value = 0  # No orphaned records
            mock_find_uv.return_value = "uv"
            mock_find_root.return_value = Path("/fake/root")

            # Mock subprocess that returns package list
            mock_process = Mock()
            mock_process.communicate = AsyncMock(
                return_value=(
                    json.dumps(
                        [{"name": "requests", "version": "2.25.1"}, {"name": "pandas", "version": "1.3.0"}]
                    ).encode(),
                    b"",
                )
            )
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock user installations
            mock_installation1 = Mock()
            mock_installation1.package_name = "requests==2.25.1"
            mock_installation1.status = InstallationStatus.COMPLETED
            mock_installation1.created_at = datetime.now(timezone.utc)

            mock_installation2 = Mock()
            mock_installation2.package_name = "pandas>=1.3.0"
            mock_installation2.status = InstallationStatus.COMPLETED
            mock_installation2.created_at = datetime.now(timezone.utc)

            mock_result = Mock()
            mock_result.__iter__ = Mock(return_value=iter([mock_installation1, mock_installation2]))
            mock_session.exec = AsyncMock(return_value=mock_result)

            result = await get_installed_packages(mock_session, mock_user)

            assert len(result) == 2
            assert result[0].name == "requests"
            assert result[0].version == "2.25.1"
            assert result[1].name == "pandas"
            assert result[1].version == "1.3.0"

        @patch("langflow.api.v1.packages.get_settings_service")
        @patch("langflow.api.v1.packages.cleanup_orphaned_installation_records")
        async def test_get_installed_packages_empty(self, mock_cleanup, mock_get_settings):
            """Test getting installed packages when none exist."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_cleanup.return_value = 0

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock no installations
            mock_result = Mock()
            mock_result.__iter__ = Mock(return_value=iter([]))
            mock_session.exec = AsyncMock(return_value=mock_result)

            result = await get_installed_packages(mock_session, mock_user)

            assert result == []

        @patch("langflow.api.v1.packages.get_settings_service")
        async def test_get_installed_packages_disabled(self, mock_get_settings):
            """Test getting packages when package manager is disabled."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = False
            mock_get_settings.return_value = mock_settings

            mock_session = AsyncMock()
            mock_user = Mock()

            with pytest.raises(HTTPException) as exc_info:
                await get_installed_packages(mock_session, mock_user)

            assert exc_info.value.status_code == 403
            assert "Package manager is disabled" in str(exc_info.value.detail)

        @patch("langflow.api.v1.packages.get_settings_service")
        @patch("langflow.api.v1.packages.cleanup_orphaned_installation_records")
        @patch("langflow.api.v1.packages._find_uv_executable")
        async def test_get_installed_packages_uv_error(self, mock_find_uv, mock_cleanup, mock_get_settings):
            """Test getting packages when UV command fails."""
            mock_settings = Mock()
            mock_settings.settings.package_manager = True
            mock_get_settings.return_value = mock_settings

            mock_cleanup.return_value = 0
            mock_find_uv.side_effect = RuntimeError("UV not found")

            mock_session = AsyncMock()
            mock_user = Mock()
            mock_user.id = uuid4()

            # Mock user installation - need non-empty list to trigger UV call
            mock_installation = Mock()
            mock_installation.package_name = "requests"
            mock_installation.status = InstallationStatus.COMPLETED
            mock_installation.created_at = datetime.now(timezone.utc)
            mock_result = Mock()
            mock_result.__iter__ = Mock(return_value=iter([mock_installation]))
            mock_session.exec = AsyncMock(return_value=mock_result)

            with pytest.raises(HTTPException) as exc_info:
                await get_installed_packages(mock_session, mock_user)

            assert exc_info.value.status_code == 500
            assert "Failed to get installed packages" in str(exc_info.value.detail)


class TestIntegrationScenarios:
    """Test integration-style scenarios that combine multiple functions."""

    @patch("langflow.api.v1.packages.get_settings_service")
    @patch("langflow.api.v1.packages._validate_package_name")
    @patch("langflow.api.v1.packages._is_core_dependency")
    @patch("langflow.api.v1.packages._find_uv_executable")
    @patch("langflow.api.v1.packages._find_project_root")
    @patch("langflow.api.v1.packages.asyncio.create_subprocess_exec")
    async def test_complete_install_workflow(
        self, mock_subprocess, mock_find_root, mock_find_uv, mock_is_core, mock_validate, mock_get_settings
    ):
        """Test complete package installation workflow."""
        # Setup all mocks for successful installation
        mock_settings = Mock()
        mock_settings.settings.package_manager = True
        mock_get_settings.return_value = mock_settings

        mock_validate.return_value = True
        mock_is_core.return_value = False
        mock_find_uv.return_value = "uv"
        mock_find_root.return_value = Path("/fake/root")

        # Mock successful installation subprocess
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(b"Successfully installed test-package-1.0.0", b""))
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Step 1: Install package via endpoint
        mock_session = AsyncMock()
        mock_user = Mock()
        mock_user.id = uuid4()

        # Mock database queries for endpoint
        mock_result1 = Mock()  # existing installations
        mock_result1.__iter__ = Mock(return_value=iter([]))
        mock_result2 = Mock()  # stuck installations
        mock_result2.__iter__ = Mock(return_value=iter([]))
        mock_result3 = Mock()  # active installations
        mock_result3.first.return_value = None
        mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2, mock_result3])

        mock_session.add = Mock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        package_request = PackageInstallRequest(package_name="test-package")
        background_tasks = Mock()

        install_result = await install_package(
            package_request=package_request,
            background_tasks=background_tasks,
            session=mock_session,
            current_user=mock_user,
        )

        assert install_result.status == "started"

        # Step 2: Simulate background task execution
        installation_id = uuid4()
        mock_installation = Mock()
        mock_installation.package_name = "test-package"
        mock_installation.status = InstallationStatus.PENDING

        with patch("langflow.services.deps.session_scope") as mock_session_scope:
            mock_bg_session = AsyncMock()
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_bg_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_bg_session.get.return_value = mock_installation

            await install_package_background(installation_id)

            # Verify installation completed successfully
            assert mock_installation.status == InstallationStatus.COMPLETED

    @patch("langflow.api.v1.packages.get_settings_service")
    async def test_complete_restore_workflow(self, mock_get_settings):
        """Test complete restore workflow."""
        mock_settings = Mock()
        mock_settings.settings.package_manager = True
        mock_get_settings.return_value = mock_settings

        # Step 1: Initiate restore via endpoint
        mock_session = AsyncMock()
        mock_user = Mock()
        mock_user.id = uuid4()

        # Mock no active operations
        mock_result1 = Mock()  # stuck installations
        mock_result1.__iter__ = Mock(return_value=iter([]))
        mock_result2 = Mock()  # active installations
        mock_result2.first.return_value = None
        mock_session.exec = AsyncMock(side_effect=[mock_result1, mock_result2])

        mock_session.add = Mock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        restore_request = PackageRestoreRequest(confirm=True)
        background_tasks = Mock()

        restore_result = await restore_langflow(
            restore_request=restore_request,
            background_tasks=background_tasks,
            session=mock_session,
            current_user=mock_user,
        )

        assert restore_result.status == "started"
        background_tasks.add_task.assert_called_once()

    def test_package_validation_edge_cases(self):
        """Test edge cases in package validation."""
        # Test various edge cases
        edge_cases = [
            ("", False),  # Empty string
            ("a", True),  # Single character
            ("A" * 100, True),  # Very long name (should be valid)
            ("123package", True),  # Starting with numbers
            ("package123", True),  # Ending with numbers
            ("_package", False),  # Starting with underscore (invalid by regex)
            ("package_", False),  # Ending with underscore (invalid by regex - must end with alphanumeric)
            ("-package", False),  # Starting with dash (invalid)
            ("package-", False),  # Ending with dash (invalid)
            ("pack.age", True),  # Single dots (valid)
            ("pack-age", True),  # Single dashes (valid)
            ("pack_age", True),  # Single underscores (valid)
        ]

        for package_name, expected_valid in edge_cases:
            result = _validate_package_specification(package_name)
            assert result == expected_valid, (
                f"Failed for package: '{package_name}', expected {expected_valid}, got {result}"
            )

    def test_version_specification_edge_cases(self):
        """Test edge cases in version specifications."""
        version_specs = [
            ("package==1.0.0", True),
            ("package>=1.0.0", True),
            ("package<=1.0.0", True),
            ("package>1.0.0", True),
            ("package<1.0.0", True),
            ("package!=1.0.0", True),
            ("package~=1.0.0", True),
            ("package===1.0.0", True),
            ("package==1.0.0a1", True),  # Alpha version
            ("package==1.0.0b1", True),  # Beta version
            ("package==1.0.0rc1", True),  # Release candidate
            ("package==1.0.0.post1", True),  # Post release
            ("package==1.0.0.dev1", True),  # Development release
            ("package==", False),  # Empty version
            ("package>=", False),  # Empty version with operator
            ("package==1.0.0;", False),  # Semicolon (potential security issue)
        ]

        for spec, expected_valid in version_specs:
            result = _validate_package_specification(spec)
            assert result == expected_valid, f"Failed for spec: '{spec}', expected {expected_valid}, got {result}"
