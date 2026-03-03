"""Agent database model for the Agent Builder feature."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Text
from sqlmodel import JSON, Field, SQLModel


class AgentBase(SQLModel):
    """Shared fields between Agent table and API schemas."""

    name: str = Field(index=True, max_length=255)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    system_prompt: str = Field(
        default="You are a helpful assistant.",
        sa_column=Column(Text, nullable=False),
    )
    tool_components: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    icon: str | None = Field(default=None, max_length=255)


class Agent(AgentBase, table=True):  # type: ignore[call-arg]
    """Persisted agent configuration.

    Agents are lightweight configs that dynamically generate flow JSON
    at execution time. Model selection happens per-chat-message, not
    at creation time.
    """

    __tablename__ = "agent"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
