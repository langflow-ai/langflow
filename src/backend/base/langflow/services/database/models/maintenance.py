"""The shared maintenance switch used by every editor and worker."""

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.sql.naming import conv
from sqlmodel import Field, SQLModel

MAINTENANCE_ID = 1
REASON_MAX_LENGTH = 1024


class MaintenanceState(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "maintenance_state"
    __table_args__ = (sa.CheckConstraint("id = 1", name=conv("ck_maintenance_state_singleton")),)

    id: int = Field(default=MAINTENANCE_ID, primary_key=True)
    enabled: bool = Field(default=False, sa_column=sa.Column(sa.Boolean(), nullable=False, server_default=sa.false()))
    reason: str | None = Field(default=None, sa_column=sa.Column(sa.String(REASON_MAX_LENGTH), nullable=True))
    set_by: UUID | None = Field(default=None, sa_column=sa.Column(sa.Uuid(), nullable=True))
    set_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
