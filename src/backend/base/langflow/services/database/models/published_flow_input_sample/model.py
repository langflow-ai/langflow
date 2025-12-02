"""Published Flow Input Sample database model for storing sample inputs and outputs."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from uuid import UUID, uuid4

from sqlalchemy import Column, Text, ForeignKey, Index
from sqlmodel import JSON, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.published_flow.model import PublishedFlow


class PublishedFlowInputSampleBase(SQLModel):
    """Base model for published flow input samples."""
    
    storage_account: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    container_name: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    file_names: List[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    sample_text: List[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    sample_output: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublishedFlowInputSample(PublishedFlowInputSampleBase, table=True):
    """Published Flow Input Sample table model."""
    
    __tablename__ = "published_flow_input_sample"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    published_flow_id: UUID = Field(
        foreign_key="published_flow.id", 
        nullable=False, 
        index=True
    )
    
    # Relationships
    published_flow: Optional["PublishedFlow"] = Relationship(
        back_populates="input_samples",
    )
    
    __table_args__ = (
        Index("ix_published_flow_input_sample_published_flow_id", "published_flow_id"),
    )


class PublishedFlowInputSampleCreate(SQLModel):
    """Schema for creating a published flow input sample."""
    
    storage_account: str | None = None
    container_name: str | None = None
    file_names: List[str] | None = None
    sample_text: List[str] | None = None
    sample_output: dict | None = None


class PublishedFlowInputSampleRead(PublishedFlowInputSampleBase):
    """Schema for reading a published flow input sample."""
    
    id: UUID
    published_flow_id: UUID