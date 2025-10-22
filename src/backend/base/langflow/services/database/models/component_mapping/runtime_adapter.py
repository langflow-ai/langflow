"""Runtime adapter database model for multi-runtime component support."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import Index, String, Text, Enum as SQLAlchemyEnum
from sqlmodel import JSON, Column, Field, SQLModel


class RuntimeTypeEnum(str, Enum):
    """Supported runtime types."""

    LANGFLOW = "langflow"
    TEMPORAL = "temporal"
    KAFKA = "kafka"
    AIRFLOW = "airflow"
    DAGSTER = "dagster"


class RuntimeAdapterBase(SQLModel):
    """Base model for runtime adapters."""

    model_config = {"use_enum_values": True}

    genesis_type: str = Field(
        max_length=100,
        index=True,
        description="Genesis component type this adapter supports"
    )
    runtime_type: RuntimeTypeEnum = Field(
        description="Target runtime for this adapter"
    )
    target_component: str = Field(
        max_length=100,
        description="Target component name in the runtime (e.g., 'EHRConnector')"
    )
    adapter_config: Optional[dict] = Field(
        default=None,
        description="Runtime-specific configuration and transformation rules"
    )
    version: str = Field(
        default="1.0.0",
        max_length=20,
        description="Version of the adapter"
    )
    compliance_rules: Optional[dict] = Field(
        default=None,
        description="Healthcare compliance validation rules for this runtime"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of this runtime adapter"
    )
    active: bool = Field(
        default=True,
        description="Whether this adapter is active"
    )
    priority: int = Field(
        default=100,
        description="Priority for adapter selection (lower = higher priority)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this adapter was created"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this adapter was last updated"
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

    @field_validator("target_component")
    @classmethod
    def validate_target_component(cls, v: str) -> str:
        """Validate target component name."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Target component name cannot be empty")
        return v.strip()

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format."""
        import re
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError("Version must follow semantic versioning format (e.g., '1.0.0')")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """Validate priority value."""
        if v < 0:
            raise ValueError("Priority must be non-negative")
        return v

    @field_validator("adapter_config", "compliance_rules")
    @classmethod
    def validate_json_fields(cls, v):
        """Validate JSON fields are properly formatted."""
        if v is not None and not isinstance(v, dict):
            raise ValueError("Field must be a valid dictionary")
        return v


class RuntimeAdapter(RuntimeAdapterBase, table=True):
    """Database table for runtime adapters."""

    __tablename__ = "runtime_adapters"
    model_config = {"use_enum_values": True}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the adapter"
    )
    genesis_type: str = Field(
        max_length=100,
        sa_column=Column(String(100), index=True, nullable=False),
        description="Genesis component type"
    )
    runtime_type: RuntimeTypeEnum = Field(
        sa_column=Column(SQLAlchemyEnum(RuntimeTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False),
        description="Target runtime for this adapter"
    )
    target_component: str = Field(
        max_length=100,
        sa_column=Column(String(100), nullable=False),
        description="Target component name"
    )
    adapter_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Runtime-specific configuration"
    )
    compliance_rules: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Compliance validation rules"
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Adapter description"
    )

    # Create indexes for performance
    __table_args__ = (
        Index("idx_genesis_runtime_active", "genesis_type", "runtime_type", "active"),
        Index("idx_runtime_active", "runtime_type", "active"),
        Index("idx_priority_active", "priority", "active"),
        Index("idx_target_component", "target_component"),
    )


class RuntimeAdapterCreate(RuntimeAdapterBase):
    """Schema for creating runtime adapters."""
    model_config = {"use_enum_values": True}


class RuntimeAdapterRead(RuntimeAdapterBase):
    """Schema for reading runtime adapters."""
    model_config = {"use_enum_values": True}

    id: UUID


class RuntimeAdapterUpdate(SQLModel):
    """Schema for updating runtime adapters."""
    model_config = {"use_enum_values": True}

    target_component: Optional[str] = None
    adapter_config: Optional[dict] = None
    version: Optional[str] = None
    compliance_rules: Optional[dict] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    priority: Optional[int] = None
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("target_component")
    @classmethod
    def validate_target_component(cls, v: Optional[str]) -> Optional[str]:
        """Validate target component name if provided."""
        if v is not None:
            if not v or len(v.strip()) == 0:
                raise ValueError("Target component name cannot be empty")
            return v.strip()
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: Optional[str]) -> Optional[str]:
        """Validate version format if provided."""
        if v is not None:
            import re
            if not re.match(r"^\d+\.\d+\.\d+$", v):
                raise ValueError("Version must follow semantic versioning format (e.g., '1.0.0')")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[int]) -> Optional[int]:
        """Validate priority value if provided."""
        if v is not None and v < 0:
            raise ValueError("Priority must be non-negative")
        return v