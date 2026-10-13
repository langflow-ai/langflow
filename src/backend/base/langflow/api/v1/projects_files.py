"""File upload and download handlers for projects.

Extracted from projects.py to reduce file size and separate file I/O concerns.
"""

import io
import zipfile
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

import orjson
from fastapi import File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from lfx.log.logger import logger
from lfx.projects import get_project_type
from sqlmodel import select

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    build_content_disposition,
    normalize_code_for_import,
    normalize_flow_for_export,
    strip_flow_secrets,
)
from langflow.api.utils.composition_zip import composition_zip, extract_composition
from langflow.api.utils.zip_utils import PROJECT_METADATA_FILENAME, extract_project_from_zip
from langflow.api.v1.flows import create_flows
from langflow.api.v1.flows_helpers import _sanitize_flow_filename
from langflow.api.v1.project_compositions import composition_error, export_composition, import_composition
from langflow.api.v1.schemas import FlowListCreate
from langflow.helpers.flow import generate_unique_flow_name
from langflow.helpers.folders import generate_unique_folder_name
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.authorization import FlowAction, filter_visible_resources
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.creation_hooks import (
    RESOURCE_PROJECT,
    PreCreationContext,
    enforce_pre_creation,
)
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

        try:
            definition = get_project_type(project.project_type)
        except ValueError as exc:
            raise HTTPException(422, "This project type is unavailable; its export policy cannot be checked.") from exc
        if not definition.exportable:
            raise HTTPException(422, f"{definition.display_name} export is not supported.")

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

        if not flows and not definition.allows_empty_project:
            raise HTTPException(status_code=404, detail="No flows found in project")

        if definition.archive_format == "composition":
            try:
                composition = await export_composition(session, current_user, project, visible_flows)
                zip_stream = composition_zip(composition)
            except (ValueError, KeyError, TypeError) as exc:
                raise composition_error(exc) from exc
            current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
            return StreamingResponse(
                zip_stream,
                media_type="application/x-zip-compressed",
                headers={"Content-Disposition": build_content_disposition(f"{current_time}_{project.name}_flows.zip")},
            )

        # Strip secret field values then normalise for git-friendly export
        # (sorted keys, volatile fields removed, code fields as line arrays).
        normalised_flows = [normalize_flow_for_export(strip_flow_secrets(flow.model_dump())) for flow in flows]
        zip_stream = io.BytesIO()

        with zipfile.ZipFile(zip_stream, "w") as zip_file:
            # Project-level metadata rides alongside the flows so a typed project survives a
            # round trip. Written unconditionally: the member is not a .json entry, so an
            # importer that predates it never reads it, and it cannot collide with a flow file.
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


def _imported_project_config(value: object, *, strict: bool = False) -> dict | None:
    """Resolve the project config from an uploaded payload.

    ``FolderCreate.project_config`` is a ``dict | None``, so a scalar or a list reaches pydantic
    as a validation error that no handler catches. Legacy ordinary-flow archives retain
    their historical no-config fallback; typed composition archives validate their schema.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        if strict:
            raise HTTPException(422, "Project configuration must be an object or null.")
        logger.warning(
            "Ignoring project_config of type %s in uploaded project; expected an object", type(value).__name__
        )
        return None
    return value


def _imported_project_type(value: object) -> str:
    """Refuse unavailable plugins; never silently change an archive's project type."""
    if value is None:
        return DEFAULT_PROJECT_TYPE
    if not isinstance(value, str) or value not in registered_project_types():
        raise HTTPException(422, "This project type is unavailable. Install its plugin before importing.")
    definition = get_project_type(value)
    if not definition.exportable:
        raise HTTPException(422, f"{definition.display_name} import is not supported.")
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
            composition = await extract_composition(contents)
            if composition is not None:
                return await import_composition(session, current_user, composition)
        except (ValueError, KeyError, TypeError) as exc:
            raise composition_error(exc) from exc
        try:
            flows_data, project_metadata = await extract_project_from_zip(contents)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not flows_data:
            project_type = _imported_project_type((project_metadata or {}).get("project_type"))
            if not get_project_type(project_type).allows_empty_project:
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

    project_type = _imported_project_type(data.get("folder_project_type"))
    definition = get_project_type(project_type)
    project = FolderCreate(
        name=data["folder_name"],
        description=data.get("folder_description", ""),
        project_type=project_type,
        project_config=_imported_project_config(
            data.get("folder_project_config"), strict=definition.archive_format == "composition"
        ),
    )

    if definition.archive_format == "composition":
        from lfx.projects.archives import ArchivedProject, ProjectComposition

        try:
            flows = [FlowCreate(**normalize_code_for_import(flow)).model_dump(mode="json") for flow in data["flows"]]
            original_projects = {str(flow["folder_id"]) for flow in flows if flow.get("folder_id")}
            if len(original_projects) > 1:
                msg = "Use a composition archive for flows from multiple projects."
                raise ValueError(msg)
            project_id = UUID(next(iter(original_projects))) if original_projects else uuid4()
            for flow in flows:
                flow["id"] = flow.get("id") or str(uuid4())
            return await import_composition(
                session,
                current_user,
                ProjectComposition(
                    root_project_id=project_id,
                    projects=[
                        ArchivedProject(
                            id=project_id,
                            name=project.name,
                            description=project.description,
                            project_type=project.project_type,
                            project_config=project.project_config,
                            flows=flows,
                        )
                    ],
                ),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise composition_error(exc) from exc

    # The one project-creation route that does not go through ``projects._new_project``: it
    # builds the Folder itself, so it runs the same hooks through the same helper. Without
    # this call a project limit would be bypassable by uploading a project export.
    await enforce_pre_creation(
        PreCreationContext(
            resource=RESOURCE_PROJECT,
            session=session,
            actor_user_id=current_user.id,
            requested_name=project.name,
        )
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
