from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectorCreate(BaseModel):
    """Schema for creating a connector."""

    connector_type: str = Field(..., description="Type of connector")
    name: str = Field(..., description="Display name")
    knowledge_base_id: str | None = Field(None, description="Associated KB ID")
    config: dict[str, Any] = Field(default_factory=dict, description="Connector config")


class ConnectorResponse(BaseModel):
    """Schema for connector response."""

    id: UUID
    name: str
    connector_type: str
    is_authenticated: bool = False
    last_sync: datetime | None = None
    sync_status: str | None = None
    file_count: int | None = None
    knowledge_base_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ConnectorUpdate(BaseModel):
    """Schema for updating a connector."""

    name: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class SyncRequest(BaseModel):
    """Schema for sync request."""

    selected_files: list[str] | None = Field(None, description="Specific files to sync")
    max_files: int = Field(100, description="Maximum files to sync")
    force_refresh: bool = Field(default=False, description="Force refresh all files")


class SyncResponse(BaseModel):
    """Schema for sync response."""

    task_id: str
    status: str
    message: str


class OAuthCallback(BaseModel):
    """Schema for OAuth callback."""

    code: str = Field(..., description="Authorization code")
    state: str | None = Field(None, description="State token")


class OAuthURLResponse(BaseModel):
    """Schema for OAuth URL response."""

    authorization_url: str
    state: str


class FileListResponse(BaseModel):
    """Schema for file list response."""

    files: list[dict[str, Any]]
    next_page_token: str | None = None
    total_count: int | None = None


class ConnectorMetadata(BaseModel):
    """Schema for connector metadata."""

    connector_type: str
    name: str
    description: str
    icon: str
    available: bool
    required_scopes: list[str] = []
    supported_mime_types: list[str] = []
