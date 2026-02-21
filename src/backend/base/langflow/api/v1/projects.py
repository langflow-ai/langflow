import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Annotated, cast
from urllib.parse import quote
from uuid import UUID

import orjson
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlmodel import apaginate
from lfx.log.logger import logger
from lfx.services.mcp_composer.service import MCPComposerService
from sqlalchemy import or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession, cascade_delete_flow, custom_params, remove_api_keys
from langflow.api.utils.mcp.config_utils import validate_mcp_server_for_project
from langflow.api.v1.auth_helpers import handle_auth_settings_update
from langflow.api.v1.flows import create_flows
from langflow.api.v1.mcp_projects import (
    get_project_sse_url,  # noqa: F401
    get_project_streamable_http_url,
    register_project_with_composer,
)
from langflow.api.v1.schemas import FlowListCreate
from langflow.api.v2.mcp import update_server
from langflow.helpers.flow import generate_unique_flow_name
from langflow.helpers.folders import generate_unique_folder_name
from langflow.initial_setup.constants import ASSISTANT_FOLDER_NAME, STARTER_FOLDER_NAME
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.database.models.flow.model import Flow, FlowCreate, FlowRead
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import (
    Folder,
    FolderCreate,
    FolderRead,
    FolderReadWithFlows,
    FolderUpdate,
)
from langflow.services.database.models.folder.pagination_model import FolderWithPaginatedFlows
from langflow.services.deps import get_service, get_settings_service, get_storage_service
from langflow.services.schema import ServiceType

router = APIRouter(prefix="/projects", tags=["Projects"])


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
        if (
            await session.exec(
                statement=select(Folder).where(Folder.name == new_project.name).where(Folder.user_id == current_user.id)
            )
        ).first():
            project_results = await session.exec(
                select(Folder).where(
                    Folder.name.like(f"{new_project.name}%"),  # type: ignore[attr-defined]
                    Folder.user_id == current_user.id,
                )
            )
            if project_results:
                project_names = [project.name for project in project_results]
                project_numbers = [int(name.split("(")[-1].split(")")[0]) for name in project_names if "(" in name]
                if project_numbers:
                    new_project.name = f"{new_project.name} ({max(project_numbers) + 1})"
                else:
                    new_project.name = f"{new_project.name} (1)"

        settings_service = get_settings_service()
        default_auth = {"auth_type": "none"}
        if not settings_service.auth_settings.AUTO_LOGIN and not new_project.auth_settings:
            default_auth = {"auth_type": "apikey"}
            new_project.auth_settings = encrypt_auth_settings(default_auth)
            await logger.adebug(
                f"Auto-enabled API key authentication for project {new_project.name} "
                f"({new_project.id}) due to AUTO_LOGIN=false"
            )

        session.add(new_project)
        await session.flush()
        await session.refresh(new_project)

        if get_settings_service().settings.add_projects_to_mcp_servers:
            try:
                streamable_http_url = await get_project_streamable_http_url(new_project.id)
                if default_auth.get("auth_type", "none") == "apikey":
                    api_key_name = f"MCP Project {new_project.name} - default"
                    unmasked_api_key = await create_api_key(session, ApiKeyCreate(name=api_key_name), current_user.id)
                    command = "uvx"
                    args = ["mcp-proxy", "--transport", "streamablehttp", "--headers", "x-api-key", unmasked_api_key.api_key, streamable_http_url]
                elif default_auth.get("auth_type", "none") == "oauth":
                    msg = "OAuth authentication is not yet implemented for MCP server creation during project creation."
                    logger.warning(msg)
                    raise HTTPException(status_code=501, detail=msg)
                else:
                    command = "uvx"
                    args = ["mcp-proxy", "--transport", "streamablehttp", streamable_http_url]

                server_config = {"command": command, "args": args}
                validation_result = await validate_mcp_server_for_project(
                    new_project.id, new_project.name, current_user, session,
                    get_storage_service(), get_settings_service(), operation="create",
                )
                if validation_result.has_conflict:
                    await logger.aerror(validation_result.conflict_message)
                    raise HTTPException(status_code=409, detail=validation_result.conflict_message)
                if validation_result.should_skip:
                    await logger.adebug(f"MCP server already exists for project {new_project.id}, updating")
                server_name = validation_result.server_name
                await update_server(server_name, server_config, current_user, session, get_storage_service(), get_settings_service())
            except HTTPException:
                raise
            except NotImplementedError:
                msg = "OAuth as default MCP authentication type is not yet implemented"
                await logger.aerror(msg)
                raise
            except Exception as e:
                msg = f"Failed to auto-register MCP server for project {new_project.id}: {e}"
                await logger.aexception(msg, exc_info=True)

        if project.components_list:
            await session.exec(update(Flow).where(Flow.id.in_(project.components_list)).values(folder_id=new_project.id))
        if project.flows_list:
            await session.exec(update(Flow).where(Flow.id.in_(project.flows_list)).values(folder_id=new_project.id))
        folder_read = FolderRead.model_validate(new_project, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return folder_read


@router.get("/", response_model=list[FolderRead], status_code=200)
async def read_projects(*, session: DbSession, current_user: CurrentActiveUser):
    try:
        projects = (await session.exec(select(Folder).where(or_(Folder.user_id == current_user.id, Folder.user_id == None)))).all()
        projects = [p for p in projects if p.name != STARTER_FOLDER_NAME]
        sorted_projects = sorted(projects, key=lambda x: x.name != DEFAULT_FOLDER_NAME)
        return [FolderRead.model_validate(p, from_attributes=True) for p in sorted_projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{project_id}", response_model=FolderWithPaginatedFlows | FolderReadWithFlows, status_code=200)
async def read_project(*, session: DbSession, project_id: UUID, current_user: CurrentActiveUser, params: Annotated[Params | None, Depends(custom_params)], page: Annotated[int | None, Query()] = None, size: Annotated[int | None, Query()] = None, is_component: bool = False, is_flow: bool = False, search: str = ""):
    try:
        project = (await session.exec(select(Folder).options(selectinload(Folder.flows)).where(Folder.id == project_id, Folder.user_id == current_user.id))).first()
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Project not found") from e
        raise HTTPException(status_code=500, detail=str(e)) from e
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        if page is not None and size is not None:
            stmt = select(Flow).where(Flow.folder_id == project_id)
            if Flow.updated_at is not None:
                stmt = stmt.order_by(Flow.updated_at.desc())
            if is_component:
                stmt = stmt.where(Flow.is_component == True)
            if is_flow:
                stmt = stmt.where(Flow.is_component == False)
            if search:
                stmt = stmt.where(Flow.name.like(f"%{search}%"))
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy")
                paginated_flows = await apaginate(session, stmt, params=params)
            return FolderWithPaginatedFlows(folder=FolderRead.model_validate(project), flows=paginated_flows)
        flows_from_current_user_in_project = [flow for flow in project.flows if flow.user_id == current_user.id]
        project.flows = flows_from_current_user_in_project
        return FolderReadWithFlows.model_validate(project, from_attributes=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{project_id}", response_model=FolderRead, status_code=200)
async def update_project(*, session: DbSession, project_id: UUID, project: FolderUpdate, current_user: CurrentActiveUser, background_tasks: BackgroundTasks):
    try:
        existing_project = (await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")
    result = await session.exec(select(Flow.id, Flow.is_component).where(Flow.folder_id == existing_project.id, Flow.user_id == current_user.id))
    flows_and_components = result.all()
    project.flows = [flow_id for flow_id, is_component in flows_and_components if not is_component]
    project.components = [flow_id for flow_id, is_component in flows_and_components if is_component]
    try:
        should_start_mcp_composer = False
        should_stop_mcp_composer = False
        if "auth_settings" in project.model_fields_set:
            auth_result = handle_auth_settings_update(existing_project=existing_project, new_auth_settings=project.auth_settings)
            should_start_mcp_composer = auth_result["should_start_composer"]
            should_stop_mcp_composer = auth_result["should_stop_composer"]
        if project.name and project.name != existing_project.name:
            old_project_name = existing_project.name
            existing_project.name = project.name
            if get_settings_service().settings.add_projects_to_mcp_servers:
                try:
                    old_validation = await validate_mcp_server_for_project(existing_project.id, old_project_name, current_user, session, get_storage_service(), get_settings_service(), operation="update")
                    new_validation = await validate_mcp_server_for_project(existing_project.id, project.name, current_user, session, get_storage_service(), get_settings_service(), operation="update")
                    if old_validation.server_name != new_validation.server_name:
                        if new_validation.has_conflict:
                            await logger.aerror(new_validation.conflict_message)
                            raise HTTPException(status_code=409, detail=new_validation.conflict_message)
                        if old_validation.server_exists and old_validation.project_id_matches:
                            await update_server(old_validation.server_name, {}, current_user, session, get_storage_service(), get_settings_service(), delete=True)
                            await update_server(new_validation.server_name, old_validation.existing_config or {}, current_user, session, get_storage_service(), get_settings_service())
                except HTTPException:
                    raise
                except Exception as e:
                    await logger.awarning(f"Failed to handle MCP server name update: {e}")
        if project.description is not None:
            existing_project.description = project.description
        if project.parent_id is not None:
            existing_project.parent_id = project.parent_id
        session.add(existing_project)
        await session.flush()
        await session.refresh(existing_project)
        if should_start_mcp_composer:
            background_tasks.add_task(register_project_with_composer, existing_project)
        elif should_stop_mcp_composer:
            mcp_composer_service = cast(MCPComposerService, get_service(ServiceType.MCP_COMPOSER_SERVICE))
            await mcp_composer_service.stop_project_composer(str(existing_project.id))
        concat_project_components = project.components + project.flows
        flows_ids = (await session.exec(select(Flow.id).where(Flow.folder_id == existing_project.id))).all()
        excluded_flows = list(set(flows_ids) - set(project.flows))
        my_collection_project = (await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME))).first()
        if my_collection_project:
            await session.exec(update(Flow).where(Flow.id.in_(excluded_flows)).values(folder_id=my_collection_project.id))
        if concat_project_components:
            await session.exec(update(Flow).where(Flow.id.in_(concat_project_components)).values(folder_id=existing_project.id))
        folder_read = FolderRead.model_validate(existing_project, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return folder_read


@router.delete("/{project_id}", status_code=204)
async def delete_project(*, session: DbSession, project_id: UUID, current_user: CurrentActiveUser):
    try:
        flows = (await session.exec(select(Flow).where(Flow.folder_id == project_id, Flow.user_id == current_user.id))).all()
        if len(flows) > 0:
            for flow in flows:
                await cascade_delete_flow(session, flow.id)
        project = (await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.name == ASSISTANT_FOLDER_NAME:
        raise HTTPException(status_code=403, detail=f"Cannot delete the {ASSISTANT_FOLDER_NAME} folder")
    if project.auth_settings and project.auth_settings.get("auth_type") == "oauth":
        try:
            mcp_composer_service = cast(MCPComposerService, get_service(ServiceType.MCP_COMPOSER_SERVICE))
            await mcp_composer_service.stop_project_composer(str(project_id))
        except Exception as e:
            await logger.aerror(f"Failed to stop MCP Composer: {e}")
    if get_settings_service().settings.add_projects_to_mcp_servers:
        try:
            validation_result = await validate_mcp_server_for_project(project_id, project.name, current_user, session, get_storage_service(), get_settings_service(), operation="delete")
            if validation_result.server_exists and validation_result.project_id_matches:
                await update_server(validation_result.server_name, {}, current_user, session, get_storage_service(), get_settings_service(), delete=True)
        except Exception as e:
            await logger.awarning(f"Failed to handle MCP server cleanup: {e}")
    try:
        await session.delete(project)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/download/{project_id}", status_code=200)
async def download_file(*, session: DbSession, project_id: UUID, current_user: CurrentActiveUser):
    """Download all flows from project as a zip file."""
    try:
        query = select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id)
        result = await session.exec(query)
        project = result.first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        flows_query = select(Flow).where(Flow.folder_id == project_id)
        flows_result = await session.exec(flows_query)
        flows = [FlowRead.model_validate(flow, from_attributes=True) for flow in flows_result.all()]
        if not flows:
            raise HTTPException(status_code=404, detail="No flows found in project")
        flows_without_api_keys = [remove_api_keys(flow.model_dump()) for flow in flows]
        zip_stream = io.BytesIO()
        with zipfile.ZipFile(zip_stream, "w") as zip_file:
            for flow in flows_without_api_keys:
                flow_json = json.dumps(jsonable_encoder(flow))
                zip_file.writestr(f"{flow['name']}.json", flow_json.encode("utf-8"))
        zip_stream.seek(0)
        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_{project.name}_flows.zip"
        encoded_filename = quote(filename)
        return StreamingResponse(zip_stream, media_type="application/x-zip-compressed", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"})
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Project not found") from e
        raise HTTPException(status_code=500, detail=str(e)) from e


def _extract_project_name_from_zip_filename(filename: str | None) -> str:
    """Extract the project name from a zip filename produced by download_file."""
    if not filename:
        return "Imported Project"
    name = filename
    if name.lower().endswith(".zip"):
        name = name[:-4]
    name = name.removesuffix("_flows")
    name = re.sub(r"^\d{8}_\d{6}_", "", name)
    return name or "Imported Project"


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file(*, session: DbSession, file: Annotated[UploadFile, File(...)], current_user: CurrentActiveUser):
    """Upload flows from a file. Accepts JSON or zip archive from /download/ endpoint."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if contents[:4] == b"PK\x03\x04":
        try:
            zip_buffer = io.BytesIO(contents)
            with zipfile.ZipFile(zip_buffer, "r") as zf:
                flow_dicts = []
                for entry_name in zf.namelist():
                    if not entry_name.lower().endswith(".json"):
                        continue
                    raw = zf.read(entry_name)
                    flow_dicts.append(orjson.loads(raw))
            if not flow_dicts:
                raise HTTPException(status_code=400, detail="No flow JSON files found inside the zip archive")
            folder_name = _extract_project_name_from_zip_filename(file.filename)
            data = {"folder_name": folder_name, "folder_description": "", "flows": flow_dicts}
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Uploaded file appears to be a zip but is corrupted") from exc
    else:
        try:
            data = orjson.loads(contents)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON.") from exc
    if not data:
        raise HTTPException(status_code=400, detail="No flows found in the file")
    project_name = await generate_unique_folder_name(data["folder_name"], current_user.id, session)
    data["folder_name"] = project_name
    project = FolderCreate(name=data["folder_name"], description=data.get("folder_description", ""))
    new_project = Folder.model_validate(project, from_attributes=True)
    new_project.id = None
    new_project.user_id = current_user.id
    settings_service = get_settings_service()
    if not settings_service.auth_settings.AUTO_LOGIN and not new_project.auth_settings:
        default_auth = {"auth_type": "apikey"}
        new_project.auth_settings = encrypt_auth_settings(default_auth)
    session.add(new_project)
    await session.flush()
    await session.refresh(new_project)
    del data["folder_name"]
    data.pop("folder_description", None)
    if "flows" in data:
        flow_list = FlowListCreate(flows=[FlowCreate(**flow) for flow in data["flows"]])
    else:
        raise HTTPException(status_code=400, detail="No flows found in the data")
    for flow in flow_list.flows:
        flow.name = await generate_unique_flow_name(flow.name, current_user.id, session)
        flow.user_id = current_user.id
        flow.folder_id = new_project.id
    return await create_flows(session=session, flow_list=flow_list, current_user=current_user)