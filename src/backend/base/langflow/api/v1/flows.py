from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import orjson
from aiofile import async_open
from anyio import Path
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import apaginate
from sqlmodel import and_, col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, cascade_delete_flow, remove_api_keys, validate_is_component, DbSession
from langflow.api.v1.schemas import FlowListCreate
from langflow.helpers.user import get_user_by_flow_id_or_endpoint_name
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.logging import logger
from langflow.services.database.models.flow.model import (
    AccessTypeEnum,
    Flow,
    FlowCreate,
    FlowHeader,
    FlowRead,
    FlowUpdate,
)
from langflow.services.database.models.flow.utils import get_webhook_component_in_flow
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder, FolderCreate
from langflow.services.auth.permissions import can_delete_flow, can_edit_flow, can_view_flow, get_user_roles_from_request
from langflow.services.deps import get_settings_service
from langflow.utils.compression import compress_response

# build router
router = APIRouter(prefix="/flows", tags=["Flows"])


async def _verify_fs_path(path: str | None) -> None:
    if path:
        path_ = Path(path)
        if not await path_.exists():
            await path_.touch()


async def _save_flow_to_fs(flow: Flow) -> None:
    if flow.fs_path:
        try:
            # First test model serialization separately to catch Pydantic issues
            flow_json = flow.model_dump_json()
            logger.debug(f"Flow {flow.name} serialized successfully, size: {len(flow_json)} chars")

            async with async_open(flow.fs_path, "w") as f:
                await f.write(flow_json)
                logger.debug(f"Flow {flow.name} written to {flow.fs_path} successfully")

        except Exception as e:
            # Enhanced error logging with specific error types
            error_type = type(e).__name__
            logger.error(f"Failed to save flow {flow.name} to filesystem: {error_type}: {str(e)}")

            if "ValidationError" in error_type or "ValueError" in error_type:
                logger.error(f"Flow data validation failed for {flow.name}")
                logger.error(f"Flow data keys: {list(flow.data.keys()) if flow.data else 'None'}")
                if flow.data:
                    logger.error(f"Nodes count: {len(flow.data.get('nodes', []))}")
                    logger.error(f"Edges count: {len(flow.data.get('edges', []))}")

            elif "OSError" in error_type or "IOError" in error_type:
                logger.error(f"File system error for {flow.name}: path={flow.fs_path}")

            elif "UnicodeError" in error_type or "JSONDecodeError" in error_type:
                logger.error(f"Encoding/JSON error for {flow.name}")
                if flow.data and "edges" in flow.data:
                    edge_count = len(flow.data["edges"])
                    logger.error(f"Flow has {edge_count} edges, checking for encoding issues")
                    for i, edge in enumerate(flow.data["edges"][:3]):  # Log first 3 edges
                        logger.error(f"Edge {i}: {edge.get('id', 'no-id')}")

            await logger.aexception("Detailed traceback for flow %s save failure", flow.name)
            # Re-raise the exception to maintain original behavior
            raise


async def _get_unique_flow_name(
    session: AsyncSession,
    base_name: str,
    user_id: UUID,
    folder_id: UUID,
) -> str:
    """
    Check if name exists in folder and append (1), (2), etc. if it does.

    Args:
        session: Database session
        base_name: The desired flow name
        user_id: User ID who owns the flow
        folder_id: Folder ID where the flow will be created

    Returns:
        A unique flow name in the specified folder
    """
    existing_result = await session.exec(
        select(Flow).where(
            Flow.name == base_name,
            Flow.user_id == user_id,
            Flow.folder_id == folder_id,
        )
    )
    existing = existing_result.first()

    if not existing:
        return base_name

    # Find next available number
    counter = 1
    while True:
        new_name = f"{base_name} ({counter})"
        exists_result = await session.exec(
            select(Flow).where(
                Flow.name == new_name,
                Flow.user_id == user_id,
                Flow.folder_id == folder_id,
            )
        )
        if not exists_result.first():
            return new_name
        counter += 1


async def clone_flow_for_marketplace(
    session: AsyncSession,
    original_flow: Flow,
    target_folder_id: UUID,
    user_id: UUID,
    marketplace_flow_name: str,
    version: str,
    tags: list[str] | None = None,
    description: str | None = None,
    locked: bool = True,
) -> Flow:
    """
    Clone a flow for marketplace publication.

    Creates a deep copy of the flow with a new ID and places it in the target folder.
    The cloned flow name follows the pattern: {marketplace_flow_name}-{version}-copy

    Args:
        session: Database session
        original_flow: The flow to clone
        target_folder_id: Folder where the clone should be placed
        user_id: User ID who owns the flow
        marketplace_flow_name: Base name for the cloned flow
        version: Version string for the flow (e.g., "v1.0", "v2.0")
        tags: Optional tags for the cloned flow (marketplace tags from publish modal).
              If None, copies tags from original flow.
        description: Optional description for the cloned flow (from publish modal).
                    If None, copies description from original flow.
        locked: Whether the cloned flow should be locked. Defaults to True.

    Returns:
        The cloned Flow object with a new ID
    """
    import copy

    # Deep copy flow data
    cloned_data = copy.deepcopy(original_flow.data) if original_flow.data else {}

    # Create unique name using version: {flow_name}-{version}-copy
    cloned_name = f"{marketplace_flow_name}-{version}-copy"

    # Create cloned flow
    cloned_flow = Flow(
        name=cloned_name,
        description=description if description is not None else original_flow.description,
        data=cloned_data,
        user_id=user_id,
        folder_id=target_folder_id,
        icon=original_flow.icon,
        tags=tags if tags is not None else original_flow.tags,  # Use marketplace tags if provided
        locked=locked,  # Prevent direct editing by default, but configurable
        is_component=original_flow.is_component,
    )

    session.add(cloned_flow)
    await session.commit()
    await session.refresh(cloned_flow)

    logger.info(f"Cloned flow '{original_flow.name}' to '{cloned_name}' for marketplace")

    return cloned_flow


async def _resolve_project_folder(
    *,
    session: AsyncSession,
    project_name: str | None,
    user_id: UUID,
) -> UUID | None:
    """
    Resolve project name to folder ID, creating folder if needed.

    Args:
        session: Database session
        project_name: Name of project to find or create. If None, uses default project.
        user_id: Current user ID

    Returns:
        Folder ID to use for flow creation
    """
    if not project_name:
        # This should not happen with the updated logic, but handle gracefully
        project_name = "Starter Project"

    # Look for existing folder with matching name (case-insensitive)
    existing_folder = (
        await session.exec(
            select(Folder).where(
                Folder.name.ilike(project_name),  # Case-insensitive search
                Folder.user_id == user_id
            )
        )
    ).first()

    if existing_folder:
        await logger.ainfo(f"Found existing project '{project_name}' with ID: {existing_folder.id}")
        return existing_folder.id

    # Project not found, create it
    await logger.ainfo(f"Project '{project_name}' not found, creating new project")
    new_folder = FolderCreate(
        name=project_name,
        description=f"Project created for {project_name}",
        user_id=user_id
    )

    db_folder = Folder.model_validate(new_folder, from_attributes=True)
    session.add(db_folder)
    await session.commit()
    await session.refresh(db_folder)

    await logger.ainfo(f"Created new project '{project_name}' with ID: {db_folder.id}")
    return db_folder.id


async def _new_flow(
    *,
    session: AsyncSession,
    flow: FlowCreate,
    user_id: UUID,
):
    try:
        await _verify_fs_path(flow.fs_path)

        """Create a new flow."""
        if flow.user_id is None:
            flow.user_id = user_id

        # First check if the flow.name is unique within the folder
        # there might be flows with name like: "MyFlow", "MyFlow (1)", "MyFlow (2)"
        # so we need to check if the name is unique with `like` operator
        # if we find a flow with the same name in the same folder, we add a number to the end of the name
        # based on the highest number found
        if (await session.exec(
            select(Flow)
            .where(Flow.name == flow.name)
            .where(Flow.user_id == user_id)
            .where(Flow.folder_id == flow.folder_id)
        )).first():
            flows = (
                await session.exec(
                    select(Flow)
                    .where(Flow.name.like(f"{flow.name} (%)"))  # type: ignore[attr-defined]
                    .where(Flow.user_id == user_id)
                    .where(Flow.folder_id == flow.folder_id)
                )
            ).all()
            if flows:
                # Use regex to extract numbers only from flows that follow the copy naming pattern:
                # "{original_name} ({number})"
                # This avoids extracting numbers from the original flow name if it naturally contains parentheses
                #
                # Examples:
                # - For flow "My Flow": matches "My Flow (1)", "My Flow (2)" → extracts 1, 2
                # - For flow "Analytics (Q1)": matches "Analytics (Q1) (1)" → extracts 1
                #   but does NOT match "Analytics (Q1)" → avoids extracting the original "1"
                extract_number = re.compile(rf"^{re.escape(flow.name)} \((\d+)\)$")
                numbers = []
                for _flow in flows:
                    result = extract_number.search(_flow.name)
                    if result:
                        numbers.append(int(result.groups(1)[0]))
                if numbers:
                    flow.name = f"{flow.name} ({max(numbers) + 1})"
                else:
                    flow.name = f"{flow.name} (1)"
            else:
                flow.name = f"{flow.name} (1)"
        # Now check if the endpoint is unique within the folder
        if (
            flow.endpoint_name
            and (
                await session.exec(
                    select(Flow)
                    .where(Flow.endpoint_name == flow.endpoint_name)
                    .where(Flow.user_id == user_id)
                    .where(Flow.folder_id == flow.folder_id)
                )
            ).first()
        ):
            flows = (
                await session.exec(
                    select(Flow)
                    .where(Flow.endpoint_name.like(f"{flow.endpoint_name}-%"))  # type: ignore[union-attr]
                    .where(Flow.user_id == user_id)
                    .where(Flow.folder_id == flow.folder_id)
                )
            ).all()
            if flows:
                # The endpoint name is like "my-endpoint","my-endpoint-1", "my-endpoint-2"
                # so we need to get the highest number and add 1
                # we need to get the last part of the endpoint name
                numbers = [int(flow.endpoint_name.split("-")[-1]) for flow in flows]
                flow.endpoint_name = f"{flow.endpoint_name}-{max(numbers) + 1}"
            else:
                flow.endpoint_name = f"{flow.endpoint_name}-1"

        db_flow = Flow.model_validate(flow, from_attributes=True)
        db_flow.updated_at = datetime.now(timezone.utc)

        if db_flow.folder_id is None:
            # Make sure flows always have a folder
            default_folder = (
                await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == user_id))
            ).first()
            if default_folder:
                db_flow.folder_id = default_folder.id

        session.add(db_flow)
    except Exception as e:
        # If it is a validation error, return the error message
        if hasattr(e, "errors"):
            raise HTTPException(status_code=400, detail=str(e)) from e
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e

    return db_flow


@router.post("/", response_model=FlowRead, status_code=201)
async def create_flow(
    *,
    session: DbSession,
    flow: FlowCreate,
    current_user: CurrentActiveUser,
    project_name: str | None = None,
):
    try:
        # Resolve project folder - always assign flows to a project
        if flow.folder_id is None:
            # Use provided project_name or default to "Starter Project"
            default_project_name = project_name or "Starter Project"
            resolved_folder_id = await _resolve_project_folder(
                session=session,
                project_name=default_project_name,
                user_id=current_user.id
            )
            if resolved_folder_id:
                flow.folder_id = resolved_folder_id

        db_flow = await _new_flow(session=session, flow=flow, user_id=current_user.id)
        await session.commit()
        await session.refresh(db_flow)

        await _save_flow_to_fs(db_flow)

    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            # Get the name of the column that failed
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            # UNIQUE constraint failed: flow.user_id, flow.folder_id, flow.name
            # or UNIQUE constraint failed: flow.name
            # Extract the last column (the actual field that needs to be unique)
            column = columns.split(",")[-1].strip()

            raise HTTPException(
                status_code=400, detail=f"{column.capitalize().replace('_', ' ')} must be unique within this folder"
            ) from e
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e
    return db_flow


@router.get("/", response_model=list[FlowRead] | Page[FlowRead] | list[FlowHeader], status_code=200)
async def read_flows(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    remove_example_flows: bool = False,
    components_only: bool = False,
    get_all: bool = True,
    folder_id: UUID | None = None,
    params: Annotated[Params, Depends()],
    header_flows: bool = False,
):
    """Retrieve a list of flows with pagination support.

    Args:
        current_user (User): The current authenticated user.
        session (Session): The database session.
        settings_service (SettingsService): The settings service.
        components_only (bool, optional): Whether to return only components. Defaults to False.

        get_all (bool, optional): Whether to return all flows without pagination. Defaults to True.
        **This field must be True because of backward compatibility with the frontend - Release: 1.0.20**

        folder_id (UUID, optional): The project ID. Defaults to None.
        params (Params): Pagination parameters.
        remove_example_flows (bool, optional): Whether to remove example flows. Defaults to False.
        header_flows (bool, optional): Whether to return only specific headers of the flows. Defaults to False.

    Returns:
        list[FlowRead] | Page[FlowRead] | list[FlowHeader]
        A list of flows or a paginated response containing the list of flows or a list of flow headers.
    """
    try:
        auth_settings = get_settings_service().auth_settings

        default_folder = (await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME))).first()
        default_folder_id = default_folder.id if default_folder else None

        starter_folder = (await session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME))).first()
        starter_folder_id = starter_folder.id if starter_folder else None

        if not starter_folder and not default_folder:
            raise HTTPException(
                status_code=404,
                detail="Starter project and default project not found. Please create a project and add flows to it.",
            )

        if not folder_id:
            folder_id = default_folder_id

        if auth_settings.AUTO_LOGIN:
            stmt = select(Flow).where(
                (Flow.user_id == None) | (Flow.user_id == current_user.id)  # noqa: E711
            )
        else:
            stmt = select(Flow).where(Flow.user_id == current_user.id)

        if remove_example_flows:
            stmt = stmt.where(Flow.folder_id != starter_folder_id)

        if components_only:
            stmt = stmt.where(Flow.is_component == True)  # noqa: E712

        if get_all:
            flows = (await session.exec(stmt)).all()
            flows = validate_is_component(flows)
            if components_only:
                flows = [flow for flow in flows if flow.is_component]
            if remove_example_flows and starter_folder_id:
                flows = [flow for flow in flows if flow.folder_id != starter_folder_id]
            if header_flows:
                # Convert to FlowHeader objects and compress the response
                flow_headers = [FlowHeader.model_validate(flow, from_attributes=True) for flow in flows]
                return compress_response(flow_headers)

            # Compress the full flows response
            return compress_response(flows)

        stmt = stmt.where(Flow.folder_id == folder_id)

        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
            )
            return await apaginate(session, stmt, params=params)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _read_flow(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
):
    """Read a flow. Includes both user-owned flows and system flows (user_id=None)."""
    # TODO: Add role-based access control for system flows
    stmt = select(Flow).where(Flow.id == flow_id).where(
        or_(Flow.user_id == user_id, Flow.user_id == None)  # noqa: E711
    )

    return (await session.exec(stmt)).first()


@router.get("/{flow_id}", response_model=FlowRead, status_code=200)
async def read_flow(
    *,
    request: Request,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
):
    """Read a flow."""
    # Fetch flow without user restriction to check permissions properly
    stmt = select(Flow).where(Flow.id == flow_id)
    db_flow = (await session.exec(stmt)).first()

    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Check if user has permission to view this flow
    user_roles = get_user_roles_from_request(request)

    if not can_view_flow(current_user, db_flow, user_roles):
        # Return 404 instead of 403 for security (don't reveal flow exists)
        raise HTTPException(status_code=404, detail="Flow not found")

    return db_flow


@router.get("/public_flow/{flow_id}", response_model=FlowRead, status_code=200)
async def read_public_flow(
    *,
    session: DbSession,
    flow_id: UUID,
):
    """Read a public flow."""
    access_type = (await session.exec(select(Flow.access_type).where(Flow.id == flow_id))).first()
    if access_type is not AccessTypeEnum.PUBLIC:
        raise HTTPException(status_code=403, detail="Flow is not public")

    current_user = await get_user_by_flow_id_or_endpoint_name(str(flow_id))
    return await read_flow(session=session, flow_id=flow_id, current_user=current_user)


@router.patch("/{flow_id}", response_model=FlowRead, status_code=200)
async def update_flow(
    *,
    request: Request,
    session: DbSession,
    flow_id: UUID,
    flow: FlowUpdate,
    current_user: CurrentActiveUser,
):
    """Update a flow."""
    settings_service = get_settings_service()
    try:
        # Fetch flow without user restriction to check permissions properly
        stmt = select(Flow).where(Flow.id == flow_id)
        db_flow = (await session.exec(stmt)).first()

        if not db_flow:
            raise HTTPException(status_code=404, detail="Flow not found")

        # Check if user has permission to edit this flow
        user_roles = get_user_roles_from_request(request)

        if not can_edit_flow(current_user, db_flow, user_roles):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to edit this flow"
            )

        update_data = flow.model_dump(exclude_unset=True, exclude_none=True)

        # Specifically handle endpoint_name when it's explicitly set to null or empty string
        if flow.endpoint_name is None or flow.endpoint_name == "":
            update_data["endpoint_name"] = None

        if settings_service.settings.remove_api_keys:
            update_data = remove_api_keys(update_data)

        # Check if folder is being changed and validate name uniqueness in the target folder
        if "folder_id" in update_data and update_data["folder_id"] != db_flow.folder_id:
            target_folder_id = update_data["folder_id"]
            flow_name = update_data.get("name", db_flow.name)

            # Check if a flow with the same name exists in the target folder
            existing_flow = (await session.exec(
                select(Flow)
                .where(Flow.name == flow_name)
                .where(Flow.user_id == current_user.id)
                .where(Flow.folder_id == target_folder_id)
                .where(Flow.id != flow_id)  # Exclude current flow
            )).first()

            if existing_flow:
                # Auto-rename the flow being moved
                new_name = await _get_unique_flow_name(
                    session, flow_name, current_user.id, target_folder_id
                )
                update_data["name"] = new_name

            # Check endpoint_name uniqueness in target folder if endpoint_name exists
            if db_flow.endpoint_name:
                endpoint_name = update_data.get("endpoint_name", db_flow.endpoint_name)
                existing_endpoint = (await session.exec(
                    select(Flow)
                    .where(Flow.endpoint_name == endpoint_name)
                    .where(Flow.user_id == current_user.id)
                    .where(Flow.folder_id == target_folder_id)
                    .where(Flow.id != flow_id)  # Exclude current flow
                )).first()

                if existing_endpoint:
                    # Auto-rename the endpoint
                    flows = (
                        await session.exec(
                            select(Flow)
                            .where(Flow.endpoint_name.like(f"{endpoint_name}-%"))  # type: ignore[union-attr]
                            .where(Flow.user_id == current_user.id)
                            .where(Flow.folder_id == target_folder_id)
                        )
                    ).all()
                    if flows:
                        numbers = [int(f.endpoint_name.split("-")[-1]) for f in flows if f.endpoint_name]
                        update_data["endpoint_name"] = f"{endpoint_name}-{max(numbers) + 1}"
                    else:
                        update_data["endpoint_name"] = f"{endpoint_name}-1"

        for key, value in update_data.items():
            setattr(db_flow, key, value)

        await _verify_fs_path(db_flow.fs_path)

        webhook_component = get_webhook_component_in_flow(db_flow.data)
        db_flow.webhook = webhook_component is not None
        db_flow.updated_at = datetime.now(timezone.utc)

        if db_flow.folder_id is None:
            default_folder = (await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME))).first()
            if default_folder:
                db_flow.folder_id = default_folder.id

        session.add(db_flow)
        await session.commit()
        await session.refresh(db_flow)

        await _save_flow_to_fs(db_flow)

    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            # Get the name of the column that failed
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            # UNIQUE constraint failed: flow.user_id, flow.folder_id, flow.name
            # or UNIQUE constraint failed: flow.name
            # Extract the last column (the actual field that needs to be unique)
            column = columns.split(",")[-1].strip()
            raise HTTPException(
                status_code=400, detail=f"{column.capitalize().replace('_', ' ')} must be unique within this folder"
            ) from e

        if hasattr(e, "status_code"):
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e
        raise HTTPException(status_code=500, detail=str(e)) from e

    return db_flow


@router.delete("/{flow_id}", status_code=200)
async def delete_flow(
    *,
    request: Request,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
):
    """Delete a flow."""
    # Fetch flow without user restriction to check permissions properly
    stmt = select(Flow).where(Flow.id == flow_id)
    flow = (await session.exec(stmt)).first()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Check if user has permission to delete this flow
    user_roles = get_user_roles_from_request(request)

    if not can_delete_flow(current_user, flow, user_roles):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete this flow"
        )

    await cascade_delete_flow(session, flow.id)
    await session.commit()
    return {"message": "Flow deleted successfully"}


@router.post("/batch/", response_model=list[FlowRead], status_code=201)
async def create_flows(
    *,
    session: DbSession,
    flow_list: FlowListCreate,
    current_user: CurrentActiveUser,
):
    """Create multiple new flows."""
    db_flows = []
    for flow in flow_list.flows:
        flow.user_id = current_user.id
        db_flow = Flow.model_validate(flow, from_attributes=True)
        session.add(db_flow)
        db_flows.append(db_flow)
    await session.commit()
    for db_flow in db_flows:
        await session.refresh(db_flow)
    return db_flows


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file(
    *,
    session: DbSession,
    file: Annotated[UploadFile, File(...)],
    current_user: CurrentActiveUser,
    folder_id: UUID | None = None,
):
    """Upload flows from a file."""
    contents = await file.read()
    data = orjson.loads(contents)
    response_list = []
    flow_list = FlowListCreate(**data) if "flows" in data else FlowListCreate(flows=[FlowCreate(**data)])
    # Now we set the user_id for all flows
    for flow in flow_list.flows:
        flow.user_id = current_user.id
        if folder_id:
            flow.folder_id = folder_id
        response = await _new_flow(session=session, flow=flow, user_id=current_user.id)
        response_list.append(response)

    try:
        await session.commit()
        for db_flow in response_list:
            await session.refresh(db_flow)
            await _save_flow_to_fs(db_flow)
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            # Get the name of the column that failed
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            # UNIQUE constraint failed: flow.user_id, flow.name
            # or UNIQUE constraint failed: flow.name
            # if the column has id in it, we want the other column
            column = columns.split(",")[1] if "id" in columns.split(",")[0] else columns.split(",")[0]

            raise HTTPException(
                status_code=400, detail=f"{column.capitalize().replace('_', ' ')} must be unique"
            ) from e
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e

    return response_list


@router.delete("/")
async def delete_multiple_flows(
    flow_ids: list[UUID],
    user: CurrentActiveUser,
    db: DbSession,
):
    """Delete multiple flows by their IDs.

    Args:
        flow_ids (List[str]): The list of flow IDs to delete.
        user (User, optional): The user making the request. Defaults to the current active user.
        db (Session, optional): The database session.

    Returns:
        dict: A dictionary containing the number of flows deleted.

    """
    try:
        flows_to_delete = (
            await db.exec(select(Flow).where(col(Flow.id).in_(flow_ids)).where(Flow.user_id == user.id))
        ).all()
        for flow in flows_to_delete:
            await cascade_delete_flow(db, flow.id)

        await db.commit()
        return {"deleted": len(flows_to_delete)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/download/", status_code=200)
async def download_multiple_file(
    flow_ids: list[UUID],
    user: CurrentActiveUser,
    db: DbSession,
):
    """Download all flows as a zip file."""
    flows = (await db.exec(select(Flow).where(and_(Flow.user_id == user.id, Flow.id.in_(flow_ids))))).all()  # type: ignore[attr-defined]

    if not flows:
        raise HTTPException(status_code=404, detail="No flows found.")

    flows_without_api_keys = [remove_api_keys(flow.model_dump()) for flow in flows]

    if len(flows_without_api_keys) > 1:
        # Create a byte stream to hold the ZIP file
        zip_stream = io.BytesIO()

        # Create a ZIP file
        with zipfile.ZipFile(zip_stream, "w") as zip_file:
            for flow in flows_without_api_keys:
                # Convert the flow object to JSON
                flow_json = json.dumps(jsonable_encoder(flow))

                # Write the JSON to the ZIP file
                zip_file.writestr(f"{flow['name']}.json", flow_json)

        # Seek to the beginning of the byte stream
        zip_stream.seek(0)

        # Generate the filename with the current datetime
        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_langflow_flows.zip"

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    return flows_without_api_keys[0]


all_starter_folder_flows_response: Response | None = None


@router.get("/basic_examples/", response_model=list[dict], status_code=200)
async def read_basic_examples():
    """Retrieve JSON content from specific allowed starter project JSON files.

    Returns:
        list[dict]: A list of JSON objects from only the hardcoded allowed files.
    """
    try:
        from langflow.utils.starter_projects_utils import get_filtered_basic_examples_json_content
        return get_filtered_basic_examples_json_content()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
