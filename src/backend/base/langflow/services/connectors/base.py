from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConnectorFile(BaseModel):
    """Represents a file from a connector."""

    id: str
    name: str
    mime_type: str
    size: int
    modified_at: str
    web_url: str | None = None
    parent_id: str | None = None


class FileInfo(BaseModel):
    """Detailed file information from connectors."""

    id: str
    name: str
    mime_type: str
    size: int = 0
    modified_time: datetime
    parent_id: str | None = None
    web_url: str | None = None
    metadata: dict[str, Any] = {}


class ConnectorMetadata(BaseModel):
    """Metadata about a connector type."""

    connector_type: str
    name: str
    description: str
    icon: str
    available: bool = True
    required_scopes: list[str] = []
    supported_mime_types: list[str] = []


class ConnectorDocument(BaseModel):
    """Represents downloaded document content."""

    file_id: str
    name: str
    content: bytes
    mime_type: str
    metadata: dict[str, Any] = {}


class BaseConnector(ABC):
    """Abstract base class for all connectors."""

    # Metadata for UI display
    CONNECTOR_NAME: str = ""
    CONNECTOR_DESCRIPTION: str = ""
    CONNECTOR_ICON: str = ""
    SUPPORTED_MIME_TYPES: list[str] = []

    def __init__(self, config: dict[str, Any]):
        """Initialize connector with configuration."""
        self.config = config

    @classmethod
    def get_metadata(cls) -> ConnectorMetadata:
        """Get connector metadata.

        Returns:
            ConnectorMetadata with connector information
        """
        return ConnectorMetadata(
            connector_type=cls.CONNECTOR_NAME or cls.__name__.lower(),
            name=cls.CONNECTOR_NAME,
            description=cls.CONNECTOR_DESCRIPTION,
            icon=cls.CONNECTOR_ICON,
            supported_mime_types=cls.SUPPORTED_MIME_TYPES,
        )

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the service.

        Returns:
            True if connection successful, False otherwise
        """

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the service.

        Returns:
            True if disconnection successful
        """

    @abstractmethod
    async def authenticate(self) -> bool:
        """Verify authentication status.

        Returns:
            True if authenticated, False otherwise
        """

    @abstractmethod
    async def list_files(self, page_token: str | None = None, max_files: int | None = None) -> dict[str, Any]:
        """List available files from the connector.

        Args:
            page_token: Token for pagination
            max_files: Maximum number of files to return

        Returns:
            Dictionary with 'files' list and optional 'next_page_token'
        """

    @abstractmethod
    async def get_file_content(self, file_id: str) -> ConnectorDocument:
        """Download file content.

        Args:
            file_id: Unique identifier of the file

        Returns:
            ConnectorDocument with file content and metadata
        """

    @abstractmethod
    async def setup_subscription(self) -> str:
        """Setup webhook subscription for real-time updates.

        Returns:
            Subscription ID for tracking
        """

    @abstractmethod
    async def handle_webhook(self, payload: dict[str, Any]) -> list[str]:
        """Process webhook notification.

        Args:
            payload: Webhook payload from provider

        Returns:
            List of affected file IDs
        """

    async def test_connection(self) -> bool:
        """Test if the connection is working.

        Default implementation tries to authenticate.
        """
        return await self.authenticate()
