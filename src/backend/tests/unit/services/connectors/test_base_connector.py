import pytest
from langflow.services.connectors.base import BaseConnector, ConnectorDocument, ConnectorFile


def test_base_connector_is_abstract():
    """Test that BaseConnector is an abstract class."""
    with pytest.raises(TypeError):
        BaseConnector()


def test_base_connector_has_required_methods():
    """Test that BaseConnector defines required methods."""
    assert hasattr(BaseConnector, "authenticate")
    assert hasattr(BaseConnector, "list_files")
    assert hasattr(BaseConnector, "get_file_content")
    assert hasattr(BaseConnector, "setup_subscription")
    assert hasattr(BaseConnector, "handle_webhook")


def test_base_connector_has_test_connection():
    """Test that BaseConnector has test_connection method."""
    assert hasattr(BaseConnector, "test_connection")


def test_base_connector_metadata_attributes():
    """Test that BaseConnector has metadata attributes."""
    assert hasattr(BaseConnector, "CONNECTOR_NAME")
    assert hasattr(BaseConnector, "CONNECTOR_DESCRIPTION")
    assert hasattr(BaseConnector, "CONNECTOR_ICON")
    assert hasattr(BaseConnector, "SUPPORTED_MIME_TYPES")


def test_connector_file_model():
    """Test ConnectorFile Pydantic model."""
    file = ConnectorFile(
        id="file123",
        name="test.pdf",
        mime_type="application/pdf",
        size=1024,
        modified_at="2024-01-01T00:00:00Z",
        web_url="https://example.com/file123",
        parent_id="folder456",
    )

    assert file.id == "file123"
    assert file.name == "test.pdf"
    assert file.mime_type == "application/pdf"
    assert file.size == 1024
    assert file.modified_at == "2024-01-01T00:00:00Z"
    assert file.web_url == "https://example.com/file123"
    assert file.parent_id == "folder456"


def test_connector_document_model():
    """Test ConnectorDocument Pydantic model."""
    document = ConnectorDocument(
        file_id="file123",
        name="test.pdf",
        content=b"test content",
        mime_type="application/pdf",
        metadata={"author": "Test Author"},
    )

    assert document.file_id == "file123"
    assert document.name == "test.pdf"
    assert document.content == b"test content"
    assert document.mime_type == "application/pdf"
    assert document.metadata == {"author": "Test Author"}


def test_concrete_connector_implementation():
    """Test that a concrete implementation can be instantiated."""

    class TestConnector(BaseConnector):
        CONNECTOR_NAME = "Test Connector"

        async def connect(self) -> bool:
            return True

        async def disconnect(self) -> bool:
            return True

        async def authenticate(self) -> bool:
            return True

        async def list_files(self, page_token=None, max_files=None):  # noqa: ARG002
            return {"files": [], "next_page_token": None}

        async def get_file_content(self, file_id: str):
            return ConnectorDocument(
                file_id=file_id, name="test.txt", content=b"test", mime_type="text/plain", metadata={}
            )

        async def setup_subscription(self) -> str:
            return "sub123"

        async def handle_webhook(self, payload):  # noqa: ARG002
            return ["file1", "file2"]

    connector = TestConnector(config={"folder": "root"})
    assert connector.config == {"folder": "root"}
    assert connector.CONNECTOR_NAME == "Test Connector"


@pytest.mark.asyncio
async def test_connector_test_connection_uses_authenticate():
    """Test that test_connection uses authenticate by default."""

    class TestConnector(BaseConnector):
        async def connect(self) -> bool:
            return True

        async def disconnect(self) -> bool:
            return True

        async def authenticate(self) -> bool:
            return True

        async def list_files(self, page_token=None, max_files=None):  # noqa: ARG002
            return {"files": []}

        async def get_file_content(self, file_id: str):
            return ConnectorDocument(
                file_id=file_id, name="test.txt", content=b"test", mime_type="text/plain", metadata={}
            )

        async def setup_subscription(self) -> str:
            return "sub123"

        async def handle_webhook(self, payload):  # noqa: ARG002
            return []

    connector = TestConnector(config={})
    result = await connector.test_connection()
    assert result is True
