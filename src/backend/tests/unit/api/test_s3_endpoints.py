"""API endpoint tests for S3 storage.

This module tests the file API endpoints (download, upload, delete) work correctly
with S3 storage. These are unit tests that mock the storage layer to focus on
testing API logic:
- Path parsing from database file records
- HTTP response construction (StreamingResponse vs content)
- Error handling and HTTP status codes
- Request parameter validation

For actual S3 storage service testing, see:
- tests/unit/services/storage/ - Unit tests with mocked boto3
- tests/integration/storage/ - Integration tests with real AWS S3
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from langflow.services.storage.s3 import S3StorageService


class TestS3FileEndpoints:
    """Test file API endpoints with S3 storage mock."""

    @pytest.fixture
    def mock_storage_service(self):
        """Mock storage service for testing API logic.

        This is a simple mock - we're testing the API layer, not S3 itself.
        """
        service = MagicMock(spec=S3StorageService)
        service.get_file = AsyncMock(return_value=b"test file content")
        service.get_file_stream = MagicMock(return_value=iter([b"chunk1", b"chunk2", b"chunk3"]))
        service.save_file = AsyncMock()
        service.delete_file = AsyncMock()
        service.get_file_size = AsyncMock(return_value=1024)
        return service

    @pytest.fixture
    def mock_settings(self):
        """Mock settings service."""
        settings = MagicMock()
        settings.settings.storage_type = "s3"
        settings.settings.max_file_size_upload = 10  # 10MB
        return settings

    @pytest.mark.asyncio
    async def test_download_file_parses_path_correctly(self, mock_storage_service, mock_settings):
        """Test that download_file correctly extracts filename from path."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=mock_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=mock_settings),
        ):
            mock_user = MagicMock()
            mock_user.id = "user_123"

            # File path uses .split("/")[-1] to get just the filename
            mock_file = MagicMock()
            mock_file.path = "user_123/subfolder/document.pdf"
            mock_file.name = "document"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                from langflow.api.v2.files import download_file

                await download_file(
                    file_id="test-id",
                    current_user=mock_user,
                    session=MagicMock(),
                    storage_service=mock_storage_service,
                    return_content=True,
                )

                # API extracts "document.pdf" from "user_123/subfolder/document.pdf" (last segment only)
                mock_storage_service.get_file.assert_called_once_with(flow_id="user_123", file_name="document.pdf")

    @pytest.mark.asyncio
    async def test_download_file_returns_streaming_response(self, mock_storage_service, mock_settings):
        """Test that download_file returns StreamingResponse for file downloads."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=mock_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=mock_settings),
        ):
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/document.pdf"
            mock_file.name = "document"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                from fastapi.responses import StreamingResponse
                from langflow.api.v2.files import download_file

                response = await download_file(
                    file_id="test-id",
                    current_user=mock_user,
                    session=MagicMock(),
                    storage_service=mock_storage_service,
                    return_content=False,
                )

                # Verify response type and headers
                assert isinstance(response, StreamingResponse)
                assert response.media_type == "application/octet-stream"
                assert "attachment" in response.headers.get("Content-Disposition", "")
                assert "document.pdf" in response.headers.get("Content-Disposition", "")

    @pytest.mark.asyncio
    async def test_download_file_returns_content_string(self, mock_storage_service, mock_settings):
        """Test that download_file returns decoded content when return_content=True."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=mock_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=mock_settings),
        ):
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/document.txt"
            mock_file.name = "document"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                from langflow.api.v2.files import download_file

                result = await download_file(
                    file_id="test-id",
                    current_user=mock_user,
                    session=MagicMock(),
                    storage_service=mock_storage_service,
                    return_content=True,
                )

                # Should return decoded string content
                assert isinstance(result, str)
                assert result == "test file content"

    @pytest.mark.asyncio
    async def test_delete_file_calls_storage_with_correct_params(self, mock_storage_service, mock_settings):
        """Test that delete_file correctly parses path and calls storage service."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=mock_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=mock_settings),
        ):
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/folder/document.pdf"
            mock_file.name = "document"

            mock_session = MagicMock()
            mock_session.delete = AsyncMock()

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                from langflow.api.v2.files import delete_file

                await delete_file(
                    file_id="test-id",
                    current_user=mock_user,
                    session=mock_session,
                    storage_service=mock_storage_service,
                )

                # Verify storage service was called with just the filename (last path segment)
                mock_storage_service.delete_file.assert_called_once_with(flow_id="user_123", file_name="document.pdf")

                # Verify database deletion
                mock_session.delete.assert_called_once_with(mock_file)

    @pytest.mark.asyncio
    async def test_storage_error_converted_to_http_exception(self, mock_storage_service, mock_settings):
        """Test that storage FileNotFoundError is converted to HTTPException with 404 status."""
        # Mock storage service to raise FileNotFoundError
        mock_storage_service.get_file.side_effect = FileNotFoundError("File not found in S3")

        with (
            patch("langflow.services.deps.get_storage_service", return_value=mock_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=mock_settings),
        ):
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/missing.pdf"
            mock_file.name = "missing"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                from langflow.api.v2.files import download_file

                # API should convert FileNotFoundError to HTTPException with 404 status
                with pytest.raises(HTTPException) as exc_info:
                    await download_file(
                        file_id="test-id",
                        current_user=mock_user,
                        session=MagicMock(),
                        storage_service=mock_storage_service,
                        return_content=True,
                    )

                assert exc_info.value.status_code == 404
                assert "File not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_saves_to_storage_service(self, mock_storage_service, mock_settings):
        """Test that file upload correctly saves to storage service."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=mock_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=mock_settings),
        ):
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.filename = "upload.txt"
            mock_file.size = 1024
            mock_file.read = AsyncMock(return_value=b"file content")

            with patch("langflow.api.v2.files.upload_user_file"):
                from langflow.api.v2.files import save_file_routine

                await save_file_routine(mock_file, mock_storage_service, mock_user, file_name="upload.txt")

                # Verify storage service was called
                mock_storage_service.save_file.assert_called_once_with(
                    flow_id="user_123", file_name="upload.txt", data=b"file content", append=False
                )
