"""Project management API endpoints.

This module provides REST API endpoints for managing Langflow projects (folders).
Projects serve as containers for flows and components, allowing users to organize
their AI workflows. The module supports CRUD operations, project export/import,
and enhanced ZIP exports with extracted component code for static analysis.
"""

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

import orjson
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlmodel import apaginate
from sqlalchemy import or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession, cascade_delete_flow, custom_params
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
from langflow.utils.project_export import (
    FILENAME_SANITIZE_PATTERN,
    extract_component_code_from_flow,
    extract_env_variables_from_flow,
    generate_env_example_content,
    generate_export_readme,
)
from langflow.utils.version import get_version_info

# Error messages
PROJECT_NOT_FOUND_ERROR = "Project not found"

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/", response_model=FolderRead, status_code=201)
async def create_project(
    *,
    session: DbSession,
    project: FolderCreate,
    current_user: CurrentActiveUser,
):
    """Create a new project.

    Creates a new project folder for the authenticated user. If a project with the same name
    already exists, automatically appends a number suffix to ensure uniqueness.

    Args:
        session: Database session
        project: Project creation data including name, description, and optional flow/component lists
        current_user: Currently authenticated user

    Returns:
        FolderRead: The created project data

    Raises:
        HTTPException: 500 if project creation fails
    """
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
    """Retrieve all projects for the current user.

    Returns a list of all projects owned by the authenticated user, excluding starter folders.
    Projects are sorted with the default folder first.

    Args:
        session: Database session
        current_user: Currently authenticated user

    Returns:
        list[FolderRead]: List of user's projects

    Raises:
        HTTPException: 500 if retrieval fails
    """
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
    """Retrieve a specific project with its flows.

    Returns project details along with associated flows. Supports pagination and filtering
    by component type, flow type, and search terms.

    Args:
        session: Database session
        project_id: UUID of the project to retrieve
        current_user: Currently authenticated user
        params: Optional pagination parameters
        is_component: Filter to show only component flows
        is_flow: Filter to show only regular flows
        search: Search term to filter flows by name

    Returns:
        FolderWithPaginatedFlows | FolderReadWithFlows: Project data with flows

    Raises:
        HTTPException: 404 if project not found, 500 if retrieval fails
    """
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
            raise HTTPException(status_code=404, detail=PROJECT_NOT_FOUND_ERROR) from e
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not project:
        raise HTTPException(status_code=404, detail=PROJECT_NOT_FOUND_ERROR)

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
    project: FolderUpdate,
    current_user: CurrentActiveUser,
):
    """Update an existing project.

    Updates project properties such as name and description. Can also move flows
    between projects by updating the components and flows lists.

    Args:
        session: Database session
        project_id: UUID of the project to update
        project: Project update data with fields to modify
        current_user: Currently authenticated user

    Returns:
        FolderRead: The updated project data

    Raises:
        HTTPException: 404 if project not found, 500 if update fails
    """
    try:
        existing_project = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
        ).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not existing_project:
        raise HTTPException(status_code=404, detail=PROJECT_NOT_FOUND_ERROR)

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
    """Delete a project and all its flows.

    Permanently deletes a project and cascades deletion to all associated flows.
    This operation cannot be undone.

    Args:
        session: Database session
        project_id: UUID of the project to delete
        current_user: Currently authenticated user

    Returns:
        204 No Content on successful deletion

    Raises:
        HTTPException: 404 if project not found, 500 if deletion fails
    """
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
        raise HTTPException(status_code=404, detail=PROJECT_NOT_FOUND_ERROR)

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
    """Download project as a ZIP archive with extracted component code.

    Creates a comprehensive export of the project including:
    - Complete project metadata in project.json
    - Individual flow JSON files organized in flows/ directory
    - Extracted Python code from custom components in components/ directory
    - README.md with export structure documentation

    The extracted code files can be used for static analysis with tools like
    mypy, ruff, and pylint.

    Args:
        session: Database session
        project_id: UUID of the project to export
        current_user: Currently authenticated user

    Returns:
        StreamingResponse: ZIP file download with project export

    Raises:
        HTTPException: 404 if project not found or no flows, 500 if export fails
    """
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
            raise HTTPException(status_code=404, detail=PROJECT_NOT_FOUND_ERROR)

        # Filter flows for current user
        flows = [flow for flow in project.flows if flow.user_id == current_user.id]

        if not flows:
            raise HTTPException(status_code=404, detail="No flows found in project")

        # Build export structure
        version_info = get_version_info()
        project_data = {
            "version": "1.0",
            "langflow_version": version_info["version"],
            "export_type": "project",
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

            # Extract component code and collect environment variables from flows
            all_code_files = {}
            all_env_vars = {}
            for flow in flows:
                try:
                    flow_data = FlowRead.model_validate(flow, from_attributes=True).model_dump()

                    # Get flow name for component organization
                    flow_name = flow_data.get("name", f"flow_{flow_data.get('id', 'unknown')}")
                    safe_flow_name = re.sub(FILENAME_SANITIZE_PATTERN, "_", flow_name)

                    # Extract component code
                    code_files = extract_component_code_from_flow(flow_data, flow_name)
                    for filename, code_content in code_files.items():
                        # Organize by flow
                        flow_code_path = f"components/{safe_flow_name}/{filename}"
                        zip_file.writestr(flow_code_path, code_content.encode("utf-8"))
                        all_code_files[flow_code_path] = True

                    # Extract environment variables
                    env_vars = extract_env_variables_from_flow(flow_data)
                    for var_name, var_info in env_vars.items():
                        if var_name in all_env_vars:
                            # Merge component lists
                            all_env_vars[var_name]["components"].extend(var_info["components"])
                            all_env_vars[var_name]["components"] = list(set(all_env_vars[var_name]["components"]))
                        else:
                            all_env_vars[var_name] = var_info
                except Exception as e:
                    # Log the error and re-raise with more context
                    import traceback

                    flow_id = getattr(flow, "id", "unknown")
                    error_details = f"Error processing flow {flow_id}: {e!s}\nTraceback: {traceback.format_exc()}"
                    raise ValueError(error_details) from e

            # Add README with export structure info
            readme_content = generate_export_readme(
                project_name=project.name,
                version="1.0",
                langflow_version=version_info["version"],
                export_timestamp=datetime.now(tz=timezone.utc).isoformat(),
                flows_count=len(flows),
                code_files_count=len(all_code_files),
            )
            zip_file.writestr("README.md", readme_content.encode("utf-8"))

            # Add .env.example file
            env_example_content = generate_env_example_content(all_env_vars)
            zip_file.writestr(".env.example", env_example_content.encode("utf-8"))

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
    """Upload and import flows from a file into a new project.

    Accepts a JSON file containing flow definitions and creates a new project
    to contain the imported flows. Flow names are automatically made unique
    if conflicts exist.

    Args:
        session: Database session
        file: Uploaded file containing flow data in JSON format
        current_user: Currently authenticated user

    Returns:
        list[FlowRead]: List of created flows

    Raises:
        HTTPException: 400 if no flows found in file or invalid format, 500 if upload fails
    """
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
