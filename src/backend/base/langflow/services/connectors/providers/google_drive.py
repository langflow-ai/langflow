"""Google Drive connector implementation."""

import io
from collections.abc import Callable
from datetime import datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from lfx.log import logger

from langflow.services.connectors.base import BaseConnector, ConnectorMetadata, FileInfo
from langflow.services.connectors.retry import (
    ErrorCategory,
    RetryConfig,
    with_exponential_backoff,
)


class GoogleDriveConnector(BaseConnector):
    """Google Drive connector implementation with patterns from OpenRAG."""

    # Supported MIME types (from OpenRAG)
    SUPPORTED_MIME_TYPES = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/html",
        "application/vnd.google-apps.document",  # Google Docs
        "application/vnd.google-apps.spreadsheet",  # Google Sheets
        "application/vnd.google-apps.presentation",  # Google Slides
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    # Google Workspace export formats (from OpenRAG)
    GOOGLE_WORKSPACE_EXPORT_FORMATS = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }

    def __init__(self, config: dict[str, Any]):
        """Initialize Google Drive connector.

        Args:
            config: Configuration containing credentials and settings
                Required keys:
                - Either 'service_account_key' or OAuth credentials
                - Optional: 'folder_id', 'recursive', 'max_file_size_mb'
        """
        super().__init__(config)
        self.service = None
        self._credentials: Credentials | None = None
        self.folder_id = config.get("folder_id", "root")
        self.recursive = config.get("recursive", True)
        self.max_file_size_mb = config.get("max_file_size_mb", 100)
        self._page_token: str | None = None  # For incremental sync

    @classmethod
    def get_metadata(cls) -> ConnectorMetadata:
        """Get connector metadata."""
        return ConnectorMetadata(
            connector_type="google_drive",
            name="Google Drive",
            description="Connect to Google Drive for document synchronization",
            icon="google-drive",
            available=True,
            required_scopes=[
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/drive.metadata.readonly",
            ],
            supported_mime_types=list(cls.SUPPORTED_MIME_TYPES),
        )

    async def connect(self) -> bool:
        """Establish connection to Google Drive.

        Returns:
            True if connection successful
        """
        try:
            # Initialize credentials (similar to OpenRAG)
            if "service_account_key" in self.config:
                # Service account authentication
                self._credentials = ServiceAccountCredentials.from_service_account_info(
                    self.config["service_account_key"],
                    scopes=self.get_metadata().required_scopes,
                )
            elif "access_token" in self.config:
                # OAuth2 credentials
                self._credentials = Credentials(
                    token=self.config["access_token"],
                    refresh_token=self.config.get("refresh_token"),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self.config.get("client_id"),
                    client_secret=self.config.get("client_secret"),
                    scopes=self.get_metadata().required_scopes,
                )

                # Refresh if needed
                if self._credentials.expired and self._credentials.refresh_token:
                    self._credentials.refresh(Request())
            else:
                logger.error("No authentication credentials provided")
                return False

            # Build the service
            self.service = build("drive", "v3", credentials=self._credentials, cache_discovery=False)

            # Test connection by listing one file
            self.service.files().list(pageSize=1, fields="files(id)").execute()

            logger.info("Successfully connected to Google Drive")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Google Drive: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Google Drive."""
        self.service = None
        self._credentials = None
        return True

    async def authenticate(self) -> bool:
        """Verify authentication status.

        Returns:
            True if authenticated
        """
        return await self.connect()

    async def get_file_content(self, file_id: str) -> Any:
        """Download file content (alias for download_file).

        Args:
            file_id: File ID to download

        Returns:
            File content as bytes
        """
        return await self.download_file(file_id)

    async def setup_subscription(self) -> str:
        """Setup webhook subscription for real-time updates.

        Returns:
            Subscription ID
        """
        # TODO: Implement webhook subscription
        msg = "Webhook subscription not yet implemented"
        raise NotImplementedError(msg)

    async def handle_webhook(self, payload: dict[str, Any]) -> list[str]:
        """Process webhook notification.

        Args:
            payload: Webhook payload

        Returns:
            List of affected file IDs
        """
        # TODO: Implement webhook handling
        msg = "Webhook handling not yet implemented"
        raise NotImplementedError(msg)

    @with_exponential_backoff(RetryConfig(max_retries=3))
    async def list_files(
        self,
        folder_id: str | None = None,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> tuple[list[FileInfo], str | None]:
        """List files in Google Drive (pattern from OpenRAG).

        Args:
            folder_id: Folder to list files from (None for configured folder)
            page_size: Number of files per page
            page_token: Token for pagination

        Returns:
            Tuple of (list of FileInfo, next page token)
        """
        if not self.service:
            msg = "Not connected to Google Drive"
            raise RuntimeError(msg)

        folder_id = folder_id or self.folder_id
        files_list = []
        next_page_token = None

        try:
            # Build query (similar to OpenRAG but with improvements)
            query_parts = [f"'{folder_id}' in parents", "trashed = false"]

            # Filter by supported MIME types
            mime_filters = [f"mimeType='{mime}'" for mime in self.SUPPORTED_MIME_TYPES]
            if mime_filters:
                query_parts.append(f"({' or '.join(mime_filters)})")

            query = " and ".join(query_parts)

            # Request fields we need
            fields = (
                "nextPageToken, files(id, name, mimeType, size, "
                "modifiedTime, parents, webViewLink, exportLinks)"
            )

            # Execute the request with retry logic
            response = self.service.files().list(
                q=query,
                pageSize=page_size,
                pageToken=page_token,
                fields=fields,
                orderBy="modifiedTime desc",
            ).execute()

            next_page_token = response.get("nextPageToken")

            for file_data in response.get("files", []):
                # Skip files that are too large
                file_size = int(file_data.get("size", 0))
                if file_size > self.max_file_size_mb * 1024 * 1024:
                    logger.warning(f"Skipping large file {file_data['name']}: {file_size} bytes")
                    continue

                # Convert to FileInfo
                file_info = FileInfo(
                    id=file_data["id"],
                    name=file_data["name"],
                    mime_type=file_data.get("mimeType", "application/octet-stream"),
                    size=file_size,
                    modified_time=datetime.fromisoformat(
                        file_data["modifiedTime"].replace("Z", "+00:00")
                    ),
                    parent_id=file_data.get("parents", [None])[0],
                    web_url=file_data.get("webViewLink"),
                    metadata={
                        "export_links": file_data.get("exportLinks", {}),
                        "is_google_workspace": file_data.get("mimeType", "").startswith(
                            "application/vnd.google-apps"
                        ),
                    },
                )
                files_list.append(file_info)

            # If recursive, also get files from subfolders (OpenRAG pattern)
            if self.recursive and folder_id != "root":
                await self._list_subfolders_files(folder_id, files_list, page_size)

        except HttpError as e:
            error_category = self._categorize_google_error(e)
            if error_category == ErrorCategory.AUTH_ERROR:
                logger.error("Authentication failed - token may be expired")
            raise

        return files_list, next_page_token

    async def _list_subfolders_files(
        self, parent_folder_id: str, files_list: list[FileInfo], page_size: int
    ):
        """Recursively list files in subfolders (from OpenRAG pattern).

        Args:
            parent_folder_id: Parent folder ID
            files_list: List to append files to
            page_size: Number of files per page
        """
        # Find all subfolders
        query = (
            f"'{parent_folder_id}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"trashed=false"
        )

        response = self.service.files().list(
            q=query, fields="files(id, name)", pageSize=1000
        ).execute()

        for folder in response.get("files", []):
            # Recursively list files in each subfolder
            subfolder_files, _ = await self.list_files(folder["id"], page_size)
            files_list.extend(subfolder_files)

    @with_exponential_backoff(RetryConfig(max_retries=3))
    async def download_file(self, file_id: str, file_info: FileInfo | None = None) -> bytes:
        """Download a file from Google Drive (improved from OpenRAG).

        Args:
            file_id: File ID to download
            file_info: Optional FileInfo with metadata

        Returns:
            File content as bytes
        """
        if not self.service:
            msg = "Not connected to Google Drive"
            raise RuntimeError(msg)

        try:
            # If it's a Google Workspace file, export it
            if file_info and file_info.metadata.get("is_google_workspace"):
                export_mime_type = self.GOOGLE_WORKSPACE_EXPORT_FORMATS.get(
                    file_info.mime_type, "text/plain"
                )
                request = self.service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            else:
                # Regular file download
                request = self.service.files().get_media(fileId=file_id)

            # Download with progress tracking (improvement over OpenRAG)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download progress: {int(status.progress() * 100)}%")

            return file_buffer.getvalue()

        except HttpError as e:
            error_category = self._categorize_google_error(e)
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    async def get_changes(
        self, page_token: str | None = None
    ) -> tuple[list[FileInfo], list[str], str | None]:
        """Get incremental changes using Changes API (improvement over OpenRAG).

        Args:
            page_token: Change token from last sync

        Returns:
            Tuple of (changed files, deleted file IDs, next page token)
        """
        if not self.service:
            msg = "Not connected to Google Drive"
            raise RuntimeError(msg)

        changed_files = []
        deleted_ids = []

        try:
            # Get start page token if not provided
            if not page_token:
                response = self.service.changes().getStartPageToken().execute()
                page_token = response.get("startPageToken")
                # Return empty on first sync
                return [], [], page_token

            # Get changes since last sync
            response = self.service.changes().list(
                pageToken=page_token,
                fields="nextPageToken, newStartPageToken, changes(file, fileId, removed)",
                pageSize=100,
            ).execute()

            for change in response.get("changes", []):
                if change.get("removed"):
                    deleted_ids.append(change["fileId"])
                elif change.get("file"):
                    file_data = change["file"]
                    # Check if file matches our criteria
                    if file_data.get("mimeType") in self.SUPPORTED_MIME_TYPES:
                        file_info = FileInfo(
                            id=file_data["id"],
                            name=file_data["name"],
                            mime_type=file_data.get("mimeType"),
                            size=int(file_data.get("size", 0)),
                            modified_time=datetime.fromisoformat(
                                file_data["modifiedTime"].replace("Z", "+00:00")
                            ),
                            parent_id=file_data.get("parents", [None])[0],
                            web_url=file_data.get("webViewLink"),
                        )
                        changed_files.append(file_info)

            next_token = response.get("newStartPageToken") or response.get("nextPageToken")
            return changed_files, deleted_ids, next_token

        except HttpError as e:
            error_category = self._categorize_google_error(e)
            logger.error(f"Failed to get changes: {e}")
            raise

    async def search_files(self, query: str, max_results: int = 50) -> list[FileInfo]:
        """Search for files by name or content.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of matching FileInfo objects
        """
        if not self.service:
            msg = "Not connected to Google Drive"
            raise RuntimeError(msg)

        try:
            # Build search query
            search_query = f"fullText contains '{query}' and trashed = false"

            response = self.service.files().list(
                q=search_query,
                pageSize=max_results,
                fields="files(id, name, mimeType, size, modifiedTime, parents, webViewLink)",
            ).execute()

            files_list = []
            for file_data in response.get("files", []):
                file_info = FileInfo(
                    id=file_data["id"],
                    name=file_data["name"],
                    mime_type=file_data.get("mimeType"),
                    size=int(file_data.get("size", 0)),
                    modified_time=datetime.fromisoformat(
                        file_data["modifiedTime"].replace("Z", "+00:00")
                    ),
                    parent_id=file_data.get("parents", [None])[0],
                    web_url=file_data.get("webViewLink"),
                )
                files_list.append(file_info)

            return files_list

        except HttpError as e:
            logger.error(f"Search failed: {e}")
            raise

    async def test_connection(self) -> tuple[bool, str | None]:
        """Test the connection to Google Drive.

        Returns:
            Tuple of (success, error message)
        """
        try:
            if not self.service:
                await self.connect()

            # Try to get user info
            about = self.service.about().get(fields="user, storageQuota").execute()
            user = about.get("user", {})
            quota = about.get("storageQuota", {})

            logger.info(
                f"Connected as {user.get('displayName', 'Unknown')} "
                f"({user.get('emailAddress', 'Unknown')})"
            )

            # Check storage quota
            used = int(quota.get("usage", 0))
            limit = int(quota.get("limit", 0))
            if limit > 0:
                percent_used = (used / limit) * 100
                logger.info(f"Storage used: {percent_used:.1f}%")

            return True, None

        except Exception as e:
            error_msg = f"Connection test failed: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _categorize_google_error(self, error: HttpError) -> ErrorCategory:
        """Categorize Google API errors.

        Args:
            error: Google API HttpError

        Returns:
            ErrorCategory for the error
        """
        if error.resp.status == 401:
            return ErrorCategory.AUTH_ERROR
        if error.resp.status == 403:
            return ErrorCategory.PERMISSION_ERROR
        if error.resp.status == 404:
            return ErrorCategory.NOT_FOUND
        if error.resp.status == 429:
            return ErrorCategory.RATE_LIMIT
        if error.resp.status >= 500:
            return ErrorCategory.SERVER_ERROR
        return ErrorCategory.TRANSIENT

    async def sync_to_knowledge_base(
        self,
        knowledge_base_id: str,
        file_filter: Callable | None = None,
        progress_callback: Callable | None = None,
    ) -> dict[str, Any]:
        """Sync files to a knowledge base (pattern from OpenRAG).

        Args:
            knowledge_base_id: Target knowledge base
            file_filter: Optional function to filter files
            progress_callback: Optional callback for progress updates

        Returns:
            Sync statistics
        """
        stats = {"files_processed": 0, "files_skipped": 0, "errors": 0, "bytes_processed": 0}

        try:
            # Get list of files
            files, _ = await self.list_files()

            for i, file_info in enumerate(files):
                # Apply filter if provided
                if file_filter and not file_filter(file_info):
                    stats["files_skipped"] += 1
                    continue

                try:
                    # Download file content
                    content = await self.download_file(file_info.id, file_info)

                    # TODO: Process and add to knowledge base
                    # This would integrate with Langflow's KB system

                    stats["files_processed"] += 1
                    stats["bytes_processed"] += len(content)

                    # Report progress
                    if progress_callback:
                        progress_callback(i + 1, len(files), file_info.name)

                except Exception as e:
                    logger.error(f"Failed to sync file {file_info.name}: {e}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise

        return stats
