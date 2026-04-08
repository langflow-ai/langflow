import warnings
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlmodel import apaginate
from lfx.log.logger import logger
from lfx.services.mcp_composer.service import MCPComposerService
from sqlalchemy import or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    cascade_delete_flow,
    custom_params,
)
from langflow.api.v1.auth_helpers import handle_auth_settings_update
from langflow.api.v1.mcp_projects import register_project_with_composer
from langflow.api.v1.projects_files import download_project_flows, upload_project_flows
from langflow.api.v1.projects_mcp_helpers import (
    cleanup_mcp_on_delete,
    handle_mcp_server_rename,
    register_mcp_servers_for_project,
)
from langflow.initial_setup.constants import ASSISTANT_FOLDER_NAME, STARTER_FOLDER_NAME
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import (
    Folder,
    FolderCreate,
    FolderRead,
    FolderReadWithFlows,
    FolderUpdate,
)
from langflow.services.database.models.folder.pagination_model import FolderWithPaginatedFlows
from langflow.services.deps import get_service, get_settings_service
from langflow.services.schema import ServiceType

router = APIRouter(prefix="/projects", tags=["Projects"])


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards and the escape character itself."""
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


@router.post("/", response_model=FolderRead, status_code=201)
async def create_project(
    *,
    session: DbSession,
    project: FolderCreate,
    current_user: CurrentActiveUser,
):
    try:
        new_project = Folder.model_validate(project, from_attributes=True)
        new_project.user_id = current_user.id
        # First check if the project.name is unique
        # there might be flows with name like: "MyFlow", "MyFlow (1)", "MyFlow (2)"
        # so we need to check if the name is unique with `like` operator
        # if we find a flow with the same name, we add a number to the end of the name
        # based on the highest number found
        if (
            await session.exec(
                statement=select(Folder).where(Folder.name == new_project.name).where(Folder.user_id == current_user.id)
            )
        ).first():
            escaped_project_name = _escape_like(new_project.name)
            project_results = await session.exec(
                select(Folder).where(
                    Folder.name.like(f"{escaped_project_name}%", escape="\\"),  # type: ignore[attr-defined]
                    Folder.user_id == current_user.id,
                )
            )
            if project_results:
                project_names = [project.name for project in project_results]
                project_numbers = []
                for name in project_names:
                    if "(" not in name:
                        continue
                    try:
                        project_numbers.append(int(name.split("(")[-1].split(")")[0]))
                    except ValueError:
                        continue
                if project_numbers:
                    new_project.name = f"{new_project.name} ({max(project_numbers) + 1})"
                else:
                    new_project.name = f"{new_project.name} (1)"

        settings_service = get_settings_service()
        mcp_auth: dict = {"auth_type": "none"}

        if project.auth_settings:
            mcp_auth = project.auth_settings.copy()
            new_project.auth_settings = encrypt_auth_settings(mcp_auth)
        # If AUTO_LOGIN is false, automatically enable API key authentication
        elif not settings_service.auth_settings.AUTO_LOGIN:
            mcp_auth = {"auth_type": "apikey"}
            new_project.auth_settings = encrypt_auth_settings(mcp_auth)
            await logger.adebug(
                "Auto-enabled API key authentication for project %s (%s) due to AUTO_LOGIN=false",
                new_project.name,
                new_project.id,
            )

        session.add(new_project)
        await session.flush()
        await session.refresh(new_project)

        # Auto-register MCP server for this project with configured default auth
        if get_settings_service().settings.add_projects_to_mcp_servers:
            await register_mcp_servers_for_project(new_project, mcp_auth, current_user, session)

        if project.components_list:
            update_statement_components = (
                update(Flow)
                .where(Flow.id.in_(project.components_list), Flow.user_id == current_user.id)  # type: ignore[attr-defined]
                .values(folder_id=new_project.id)
            )
            await session.exec(update_statement_components)

        if project.flows_list:
            update_statement_flows = (
                update(Flow)
                .where(Flow.id.in_(project.flows_list), Flow.user_id == current_user.id)  # type: ignore[attr-defined]
                .values(folder_id=new_project.id)
            )
            await session.exec(update_statement_flows)

        # Convert to FolderRead while session is still active to avoid detached instance errors
        folder_read = FolderRead.model_validate(new_project, from_attributes=True)
    except HTTPException:
        # Re-raise HTTP exceptions (like 409 conflicts) without modification
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return folder_read


@router.get("/", response_model=list[FolderRead], status_code=200)
async def read_projects(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        projects = (
            await session.exec(
                select(Folder).where(
                    or_(Folder.user_id == current_user.id, Folder.user_id == None)  # noqa: E711
                )
            )
        ).all()
        projects = [project for project in projects if project.name != STARTER_FOLDER_NAME]
        sorted_projects = sorted(projects, key=lambda x: x.name != DEFAULT_FOLDER_NAME)

        # Convert to FolderRead while session is still active to avoid detached instance errors
        return [FolderRead.model_validate(project, from_attributes=True) for project in sorted_projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{project_id}", response_model=FolderWithPaginatedFlows | FolderReadWithFlows, status_code=200)
async def read_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    params: Annotated[Params | None, Depends(custom_params)],
    page: Annotated[int | None, Query()] = None,
    size: Annotated[int | None, Query()] = None,
    is_component: bool = False,
    is_flow: bool = False,
    search: str = "",
):
    try:
        project = (
            await session.exec(
                select(Folder)
                .options(selectinload(Folder.flows))
                .where(Folder.id == project_id, Folder.user_id == current_user.id)
            )
        ).first()
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Project not found") from e
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Check if pagination is explicitly requested by the user (both page and size provided)
        if page is not None and size is not None:
            stmt = select(Flow).where(Flow.folder_id == project_id, Flow.user_id == current_user.id)

            if Flow.updated_at is not None:
                stmt = stmt.order_by(Flow.updated_at.desc())  # type: ignore[attr-defined]
            if is_component:
                stmt = stmt.where(Flow.is_component == True)  # noqa: E712
            if is_flow:
                stmt = stmt.where(Flow.is_component == False)  # noqa: E712
            if search:
                _search = _escape_like(search)
                stmt = stmt.where(Flow.name.like(f"%{_search}%", escape="\\"))  # type: ignore[attr-defined]

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
                )
                paginated_flows = await apaginate(session, stmt, params=params)

            return FolderWithPaginatedFlows(folder=FolderRead.model_validate(project), flows=paginated_flows)

        # If no pagination requested, return all flows for the current user
        flows_from_current_user_in_project = [flow for flow in project.flows if flow.user_id == current_user.id]
        project.flows = flows_from_current_user_in_project

        # Convert to FolderReadWithFlows while session is still active to avoid detached instance errors
        return FolderReadWithFlows.model_validate(project, from_attributes=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{project_id}", response_model=FolderRead, status_code=200)
async def update_project(
    *,
    session: DbSession,
    project_id: UUID,
    project: FolderUpdate,  # Assuming FolderUpdate is a Pydantic model defining updatable fields
    current_user: CurrentActiveUser,
    background_tasks: BackgroundTasks,
):
    try:
        existing_project = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
        ).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await session.exec(
        select(Flow.id, Flow.is_component).where(Flow.folder_id == existing_project.id, Flow.user_id == current_user.id)
    )
    flows_and_components = result.all()

    project.flows = [flow_id for flow_id, is_component in flows_and_components if not is_component]
    project.components = [flow_id for flow_id, is_component in flows_and_components if is_component]

    try:
        # Track if MCP Composer needs to be started or stopped
        should_start_mcp_composer = False
        should_stop_mcp_composer = False

        # Check if auth_settings is being updated
        if "auth_settings" in project.model_fields_set:  # Check if auth_settings was explicitly provided
            auth_result = handle_auth_settings_update(
                existing_project=existing_project,
                new_auth_settings=project.auth_settings,
            )

            should_start_mcp_composer = auth_result["should_start_composer"]
            should_stop_mcp_composer = auth_result["should_stop_composer"]

        # Handle project rename and corresponding MCP server rename
        if project.name and project.name != existing_project.name:
            old_project_name = existing_project.name
            existing_project.name = project.name

            if get_settings_service().settings.add_projects_to_mcp_servers:
                await handle_mcp_server_rename(existing_project, old_project_name, project.name, current_user, session)

        if project.description is not None:
            existing_project.description = project.description

        if project.parent_id is not None:
            existing_project.parent_id = project.parent_id

        session.add(existing_project)
        await session.flush()
        await session.refresh(existing_project)

        # Start MCP Composer if auth changed to OAuth
        if should_start_mcp_composer:
            await logger.adebug(
                "Auth settings changed to OAuth for project %s (%s), starting MCP Composer",
                existing_project.name,
                existing_project.id,
            )
            background_tasks.add_task(register_project_with_composer, existing_project)

        # Stop MCP Composer if auth changed FROM OAuth to something else
        elif should_stop_mcp_composer:
            await logger.ainfo(
                "Auth settings changed from OAuth for project %s (%s), stopping MCP Composer",
                existing_project.name,
                existing_project.id,
            )

            mcp_composer_service: MCPComposerService = cast(
                MCPComposerService, get_service(ServiceType.MCP_COMPOSER_SERVICE)
            )
            await mcp_composer_service.stop_project_composer(str(existing_project.id))

        concat_project_components = project.components + project.flows

        flows_ids = (await session.exec(select(Flow.id).where(Flow.folder_id == existing_project.id))).all()

        excluded_flows = list(set(flows_ids) - set(project.flows))

        my_collection_project = (await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME))).first()
        if my_collection_project:
            update_statement_my_collection = (
                update(Flow).where(Flow.id.in_(excluded_flows)).values(folder_id=my_collection_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_my_collection)

        if concat_project_components:
            update_statement_components = (
                update(Flow).where(Flow.id.in_(concat_project_components)).values(folder_id=existing_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_components)

        # Convert to FolderRead while session is still active to avoid detached instance errors
        folder_read = FolderRead.model_validate(existing_project, from_attributes=True)

    except HTTPException:
        # Re-raise HTTP exceptions (like 409 conflicts) without modification
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return folder_read


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    try:
        flows = (
            await session.exec(select(Flow).where(Flow.folder_id == project_id, Flow.user_id == current_user.id))
        ).all()
        if len(flows) > 0:
            for flow in flows:
                await cascade_delete_flow(session, flow.id)

        project = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
        ).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Prevent deletion of the Langflow Assistant folder
    if project.name == ASSISTANT_FOLDER_NAME:
        msg = f"Cannot delete the '{ASSISTANT_FOLDER_NAME}' folder, that contains pre-built flows."
        await logger.adebug("Cannot delete the '%s' folder, that contains pre-built flows.", ASSISTANT_FOLDER_NAME)
        raise HTTPException(
            status_code=403,
            detail=msg,
        )

    await cleanup_mcp_on_delete(project, project_id, current_user, session)

    try:
        await session.delete(project)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/download/{project_id}", status_code=200)
async def download_file(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    """Download all flows from project as a zip file."""
    return await download_project_flows(session=session, project_id=project_id, current_user=current_user)


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file(
    *,
    session: DbSession,
    file: Annotated[UploadFile | None, File()] = None,
    current_user: CurrentActiveUser,
):
    """Upload flows from a file.

    Accepts either a JSON file with project metadata (folder_name, folder_description, flows)
    or a ZIP file containing individual flow JSON files (as produced by the download endpoint).
    """
    return await upload_project_flows(session=session, file=file, current_user=current_user)
