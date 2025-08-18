import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

import orjson
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlmodel import apaginate
from sqlalchemy import or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession, cascade_delete_flow, custom_params, remove_api_keys
from langflow.api.v1.flows import create_flows
from langflow.api.v1.schemas import FlowListCreate
from langflow.helpers.flow import generate_unique_flow_name
from langflow.helpers.folders import generate_unique_folder_name
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
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
from langflow.utils.version import get_version_info

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

        session.add(new_project)
        await session.commit()
        await session.refresh(new_project)

        if project.components_list:
            update_statement_components = (
                update(Flow).where(Flow.id.in_(project.components_list)).values(folder_id=new_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_components)
            await session.commit()

        if project.flows_list:
            update_statement_flows = (
                update(Flow).where(Flow.id.in_(project.flows_list)).values(folder_id=new_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_flows)
            await session.commit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return new_project


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
        return sorted(projects, key=lambda x: x.name != DEFAULT_FOLDER_NAME)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{project_id}", response_model=FolderWithPaginatedFlows | FolderReadWithFlows, status_code=200)
async def read_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    params: Annotated[Params | None, Depends(custom_params)],
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
        if params and params.page and params.size:
            stmt = select(Flow).where(Flow.folder_id == project_id)

            if Flow.updated_at is not None:
                stmt = stmt.order_by(Flow.updated_at.desc())  # type: ignore[attr-defined]
            if is_component:
                stmt = stmt.where(Flow.is_component == True)  # noqa: E712
            if is_flow:
                stmt = stmt.where(Flow.is_component == False)  # noqa: E712
            if search:
                stmt = stmt.where(Flow.name.like(f"%{search}%"))  # type: ignore[attr-defined]
            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
                )
                paginated_flows = await apaginate(session, stmt, params=params)

            return FolderWithPaginatedFlows(folder=FolderRead.model_validate(project), flows=paginated_flows)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    flows_from_current_user_in_project = [flow for flow in project.flows if flow.user_id == current_user.id]
    project.flows = flows_from_current_user_in_project
    return project


@router.patch("/{project_id}", response_model=FolderRead, status_code=200)
async def update_project(
    *,
    session: DbSession,
    project_id: UUID,
    project: FolderUpdate,  # Assuming FolderUpdate is a Pydantic model defining updatable fields
    current_user: CurrentActiveUser,
):
    try:
        existing_project = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
        ).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        if project.name and project.name != existing_project.name:
            existing_project.name = project.name
            session.add(existing_project)
            await session.commit()
            await session.refresh(existing_project)
            return existing_project

        project_data = existing_project.model_dump(exclude_unset=True)
        for key, value in project_data.items():
            if key not in {"components", "flows"}:
                setattr(existing_project, key, value)
        session.add(existing_project)
        await session.commit()
        await session.refresh(existing_project)

        concat_project_components = project.components + project.flows

        flows_ids = (await session.exec(select(Flow.id).where(Flow.folder_id == existing_project.id))).all()

        excluded_flows = list(set(flows_ids) - set(concat_project_components))

        my_collection_project = (await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME))).first()
        if my_collection_project:
            update_statement_my_collection = (
                update(Flow).where(Flow.id.in_(excluded_flows)).values(folder_id=my_collection_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_my_collection)
            await session.commit()

        if concat_project_components:
            update_statement_components = (
                update(Flow).where(Flow.id.in_(concat_project_components)).values(folder_id=existing_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_components)
            await session.commit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return existing_project


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

    try:
        await session.delete(project)
        await session.commit()
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
    """Download project with flows and extracted component code as a ZIP archive."""
    import re

    try:
        # Get project with flows
        project = (
            await session.exec(
                select(Folder)
                .options(selectinload(Folder.flows))
                .where(Folder.id == project_id, Folder.user_id == current_user.id)
            )
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Filter flows for current user
        flows = [flow for flow in project.flows if flow.user_id == current_user.id]

        if not flows:
            raise HTTPException(status_code=404, detail="No flows found in project")

        # Build export structure
        version_info = get_version_info()
        project_data = {
            "version": "2.0",  # Enhanced export format version
            "langflow_version": version_info["version"],
            "export_type": "project_enhanced",
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
            "project": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "auth_settings": getattr(project, "auth_settings", {}) or {},
            },
            "flows": [FlowRead.model_validate(flow, from_attributes=True).model_dump(mode="json") for flow in flows],
        }

        # Create ZIP archive
        zip_stream = io.BytesIO()

        with zipfile.ZipFile(zip_stream, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add main project metadata
            project_json = json.dumps(project_data, indent=2)
            zip_file.writestr("project.json", project_json.encode("utf-8"))

            # Add individual flow files and extract component code
            all_code_files = {}
            for flow in flows:
                try:
                    flow_data = remove_api_keys(FlowRead.model_validate(flow, from_attributes=True).model_dump())
                    flow_json = json.dumps(jsonable_encoder(flow_data), indent=2)

                    # Sanitize flow name for filename
                    flow_name = flow_data.get("name", f"flow_{flow_data.get('id', 'unknown')}")
                    safe_flow_name = re.sub(r"[^a-zA-Z0-9_-]", "_", flow_name)
                    zip_file.writestr(f"flows/{safe_flow_name}.json", flow_json.encode("utf-8"))

                    # Extract component code
                    code_files = extract_component_code_from_flow(flow_data, flow_name)
                    for filename, code_content in code_files.items():
                        # Organize by flow
                        flow_code_path = f"components/{safe_flow_name}/{filename}"
                        zip_file.writestr(flow_code_path, code_content.encode("utf-8"))
                        all_code_files[flow_code_path] = True
                except Exception as e:
                    # Log the error and re-raise with more context
                    import traceback

                    flow_id = getattr(flow, "id", "unknown")
                    error_details = f"Error processing flow {flow_id}: {e!s}\nTraceback: {traceback.format_exc()}"
                    raise ValueError(error_details) from e

            # Add README with export structure info
            readme_content = f"""# {project.name}

This export contains the complete project structure with extracted component code.

## Structure

- `project.json` - Project metadata and complete flow definitions
- `flows/` - Individual flow JSON files
- `components/` - Extracted Python code from custom components, organized by flow

## Export Info

- Export format version: 2.0
- Langflow version: {version_info["version"]}
- Exported at: {datetime.now(tz=timezone.utc).isoformat()}
- Total flows: {len(flows)}
- Code files extracted: {len(all_code_files)}

## Usage

The extracted Python files in the `components/` directory can be used for:
- Static analysis with tools like mypy, ruff, pylint
- Code review and auditing
- Understanding component logic outside of Langflow

Each component file includes metadata in its docstring indicating the original component type, ID, and parent flow.
"""
            zip_file.writestr("README.md", readme_content.encode("utf-8"))

        zip_stream.seek(0)

        # Generate filename
        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_{project.name}_export.zip"

        # URL encode filename to handle non-ASCII characters
        encoded_filename = quote(filename)

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file(
    *,
    session: DbSession,
    file: Annotated[UploadFile, File(...)],
    current_user: CurrentActiveUser,
):
    """Upload flows from a file."""
    contents = await file.read()
    data = orjson.loads(contents)

    if not data:
        raise HTTPException(status_code=400, detail="No flows found in the file")

    project_name = await generate_unique_folder_name(data["folder_name"], current_user.id, session)

    data["folder_name"] = project_name

    project = FolderCreate(name=data["folder_name"], description=data["folder_description"])

    new_project = Folder.model_validate(project, from_attributes=True)
    new_project.id = None
    new_project.user_id = current_user.id
    session.add(new_project)
    await session.commit()
    await session.refresh(new_project)

    del data["folder_name"]
    del data["folder_description"]

    if "flows" in data:
        flow_list = FlowListCreate(flows=[FlowCreate(**flow) for flow in data["flows"]])
    else:
        raise HTTPException(status_code=400, detail="No flows found in the data")
    # Now we set the user_id for all flows
    for flow in flow_list.flows:
        flow_name = await generate_unique_flow_name(flow.name, current_user.id, session)
        flow.name = flow_name
        flow.user_id = current_user.id
        flow.folder_id = new_project.id

    return await create_flows(session=session, flow_list=flow_list, current_user=current_user)


@router.get("/export/{project_id}", status_code=200)
async def export_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    """Export a project with flows and extracted component code as a ZIP archive."""
    import re

    try:
        # Get project with flows
        project = (
            await session.exec(
                select(Folder)
                .options(selectinload(Folder.flows))
                .where(Folder.id == project_id, Folder.user_id == current_user.id)
            )
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Filter flows for current user
        flows = [flow for flow in project.flows if flow.user_id == current_user.id]

        if not flows:
            raise HTTPException(status_code=404, detail="No flows found in project")

        # Build export structure
        version_info = get_version_info()
        project_data = {
            "version": "1.0",  # Enhanced export format version
            "langflow_version": version_info["version"],
            "export_type": "project_enhanced",
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
            "project": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "auth_settings": getattr(project, "auth_settings", {}) or {},
            },
            "flows": [FlowRead.model_validate(flow, from_attributes=True).model_dump(mode="json") for flow in flows],
        }

        # Create ZIP archive
        zip_stream = io.BytesIO()

        with zipfile.ZipFile(zip_stream, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add main project metadata
            project_json = json.dumps(project_data, indent=2)
            zip_file.writestr("project.json", project_json.encode("utf-8"))

            # Add individual flow files and extract component code
            all_code_files = {}
            for flow in flows:
                try:
                    flow_data = remove_api_keys(FlowRead.model_validate(flow, from_attributes=True).model_dump())
                    flow_json = json.dumps(jsonable_encoder(flow_data), indent=2)

                    # Sanitize flow name for filename
                    flow_name = flow_data.get("name", f"flow_{flow_data.get('id', 'unknown')}")
                    safe_flow_name = re.sub(r"[^a-zA-Z0-9_-]", "_", flow_name)
                    zip_file.writestr(f"flows/{safe_flow_name}.json", flow_json.encode("utf-8"))

                    # Extract component code
                    code_files = extract_component_code_from_flow(flow_data, flow_name)
                    for filename, code_content in code_files.items():
                        # Organize by flow
                        flow_code_path = f"components/{safe_flow_name}/{filename}"
                        zip_file.writestr(flow_code_path, code_content.encode("utf-8"))
                        all_code_files[flow_code_path] = True
                except Exception as e:
                    # Log the error and re-raise with more context
                    import traceback

                    flow_id = getattr(flow, "id", "unknown")
                    error_details = f"Error processing flow {flow_id}: {e!s}\nTraceback: {traceback.format_exc()}"
                    raise ValueError(error_details) from e

            # Add README with export structure info
            readme_content = f"""# {project.name}

This export contains the complete project structure with extracted component code.

## Structure

- `project.json` - Project metadata and complete flow definitions
- `flows/` - Individual flow JSON files
- `components/` - Extracted Python code from custom components, organized by flow

## Export Info

- Export format version: 1.0
- Langflow version: {version_info["version"]}
- Exported at: {datetime.now(tz=timezone.utc).isoformat()}
- Total flows: {len(flows)}
- Code files extracted: {len(all_code_files)}

## Usage

The extracted Python files in the `components/` directory can be used for:
- Static analysis with tools like mypy, ruff, pylint
- Code review and auditing
- Understanding component logic outside of Langflow

Each component file includes metadata in its docstring indicating the original component type, ID, and parent flow.
"""
            zip_file.writestr("README.md", readme_content.encode("utf-8"))

        zip_stream.seek(0)

        # Generate filename
        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_{project.name}_export.zip"

        # URL encode filename to handle non-ASCII characters
        encoded_filename = quote(filename)

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _is_valid_node(node: dict) -> bool:
    """Check if a node is valid and has the required structure."""
    return isinstance(node, dict) and "data" in node and "node" in node["data"] and "template" in node["data"]["node"]


def _extract_code_from_node(node: dict) -> str | None:
    """Extract code content from a node's template."""
    template = node["data"]["node"]["template"]
    if "code" not in template:
        return None

    code_field = template["code"]
    if not isinstance(code_field, dict) or "value" not in code_field:
        return None

    code_content = code_field["value"]
    if not code_content or not isinstance(code_content, str):
        return None

    return code_content


def _generate_code_filename(node: dict) -> str:
    """Generate a sanitized filename for the component code."""
    node_data = node["data"]
    component_type = node_data.get("type", "component")
    component_id = node.get("id", "unknown")

    # Sanitize filename components
    safe_component_type = _RE_SAFE_COMPONENT_TYPE.sub("_", component_type)
    safe_component_id = _RE_SAFE_COMPONENT_ID.sub("_", component_id)

    return f"{safe_component_type}_{safe_component_id}.py"


def _create_code_file_content(node: dict, flow_name: str, code_content: str) -> str:
    """Create the complete code file content with docstring."""
    node_data = node["data"]
    component_type = node_data.get("type", "component")
    component_id = node.get("id", "unknown")

    docstring = f'"""Component: {component_type}\nID: {component_id}\nFlow: {flow_name}\n"""\n\n'
    return docstring + code_content


def extract_component_code_from_flow(flow_data: dict, flow_name: str) -> dict[str, str]:
    """Extract code from components in a flow and return a mapping of filenames to code content."""
    code_files = {}

    if "data" not in flow_data or "nodes" not in flow_data["data"]:
        return code_files

    nodes = flow_data["data"]["nodes"]

    for node in nodes:
        if not _is_valid_node(node):
            continue

        code_content = _extract_code_from_node(node)
        if code_content is None:
            continue

        filename = _generate_code_filename(node)
        file_content = _create_code_file_content(node, flow_name, code_content)
        code_files[filename] = file_content

    return code_files


_RE_SAFE_COMPONENT_TYPE = re.compile(r"\W")

_RE_SAFE_COMPONENT_ID = re.compile(r"[^a-zA-Z0-9_-]")
