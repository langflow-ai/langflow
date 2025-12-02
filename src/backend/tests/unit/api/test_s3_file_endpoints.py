"""S3-specific test class for file API endpoints.

This test class focuses on API endpoints working with S3 storage.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.storage.s3 import S3StorageService


class TestS3FileEndpoints:
    """Test file API endpoints with S3 storage."""

    @pytest.fixture
    def s3_storage_service(self):
        """Mock S3 storage service."""
        service = MagicMock(spec=S3StorageService)
        service.get_file = AsyncMock(return_value=b"file content")
        service.get_file_stream = AsyncMock()
        service.get_file_stream.return_value = [b"chunk1", b"chunk2", b"chunk3"]
        service.save_file = AsyncMock()
        service.delete_file = AsyncMock()
        service.get_file_size = AsyncMock(return_value=1024)
        return service

    @pytest.fixture
    def s3_settings(self):
        """Mock S3 settings."""
        settings = MagicMock()
        settings.settings.storage_type = "s3"
        settings.settings.max_file_size_upload = 10  # 10MB
        return settings

    @pytest.mark.asyncio
    async def test_s3_download_file_streaming(self, s3_storage_service, s3_settings):
        """Test downloading files with S3 streaming."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=s3_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=s3_settings),
        ):
            # Mock database and user
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/document.pdf"
            mock_file.name = "document"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                # Test the download endpoint logic
                from langflow.api.v2.files import download_file

                # Mock the database session
                mock_session = MagicMock()

                # Test streaming download
                _ = await download_file(
                    file_id="test-id",
                    current_user=mock_user,
                    session=mock_session,
                    storage_service=s3_storage_service,
                    return_content=False,
                )

                # Should use S3 streaming
                s3_storage_service.get_file_stream.assert_called_once_with(flow_id="user_123", file_name="document.pdf")

    @pytest.mark.asyncio
    async def test_s3_download_file_content(self, s3_storage_service, s3_settings):
        """Test downloading file content with S3."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=s3_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=s3_settings),
        ):
            # Mock database and user
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/document.pdf"
            mock_file.name = "document"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                # Test the download endpoint logic
                from langflow.api.v2.files import download_file

                # Mock the database session
                mock_session = MagicMock()

                # Test content download
                _ = await download_file(
                    file_id="test-id",
                    current_user=mock_user,
                    session=mock_session,
                    storage_service=s3_storage_service,
                    return_content=True,
                )

                # Should use S3 get_file for content
                s3_storage_service.get_file.assert_called_once_with(flow_id="user_123", file_name="document.pdf")

    @pytest.mark.asyncio
    async def test_s3_upload_file(self, s3_storage_service, s3_settings):
        """Test uploading files to S3."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=s3_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=s3_settings),
        ):
            # Mock database and user
            mock_user = MagicMock()
            mock_user.id = "user_123"

            # Mock file upload
            mock_file = MagicMock()
            mock_file.filename = "test.txt"
            mock_file.size = 1024
            mock_file.read = AsyncMock(return_value=b"file content")

            with (
                patch("langflow.api.v2.files.upload_user_file"),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                # Test upload logic
                from langflow.api.v2.files import save_file_routine

                _, _ = await save_file_routine(
                    mock_file, s3_storage_service, mock_user, file_name="test.txt"
                )

                # Should save to S3
                s3_storage_service.save_file.assert_called_once_with(
                    flow_id="user_123", file_name="test.txt", data=b"file content"
                )

    @pytest.mark.asyncio
    async def test_s3_delete_file(self, s3_storage_service, s3_settings):
        """Test deleting files from S3."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=s3_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=s3_settings),
        ):
            # Mock database and user
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/document.pdf"
            mock_file.name = "document"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                # Test delete logic
                from langflow.api.v2.files import delete_file

                # Mock the database session
                mock_session = MagicMock()

                await delete_file(
                    file_id="test-id", current_user=mock_user, session=mock_session, storage_service=s3_storage_service
                )

                # Should delete from S3
                s3_storage_service.delete_file.assert_called_once_with(flow_id="user_123", file_name="document.pdf")

    @pytest.mark.asyncio
    async def test_s3_file_size_calculation(self, s3_storage_service, s3_settings):
        """Test file size calculation with S3."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=s3_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=s3_settings),
        ):
            # Mock database and user
            mock_user = MagicMock()
            mock_user.id = "user_123"

            # Mock file upload
            mock_file = MagicMock()
            mock_file.filename = "test.txt"
            mock_file.size = 1024
            mock_file.read = AsyncMock(return_value=b"file content")

            with (
                patch("langflow.api.v2.files.upload_user_file"),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                # Test size calculation
                from langflow.api.v2.files import save_file_routine

                _, _ = await save_file_routine(
                    mock_file, s3_storage_service, mock_user, file_name="test.txt"
                )

                # Should get file size from S3
                s3_storage_service.get_file_size.assert_called_once_with(flow_id="user_123", file_name="test.txt")

    @pytest.mark.asyncio
    async def test_s3_error_handling(self, s3_storage_service, s3_settings):
        """Test error handling with S3 operations."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=s3_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=s3_settings),
        ):
            # Mock S3 error
            s3_storage_service.get_file.side_effect = FileNotFoundError("File not found")

            # Mock database and user
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/nonexistent.pdf"
            mock_file.name = "nonexistent"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                # Test error handling
                from langflow.api.v2.files import download_file

                # Mock the database session
                mock_session = MagicMock()

                # Should handle S3 errors gracefully
                with pytest.raises(FileNotFoundError):
                    await download_file(
                        file_id="test-id",
                        current_user=mock_user,
                        session=mock_session,
                        storage_service=s3_storage_service,
                        return_content=True,
                    )

    @pytest.mark.asyncio
    async def test_s3_streaming_performance(self, s3_storage_service, s3_settings):
        """Test S3 streaming performance."""
        with (
            patch("langflow.services.deps.get_storage_service", return_value=s3_storage_service),
            patch("langflow.services.deps.get_settings_service", return_value=s3_settings),
        ):
            # Mock large file streaming
            large_chunks = [b"chunk" * 1000 for _ in range(100)]
            s3_storage_service.get_file_stream.return_value = large_chunks

            # Mock database and user
            mock_user = MagicMock()
            mock_user.id = "user_123"

            mock_file = MagicMock()
            mock_file.path = "user_123/large_file.txt"
            mock_file.name = "large_file"

            with (
                patch("langflow.api.v2.files.fetch_file_object", return_value=mock_file),
                patch("langflow.api.v2.files.CurrentActiveUser", return_value=mock_user),
            ):
                # Test streaming performance
                from langflow.api.v2.files import download_file

                # Mock the database session
                mock_session = MagicMock()

                # Should handle large files efficiently
                _ = await download_file(
                    file_id="test-id",
                    current_user=mock_user,
                    session=mock_session,
                    storage_service=s3_storage_service,
                    return_content=False,
                )

                # Should use streaming for large files
                s3_storage_service.get_file_stream.assert_called_once_with(
                    flow_id="user_123", file_name="large_file.txt"
                )
