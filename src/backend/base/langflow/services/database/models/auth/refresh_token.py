"""Persist native refresh sessions without storing reusable credentials."""

from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class RefreshTokenSession(SQLModel, table=True):
    __tablename__ = "refresh_token_session"

    session_digest: str = Field(primary_key=True, max_length=64)
    user_id: UUIDstr = Field(foreign_key="user.id", ondelete="CASCADE", index=True, nullable=False)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    revoked: bool = Field(default=False)
