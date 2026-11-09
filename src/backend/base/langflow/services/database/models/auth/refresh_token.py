"""Persist native refresh sessions without storing reusable credentials."""

from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class RefreshTokenSession(SQLModel, table=True):
    __tablename__ = "refresh_token_session"

    session_digest: str = Field(primary_key=True, max_length=64)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    revoked: bool = Field(default=False)
