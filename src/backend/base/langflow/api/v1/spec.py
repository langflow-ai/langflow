"""Genesis Specification to Flow Conversion API endpoints."""

from __future__ import annotations

from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser
from langflow.services.deps import get_session
from langflow.services.spec.service import SpecService
from langflow.logging import logger

# Build router
router = APIRouter(prefix="/spec", tags=["Specification"])


class SpecConvertRequest(BaseModel):
    """Request model for spec conversion."""
    spec_yaml: str = Field(..., description="YAML specification string")
    variables: Optional[Dict[str, Any]] = Field(None, description="Runtime variables for resolution")
    tweaks: Optional[Dict[str, Any]] = Field(None, description="Component field tweaks to apply")


class SpecConvertResponse(BaseModel):
    """Response model for spec conversion."""
    flow: Dict[str, Any] = Field(..., description="Converted Langflow flow JSON")
    success: bool = Field(True, description="Conversion success status")


# SpecCreateFlowRequest and SpecCreateFlowResponse removed -
# Now using existing flows API for flow creation


class SpecValidationRequest(BaseModel):
    """Request model for spec validation."""
    spec_yaml: str = Field(..., description="YAML specification string")


class SpecValidationResponse(BaseModel):
    """Response model for spec validation."""
    valid: bool = Field(..., description="Validation result")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class ComponentsResponse(BaseModel):
    """Response model for available components."""
    components: Dict[str, Any] = Field(..., description="Available components and their configurations")


class ComponentMappingRequest(BaseModel):
    """Request model for component mapping info."""
    spec_type: str = Field(..., description="Specification component type")


class ComponentMappingResponse(BaseModel):
    """Response model for component mapping info."""
    spec_type: str = Field(..., description="Original spec type")
    langflow_component: str = Field(..., description="Mapped Langflow component")
    config: Dict[str, Any] = Field(default_factory=dict, description="Component configuration")
    input_field: Optional[str] = Field(None, description="Input field name")
    output_field: Optional[str] = Field(None, description="Output field name")
    output_types: list[str] = Field(default_factory=list, description="Expected output types")
    is_tool: bool = Field(..., description="Whether component is used as a tool")


@router.post("/convert", response_model=SpecConvertResponse)
async def convert_spec_to_flow(
    request: SpecConvertRequest,
    _current_user: CurrentActiveUser
) -> SpecConvertResponse:
    """
    Convert YAML specification to Langflow JSON.

    Takes a Genesis agent specification in YAML format and converts it to
    Langflow flow JSON with proper edge connections and component mappings.
    """
    try:
        service = SpecService()
        flow = await service.convert_spec_to_flow(
            spec_yaml=request.spec_yaml,
            variables=request.variables,
            tweaks=request.tweaks
        )

        return SpecConvertResponse(flow=flow, success=True)

    except ValueError as e:
        logger.error(f"Spec conversion error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error during spec conversion: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during conversion") from e


# Removed create_flow_from_spec endpoint - now using two-step process:
# 1. Convert spec using /convert endpoint
# 2. Create flow using existing /api/v1/flows endpoint


@router.post("/validate", response_model=SpecValidationResponse)
async def validate_spec(
    request: SpecValidationRequest,
    _current_user: CurrentActiveUser
) -> SpecValidationResponse:
    """
    Validate specification without converting.

    Performs validation on the YAML specification to check for structure,
    component types, and other potential issues without full conversion.
    """
    try:
        service = SpecService()
        result = service.validate_spec(request.spec_yaml)

        return SpecValidationResponse(
            valid=result["valid"],
            errors=result["errors"],
            warnings=result["warnings"]
        )

    except Exception as e:
        logger.error(f"Spec validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during validation") from e


@router.get("/components", response_model=ComponentsResponse)
async def get_available_components(
    _current_user: CurrentActiveUser
) -> ComponentsResponse:
    """
    Get list of available components with their configurations.

    Returns all available Genesis component types that can be used in
    specifications, along with their options and input/output configurations.
    """
    try:
        service = SpecService()
        components = service.get_available_components()

        return ComponentsResponse(components=components)

    except Exception as e:
        logger.error(f"Error fetching components: {e}")
        raise HTTPException(status_code=500, detail="Internal server error fetching components") from e


@router.post("/component-mapping", response_model=ComponentMappingResponse)
async def get_component_mapping(
    request: ComponentMappingRequest,
    _current_user: CurrentActiveUser
) -> ComponentMappingResponse:
    """
    Get information about how a specification type maps to components.

    Provides detailed information about how a Genesis specification component
    type maps to Langflow components, including configurations and I/O details.
    """
    try:
        service = SpecService()
        mapping_info = service.get_component_mapping_info(request.spec_type)

        return ComponentMappingResponse(**mapping_info)

    except Exception as e:
        logger.error(f"Error getting component mapping: {e}")
        raise HTTPException(status_code=500, detail="Internal server error getting mapping") from e