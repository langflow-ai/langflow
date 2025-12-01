"""API endpoints for spec_flow_builder."""

import logging
import re
from datetime import datetime, timezone
from uuid import UUID

import yaml
from fastapi import APIRouter, HTTPException, Response
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.interface.components import get_and_cache_all_types_dict
from langflow.services.database.models.flow import Flow, FlowCreate
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_settings_service
from .component_resolver import ComponentResolver
from .models import ValidateSpecRequest, ValidationReport, CreateFlowRequest, CreateFlowResponse, ExportYamlResponse
from .validator import SpecValidator
from .provides_validator import ProvidesConnectionValidator
from .config_validator import ConfigValidator
from .node_builder import NodeBuilder
from .config_builder import ConfigBuilder
from .edge_builder import EdgeBuilder
from .yaml_exporter import FlowToYamlConverter

logger = logging.getLogger(__name__)

# Create router with prefix and tags
router = APIRouter(prefix="/spec-builder", tags=["Spec Flow Builder"])


# ============================================================================
# Helper Functions
# ============================================================================


async def _get_or_create_folder(session: DbSession, user_id: UUID, folder_name: str = DEFAULT_FOLDER_NAME) -> Folder:
    """
    Get or create a folder for the user.

    Args:
        session: Database session
        user_id: User ID
        folder_name: Name of the folder (default: DEFAULT_FOLDER_NAME)

    Returns:
        Folder instance
    """
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


def _sanitize_filename(name: str) -> str:
    """
    Sanitize flow name for use in filename.

    Converts flow name to a safe filename by:
    - Converting to lowercase
    - Replacing spaces and special characters with hyphens
    - Collapsing multiple hyphens into one
    - Removing leading/trailing hyphens

    Args:
        name: Flow name to sanitize

    Returns:
        Sanitized filename-safe string

    Examples:
        "EOC Check Agent" -> "eoc-check-agent"
        "My Flow (v2)!" -> "my-flow-v2"
        "Test___Flow" -> "test-flow"
    """
    # Convert to lowercase and replace non-alphanumeric chars with hyphens
    sanitized = re.sub(r"[^a-z0-9_-]", "-", name.lower())
    # Collapse multiple hyphens/underscores into single hyphen
    sanitized = re.sub(r"[-_]+", "-", sanitized)
    # Remove leading/trailing hyphens
    return sanitized.strip("-")


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/validate", response_model=ValidationReport)
async def validate_spec(request: ValidateSpecRequest) -> ValidationReport:
    """
    Validate a YAML specification.

    This endpoint checks if all components defined in the YAML spec
    exist in the Langflow component catalog.

    Request body:
        {
            "yaml_content": "id: urn:agent:...\ncomponents:\n- type: PromptComponent\n  ..."
        }

    Response:
        {
            "valid": true,
            "total_components": 6,
            "found_components": 6,
            "missing_components": 0,
            "components": [
                {
                    "id": "eoc-prompt",
                    "name": "Agent Instructions",
                    "yaml_type": "PromptComponent",
                    "found": true,
                    "catalog_name": "Prompt Template",
                    "category": "processing"
                },
                ...
            ],
            "errors": []
        }

    Args:
        request: ValidateSpecRequest with yaml_content

    Returns:
        ValidationReport with detailed validation results

    Raises:
        HTTPException: If validation process fails unexpectedly
    """
    try:
        logger.info("Received validation request")

        # Create resolver
        resolver = ComponentResolver()
        # Run main validation (component existence, counts, etc.)
        validator = SpecValidator(resolver)
        report = await validator.validate(request.yaml_content)

        provides_validator = ProvidesConnectionValidator(resolver)
        provides_errors = await provides_validator.validate(request.yaml_content)
        if provides_errors:
            raise HTTPException(status_code=400, detail={"errors": provides_errors})

        # Validate component config keys and types against catalog templates
        config_validator = ConfigValidator(resolver)
        config_errors = await config_validator.validate(request.yaml_content)
        if config_errors:
            raise HTTPException(status_code=400, detail={"errors": config_errors})

        # Run validation (this checks component existence; 'provides' is checked by dependency)

        logger.info(f"Validation complete: valid={report.valid}, found={report.found_components}/{report.total_components}")

        return report

    except HTTPException as e:
        # Propagate intended HTTP errors (e.g., 400 for validation)
        raise e
    except Exception as e:
        logger.error(f"Validation endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/create-flow", response_model=CreateFlowResponse)
async def create_flow(
    request: CreateFlowRequest, session: DbSession, current_user: CurrentActiveUser
) -> CreateFlowResponse:
    """
    Create a flow from YAML specification.

    This endpoint takes a YAML specification and creates a complete flow by:
    1. Building nodes from components (NodeBuilder)
    2. Applying configuration to nodes (ConfigBuilder)
    3. Creating edges based on 'provides' relationships (EdgeBuilder)
    4. Saving the flow to the database

    Request body:
        {
            "yaml_content": "id: urn:agent:...\ncomponents:\n- type: PromptComponent\n  ...",
            "flow_name": "My Custom Flow",  # Optional
            "folder_id": "folder-uuid"       # Optional
        }

    Response:
        {
            "success": true,
            "message": "Flow created successfully",
            "flow_id": "flow-uuid",
            "flow_name": "My Custom Flow"
        }

    Args:
        request: CreateFlowRequest with yaml_content and optional flow_name/folder_id
        session: Database session (injected)
        current_user: Current authenticated user (injected)

    Returns:
        CreateFlowResponse with creation status and flow details

    Raises:
        HTTPException: If flow creation fails or user is not authenticated
    """
    try:
        logger.info(f"Received create-flow request from user {current_user.id}")

        # Step 1: Parse YAML to extract metadata
        try:
            spec = yaml.safe_load(request.yaml_content)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            return CreateFlowResponse(
                success=False,
                message=f"Invalid YAML format: {str(e)}",
                flow_id=None,
                flow_name=None,
            )

        # Step 2: Validate the YAML
        resolver = ComponentResolver()
        validator = SpecValidator(resolver)
        report = await validator.validate(request.yaml_content)

        if not report.valid:
            logger.warning(f"YAML validation failed: {report.errors}")
            return CreateFlowResponse(
                success=False,
                message=f"YAML validation failed: {', '.join(report.errors[:3])}",
                flow_id=None,
                flow_name=None,
            )

        # Step 2: Fetch all components once (will be used by all builders)
        logger.info("Fetching component catalog")
        settings_service = get_settings_service()
        all_components = await get_and_cache_all_types_dict(settings_service)
        total_components = sum(len(comps) for comps in all_components.values())
        logger.info(f"Fetched {total_components} components across {len(all_components)} categories")

        # Step 3: Build nodes
        logger.info("Building nodes from YAML specification")
        node_builder = NodeBuilder(all_components)
        nodes = await node_builder.build_nodes(request.yaml_content)

        # Step 4: Apply configuration to nodes
        logger.info("Applying configuration to nodes")
        config_builder = ConfigBuilder(all_components)
        configured_nodes = await config_builder.apply_config(nodes, request.yaml_content)

        # Step 5: Build edges
        logger.info("Building edges between nodes")
        logger.info(f"Passing {len(configured_nodes)} nodes to EdgeBuilder")

        # Debug: Log node yaml_component_ids before passing to EdgeBuilder
        node_yaml_ids = [node.get("data", {}).get("yaml_component_id") for node in configured_nodes]
        logger.info(f"Node yaml_component_ids being passed to EdgeBuilder: {node_yaml_ids}")

        edge_builder = EdgeBuilder(all_components)
        edges = await edge_builder.build_edges(configured_nodes, request.yaml_content)

        logger.info(f"EdgeBuilder returned {len(edges)} edges")
        if len(edges) == 0:
            logger.warning("⚠️ No edges were created! This might indicate a problem.")
            logger.warning(f"Nodes have yaml_component_ids: {node_yaml_ids}")
            # Parse YAML to show provides relationships
            try:
                yaml_provides_count = 0
                for comp in spec.get("components", []):
                    provides = comp.get("provides", [])
                    if provides:
                        yaml_provides_count += len(provides)
                        logger.warning(f"Component '{comp.get('id')}' has {len(provides)} provides entries")
                logger.warning(f"YAML has {yaml_provides_count} total provides relationships but 0 edges were created!")
            except Exception as e:
                logger.error(f"Error checking provides relationships: {e}")

        # Step 6: Build complete flow JSON structure
        logger.info("Building complete flow JSON structure")
        flow_name = request.flow_name or spec.get("name", "Untitled Flow")
        flow_description = spec.get("description", "")

        flow_json = {
            "name": flow_name,
            "description": flow_description,
            "data": {
                "nodes": configured_nodes,
                "edges": edges,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
            },
        }

        logger.info(f"✓ Flow JSON built with {len(configured_nodes)} nodes and {len(edges)} edges")

        # Step 7: Save flow to database
        logger.info("Saving flow to database")

        # Get or create folder
        folder_id_uuid = None
        if request.folder_id:
            try:
                folder_id_uuid = UUID(request.folder_id)
                folder = await session.get(Folder, folder_id_uuid)
                if not folder:
                    logger.warning(f"Folder with ID {folder_id_uuid} not found, using default folder")
                    folder = await _get_or_create_folder(session, current_user.id)
            except ValueError:
                logger.warning(f"Invalid folder_id format: {request.folder_id}, using default folder")
                folder = await _get_or_create_folder(session, current_user.id)
        else:
            folder = await _get_or_create_folder(session, current_user.id)

        # Create flow record
        flow_create = FlowCreate(
            name=flow_name,
            description=flow_description,
            data=flow_json.get("data", {}),
            folder_id=folder.id,
            user_id=current_user.id,
        )

        flow = Flow.model_validate(flow_create, from_attributes=True)
        session.add(flow)
        await session.commit()
        await session.refresh(flow)

        logger.info(f"Flow created successfully with ID: {flow.id}")

        return CreateFlowResponse(
            success=True,
            message="Flow created successfully",
            flow_id=str(flow.id),
            flow_name=flow.name,
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Create-flow endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Flow creation failed: {str(e)}")


@router.get("/export-yaml/{flow_id}", response_model=ExportYamlResponse)
async def export_yaml(
    flow_id: str, session: DbSession, current_user: CurrentActiveUser
) -> ExportYamlResponse:
    """
    Export an existing flow to YAML specification format.

    This endpoint takes a flow ID and converts it back to YAML specification by:
    1. Fetching the flow from the database
    2. Extracting metadata (name, description, etc.)
    3. Converting nodes to YAML components
    4. Analyzing edges to build 'provides' relationships
    5. Generating formatted YAML string

    Path parameters:
        flow_id: UUID of the flow to export

    Response:
        {
            "success": true,
            "message": "Flow exported successfully",
            "yaml_content": "id: urn:agent:...\ncomponents:\n- type: PromptComponent\n  ...",
            "flow_name": "My Flow"
        }

    Args:
        flow_id: UUID of the flow to export
        session: Database session (injected)
        current_user: Current authenticated user (injected)

    Returns:
        ExportYamlResponse with YAML content and export status

    Raises:
        HTTPException: If flow is not found or export fails
    """
    try:
        logger.info(f"Received export-yaml request for flow {flow_id} from user {current_user.id}")

        # Step 1: Validate flow_id format
        try:
            flow_uuid = UUID(flow_id)
        except ValueError:
            logger.error(f"Invalid flow_id format: {flow_id}")
            return ExportYamlResponse(
                success=False,
                message=f"Invalid flow_id format: {flow_id}",
                yaml_content=None,
                flow_name=None,
            )

        # Step 2: Fetch flow from database
        flow = await session.get(Flow, flow_uuid)
        if not flow:
            logger.warning(f"Flow with ID {flow_id} not found")
            raise HTTPException(status_code=404, detail=f"Flow with ID {flow_id} not found")

        # Check if user owns the flow
        # if flow.user_id != current_user.id:
        #     logger.warning(f"User {current_user.id} attempted to export flow {flow_id} owned by {flow.user_id}")
        #     raise HTTPException(status_code=403, detail="You do not have permission to export this flow")

        # Step 3: Fetch component catalog
        logger.info("Fetching component catalog for export")
        settings_service = get_settings_service()
        all_components = await get_and_cache_all_types_dict(settings_service)
        total_components = sum(len(comps) for comps in all_components.values())
        logger.info(f"Fetched {total_components} components for export")

        # Step 4: Convert flow to YAML
        logger.info(f"Converting flow '{flow.name}' to YAML specification")
        converter = FlowToYamlConverter(all_components)

        # Prepare flow data for conversion
        flow_data = {
            "id": str(flow.id),
            "name": flow.name,
            "description": flow.description or "",
            "data": flow.data,  # Contains nodes and edges
        }

        yaml_content = await converter.convert_flow_to_yaml(flow_data)

        logger.info(f"Successfully exported flow '{flow.name}' to YAML ({len(yaml_content)} chars)")

        return ExportYamlResponse(
            success=True,
            message="Flow exported successfully",
            yaml_content=yaml_content,
            flow_name=flow.name,
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Export-yaml endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"YAML export failed: {str(e)}")


@router.get("/download-yaml/{flow_id}")
async def download_yaml(
    flow_id: str, session: DbSession, current_user: CurrentActiveUser
) -> Response:
    """
    Download an existing flow as a YAML file.

    This endpoint is similar to export-yaml but returns the YAML as a downloadable file
    with proper headers to trigger browser download dialog.

    Path parameters:
        flow_id: UUID of the flow to download

    Response:
        Raw YAML file with Content-Disposition header for download

    Filename format:
        {sanitized_flow_name}_{timestamp}.yaml
        Example: eoc-check-agent_2025-11-10.yaml

    Args:
        flow_id: UUID of the flow to download
        session: Database session (injected)
        current_user: Current authenticated user (injected)

    Returns:
        Response with YAML content and download headers

    Raises:
        HTTPException: If flow is not found or download fails
    """
    try:
        logger.info(f"Received download-yaml request for flow {flow_id} from user {current_user.id}")

        # Step 1: Validate flow_id format
        try:
            flow_uuid = UUID(flow_id)
        except ValueError:
            logger.error(f"Invalid flow_id format: {flow_id}")
            raise HTTPException(status_code=400, detail=f"Invalid flow_id format: {flow_id}")

        # Step 2: Fetch flow from database
        flow = await session.get(Flow, flow_uuid)
        if not flow:
            logger.warning(f"Flow with ID {flow_id} not found")
            raise HTTPException(status_code=404, detail=f"Flow with ID {flow_id} not found")

        # Check if user owns the flow
        # if flow.user_id != current_user.id:
        #     logger.warning(f"User {current_user.id} attempted to download flow {flow_id} owned by {flow.user_id}")
        #     raise HTTPException(status_code=403, detail="You do not have permission to download this flow")

        # Step 3: Fetch component catalog
        logger.info("Fetching component catalog for download")
        settings_service = get_settings_service()
        all_components = await get_and_cache_all_types_dict(settings_service)

        # Step 4: Convert flow to YAML
        logger.info(f"Converting flow '{flow.name}' to YAML for download")
        converter = FlowToYamlConverter(all_components)

        # Prepare flow data for conversion
        flow_data = {
            "id": str(flow.id),
            "name": flow.name,
            "description": flow.description or "",
            "data": flow.data,
        }

        yaml_content = await converter.convert_flow_to_yaml(flow_data)

        # Step 5: Generate filename
        sanitized_name = _sanitize_filename(flow.name)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"{sanitized_name}_{timestamp}.yaml"

        logger.info(f"Prepared download: {filename} ({len(yaml_content)} chars)")

        # Step 6: Return YAML as downloadable file
        return Response(
            content=yaml_content,
            media_type="text/yaml; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(yaml_content.encode("utf-8"))),
            },
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Download-yaml endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"YAML download failed: {str(e)}")

@router.get("/published-agent-yaml/{flow_id}")
async def export_yaml(
    flow_id: str, session: DbSession, current_user: CurrentActiveUser
) -> dict:
    """
    Export an existing flow as YAML content.

    This endpoint returns the YAML content as a JSON response instead of
    triggering a file download. Useful for integrations or preview purposes.

    Path parameters:
        flow_id: UUID of the flow to export

    Response:
        JSON object containing:
        - yaml_content: The YAML string
        - flow_name: Name of the flow
        - flow_id: UUID of the flow
        - exported_at: ISO timestamp of export

    Args:
        flow_id: UUID of the flow to export
        session: Database session (injected)
        current_user: Current authenticated user (injected)

    Returns:
        Dictionary with YAML content and metadata

    Raises:
        HTTPException: If flow is not found or export fails
    """
    try:
        logger.info(f"Received export-yaml request for flow {flow_id} from user {current_user.id}")

        # Step 1: Validate flow_id format
        try:
            flow_uuid = UUID(flow_id)
        except ValueError:
            logger.error(f"Invalid flow_id format: {flow_id}")
            raise HTTPException(status_code=400, detail=f"Invalid flow_id format: {flow_id}")

        # Step 2: Fetch flow from database
        flow = await session.get(Flow, flow_uuid)
        if not flow:
            logger.warning(f"Flow with ID {flow_id} not found")
            raise HTTPException(status_code=404, detail=f"Flow with ID {flow_id} not found")

        # Optional: Check if user owns the flow
        # if flow.user_id != current_user.id:
        #     logger.warning(f"User {current_user.id} attempted to export flow {flow_id} owned by {flow.user_id}")
        #     raise HTTPException(status_code=403, detail="You do not have permission to export this flow")

        # Step 3: Fetch component catalog
        logger.info("Fetching component catalog for export")
        settings_service = get_settings_service()
        all_components = await get_and_cache_all_types_dict(settings_service)

        # Step 4: Convert flow to YAML
        logger.info(f"Converting flow '{flow.name}' to YAML for export")
        converter = FlowToYamlConverter(all_components)

        # Prepare flow data for conversion
        flow_data = {
            "id": str(flow.id),
            "name": flow.name,
            "description": flow.description or "",
            "data": flow.data,
        }

        yaml_content = await converter.convert_flow_to_yaml(flow_data)

        # Step 5: Prepare response
        response_data = {
            "yaml_content": yaml_content,
            "flow_name": flow.name,
            "flow_id": str(flow.id),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Successfully exported flow '{flow.name}' as YAML ({len(yaml_content)} chars)")

        return response_data

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Export-yaml endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"YAML export failed: {str(e)}")
