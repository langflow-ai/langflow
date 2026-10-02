"""Durable OAuth consent binding and one-time callback state."""

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class ConnectionOAuth(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "connection_oauth"

    connection_id: UUID = Field(
        sa_column=sa.Column(
            sa.Uuid(), sa.ForeignKey("connection.id", ondelete="CASCADE"), primary_key=True, nullable=False
        )
    )
    generation: UUID = Field(default_factory=uuid4)
    user_id: UUID = Field(sa_column=sa.Column(sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False))
    registration_id: str = Field(max_length=120)
    config_digest: str = Field(max_length=64)
    state_digest: str | None = Field(default=None, max_length=64, unique=True)
    browser_digest: str | None = Field(default=None, max_length=64)
    encrypted_verifier: str | None = Field(default=None, sa_column=sa.Column(sa.Text(), nullable=True))
    scopes: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON(), nullable=False))
    expires_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
