from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.connectors.schemas import (
    ConnectorCreate,
    ConnectorMetadata,
    ConnectorResponse,
    ConnectorUpdate,
    FileListResponse,
    OAuthCallback,
    OAuthURLResponse,
    SyncRequest,
    SyncResponse,
)
from pydantic import ValidationError


class TestConnectorCreate:
    """Test ConnectorCreate schema."""

    def test_connector_create_valid(self):
        """Test creating ConnectorCreate with valid data."""
        data = {"connector_type": "google_drive", "name": "My Drive", "config": {"folder": "root"}}

        schema = ConnectorCreate(**data)
        assert schema.connector_type == "google_drive"
        assert schema.name == "My Drive"
        assert schema.config == {"folder": "root"}
        assert schema.knowledge_base_id is None

    def test_connector_create_with_knowledge_base(self):
        """Test ConnectorCreate with knowledge_base_id."""
        data = {
            "connector_type": "onedrive",
            "name": "OneDrive Connection",
            "knowledge_base_id": "kb-123",
            "config": {},
        }

        schema = ConnectorCreate(**data)
        assert schema.knowledge_base_id == "kb-123"

    def test_connector_create_missing_required_fields(self):
        """Test ConnectorCreate fails without required fields."""
        with pytest.raises(ValidationError):
            ConnectorCreate(name="Test")  # Missing connector_type

    def test_connector_create_default_config(self):
        """Test ConnectorCreate has default empty config."""
        data = {"connector_type": "google_drive", "name": "Test Drive"}

        schema = ConnectorCreate(**data)
        assert schema.config == {}


class TestConnectorResponse:
    """Test ConnectorResponse schema."""

    def test_connector_response_valid(self):
        """Test creating ConnectorResponse with valid data."""
        conn_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "id": conn_id,
            "name": "Test Connection",
            "connector_type": "google_drive",
            "is_authenticated": True,
            "created_at": now,
            "updated_at": now,
        }

        schema = ConnectorResponse(**data)
        assert schema.id == conn_id
        assert schema.name == "Test Connection"
        assert schema.connector_type == "google_drive"
        assert schema.is_authenticated is True

    def test_connector_response_optional_fields(self):
        """Test ConnectorResponse with optional fields."""
        conn_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "id": conn_id,
            "name": "Test",
            "connector_type": "onedrive",
            "created_at": now,
            "updated_at": now,
            "last_sync": now,
            "sync_status": "completed",
            "file_count": 42,
            "knowledge_base_id": "kb-456",
        }

        schema = ConnectorResponse(**data)
        assert schema.last_sync == now
        assert schema.sync_status == "completed"
        assert schema.file_count == 42
        assert schema.knowledge_base_id == "kb-456"

    def test_connector_response_defaults(self):
        """Test ConnectorResponse default values."""
        conn_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {"id": conn_id, "name": "Test", "connector_type": "google_drive", "created_at": now, "updated_at": now}

        schema = ConnectorResponse(**data)
        assert schema.is_authenticated is False
        assert schema.last_sync is None
        assert schema.sync_status is None
        assert schema.file_count is None


class TestConnectorUpdate:
    """Test ConnectorUpdate schema."""

    def test_connector_update_all_fields(self):
        """Test ConnectorUpdate with all fields."""
        data = {"name": "Updated Name", "config": {"new_key": "new_value"}, "is_active": False}

        schema = ConnectorUpdate(**data)
        assert schema.name == "Updated Name"
        assert schema.config == {"new_key": "new_value"}
        assert schema.is_active is False

    def test_connector_update_partial(self):
        """Test ConnectorUpdate with partial data."""
        data = {"name": "New Name"}

        schema = ConnectorUpdate(**data)
        assert schema.name == "New Name"
        assert schema.config is None
        assert schema.is_active is None

    def test_connector_update_empty(self):
        """Test ConnectorUpdate with no data."""
        schema = ConnectorUpdate()
        assert schema.name is None
        assert schema.config is None
        assert schema.is_active is None


class TestSyncRequest:
    """Test SyncRequest schema."""

    def test_sync_request_defaults(self):
        """Test SyncRequest default values."""
        schema = SyncRequest()
        assert schema.selected_files is None
        assert schema.max_files == 100
        assert schema.force_refresh is False

    def test_sync_request_with_selected_files(self):
        """Test SyncRequest with selected files."""
        data = {"selected_files": ["file1", "file2", "file3"], "max_files": 50, "force_refresh": True}

        schema = SyncRequest(**data)
        assert schema.selected_files == ["file1", "file2", "file3"]
        assert schema.max_files == 50
        assert schema.force_refresh is True

    def test_sync_request_custom_max_files(self):
        """Test SyncRequest with custom max_files."""
        data = {"max_files": 200}

        schema = SyncRequest(**data)
        assert schema.max_files == 200


class TestSyncResponse:
    """Test SyncResponse schema."""

    def test_sync_response_valid(self):
        """Test creating SyncResponse with valid data."""
        data = {"task_id": "task-123", "status": "pending", "message": "Sync started"}

        schema = SyncResponse(**data)
        assert schema.task_id == "task-123"
        assert schema.status == "pending"
        assert schema.message == "Sync started"

    def test_sync_response_required_fields(self):
        """Test SyncResponse requires all fields."""
        with pytest.raises(ValidationError):
            SyncResponse(task_id="task-123", status="pending")  # Missing message


class TestOAuthCallback:
    """Test OAuthCallback schema."""

    def test_oauth_callback_with_state(self):
        """Test OAuthCallback with state."""
        data = {"code": "auth-code-123", "state": "state-token-456"}

        schema = OAuthCallback(**data)
        assert schema.code == "auth-code-123"
        assert schema.state == "state-token-456"

    def test_oauth_callback_without_state(self):
        """Test OAuthCallback without state."""
        data = {"code": "auth-code-123"}

        schema = OAuthCallback(**data)
        assert schema.code == "auth-code-123"
        assert schema.state is None

    def test_oauth_callback_missing_code(self):
        """Test OAuthCallback requires code."""
        with pytest.raises(ValidationError):
            OAuthCallback(state="state-token")  # Missing code


class TestOAuthURLResponse:
    """Test OAuthURLResponse schema."""

    def test_oauth_url_response_valid(self):
        """Test OAuthURLResponse with valid data."""
        data = {"authorization_url": "https://accounts.google.com/o/oauth2/auth?...", "state": "csrf-token-123"}

        schema = OAuthURLResponse(**data)
        assert "accounts.google.com" in schema.authorization_url
        assert schema.state == "csrf-token-123"

    def test_oauth_url_response_required_fields(self):
        """Test OAuthURLResponse requires both fields."""
        with pytest.raises(ValidationError):
            OAuthURLResponse(authorization_url="https://example.com")  # Missing state


class TestFileListResponse:
    """Test FileListResponse schema."""

    def test_file_list_response_with_files(self):
        """Test FileListResponse with files."""
        data = {
            "files": [{"id": "file1", "name": "doc.pdf"}, {"id": "file2", "name": "sheet.xlsx"}],
            "next_page_token": "token-123",
            "total_count": 2,
        }

        schema = FileListResponse(**data)
        assert len(schema.files) == 2
        assert schema.files[0]["id"] == "file1"
        assert schema.next_page_token == "token-123"  # noqa: S105
        assert schema.total_count == 2

    def test_file_list_response_empty(self):
        """Test FileListResponse with no files."""
        data = {"files": []}

        schema = FileListResponse(**data)
        assert schema.files == []
        assert schema.next_page_token is None
        assert schema.total_count is None

    def test_file_list_response_required_files(self):
        """Test FileListResponse requires files field."""
        with pytest.raises(ValidationError):
            FileListResponse(next_page_token="token")  # Missing files  # noqa: S106


class TestConnectorMetadata:
    """Test ConnectorMetadata schema."""

    def test_connector_metadata_full(self):
        """Test ConnectorMetadata with all fields."""
        data = {
            "connector_type": "google_drive",
            "name": "Google Drive",
            "description": "Connect to Google Drive",
            "icon": "google-drive-icon",
            "available": True,
            "required_scopes": ["drive.readonly"],
            "supported_mime_types": ["text/*", "application/pdf"],
        }

        schema = ConnectorMetadata(**data)
        assert schema.connector_type == "google_drive"
        assert schema.name == "Google Drive"
        assert schema.description == "Connect to Google Drive"
        assert schema.icon == "google-drive-icon"
        assert schema.available is True
        assert len(schema.required_scopes) == 1
        assert len(schema.supported_mime_types) == 2

    def test_connector_metadata_defaults(self):
        """Test ConnectorMetadata default values."""
        data = {
            "connector_type": "custom",
            "name": "Custom Connector",
            "description": "Custom",
            "icon": "icon",
            "available": False,
        }

        schema = ConnectorMetadata(**data)
        assert schema.required_scopes == []
        assert schema.supported_mime_types == []

    def test_connector_metadata_required_fields(self):
        """Test ConnectorMetadata requires core fields."""
        with pytest.raises(ValidationError):
            ConnectorMetadata(connector_type="test", name="Test")  # Missing description, icon, available
