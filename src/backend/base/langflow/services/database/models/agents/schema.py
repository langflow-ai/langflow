"""Pydantic schemas for Agent API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """Request schema for creating an agent."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str = "You are a helpful assistant."
    tool_components: list[str] = Field(default_factory=list)
    icon: str | None = None


class AgentUpdate(BaseModel):
    """Request schema for updating an agent. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str | None = None
    tool_components: list[str] | None = None
    icon: str | None = None


class AgentRead(BaseModel):
    """Response schema for reading an agent."""

    id: UUID
    name: str
    description: str | None
    system_prompt: str
    tool_components: list[str]
    icon: str | None
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
