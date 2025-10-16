"""Component mapping database model for runtime-agnostic component mappings."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import Index, String, Text, text
from sqlmodel import JSON, Column, Field, SQLModel


class ComponentCategoryEnum(str, Enum):
    """Component categories for organizing mappings."""

    HEALTHCARE = "healthcare"
    AGENT = "agent"
    TOOL = "tool"
    DATA = "data"
    PROMPT = "prompt"
    MEMORY = "memory"
    LLM = "llm"
    EMBEDDING = "embedding"
    VECTOR_STORE = "vector_store"
    IO = "io"
    PROCESSING = "processing"
    INTEGRATION = "integration"


class ComponentMappingBase(SQLModel):
    """Base model for component mappings."""

    genesis_type: str = Field(
        max_length=100,
        index=True,
        description="Genesis component type (e.g., 'genesis:ehr_connector')"
    )
    base_config: Optional[dict] = Field(
        default=None,
        description="Default configuration for the component"
    )
    io_mapping: Optional[dict] = Field(
        default=None,
        description="Input/output field mappings and type information"
    )
    component_category: ComponentCategoryEnum = Field(
        default=ComponentCategoryEnum.TOOL,
        description="Category for organizing components"
    )
    healthcare_metadata: Optional[dict] = Field(
        default=None,
        description="HIPAA compliance, medical standards, and healthcare-specific metadata"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the component"
    )
    version: str = Field(
        default="1.0.0",
        max_length=20,
        description="Version of the component mapping"
    )
    active: bool = Field(
        default=True,
        description="Whether this mapping is active and should be used"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this mapping was created"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this mapping was last updated"
    )

    @field_validator("genesis_type")
    @classmethod
    def validate_genesis_type(cls, v: str) -> str:
        """Validate genesis type format."""
        if not v.startswith("genesis:"):
            raise ValueError("Genesis type must start with 'genesis:'")
        if len(v) < 9:  # "genesis:" + at least 1 char
            raise ValueError("Genesis type must have content after 'genesis:'")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format (simple semantic versioning)."""
        import re
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError("Version must follow semantic versioning format (e.g., '1.0.0')")
        return v

    @field_validator("healthcare_metadata", "base_config", "io_mapping")
    @classmethod
    def validate_json_fields(cls, v):
        """Validate JSON fields are properly formatted."""
        if v is not None and not isinstance(v, dict):
            raise ValueError("Field must be a valid dictionary")
        return v


class ComponentMapping(ComponentMappingBase, table=True):
    """Database table for component mappings."""

    __tablename__ = "component_mappings"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the mapping"
    )
    genesis_type: str = Field(
        max_length=100,
        sa_column=Column(String(100), index=True, nullable=False),
        description="Genesis component type"
    )
    base_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Default configuration"
    )
    io_mapping: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="I/O mappings"
    )
    healthcare_metadata: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Healthcare compliance metadata"
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Component description"
    )

    # Create indexes for performance
    __table_args__ = (
        Index("idx_genesis_type_active", "genesis_type", "active"),
        Index("idx_category_active", "component_category", "active"),
        Index("idx_version_active", "version", "active"),
        Index("idx_created_at", "created_at"),
    )


class ComponentMappingCreate(ComponentMappingBase):
    """Schema for creating component mappings."""
    pass


class ComponentMappingRead(ComponentMappingBase):
    """Schema for reading component mappings."""

    id: UUID


class ComponentMappingUpdate(SQLModel):
    """Schema for updating component mappings."""

    base_config: Optional[dict] = None
    io_mapping: Optional[dict] = None
    component_category: Optional[ComponentCategoryEnum] = None
    healthcare_metadata: Optional[dict] = None
    description: Optional[str] = None
    version: Optional[str] = None
    active: Optional[bool] = None
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: Optional[str]) -> Optional[str]:
        """Validate version format if provided."""
        if v is not None:
            import re
            if not re.match(r"^\d+\.\d+\.\d+$", v):
                raise ValueError("Version must follow semantic versioning format (e.g., '1.0.0')")
        return v