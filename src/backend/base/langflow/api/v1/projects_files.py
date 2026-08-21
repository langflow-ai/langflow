"""File upload and download handlers for projects.

Extracted from projects.py to reduce file size and separate file I/O concerns.
"""

import io
import zipfile
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import orjson
from fastapi import File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    build_content_disposition,
    normalize_code_for_import,
    normalize_flow_for_export,
    strip_flow_secrets,
)
from langflow.api.utils.zip_utils import PROJECT_METADATA_FILENAME, extract_project_from_zip
from langflow.api.v1.flows import create_flows
from langflow.api.v1.flows_helpers import _sanitize_flow_filename
from langflow.api.v1.schemas import FlowListCreate
from langflow.helpers.flow import generate_unique_flow_name
from langflow.helpers.folders import generate_unique_folder_name
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.authorization import FlowAction, filter_visible_resources
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.database.models.base import orjson_dumps
from langflow.services.database.models.flow.model import Flow, FlowCreate, FlowRead
from langflow.services.database.models.folder.model import (
    Folder,
    FolderCreate,
)
from langflow.services.database.models.folder.utils import DEFAULT_PROJECT_TYPE, registered_project_types
from langflow.services.deps import get_settings_service


async def download_project_flows(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    project_owner_id: UUID | None = None,
) -> StreamingResponse:
    """Download all flows from project as a zip file."""
    try:
        owner_id = project_owner_id or current_user.id
        query = select(Folder).where(Folder.id == project_id, Folder.user_id == owner_id)
        result = await session.exec(query)
        project = result.first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        flows_query = select(Flow).where(Flow.folder_id == project_id, Flow.user_id == owner_id)
        flows_result = await session.exec(flows_query)
        visible_flows = await filter_visible_resources(
            current_user,
            resource_type="flow",
            candidates=list(flows_result.all()),
            domain_extractor=lambda flow: _resolve_authz_domain(flow.workspace_id, flow.folder_id),
            owner_extractor=lambda flow: flow.user_id,
            act=FlowAction.READ,
        )
        flows = [FlowRead.model_validate(flow, from_attributes=True) for flow in visible_flows]

        if not flows:
            raise HTTPException(status_code=404, detail="No flows found in project")

        # Strip secret field values then normalise for git-friendly export
        # (sorted keys, volatile fields removed, code fields as line arrays).
        normalised_flows = [normalize_flow_for_export(strip_flow_secrets(flow.model_dump())) for flow in flows]
        zip_stream = io.BytesIO()

        with zipfile.ZipFile(zip_stream, "w") as zip_file:
            # Project-level metadata rides alongside the flows so a typed project survives a
            # round trip. Written only when there is something to carry: an untyped project
            # exports exactly as it did before this member existed. That matters because an
            # importer that predates it reads every .json entry as a flow, so a zip carrying
            # this member imports as a junk flow on an older deployment. Absence means the
            # default type, which is what the importer assumes.
            if project.project_type != DEFAULT_PROJECT_TYPE or project.project_config is not None:
                project_metadata = {
                    "project_type": project.project_type,
                    "project_config": project.project_config,
                }
                zip_file.writestr(
                    PROJECT_METADATA_FILENAME,
                    orjson_dumps(project_metadata, sort_keys=True).encode("utf-8"),
                )
            for flow in normalised_flows:
                safe_name = _sanitize_flow_filename(str(flow["name"]), str(flow.get("id", "flow")))
                # Serialise with sorted keys and 2-space indent for stable diffs.
                flow_json = orjson_dumps(flow, sort_keys=True)
                zip_file.writestr(f"{safe_name}.json", flow_json.encode("utf-8"))

        zip_stream.seek(0)

        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_{project.name}_flows.zip"

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": build_content_disposition(filename)},
        )

    except HTTPException:
        raise
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Project not found") from e
        logger.exception("Error downloading project flows for project_id=%s", project_id)
        raise HTTPException(
            status_code=500, detail="An internal error occurred while downloading project flows."
        ) from e


def _imported_project_type(value: object) -> str:
    """Resolve the project type from an uploaded payload.

    Unlike the create and update paths, an import does not reject an unknown type. The archive
    may come from a deployment that has a project type this one does not, and refusing the whole
    import over it would lose the flows too. Fall back to the default and say so in the log.
    """
    if value is None:
        return DEFAULT_PROJECT_TYPE
    if not isinstance(value, str) or value not in registered_project_types():
        logger.warning(
            "Ignoring unknown project_type %r in uploaded project; importing as %s", value, DEFAULT_PROJECT_TYPE
        )
        return DEFAULT_PROJECT_TYPE
    return value


async def upload_project_flows(
    *,
    session: DbSession,
    file: Annotated[UploadFile | None, File()] = None,
    current_user: CurrentActiveUser,
) -> list[FlowRead]:
    """Upload flows from a file.

    Accepts either a JSON file with project metadata (folder_name, folder_description, flows)
    or a ZIP file containing individual flow JSON files (as produced by the download endpoint).
    """
    if file is None:
        raise HTTPException(status_code=400, detail="No file provided")

    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    # Detect ZIP files and extract flow data
    if zipfile.is_zipfile(io.BytesIO(contents)):
        try:
            flows_data, project_metadata = await extract_project_from_zip(contents)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not flows_data:
            raise HTTPException(status_code=400, detail="No valid flow JSON files found in the ZIP")

        # Use the uploaded filename (without extension) as the project name
        project_name_base = file.filename.rsplit(".", 1)[0] if file.filename else "Imported Project"
        project_name_base = project_name_base or "Imported Project"
        data: dict = {
            "folder_name": project_name_base,
            "folder_description": "",
            "flows": flows_data,
        }
        if project_metadata:
            data["folder_project_type"] = project_metadata.get("project_type")
            data["folder_project_config"] = project_metadata.get("project_config")
    else:
        try:
            data = orjson.loads(contents)
        except orjson.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}") from e

    if not data:
        raise HTTPException(status_code=400, detail="No flows found in the file")

    # Validate that the uploaded JSON has the required structure before accessing keys
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="Invalid project data: expected a JSON object with 'folder_name' and 'flows' fields",
        )

    missing_keys = [key for key in ("folder_name", "flows") if key not in data]
    if missing_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required field(s): {', '.join(missing_keys)}",
        )
    project_name = await generate_unique_folder_name(data["folder_name"], current_user.id, session)

    data["folder_name"] = project_name

    project = FolderCreate(
        name=data["folder_name"],
        description=data.get("folder_description", ""),
        project_type=_imported_project_type(data.get("folder_project_type")),
        project_config=data.get("folder_project_config"),
    )

    new_project = Folder.model_validate(project, from_attributes=True)
    new_project.id = None
    new_project.user_id = current_user.id

    settings_service = get_settings_service()

    # If AUTO_LOGIN is false, automatically enable API key authentication
    if not settings_service.auth_settings.AUTO_LOGIN and not new_project.auth_settings:
        default_auth = {"auth_type": "apikey"}
        new_project.auth_settings = encrypt_auth_settings(default_auth)
        await logger.adebug(
            "Auto-enabled API key authentication for uploaded project %s (%s) due to AUTO_LOGIN=false",
            new_project.name,
            new_project.id,
        )

    session.add(new_project)
    await session.flush()
    await session.refresh(new_project)
    del data["folder_name"]
    data.pop("folder_description", None)

    if "flows" in data:
        # Normalise code fields: if exported with code-as-lines format, rejoin to
        # strings before creating Pydantic models so the DB always stores strings.
        flow_list = FlowListCreate(flows=[FlowCreate(**normalize_code_for_import(flow)) for flow in data["flows"]])
    else:
        raise HTTPException(status_code=400, detail="No flows found in the data")
    # Generate unique names, tracking names already assigned within this batch
    # to avoid collisions when multiple flows would get the same generated name
    used_names_in_batch: set[str] = set()
    for flow in flow_list.flows:
        flow_name = await generate_unique_flow_name(flow.name, current_user.id, session)
        # Ensure the name is also unique within the current batch;
        # generate suffixed candidates and verify each against DB
        base_name = flow_name
        n = 1
        while flow_name in used_names_in_batch:
            candidate = f"{base_name} ({n})"
            n += 1
            flow_name = await generate_unique_flow_name(candidate, current_user.id, session)
        used_names_in_batch.add(flow_name)
        flow.name = flow_name
        flow.user_id = current_user.id
        flow.folder_id = new_project.id
        flow.workspace_id = new_project.workspace_id

    return await create_flows(session=session, flow_list=flow_list, current_user=current_user)
