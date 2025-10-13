from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, field_validator
from sqlalchemy import Text
from sqlmodel import JSON, Column, Field, SQLModel


class PublishedAgentBase(SQLModel):
    """Base model for PublishedAgent with simplified structure."""
    
    flow_id: UUID = Field(foreign_key="flow.id", index=True, description="ID of the flow being published")
    data: dict | None = Field(
        default=None, 
        sa_column=Column(JSON, nullable=True),
        description="Complete flow data including nodes, edges, and configuration"
    )
    category_id: str | None = Field(default=None, nullable=True, index=True, description="Category ID for organizing published agents")
    is_published: bool = Field(default=True, nullable=False, index=True, description="Published status flag")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        description="Timestamp when the agent was published"
    )
    deleted_at: datetime | None = Field(
        default=None,
        nullable=True,
        description="Timestamp when the agent was deleted (soft delete)"
    )
    display_name: str | None = Field(default=None, nullable=True, description="Custom display name for the published agent")
    description: str | None = Field(default=None, nullable=True, description="Custom description for the published agent")

    @field_validator("data")
    @classmethod
    def validate_flow_data(cls, v):
        """Validate that data contains required flow structure if provided."""
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("Flow data must be a valid JSON object")
        
        # Validate flow structure
        if v and not all(key in v for key in ["nodes", "edges"]):
            raise ValueError("Flow data must contain 'nodes' and 'edges' arrays")
        
        return v


class PublishedAgent(PublishedAgentBase, table=True):  # type: ignore[call-arg]
    """Database table model for published agents."""
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(index=True, foreign_key="user.id", nullable=True)

    def soft_delete(self):
        """Soft delete the published agent."""
        self.deleted_at = datetime.now(timezone.utc)
        self.is_published = False


class PublishedAgentCreate(SQLModel):
    """Schema for creating a new published agent."""
    flow_id: UUID
    category_id: str | None = None
    display_name: str | None = None  
    description: str | None = None   

class PublishedAgentRead(PublishedAgentBase):
    """Schema for reading published agent data."""
    id: UUID
    user_id: UUID | None


class PublishedAgentUpdate(SQLModel):
    """Schema for updating published agent data."""
    data: dict | None = None
    category_id: str | None = None
    is_published: bool | None = None
    display_name: str | None = None  
    description: str | None = None   # For customizing description

    @field_validator("data")
    @classmethod
    def validate_flow_data(cls, v):
        """Validate that data contains required flow structure if provided."""
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("Flow data must be a valid JSON object")
        
        # Validate flow structure
        if v and not all(key in v for key in ["nodes", "edges"]):
            raise ValueError("Flow data must contain 'nodes' and 'edges' arrays")
        
        return v


class PublishedAgentHeader(BaseModel):
    """Lightweight model for listing published agents without full flow data."""
    id: UUID
    flow_id: UUID
    category_id: str | None
    is_published: bool
    created_at: datetime
    deleted_at: datetime | None
    user_id: UUID | None
    display_name: str | None
    description: str | None