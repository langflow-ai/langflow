from datetime import datetime
from typing import List
from uuid import UUID

import orjson
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlmodel import Session, select

from langflow.api.utils import remove_api_keys, validate_is_component
from langflow.api.v1.schemas import FlowListCreate, FlowListRead
from langflow.initial_setup.setup import STARTER_FOLDER_NAME
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow import Flow, FlowCreate, FlowRead, FlowUpdate
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
    """Create a new flow."""
    if flow.user_id is None:
        flow.user_id = current_user.id

    db_flow = Flow.model_validate(flow, from_attributes=True)
    db_flow.updated_at = datetime.utcnow()

    session.add(db_flow)
    session.commit()
    session.refresh(db_flow)
    return db_flow


@router.get("/", response_model=list[FlowRead], status_code=200)
def read_flows(
    *,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    settings_service: "SettingsService" = Depends(get_settings_service),
):
    """Read all flows."""
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
        try:
            example_flows = session.exec(
                select(Flow).where(
                    Flow.user_id == None,  # noqa
                    Flow.folder == STARTER_FOLDER_NAME,
                )
            ).all()
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

    db_flow = read_flow(
        session=session,
        flow_id=flow_id,
        current_user=current_user,
        settings_service=settings_service,
    )
    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    flow_data = flow.model_dump(exclude_unset=True)
    if settings_service.settings.REMOVE_API_KEYS:
        flow_data = remove_api_keys(flow_data)
    for key, value in flow_data.items():
        if value is not None:
            setattr(db_flow, key, value)
    db_flow.updated_at = datetime.utcnow()
    session.add(db_flow)
    session.commit()
    session.refresh(db_flow)
    return db_flow


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
    session.delete(flow)
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
):
    """Upload flows from a file."""
    contents = await file.read()
    data = orjson.loads(contents)
    if "flows" in data:
        flow_list = FlowListCreate(**data)
    else:
        flow_list = FlowListCreate(flows=[FlowCreate(**flow) for flow in data])
    # Now we set the user_id for all flows
    for flow in flow_list.flows:
        flow.user_id = current_user.id

    return create_flows(session=session, flow_list=flow_list, current_user=current_user)


@router.get("/download/", response_model=FlowListRead, status_code=200)
async def download_file(
    *,
    session: Session = Depends(get_session),
    settings_service: "SettingsService" = Depends(get_settings_service),
    current_user: User = Depends(get_current_active_user),
):
    """Download all flows as a file."""
    flows = read_flows(current_user=current_user, session=session, settings_service=settings_service)
    return FlowListRead(flows=flows)
