"""Persistent storage model for A2A tasks.

Replaces the in-memory task store so A2A task state survives process
restarts and is shared across workers. ``flow_id`` is stored as a plain
string (not a foreign key) to match the protocol-level identifier and to
keep the table independent of flow lifecycle.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSONB on Postgres, JSON elsewhere (SQLite) — same variant the other
# JSON-bearing tables use.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")


class A2ATask(SQLModel, table=True):
    __tablename__ = "a2a_task"

    task_id: str = Field(primary_key=True, index=True)
    context_id: str = Field(index=True)
    flow_id: str = Field(index=True)
    state: str = Field(default="submitted", index=True)
    artifacts: list = Field(default_factory=list, sa_column=Column(JsonVariant, nullable=False))
    task_metadata: dict = Field(default_factory=dict, sa_column=Column(JsonVariant, nullable=False))
    status_message: dict | None = Field(default=None, sa_column=Column(JsonVariant, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    def to_a2a_dict(self) -> dict:
        """Serialize to the A2A Task dict shape used across the API."""
        status: dict = {"state": self.state, "timestamp": self.updated_at.isoformat()}
        if self.status_message:
            status["message"] = self.status_message
        return {
            "id": self.task_id,
            "kind": "task",
            "contextId": self.context_id,
            "status": status,
            "artifacts": self.artifacts or [],
            "metadata": self.task_metadata or {},
            "_created_at": self.created_at.isoformat(),
            "_updated_at": self.updated_at.isoformat(),
        }
