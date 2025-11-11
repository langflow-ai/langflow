"""Spec Flow Builder API - Endpoints for YAML spec validation and flow creation."""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow import Flow, FlowCreate, FlowRead
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.spec_flow_builder import (
    AnalyzeComponentsRequest,
    ComponentResolver,
    ComponentStatus,
    CreateFlowRequest,
    EdgeBuilder,
    FlowPreview,
    PreviewFlowRequest,
    SpecFlowConverter,
    SpecFlowValidator,
    ValidateSpecRequest,
    ValidationReport,
)
from langflow.services.spec_flow_builder.utils import sanitize_flow_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spec-builder", tags=["Spec Flow Builder"])


# ============================================================================
# Helper Functions
# ============================================================================


async def _get_or_create_folder(session: DbSession, user_id: UUID, folder_name: str = DEFAULT_FOLDER_NAME) -> Folder:
    """Get or create a folder for the user."""
    # Check if folder exists
    statement = select(Folder).where(Folder.name == folder_name, Folder.user_id == user_id)
    result = await session.exec(statement)
    folder = result.first()

    if not folder:
        # Create folder
        folder = Folder(name=folder_name, user_id=user_id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)

    return folder


async def _create_flow_from_json(
    session: DbSession, user_id: UUID, flow_json: Dict[str, Any], flow_name: Optional[str], folder_id: Optional[UUID]
) -> Flow:
    """Create a flow in the database from flow JSON."""
    # Get or create folder
    if folder_id:
        folder = await session.get(Folder, folder_id)
        if not folder:
            raise ValueError(f"Folder with ID {folder_id} not found")
    else:
        folder = await _get_or_create_folder(session, user_id)

    # Extract name from flow_json or use provided name
    name = flow_name or flow_json.get("name", "Untitled Flow")
    name = sanitize_flow_name(name)

    # Create flow
    flow_create = FlowCreate(
        name=name,
        description=flow_json.get("description", ""),
        data=flow_json.get("data", {}),
        folder_id=folder.id,
        user_id=user_id,
    )

    flow = Flow.model_validate(flow_create, from_attributes=True)
    session.add(flow)
    await session.commit()
    await session.refresh(flow)

    return flow


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/validate", response_model=ValidationReport, status_code=status.HTTP_200_OK)
async def validate_spec(request: ValidateSpecRequest, session: DbSession) -> ValidationReport:
    """
    Validate YAML specification.

    Performs comprehensive validation:
    - Component existence check
    - Config field validation
    - Provides relationship validation

    Returns detailed validation report with errors and warnings.
    """
    try:
        # Initialize resolver and validator
        resolver = ComponentResolver()
        validator = SpecFlowValidator(resolver)

        # Perform validation
        report = await validator.validate(request.yaml_content)

        return report

    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Validation failed: {str(e)}")


@router.post("/analyze-components", response_model=Dict[str, List[ComponentStatus]], status_code=status.HTTP_200_OK)
async def analyze_components(request: AnalyzeComponentsRequest, session: DbSession) -> Dict[str, List[ComponentStatus]]:
    """
    Analyze components in the specification.

    Returns detailed information about each component:
    - Whether it exists in the catalog
    - What it maps to
    - Available fields
    - Issues found
    """
    try:
        # Initialize resolver and validator
        resolver = ComponentResolver()
        validator = SpecFlowValidator(resolver)

        # Perform validation
        report = await validator.validate(request.yaml_content)

        # Return component statuses grouped by validity
        valid_components = [comp for comp in report.components if comp.exists]
        invalid_components = [comp for comp in report.components if not comp.exists]

        return {"valid": valid_components, "invalid": invalid_components}

    except Exception as e:
        logger.error(f"Component analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Component analysis failed: {str(e)}"
        )


@router.post("/preview", response_model=FlowPreview, status_code=status.HTTP_200_OK)
async def preview_flow(request: PreviewFlowRequest, session: DbSession) -> FlowPreview:
    """
    Preview flow without creating it (dry-run).

    Converts YAML to flow JSON and returns:
    - Complete flow structure
    - Node and edge counts
    - Validation summary
    """
    try:
        # Initialize components
        resolver = ComponentResolver()
        validator = SpecFlowValidator(resolver)
        edge_builder = EdgeBuilder(resolver)
        converter = SpecFlowConverter(resolver, edge_builder)

        # Validate first
        validation_report = await validator.validate(request.yaml_content)

        # Convert to flow JSON
        flow_json = await converter.convert(request.yaml_content)

        # Build preview
        nodes = flow_json.get("data", {}).get("nodes", [])
        edges = flow_json.get("data", {}).get("edges", [])

        preview = FlowPreview(
            flow_json=flow_json,
            nodes_count=len(nodes),
            edges_count=len(edges),
            validation_summary={
                "is_valid": validation_report.is_valid,
                "error_count": len(validation_report.errors),
                "warning_count": len(validation_report.warnings),
                "components_valid": validation_report.summary.valid_components if validation_report.summary else 0,
            },
        )

        return preview

    except ValueError as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Preview error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Preview failed: {str(e)}")


@router.post("/create-flow", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
async def create_flow(
    request: CreateFlowRequest, session: DbSession, current_user: CurrentActiveUser
) -> FlowRead:
    """
    Create a flow from YAML specification.

    Full pipeline:
    1. Validate YAML (fails if invalid)
    2. Convert to flow JSON
    3. Create flow in database
    4. Return created flow

    Requires authentication.
    """
    try:
        # Initialize components
        resolver = ComponentResolver()
        validator = SpecFlowValidator(resolver)
        edge_builder = EdgeBuilder(resolver)
        converter = SpecFlowConverter(resolver, edge_builder)

        # Step 1: Validate
        logger.info("Validating specification...")
        validation_report = await validator.validate(request.yaml_content)

        if not validation_report.is_valid:
            error_msg = "; ".join(validation_report.errors[:5])  # Limit to first 5 errors
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Specification validation failed: {error_msg}",
            )

        # Step 2: Convert
        logger.info("Converting specification to flow JSON...")
        flow_json = await converter.convert(request.yaml_content)

        # Step 3: Create flow
        logger.info("Creating flow in database...")
        folder_id = UUID(request.folder_id) if request.folder_id else None
        flow = await _create_flow_from_json(
            session=session,
            user_id=current_user.id,
            flow_json=flow_json,
            flow_name=request.flow_name,
            folder_id=folder_id,
        )

        logger.info(f"Flow created successfully: {flow.id}")

        # Return as FlowRead
        return FlowRead.model_validate(flow, from_attributes=True)

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Flow creation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Flow creation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Flow creation failed: {str(e)}"
        )


@router.get("/component-catalog", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_component_catalog(session: DbSession) -> Dict[str, Any]:
    """
    Get all available components.

    Returns the component catalog with all available components
    organized by category.

    This is a cached wrapper around /api/v1/all.
    """
    try:
        resolver = ComponentResolver()
        components = await resolver.fetch_all_components()

        # Return summary info
        return {
            "categories": list(components.keys()),
            "total_categories": len(components),
            "total_components": sum(len(comps) for comps in components.values()),
            "components": components,
        }

    except Exception as e:
        logger.error(f"Failed to fetch component catalog: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch component catalog: {str(e)}"
        )


@router.get(
    "/component/{category}/{component_name}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK
)
async def get_component_details(category: str, component_name: str, session: DbSession) -> Dict[str, Any]:
    """
    Get detailed information for a specific component.

    Returns:
    - Component template with all fields
    - Input fields list
    - Output types
    - Display name and description
    """
    try:
        resolver = ComponentResolver()
        await resolver.fetch_all_components()

        # Get template
        template = resolver.get_component_template(category, component_name)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component '{component_name}' not found in category '{category}'",
            )

        # Get additional info
        input_fields = resolver.get_input_fields(category, component_name)
        output_types = resolver.get_output_types(category, component_name)
        display_name = resolver.get_component_display_name(category, component_name)

        return {
            "category": category,
            "component_name": component_name,
            "display_name": display_name,
            "template": template,
            "input_fields": input_fields,
            "output_types": output_types,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get component details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get component details: {str(e)}"
        )
