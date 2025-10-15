"""Genesis Specification to Flow Conversion API endpoints."""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from pathlib import Path
import yaml

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import DbSession, CurrentActiveUser
from langflow.services.spec.service import SpecService
from langflow.services.database.models.flow import Flow
from langflow.logging import logger

# Build router
router = APIRouter(prefix="/spec", tags=["Specification"])

# Base path to specifications library
SPEC_LIBRARY_BASE_PATH = Path(__file__).parent.parent.parent / "specifications_library" / "agents"


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


# New models for specification library endpoints
class CreateFlowFromLibraryRequest(BaseModel):
    """Request to create flow from specification library."""
    specification_file: str = Field(
        ...,
        description="Relative path to YAML file from specifications_library/agents/",
        examples=["multi-tool/accumulator-check-agent.yaml", "simple/classification-agent.yaml"]
    )
    folder_id: Optional[UUID] = Field(None, description="Optional folder ID to organize the flow")


class CreateFlowFromLibraryResponse(BaseModel):
    """Response after creating flow from specification library."""
    success: bool = Field(..., description="Creation success status")
    flow_id: Optional[str] = Field(None, description="Created flow ID")
    flow_name: Optional[str] = Field(None, description="Created flow name")
    specification_urn: Optional[str] = Field(None, description="Specification URN from YAML")
    specification_file: str = Field(..., description="Source specification file path")
    message: str = Field(..., description="Success/error message")
    error: Optional[str] = Field(None, description="Error type if failed")
    details: Optional[str] = Field(None, description="Additional error details")


class AvailableSpecification(BaseModel):
    """Available specification metadata."""
    file_path: str = Field(..., description="Relative path from specifications_library/agents/")
    name: str = Field(..., description="Agent name from YAML")
    specification_urn: str = Field(..., description="Specification URN")
    kind: str = Field(..., description="Agent kind (Single Agent, Multi Agent, etc.)")
    subdomain: Optional[str] = Field(None, description="Sub-domain category")
    description: Optional[str] = Field(None, description="Agent description")


class AvailableSpecificationsResponse(BaseModel):
    """Response listing available specifications."""
    success: bool = Field(True, description="Success status")
    total: int = Field(..., description="Total number of available specifications")
    specifications: List[AvailableSpecification] = Field(..., description="List of specifications")


@router.get("/available-specifications", response_model=AvailableSpecificationsResponse)
async def list_available_specifications() -> AvailableSpecificationsResponse:
    """
    List all YAML specifications available in the library.

    Returns metadata for all specification files that can be converted to flows.
    Use the file_path from this response in the create-flow-from-library endpoint.
    """
    specifications = []

    try:
        # Find all YAML files in specifications_library/agents
        yaml_files = list(SPEC_LIBRARY_BASE_PATH.rglob("*.yaml"))

        for yaml_file in yaml_files:
            try:
                # Read and parse YAML
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    spec_dict = yaml.safe_load(f.read())

                if not spec_dict:
                    continue

                # Get relative path from base
                relative_path = yaml_file.relative_to(SPEC_LIBRARY_BASE_PATH)

                # Extract metadata
                specifications.append(AvailableSpecification(
                    file_path=str(relative_path),
                    name=spec_dict.get('name', yaml_file.stem),
                    specification_urn=spec_dict.get('id', ''),
                    kind=spec_dict.get('kind', 'Unknown'),
                    subdomain=spec_dict.get('subDomain'),
                    description=spec_dict.get('description')
                ))

            except Exception as e:
                logger.warning(f"Could not read specification {yaml_file.name}: {e}")
                continue

        # Sort by file path
        specifications.sort(key=lambda s: s.file_path)

        return AvailableSpecificationsResponse(
            success=True,
            total=len(specifications),
            specifications=specifications
        )

    except Exception as e:
        logger.error(f"Error listing specifications: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to list available specifications"
        )


@router.post("/create-flow-from-library", response_model=CreateFlowFromLibraryResponse, status_code=201)
async def create_flow_from_specification_library(
    *,
    request: CreateFlowFromLibraryRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> CreateFlowFromLibraryResponse:
    """
    Create a Langflow flow from YAML specification in the library.

    Reads the specified YAML file from specifications_library/agents/ directory,
    converts it to a Langflow flow, and saves it to the database using the
    authenticated current user as the flow owner.

    Use GET /api/v1/spec/available-specifications to see all available files.
    """
    try:
        # Construct full path to YAML file
        yaml_file_path = SPEC_LIBRARY_BASE_PATH / request.specification_file

        # Check if file exists
        if not yaml_file_path.exists():
            logger.error(f"Specification file not found: {yaml_file_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Specification file '{request.specification_file}' not found in library"
            )

        # Security check: ensure path is within specifications_library (prevent path traversal)
        try:
            yaml_file_path.resolve().relative_to(SPEC_LIBRARY_BASE_PATH.resolve())
        except ValueError:
            logger.error(f"Path traversal attempt: {request.specification_file}")
            raise HTTPException(
                status_code=400,
                detail="Invalid specification file path"
            )

        # Read YAML file
        try:
            with open(yaml_file_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
                spec_dict = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error for {request.specification_file}: {e}")
            return CreateFlowFromLibraryResponse(
                success=False,
                specification_file=request.specification_file,
                message="Invalid YAML format",
                error="YAML parsing failed",
                details=str(e)
            )
        except Exception as e:
            logger.error(f"Error reading file {request.specification_file}: {e}")
            return CreateFlowFromLibraryResponse(
                success=False,
                specification_file=request.specification_file,
                message="Failed to read specification file",
                error="File read error",
                details=str(e)
            )

        if not spec_dict:
            return CreateFlowFromLibraryResponse(
                success=False,
                specification_file=request.specification_file,
                message="Empty YAML specification",
                error="Empty YAML"
            )

        # Convert YAML to flow JSON using SpecService
        service = SpecService()
        try:
            flow_data = await service.convert_spec_to_flow(yaml_content)
        except Exception as e:
            logger.error(f"Spec conversion error for {request.specification_file}: {e}")
            return CreateFlowFromLibraryResponse(
                success=False,
                specification_file=request.specification_file,
                message="Failed to convert specification to flow",
                error="Conversion error",
                details=str(e)
            )

        # Extract flow metadata from YAML
        flow_name = spec_dict.get('name', yaml_file_path.stem)
        description = spec_dict.get('description', '')
        specification_urn = spec_dict.get('id', '')

        # Create Flow record in database using authenticated user
        flow = Flow(
            id=uuid4(),
            name=flow_name,
            description=description,
            data=flow_data.get("data"),
            user_id=current_user.id,  # Use authenticated user automatically
            folder_id=request.folder_id,
            is_component=False,
        )

        session.add(flow)
        await session.commit()
        await session.refresh(flow)

        logger.info(f"✅ Created flow '{flow_name}' (ID: {flow.id}) from {request.specification_file} for user {current_user.id}")

        return CreateFlowFromLibraryResponse(
            success=True,
            flow_id=str(flow.id),
            flow_name=flow_name,
            specification_urn=specification_urn,
            specification_file=request.specification_file,
            message="Flow created successfully from specification library"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating flow from {request.specification_file}: {e}", exc_info=True)
        return CreateFlowFromLibraryResponse(
            success=False,
            specification_file=request.specification_file,
            message="Internal server error",
            error="Unexpected error",
            details=str(e)
        )


