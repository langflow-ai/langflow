from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import orjson
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi_pagination import Page, Params, add_pagination
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import Session, and_, col, select

from langflow.api.utils import CurrentActiveUser, DbSession, cascade_delete_flow, remove_api_keys, validate_is_component
from langflow.api.v1.schemas import FlowListCreate
from langflow.initial_setup.setup import STARTER_FOLDER_NAME
from langflow.services.database.models.flow import Flow, FlowCreate, FlowRead, FlowUpdate
from langflow.services.database.models.flow.model import FlowHeader
from langflow.services.database.models.flow.utils import get_webhook_component_in_flow
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.transactions.crud import get_transactions_by_flow_id
from langflow.services.database.models.user.model import User
from langflow.services.database.models.vertex_builds.crud import get_vertex_builds_by_flow_id
from langflow.services.deps import get_settings_service
from langflow.services.settings.service import SettingsService

# build router
router = APIRouter(prefix="/flows", tags=["Flows"])


@router.post("/", response_model=FlowRead, status_code=201)
async def create_flow(
    *,
    session: DbSession,
    flow: FlowCreate,
    current_user: CurrentActiveUser,
):
    try:
        """Create a new flow."""
        if flow.user_id is None:
            flow.user_id = current_user.id

        # First check if the flow.name is unique
        # there might be flows with name like: "MyFlow", "MyFlow (1)", "MyFlow (2)"
        # so we need to check if the name is unique with `like` operator
        # if we find a flow with the same name, we add a number to the end of the name
        # based on the highest number found
        if session.exec(select(Flow).where(Flow.name == flow.name).where(Flow.user_id == current_user.id)).first():
            flows = session.exec(
                select(Flow).where(Flow.name.like(f"{flow.name} (%")).where(Flow.user_id == current_user.id)  # type: ignore[attr-defined]
            ).all()
            if flows:
                extract_number = re.compile(r"\((\d+)\)$")
                numbers = []
                for _flow in flows:
                    result = extract_number.search(_flow.name)
                    if result:
                        numbers.append(int(result.groups(1)[0]))
                if numbers:
                    flow.name = f"{flow.name} ({max(numbers) + 1})"
            else:
                flow.name = f"{flow.name} (1)"
        # Now check if the endpoint is unique
        if (
            flow.endpoint_name
            and session.exec(
                select(Flow).where(Flow.endpoint_name == flow.endpoint_name).where(Flow.user_id == current_user.id)
            ).first()
        ):
            flows = session.exec(
                select(Flow)
                .where(Flow.endpoint_name.like(f"{flow.endpoint_name}-%"))  # type: ignore[union-attr]
                .where(Flow.user_id == current_user.id)
            ).all()
            if flows:
                # The endpoitn name is like "my-endpoint","my-endpoint-1", "my-endpoint-2"
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
            default_folder = session.exec(
                select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == current_user.id)
            ).first()
            if default_folder:
                db_flow.folder_id = default_folder.id

        session.add(db_flow)
        session.commit()
        session.refresh(db_flow)
    except Exception as e:
        # If it is a validation error, return the error message
        if hasattr(e, "errors"):
            raise HTTPException(status_code=400, detail=str(e)) from e
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

        folder_id (UUID, optional): The folder ID. Defaults to None.
        params (Params): Pagination parameters.
        remove_example_flows (bool, optional): Whether to remove example flows. Defaults to False.
        header_flows (bool, optional): Whether to return only specific headers of the flows. Defaults to False.

    Returns:
        list[FlowRead] | Page[FlowRead] | list[FlowHeader]
        A list of flows or a paginated response containing the list of flows or a list of flow headers.
    """
    try:
        auth_settings = get_settings_service().auth_settings

        default_folder = session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME)).first()
        default_folder_id = default_folder.id if default_folder else None

        starter_folder = session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME)).first()
        starter_folder_id = starter_folder.id if starter_folder else None

        if not starter_folder and not default_folder:
            raise HTTPException(
                status_code=404,
                detail="Starter folder and default folder not found. Please create a folder and add flows to it.",
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
            flows = session.exec(stmt).all()
            flows = validate_is_component(flows)
            if components_only:
                flows = [flow for flow in flows if flow.is_component]
            if remove_example_flows and starter_folder_id:
                flows = [flow for flow in flows if flow.folder_id != starter_folder_id]
            if header_flows:
                return [
                    {"id": flow.id, "name": flow.name, "folder_id": flow.folder_id, "is_component": flow.is_component}
                    for flow in flows
                ]
            return flows

        stmt = stmt.where(Flow.folder_id == folder_id)
        return paginate(session, stmt, params=params)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _read_flow(
    session: Session,
    flow_id: UUID,
    current_user: User,
    settings_service: SettingsService,
):
    """Read a flow."""
    auth_settings = settings_service.auth_settings
    stmt = select(Flow).where(Flow.id == flow_id)
    if auth_settings.AUTO_LOGIN:
        # If auto login is enable user_id can be current_user.id or None
        # so write an OR
        stmt = stmt.where(
            (Flow.user_id == current_user.id) | (Flow.user_id == None)  # noqa: E711
        )
    return session.exec(stmt).first()


@router.get("/{flow_id}", response_model=FlowRead, status_code=200)
async def read_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
):
    """Read a flow."""
    if user_flow := _read_flow(session, flow_id, current_user, get_settings_service()):
        return user_flow
    raise HTTPException(status_code=404, detail="Flow not found")


@router.patch("/{flow_id}", response_model=FlowRead, status_code=200)
async def update_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    flow: FlowUpdate,
    current_user: CurrentActiveUser,
):
    """Update a flow."""
    settings_service = get_settings_service()
    try:
        db_flow = _read_flow(
            session=session,
            flow_id=flow_id,
            current_user=current_user,
            settings_service=settings_service,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    try:
        flow_data = flow.model_dump(exclude_unset=True)
        if settings_service.settings.remove_api_keys:
            flow_data = remove_api_keys(flow_data)
        for key, value in flow_data.items():
            setattr(db_flow, key, value)
        webhook_component = get_webhook_component_in_flow(db_flow.data)
        db_flow.webhook = webhook_component is not None
        db_flow.updated_at = datetime.now(timezone.utc)

        if db_flow.folder_id is None:
            default_folder = session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME)).first()
            if default_folder:
                db_flow.folder_id = default_folder.id
        session.add(db_flow)
        session.commit()
        session.refresh(db_flow)
    except Exception as e:
        # If it is a validation error, return the error message
        if hasattr(e, "errors"):
            raise HTTPException(status_code=400, detail=str(e)) from e
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
        raise HTTPException(status_code=500, detail=str(e)) from e

    return db_flow


@router.delete("/{flow_id}", status_code=200)
def delete_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
):
    """Delete a flow."""
    flow = _read_flow(
        session=session,
        flow_id=flow_id,
        current_user=current_user,
        settings_service=get_settings_service(),
    )
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    cascade_delete_flow(session, flow)
    session.commit()
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
    session.commit()
    for db_flow in db_flows:
        session.refresh(db_flow)
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
        response = await create_flow(session=session, flow=flow, current_user=current_user)
        response_list.append(response)

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
        flows_to_delete = db.exec(select(Flow).where(col(Flow.id).in_(flow_ids)).where(Flow.user_id == user.id)).all()
        for flow in flows_to_delete:
            transactions_to_delete = get_transactions_by_flow_id(db, flow.id)
            for transaction in transactions_to_delete:
                db.delete(transaction)

            builds_to_delete = get_vertex_builds_by_flow_id(db, flow.id)
            for build in builds_to_delete:
                db.delete(build)

            db.delete(flow)

        db.commit()
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
    flows = db.exec(select(Flow).where(and_(Flow.user_id == user.id, Flow.id.in_(flow_ids)))).all()  # type: ignore[attr-defined]

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


@router.get("/basic_examples/", response_model=list[FlowRead], status_code=200)
async def read_basic_examples(
    *,
    session: DbSession,
):
    """Retrieve a list of basic example flows.

    Args:
        session (Session): The database session.

    Returns:
        list[FlowRead]: A list of basic example flows.
    """
    try:
        # Get the starter folder
        starter_folder = session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME)).first()

        if not starter_folder:
            return []

        # Get all flows in the starter folder
        return session.exec(select(Flow).where(Flow.folder_id == starter_folder.id)).all()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


add_pagination(router)
