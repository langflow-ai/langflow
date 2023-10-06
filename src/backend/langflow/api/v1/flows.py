from typing import List
from uuid import UUID
from fastapi.encoders import jsonable_encoder

from langflow.api.utils import remove_api_keys
from langflow.api.v1.schemas import FlowListCreate, FlowListRead
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow import (
    Flow,
    FlowCreate,
    FlowRead,
    FlowUpdate,
)
from langflow.services.database.models.user.user import User
from langflow.services.getters import get_session
from langflow.services.getters import get_settings_service
import orjson
from sqlmodel import Session
from fastapi import APIRouter, Depends, HTTPException

from fastapi import File, UploadFile

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

    db_flow = Flow.from_orm(flow)

    session.add(db_flow)
    session.commit()
    session.refresh(db_flow)
    return db_flow


@router.get("/", response_model=list[FlowRead], status_code=200)
def read_flows(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    """Read all flows."""
    try:
        flows = current_user.flows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return [jsonable_encoder(flow) for flow in flows]


@router.get("/{flow_id}", response_model=FlowRead, status_code=200)
def read_flow(
    *,
    session: Session = Depends(get_session),
    flow_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Read a flow."""
    if user_flow := (
        session.query(Flow)
        .filter(Flow.id == flow_id)
        .filter(Flow.user_id == current_user.id)
        .first()
    ):
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

    db_flow = read_flow(session=session, flow_id=flow_id, current_user=current_user)
    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    flow_data = flow.dict(exclude_unset=True)
    if settings_service.settings.REMOVE_API_KEYS:
        flow_data = remove_api_keys(flow_data)
    for key, value in flow_data.items():
        if value is not None:
            setattr(db_flow, key, value)
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
):
    """Delete a flow."""
    flow = read_flow(session=session, flow_id=flow_id, current_user=current_user)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    session.delete(flow)
    session.commit()
    return {"message": "Flow deleted successfully"}


# Define a new model to handle multiple flows


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
        db_flow = Flow.from_orm(flow)
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
    current_user: User = Depends(get_current_active_user),
):
    """Download all flows as a file."""
    flows = read_flows(session=session, current_user=current_user)
    return FlowListRead(flows=flows)
