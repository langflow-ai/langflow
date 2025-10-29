from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, Relationship, SQLModel


class ConnectorConnection(SQLModel, table=True):
    """Model for storing connector connections."""

    __tablename__ = "connector_connections"
    __table_args__ = (UniqueConstraint("user_id", "knowledge_base_id", "connector_type", "name"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    knowledge_base_id: str | None = Field(default=None, max_length=255, index=True)
    connector_type: str = Field(max_length=50, index=True)
    name: str = Field(max_length=255)
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    webhook_subscription_id: str | None = Field(default=None, max_length=255)
    webhook_secret: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    last_sync_at: datetime | None = Field(default=None)
    sync_status: str | None = Field(default=None, max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    oauth_token: Optional["ConnectorOAuthToken"] = Relationship(back_populates="connection", cascade_delete=True)
    sync_logs: list["ConnectorSyncLog"] = Relationship(back_populates="connection", cascade_delete=True)


class ConnectorOAuthToken(SQLModel, table=True):
    """Model for storing encrypted OAuth tokens."""

    __tablename__ = "connector_oauth_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    connection_id: UUID = Field(foreign_key="connector_connections.id", unique=True)
    encrypted_access_token: str = Field()
    encrypted_refresh_token: str | None = Field(default=None)
    token_expiry: datetime | None = Field(default=None)
    scopes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    provider_account_id: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    connection: ConnectorConnection = Relationship(back_populates="oauth_token")


class ConnectorSyncLog(SQLModel, table=True):
    """Model for tracking sync operations."""

    __tablename__ = "connector_sync_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    connection_id: UUID = Field(foreign_key="connector_connections.id", index=True)
    sync_type: str | None = Field(default=None, max_length=50)
    status: str = Field(max_length=50, default="pending")
    files_processed: int = Field(default=0)
    files_failed: int = Field(default=0)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = Field(default=None)
    error_message: str | None = Field(default=None)
    checkpoint: dict | None = Field(default=None, sa_column=Column(JSON))
    page_token: str | None = Field(default=None, max_length=500)

    # Relationships
    connection: ConnectorConnection = Relationship(back_populates="sync_logs")


class ConnectorDeadLetterQueue(SQLModel, table=True):
    """Model for storing failed sync operations that need manual intervention or retry."""

    __tablename__ = "connector_dead_letter_queue"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    connection_id: UUID = Field(foreign_key="connector_connections.id", index=True)
    operation_type: str = Field(max_length=50)  # sync, download, extract, etc.
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))  # Operation details
    error_category: str = Field(max_length=50)  # ErrorCategory enum value
    error_message: str | None = Field(default=None)
    error_details: dict | None = Field(default=None, sa_column=Column(JSON))
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    last_retry_at: datetime | None = Field(default=None)
    next_retry_at: datetime | None = Field(default=None)
    status: str = Field(default="pending", max_length=50)  # pending, retrying, failed, resolved
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = Field(default=None)

    # Relationships
    connection: ConnectorConnection = Relationship()
