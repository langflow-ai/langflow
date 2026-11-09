"""Persist refresh token revocations without storing reusable credentials."""

from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class RevokedRefreshToken(SQLModel, table=True):
    __tablename__ = "revoked_refresh_token"

    token_digest: str = Field(primary_key=True, max_length=64)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
