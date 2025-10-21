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
from langflow.services.runtime.flow_to_spec_converter import FlowToSpecConverter
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
    detailed: bool = Field(True, description="Whether to perform detailed semantic validation")
    format_report: bool = Field(False, description="Whether to return a formatted validation report")


class ValidationIssue(BaseModel):
    """Individual validation issue with context."""
    code: str = Field(..., description="Error/warning code")
    message: str = Field(..., description="Human-readable message")
    severity: str = Field(..., description="Issue severity: error, warning, or suggestion")
    component_id: Optional[str] = Field(None, description="ID of the component with the issue")
    field: Optional[str] = Field(None, description="Specific field with the issue")
    suggestion: Optional[str] = Field(None, description="Actionable suggestion to fix the issue")


class ValidationSummary(BaseModel):
    """Validation summary statistics."""
    error_count: int = Field(..., description="Number of errors found")
    warning_count: int = Field(..., description="Number of warnings found")
    suggestion_count: int = Field(..., description="Number of suggestions provided")


class ValidationPhases(BaseModel):
    """Validation phases status."""
    schema_validation: bool = Field(..., description="JSON Schema validation passed")
    structure_validation: bool = Field(..., description="Basic structure validation passed")
    component_validation: bool = Field(..., description="Component existence validation passed")
    type_validation: bool = Field(..., description="Type compatibility validation passed")
    semantic_validation: Optional[bool] = Field(None, description="Semantic validation passed (if performed)")


class SpecValidationResponse(BaseModel):
    """Enhanced response model for spec validation."""
    valid: bool = Field(..., description="Overall validation result")
    errors: List[ValidationIssue] = Field(default_factory=list, description="Validation errors with context")
    warnings: List[ValidationIssue] = Field(default_factory=list, description="Validation warnings with context")
    suggestions: List[ValidationIssue] = Field(default_factory=list, description="Improvement suggestions")
    summary: ValidationSummary = Field(..., description="Validation summary statistics")
    validation_phases: ValidationPhases = Field(..., description="Status of each validation phase")
    formatted_report: Optional[str] = Field(None, description="Human-readable validation report (if requested)")
    actionable_suggestions: List[str] = Field(default_factory=list, description="List of actionable suggestions")


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
    Enhanced specification validation with comprehensive error reporting.

    Performs multi-phase validation including JSON Schema validation, semantic analysis,
    component relationship validation, and provides actionable suggestions for improvement.
    """
    try:
        service = SpecService()
        result = await service.validate_spec(
            spec_yaml=request.spec_yaml,
            detailed=request.detailed
        )

        # Convert validation issues to proper format
        def convert_issues(issues):
            converted = []
            for issue in issues:
                if isinstance(issue, dict):
                    converted.append(ValidationIssue(**issue))
                else:
                    # Handle legacy string format
                    converted.append(ValidationIssue(
                        code="LEGACY_ISSUE",
                        message=str(issue),
                        severity="error"
                    ))
            return converted

        errors = convert_issues(result.get("errors", []))
        warnings = convert_issues(result.get("warnings", []))
        suggestions = convert_issues(result.get("suggestions", []))

        # Extract summary
        summary_data = result.get("summary", {})
        summary = ValidationSummary(
            error_count=summary_data.get("error_count", len(errors)),
            warning_count=summary_data.get("warning_count", len(warnings)),
            suggestion_count=summary_data.get("suggestion_count", len(suggestions))
        )

        # Extract validation phases
        phases_data = result.get("validation_phases", {})
        phases = ValidationPhases(
            schema_validation=phases_data.get("schema_validation", True),
            structure_validation=phases_data.get("structure_validation", True),
            component_validation=phases_data.get("component_validation", True),
            type_validation=phases_data.get("type_validation", True),
            semantic_validation=phases_data.get("semantic_validation")
        )

        # Get formatted report if requested
        formatted_report = None
        if request.format_report:
            formatted_report = service.format_validation_report(result)

        # Get actionable suggestions
        actionable_suggestions = service.get_validation_suggestions(result)

        return SpecValidationResponse(
            valid=result["valid"],
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            summary=summary,
            validation_phases=phases,
            formatted_report=formatted_report,
            actionable_suggestions=actionable_suggestions
        )

    except Exception as e:
        logger.error(f"Spec validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during validation") from e


@router.post("/validate-quick", response_model=SpecValidationResponse)
async def validate_spec_quick(
    request: SpecValidationRequest
) -> SpecValidationResponse:
    """
    Quick specification validation for real-time feedback.

    Performs lightweight validation that's optimized for speed, suitable for
    real-time validation in editors and CLI tools. Skips expensive semantic
    analysis but covers essential validation rules.
    """
    try:
        service = SpecService()
        result = await service.validate_spec_quick(request.spec_yaml)

        # Convert validation issues to proper format
        def convert_issues(issues):
            converted = []
            for issue in issues:
                if isinstance(issue, dict):
                    converted.append(ValidationIssue(**issue))
                else:
                    # Handle legacy string format
                    converted.append(ValidationIssue(
                        code="LEGACY_ISSUE",
                        message=str(issue),
                        severity="error"
                    ))
            return converted

        errors = convert_issues(result.get("errors", []))
        warnings = convert_issues(result.get("warnings", []))
        suggestions = convert_issues(result.get("suggestions", []))

        # Extract summary
        summary_data = result.get("summary", {})
        summary = ValidationSummary(
            error_count=summary_data.get("error_count", len(errors)),
            warning_count=summary_data.get("warning_count", len(warnings)),
            suggestion_count=summary_data.get("suggestion_count", len(suggestions))
        )

        # Extract validation phases
        phases_data = result.get("validation_phases", {})
        phases = ValidationPhases(
            schema_validation=phases_data.get("schema_validation"),
            structure_validation=phases_data.get("structure_validation"),
            component_validation=phases_data.get("component_validation"),
            type_validation=phases_data.get("type_validation"),
            semantic_validation=phases_data.get("semantic_validation")  # Will be None for quick validation
        )

        # Get formatted report if requested
        formatted_report = None
        if request.format_report:
            formatted_report = service.format_validation_report(result)

        # Get actionable suggestions
        actionable_suggestions = service.get_validation_suggestions(result)

        return SpecValidationResponse(
            valid=result["valid"],
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            summary=summary,
            validation_phases=phases,
            formatted_report=formatted_report,
            actionable_suggestions=actionable_suggestions
        )

    except Exception as e:
        logger.error(f"Quick spec validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during quick validation") from e


@router.get("/error-context/{error_code}")
async def get_error_context(error_code: str):
    """
    Get detailed context and help for a specific error code.

    Provides comprehensive information about validation errors including
    descriptions, examples, documentation links, and resolution steps.
    """
    try:
        service = SpecService()
        context = service.get_error_context(error_code)

        return {
            "error_code": error_code,
            "context": context,
            "timestamp": "2025-01-16T10:30:00Z"
        }

    except Exception as e:
        logger.error(f"Error getting error context: {e}")
        raise HTTPException(status_code=500, detail="Internal server error getting error context") from e


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


# Export (reverse conversion) endpoints

class FlowExportRequest(BaseModel):
    """Request model for flow export to Genesis specification."""
    flow_data: Dict[str, Any] = Field(..., description="Langflow flow JSON data")
    preserve_variables: bool = Field(True, description="Whether to preserve original variable values")
    include_metadata: bool = Field(False, description="Whether to include extended metadata")
    name_override: Optional[str] = Field(None, description="Override flow name in specification")
    description_override: Optional[str] = Field(None, description="Override flow description")
    domain_override: Optional[str] = Field(None, description="Override domain (default: converted)")


class FlowExportResponse(BaseModel):
    """Response model for flow export."""
    specification: Dict[str, Any] = Field(..., description="Generated Genesis specification")
    success: bool = Field(True, description="Export success status")
    warnings: List[str] = Field(default_factory=list, description="Export warnings")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Export statistics")


class BatchFlowExportRequest(BaseModel):
    """Request model for batch flow export."""
    flows: List[Dict[str, Any]] = Field(..., description="List of Langflow flow JSON data")
    preserve_variables: bool = Field(True, description="Whether to preserve original variable values")
    include_metadata: bool = Field(False, description="Whether to include extended metadata")
    domain_override: Optional[str] = Field(None, description="Override domain for all specifications")


class BatchFlowExportResponse(BaseModel):
    """Response model for batch flow export."""
    specifications: List[Dict[str, Any]] = Field(..., description="Generated Genesis specifications")
    success: bool = Field(True, description="Overall export success status")
    total_processed: int = Field(..., description="Total number of flows processed")
    successful_exports: int = Field(..., description="Number of successful exports")
    failed_exports: int = Field(..., description="Number of failed exports")
    warnings: List[str] = Field(default_factory=list, description="Export warnings")
    errors: List[str] = Field(default_factory=list, description="Export errors")


class FlowValidationForExportRequest(BaseModel):
    """Request model for flow validation before export."""
    flow_data: Dict[str, Any] = Field(..., description="Langflow flow JSON data")


class FlowValidationForExportResponse(BaseModel):
    """Response model for flow validation before export."""
    valid: bool = Field(..., description="Whether flow can be exported")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    recommendations: List[str] = Field(default_factory=list, description="Export recommendations")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Flow statistics")


@router.post("/export", response_model=FlowExportResponse)
async def export_flow_to_spec(
    request: FlowExportRequest
) -> FlowExportResponse:
    """
    Export Langflow flow to Genesis specification.

    Converts a Langflow flow JSON back to Genesis YAML specification with
    support for variable preservation, metadata extraction, and custom naming.
    """
    try:
        converter = FlowToSpecConverter()

        specification = converter.convert_flow_to_spec(
            flow_data=request.flow_data,
            preserve_variables=request.preserve_variables,
            include_metadata=request.include_metadata,
            name_override=request.name_override,
            description_override=request.description_override,
            domain_override=request.domain_override
        )

        # Extract conversion metadata if available
        conversion_meta = specification.pop("_conversion", {})
        statistics = {
            "components_converted": len(specification.get("components", {})),
            "edges_inferred": len([c for c in specification.get("components", {}).values()
                                 if c.get("provides")]),
            "variables_preserved": len(specification.get("variables", {})),
            "converted_at": conversion_meta.get("convertedAt"),
            "converter_version": conversion_meta.get("converterVersion")
        }

        return FlowExportResponse(
            specification=specification,
            success=True,
            warnings=[],
            statistics=statistics
        )

    except Exception as e:
        logger.error(f"Flow export error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/export-batch", response_model=BatchFlowExportResponse)
async def export_flows_batch_to_spec(
    request: BatchFlowExportRequest
) -> BatchFlowExportResponse:
    """
    Export multiple Langflow flows to Genesis specifications.

    Converts multiple Langflow flow JSONs to Genesis specifications in a single
    operation with consolidated error handling and reporting.
    """
    try:
        converter = FlowToSpecConverter()

        specifications = converter.convert_flows_batch(
            flows=request.flows,
            preserve_variables=request.preserve_variables,
            include_metadata=request.include_metadata,
            domain_override=request.domain_override
        )

        # Calculate statistics
        total_processed = len(request.flows)
        successful_exports = len(specifications)
        failed_exports = total_processed - successful_exports

        return BatchFlowExportResponse(
            specifications=specifications,
            success=failed_exports == 0,
            total_processed=total_processed,
            successful_exports=successful_exports,
            failed_exports=failed_exports,
            warnings=[],
            errors=[]
        )

    except Exception as e:
        logger.error(f"Batch flow export error: {e}")
        # Parse error message for batch failures
        error_msg = str(e)
        if "Batch conversion partially failed" in error_msg:
            # Extract individual failures
            return BatchFlowExportResponse(
                specifications=[],
                success=False,
                total_processed=len(request.flows),
                successful_exports=0,
                failed_exports=len(request.flows),
                warnings=[],
                errors=[error_msg]
            )
        else:
            raise HTTPException(status_code=400, detail=error_msg) from e


@router.post("/validate-for-export", response_model=FlowValidationForExportResponse)
async def validate_flow_for_export(
    request: FlowValidationForExportRequest
) -> FlowValidationForExportResponse:
    """
    Validate Langflow flow for export to Genesis specification.

    Checks if a flow can be successfully converted to Genesis specification
    and provides recommendations for improving the conversion process.
    """
    try:
        converter = FlowToSpecConverter()

        validation_result = converter.validate_flow_for_conversion(request.flow_data)

        return FlowValidationForExportResponse(
            valid=validation_result["valid"],
            warnings=validation_result["warnings"],
            errors=validation_result["errors"],
            recommendations=validation_result["recommendations"],
            statistics=validation_result["statistics"]
        )

    except Exception as e:
        logger.error(f"Flow export validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during validation") from e


