import io
import json
import re
from datetime import datetime, timezone
from typing import List
from uuid import UUID
import zipfile

from fastapi.responses import StreamingResponse
import orjson
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlmodel import Session, and_, col, select

from langflow.api.utils import remove_api_keys, validate_is_component
from langflow.api.v1.schemas import FlowListCreate, FlowListRead
from langflow.initial_setup.setup import STARTER_FOLDER_NAME
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow import Flow, FlowCreate, FlowRead, FlowUpdate
from langflow.services.database.models.flow.utils import get_webhook_component_in_flow, delete_flow_by_id
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session, get_settings_service
from langflow.services.settings.service import SettingsService

# build router
router = APIRouter(prefix="/flows", tags=["Flows"])


@router.post("/", response_model=FlowRead, status_code=201)
def create_flow(
    *,
    session: Session = Depends(get_session),
    flow: FlowCreate,
    current_user: User = Depends(get_current_active_user),
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
                select(Flow).where(Flow.name.like(f"{flow.name} (%")).where(Flow.user_id == current_user.id)  # type: ignore
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
                .where(Flow.endpoint_name.like(f"{flow.endpoint_name}-%"))  # type: ignore
                .where(Flow.user_id == current_user.id)
            ).all()
            if flows:
                # The endpoitn name is like "my-endpoint","my-endpoint-1", "my-endpoint-2"
                # so we need to get the highest number and add 1
                # we need to get the last part of the endpoint name
                numbers = [int(flow.endpoint_name.split("-")[-1]) for flow in flows]  # type: ignore
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
        return db_flow
    except Exception as e:
        # If it is a validation error, return the error message
        if hasattr(e, "errors"):
            raise HTTPException(status_code=400, detail=str(e)) from e
        elif "UNIQUE constraint failed" in str(e):
            # Get the name of the column that failed
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            # UNIQUE constraint failed: flow.user_id, flow.name
            # or UNIQUE constraint failed: flow.name
            # if the column has id in it, we want the other column
            column = columns.split(",")[1] if "id" in columns.split(",")[0] else columns.split(",")[0]

            raise HTTPException(
                status_code=400, detail=f"{column.capitalize().replace('_', ' ')} must be unique"
            ) from e
        elif isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[FlowRead], status_code=200)
def read_flows(
    *,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    settings_service: "SettingsService" = Depends(get_settings_service),
    remove_example_flows: bool = False,
):
    """
    Retrieve a list of flows.

    Args:
        current_user (User): The current authenticated user.
        session (Session): The database session.
        settings_service (SettingsService): The settings service.
        remove_example_flows (bool, optional): Whether to remove example flows. Defaults to False.


    Returns:
        List[Dict]: A list of flows in JSON format.
    """

    try:
        auth_settings = settings_service.auth_settings
        if auth_settings.AUTO_LOGIN:
            flows = session.exec(
                select(Flow).where(
                    (Flow.user_id == None) | (Flow.user_id == current_user.id)  # noqa
                )
            ).all()
        else:
            flows = current_user.flows

        flows = validate_is_component(flows)  # type: ignore
        flow_ids = [flow.id for flow in flows]
        # with the session get the flows that DO NOT have a user_id
        if not remove_example_flows:
            try:
                folder = session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME)).first()

                example_flows = folder.flows if folder else []
                for example_flow in example_flows:
                    if example_flow.id not in flow_ids:
                        flows.append(example_flow)  # type: ignore
            except Exception as e:
                logger.error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return [jsonable_encoder(flow) for flow in flows]


@router.get("/{flow_id}", response_model=FlowRead, status_code=200)
def read_flow(
    *,
    session: Session = Depends(get_session),
    flow_id: UUID,
    current_user: User = Depends(get_current_active_user),
    settings_service: "SettingsService" = Depends(get_settings_service),
):
    """Read a flow."""
    auth_settings = settings_service.auth_settings
    stmt = select(Flow).where(Flow.id == flow_id)
    if auth_settings.AUTO_LOGIN:
        # If auto login is enable user_id can be current_user.id or None
        # so write an OR
        stmt = stmt.where(
            (Flow.user_id == current_user.id) | (Flow.user_id == None)  # noqa
        )  # noqa
    if user_flow := session.exec(stmt).first():
        return user_flow
    else:
        raise HTTPException(status_code=404, detail="Flow not found")


@router.patch("/{flow_id}", response_model=FlowRead, status_code=200)
def update_flow(
    *,
    session: Session = Depends(get_session),
    flow_id: UUID,
    flow: FlowUpdate,
    current_user: User = Depends(get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    """Update a flow."""
    try:
        db_flow = read_flow(
            session=session,
            flow_id=flow_id,
            current_user=current_user,
            settings_service=settings_service,
        )
        if not db_flow:
            raise HTTPException(status_code=404, detail="Flow not found")
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
        return db_flow
    except Exception as e:
        # If it is a validation error, return the error message
        if hasattr(e, "errors"):
            raise HTTPException(status_code=400, detail=str(e)) from e
        elif "UNIQUE constraint failed" in str(e):
            # Get the name of the column that failed
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            # UNIQUE constraint failed: flow.user_id, flow.name
            # or UNIQUE constraint failed: flow.name
            # if the column has id in it, we want the other column
            column = columns.split(",")[1] if "id" in columns.split(",")[0] else columns.split(",")[0]

            raise HTTPException(
                status_code=400, detail=f"{column.capitalize().replace('_', ' ')} must be unique"
            ) from e
        elif isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{flow_id}", status_code=200)
def delete_flow(
    *,
    session: Session = Depends(get_session),
    flow_id: UUID,
    current_user: User = Depends(get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    """Delete a flow."""
    flow = read_flow(
        session=session,
        flow_id=flow_id,
        current_user=current_user,
        settings_service=settings_service,
    )
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    delete_flow_by_id(str(flow_id), session)
    session.commit()
    return {"message": "Flow deleted successfully"}


@router.post("/batch/", response_model=List[FlowRead], status_code=201)
def create_flows(
    *,
    session: Session = Depends(get_session),
    flow_list: FlowListCreate,
    current_user: User = Depends(get_current_active_user),
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


@router.post("/upload/", response_model=List[FlowRead], status_code=201)
async def upload_file(
    *,
    session: Session = Depends(get_session),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    folder_id: UUID | None = None,
):
    """Upload flows from a file."""
    contents = await file.read()
    data = orjson.loads(contents)
    response_list = []
    if "flows" in data:
        flow_list = FlowListCreate(**data)
    else:
        flow_list = FlowListCreate(flows=[FlowCreate(**data)])
    # Now we set the user_id for all flows
    for flow in flow_list.flows:
        flow.user_id = current_user.id
        if folder_id:
            flow.folder_id = folder_id
        response = create_flow(session=session, flow=flow, current_user=current_user)
        response_list.append(response)

    return response_list


@router.delete("/")
async def delete_multiple_flows(
    flow_ids: List[UUID], user: User = Depends(get_current_active_user), db: Session = Depends(get_session)
):
    """
    Delete multiple flows by their IDs.

    Args:
        flow_ids (List[str]): The list of flow IDs to delete.
        user (User, optional): The user making the request. Defaults to the current active user.

    Returns:
        dict: A dictionary containing the number of flows deleted.

    """
    try:
        deleted_flows = db.exec(select(Flow).where(col(Flow.id).in_(flow_ids)).where(Flow.user_id == user.id)).all()
        for flow in deleted_flows:
            db.delete(flow)
        db.commit()
        return {"deleted": len(deleted_flows)}
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/download/", status_code=200)
async def download_multiple_file(
    flow_ids: List[UUID],
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    """Download all flows as a zip file."""
    flows = db.exec(select(Flow).where(and_(Flow.user_id == user.id, Flow.id.in_(flow_ids)))).all()  # type: ignore

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
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_langflow_flows.zip"

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        return FlowListRead(flows=flows_without_api_keys)
