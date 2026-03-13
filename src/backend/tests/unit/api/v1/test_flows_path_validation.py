"""Unit tests for flow filesystem path validation security."""

from unittest.mock import MagicMock
from uuid import uuid4

import anyio
import pytest
from fastapi import HTTPException
from langflow.api.v1.flows import _get_safe_flow_path
from langflow.services.storage.service import StorageService


@pytest.fixture
def mock_storage_service(tmp_path):
    """Create a mock storage service with a temporary data directory."""
    service = MagicMock(spec=StorageService)
    service.data_dir = tmp_path
    return service


@pytest.fixture
def user_id():
    """Create a test user ID."""
    return uuid4()


class TestPathValidation:
    """Test cases for path validation security."""

    def test_rejects_absolute_path_outside_allowed_directory(self, mock_storage_service, user_id):
        """Test that absolute paths outside the allowed directory are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _get_safe_flow_path("/etc/passwd", user_id, mock_storage_service)
        assert exc_info.value.status_code == 400
        assert "within" in exc_info.value.detail.lower() or "outside" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_accepts_absolute_path_within_allowed_directory(self, mock_storage_service, user_id, tmp_path):
        """Test that absolute paths within the user's flows directory are accepted."""
        from pathlib import Path as StdlibPath

        import anyio

        mock_storage_service.data_dir = anyio.Path(tmp_path)
        base_dir = mock_storage_service.data_dir / "flows" / str(user_id)
        await base_dir.mkdir(parents=True, exist_ok=True)

        # Create an absolute path within the allowed directory (resolve to get actual absolute path)
        base_dir_stdlib = StdlibPath(str(base_dir)).resolve()
        allowed_absolute = str(base_dir_stdlib / "my_flow.json")

        path = _get_safe_flow_path(allowed_absolute, user_id, mock_storage_service)
        assert path is not None
        # Verify the returned path matches what we expect
        assert str(path) == allowed_absolute or str(path).endswith("my_flow.json")

    def test_rejects_directory_traversal(self, mock_storage_service, user_id):
        """Test that directory traversal sequences are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _get_safe_flow_path("../../etc/passwd", user_id, mock_storage_service)
        assert exc_info.value.status_code == 400
        assert "directory traversal" in exc_info.value.detail.lower()

    def test_rejects_backslash_directory_traversal(self, mock_storage_service, user_id):
        """Test that backslash directory traversal is caught after normalization."""
        # Backslash traversal should be normalized first, then caught
        with pytest.raises(HTTPException) as exc_info:
            _get_safe_flow_path("sub\\..\\etc\\passwd", user_id, mock_storage_service)
        assert exc_info.value.status_code == 400
        assert "directory traversal" in exc_info.value.detail.lower()

    def test_rejects_windows_backslash_traversal(self, mock_storage_service, user_id):
        """Test that Windows-style backslash traversal is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _get_safe_flow_path("folder\\..\\..\\etc\\passwd", user_id, mock_storage_service)
        assert exc_info.value.status_code == 400
        assert "directory traversal" in exc_info.value.detail.lower()

    def test_rejects_multiple_traversal(self, mock_storage_service, user_id):
        """Test that multiple directory traversals are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _get_safe_flow_path("../../../etc/passwd", user_id, mock_storage_service)
        assert exc_info.value.status_code == 400

    def test_rejects_traversal_in_subpath(self, mock_storage_service, user_id):
        """Test that traversal in subpaths is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _get_safe_flow_path("subfolder/../../etc/passwd", user_id, mock_storage_service)
        assert exc_info.value.status_code == 400

    def test_rejects_null_bytes(self, mock_storage_service, user_id):
        """Test that null bytes are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _get_safe_flow_path("file\x00name.json", user_id, mock_storage_service)
        assert exc_info.value.status_code == 400
        assert "null bytes" in exc_info.value.detail.lower()

    def test_rejects_empty_path(self, mock_storage_service, user_id):
        """Test that empty paths are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _get_safe_flow_path("", user_id, mock_storage_service)
        assert exc_info.value.status_code == 400

    def test_accepts_simple_relative_path(self, mock_storage_service, user_id):
        """Test that simple relative paths are accepted."""
        path = _get_safe_flow_path("my_flow.json", user_id, mock_storage_service)
        assert path is not None
        # Verify it's within the user's flows directory
        assert str(user_id) in str(path)
        assert "flows" in str(path)

    def test_accepts_nested_relative_path(self, mock_storage_service, user_id):
        """Test that nested relative paths are accepted."""
        path = _get_safe_flow_path("subfolder/my_flow.json", user_id, mock_storage_service)
        assert path is not None
        assert str(user_id) in str(path)
        assert "flows" in str(path)
        assert "subfolder" in str(path)

    def test_accepts_deeply_nested_path(self, mock_storage_service, user_id):
        """Test that deeply nested relative paths are accepted."""
        path = _get_safe_flow_path("a/b/c/d/e/flow.json", user_id, mock_storage_service)
        assert path is not None
        assert str(user_id) in str(path)

    def test_path_is_user_isolated(self, mock_storage_service, user_id):  # noqa: ARG002
        """Test that paths are isolated per user."""
        user1_id = uuid4()
        user2_id = uuid4()

        path1 = _get_safe_flow_path("flow.json", user1_id, mock_storage_service)
        path2 = _get_safe_flow_path("flow.json", user2_id, mock_storage_service)

        # Paths should be different and contain their respective user IDs
        assert str(path1) != str(path2)
        assert str(user1_id) in str(path1)
        assert str(user2_id) in str(path2)
        assert str(user1_id) not in str(path2)
        assert str(user2_id) not in str(path1)

    def test_handles_leading_slash_in_relative_path(self, mock_storage_service, user_id):
        """Test that leading slashes in relative paths are handled correctly."""
        _get_safe_flow_path("flow.json", user_id, mock_storage_service)
        # Leading slash makes it absolute, so it will be checked against base directory
        # For a simple "/flow.json", it's not within the base dir, so it should be rejected
        with pytest.raises(HTTPException):
            _get_safe_flow_path("/flow.json", user_id, mock_storage_service)

    def test_accepts_paths_with_double_slash(self, mock_storage_service, user_id):
        """Test that paths with double slashes are normalized (not rejected, but normalized by Path)."""
        # Double slashes are normalized by the Path library, so they're acceptable
        # The security concern is directory traversal, not double slashes
        path = _get_safe_flow_path("sub//folder/file.json", user_id, mock_storage_service)
        assert path is not None

    def test_accepts_valid_filename_characters(self, mock_storage_service, user_id):
        """Test that valid filename characters are accepted."""
        valid_paths = [
            "flow.json",
            "my-flow.json",
            "flow_123.json",
            "flow.name.json",
            "subfolder/flow.json",
            "flow (1).json",
        ]
        for valid_path in valid_paths:
            path = _get_safe_flow_path(valid_path, user_id, mock_storage_service)
            assert path is not None

    @pytest.mark.asyncio
    async def test_path_resolves_within_base_directory(self, mock_storage_service, user_id, tmp_path):
        """Test that resolved paths stay within the base directory."""
        from pathlib import Path as StdlibPath

        # Create a real path structure to test resolution
        mock_storage_service.data_dir = anyio.Path(tmp_path)

        path = _get_safe_flow_path("flow.json", user_id, mock_storage_service)
        # Use stdlib Path for synchronous resolution check
        resolved = StdlibPath(str(path)).resolve()
        base_dir_str = str(mock_storage_service.data_dir / "flows" / str(user_id))
        resolved_base = StdlibPath(base_dir_str).resolve()

        # Resolved path should start with resolved base
        assert str(resolved).startswith(str(resolved_base))
