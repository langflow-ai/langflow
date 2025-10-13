"""Genesis Specification to Flow Conversion API endpoints."""

from __future__ import annotations

from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import DbSession
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
    request: SpecConvertRequest
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
    request: SpecValidationRequest
) -> SpecValidationResponse:
    """
    Validate specification without converting.

    Performs enhanced validation on the YAML specification to check for structure,
    component existence, connections, and healthcare-specific compliance.
    """
    try:
        service = SpecService()
        result = await service.validate_spec(request.spec_yaml)

        return SpecValidationResponse(
            valid=result["valid"],
            errors=result["errors"],
            warnings=result["warnings"]
        )

    except Exception as e:
        logger.error(f"Spec validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during validation") from e


@router.get("/components", response_model=ComponentsResponse)
async def get_available_components() -> ComponentsResponse:
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
    request: ComponentMappingRequest
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


class KnowledgeRequest(BaseModel):
    """Request model for knowledge endpoint."""
    query_type: str = Field(default="all", description="Type of knowledge: components, patterns, specifications, or all")
    reload_cache: bool = Field(default=False, description="Force reload from disk")


class KnowledgeResponse(BaseModel):
    """Response model for knowledge endpoint."""
    success: bool = Field(..., description="Success status")
    knowledge: Dict[str, Any] = Field(..., description="Knowledge data")
    message: str = Field(..., description="Status message")


@router.post("/knowledge", response_model=KnowledgeResponse)
async def get_knowledge(
    request: KnowledgeRequest
) -> KnowledgeResponse:
    """
    Get available components, patterns, and specifications.

    Returns knowledge about available Genesis components, patterns that can be used,
    and example specifications from the library.
    """
    try:
        # Import the mapper directly to avoid recursion through KnowledgeLoader
        from langflow.custom.genesis.spec.mapper import ComponentMapper
        from pathlib import Path
        import json
        import yaml

        knowledge = {}

        # Get components from mapper
        if request.query_type in ["components", "all"]:
            mapper = ComponentMapper()
            components = {}

            # Get all component mappings from different categories
            all_mappings = {}
            all_mappings.update(mapper.AUTONOMIZE_MODELS)
            all_mappings.update(mapper.MCP_MAPPINGS)
            all_mappings.update(mapper.STANDARD_MAPPINGS)

            # Convert to knowledge format
            for spec_type, mapping_info in all_mappings.items():
                components[spec_type] = {
                    "component": mapping_info.get("component", ""),
                    "description": f"Genesis component type {spec_type}",
                    "config": mapping_info.get("config", {}),
                    "is_tool": mapper.is_tool_component(spec_type)
                }

            knowledge["components"] = components

        # Get patterns from disk if requested
        if request.query_type in ["patterns", "all"]:
            base_path = Path(__file__).parent.parent.parent / "specifications_library"
            patterns_file = base_path / "documentation" / "patterns" / "pattern-catalog.md"

            patterns = {}
            if patterns_file.exists():
                # Simple pattern extraction from markdown
                content = patterns_file.read_text()
                # Extract pattern names (basic implementation)
                import re
                pattern_matches = re.findall(r'## (.*?) Pattern', content)
                for pattern_name in pattern_matches:
                    patterns[pattern_name.lower().replace(' ', '_')] = {
                        "name": pattern_name,
                        "description": f"{pattern_name} pattern for agent specifications"
                    }

            knowledge["patterns"] = patterns

        # Get specifications from disk if requested
        if request.query_type in ["specifications", "all"]:
            base_path = Path(__file__).parent.parent.parent / "specifications_library"
            specs = {}

            # Walk through all YAML files in specifications_library
            for spec_file in base_path.rglob("*.yaml"):
                if "documentation" not in str(spec_file):
                    try:
                        with open(spec_file, 'r') as f:
                            spec_data = yaml.safe_load(f)
                            if spec_data and "name" in spec_data:
                                spec_key = spec_file.stem
                                specs[spec_key] = {
                                    "name": spec_data.get("name"),
                                    "description": spec_data.get("description", ""),
                                    "kind": spec_data.get("kind", ""),
                                    "path": str(spec_file.relative_to(base_path))
                                }
                    except Exception as e:
                        logger.warning(f"Could not load spec from {spec_file}: {e}")

            knowledge["specifications"] = specs

        return KnowledgeResponse(
            success=True,
            knowledge=knowledge,
            message=f"Loaded {request.query_type} knowledge successfully"
        )

    except Exception as e:
        logger.error(f"Error loading knowledge: {e}")
        raise HTTPException(status_code=500, detail="Internal server error loading knowledge") from e


