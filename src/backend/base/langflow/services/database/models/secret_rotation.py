"""A receipt for a fully verified database rewrap, not external key activation."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


class SecretRotation(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "secret_rotation"

    id: str = Field(default_factory=lambda: str(uuid4()), sa_column=Column(String(36), primary_key=True))
    instance_uid: str | None = Field(default=None, max_length=128)
    old_fingerprint: str = Field(max_length=64)
    new_fingerprint: str = Field(max_length=64)
    backup_sha256: str = Field(max_length=64)
    rotated_values: int
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False)
    )
