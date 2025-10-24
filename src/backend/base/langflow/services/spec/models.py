"""Models for the spec service component validation and unified conversion."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class Component(BaseModel):
    """Component model for FlowConverter validation in spec service.

    This model represents a component in the Genesis specification system
    for use in unified conversion and validation processes.
    """

    id: str = Field(description="Unique identifier for the component")
    name: str = Field(description="Display name of the component")
    kind: str = Field(
        default="Tool",
        description="Component kind (e.g., Tool, Agent, LLM)"
    )
    type: str = Field(description="Component type identifier")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Component configuration parameters"
    )
    asTools: bool = Field(
        default=False,
        description="Whether this component can be used as a tool"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the component"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata for the component"
    )

    class Config:
        """Pydantic configuration."""
        extra = "allow"  # Allow additional fields for flexibility


class ValidationResult(BaseModel):
    """Result of component validation operations."""

    valid: bool = Field(description="Whether the validation passed")
    errors: list[str] = Field(
        default_factory=list,
        description="List of validation errors"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="List of validation warnings"
    )
    component_id: Optional[str] = Field(
        default=None,
        description="ID of the component that was validated"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional validation metadata"
    )


class ConversionContext(BaseModel):
    """Context information for component conversion operations."""

    source_format: str = Field(description="Source format (e.g., 'genesis')")
    target_format: str = Field(description="Target format (e.g., 'langflow')")
    conversion_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Options that control the conversion process"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context metadata"
    )