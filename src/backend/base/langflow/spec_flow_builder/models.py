"""Pydantic models for spec_flow_builder API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ValidateSpecRequest(BaseModel):
    """Request model for validating a YAML specification."""

    yaml_content: str = Field(..., description="YAML specification content to validate")


class ComponentStatus(BaseModel):
    """Status of a single component in the specification."""

    id: str = Field(..., description="Component ID from YAML")
    name: str = Field(..., description="Component name from YAML")
    yaml_type: str = Field(..., description="Component type from YAML (e.g., PromptComponent)")
    found: bool = Field(..., description="Whether component exists in catalog")
    catalog_name: Optional[str] = Field(None, description="Catalog component name if found (e.g., 'Prompt Template')")
    category: Optional[str] = Field(None, description="Component category if found (e.g., 'processing')")
    error: Optional[str] = Field(None, description="Error message if not found")


class ValidationReport(BaseModel):
    """Validation report for the entire specification."""

    valid: bool = Field(..., description="Overall validation status - True if all components found")
    total_components: int = Field(..., description="Total number of components in YAML")
    found_components: int = Field(..., description="Number of components found in catalog")
    missing_components: int = Field(..., description="Number of missing components")
    components: List[ComponentStatus] = Field(..., description="Detailed status for each component")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")


class CreateFlowRequest(BaseModel):
    """Request model for creating a flow from YAML specification."""

    yaml_content: str = Field(..., description="YAML specification content to convert to flow")
    flow_name: Optional[str] = Field(None, description="Optional custom name for the flow")
    folder_id: Optional[str] = Field(None, description="Optional folder ID to save the flow in")


class CreateFlowResponse(BaseModel):
    """Response model for flow creation."""

    success: bool = Field(..., description="Whether the flow was created successfully")
    message: str = Field(..., description="Success or error message")
    flow_id: Optional[str] = Field(None, description="ID of the created flow if successful")
    flow_name: Optional[str] = Field(None, description="Name of the created flow if successful")