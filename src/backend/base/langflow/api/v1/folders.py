from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from langflow.api.v1.flows import create_flows
from langflow.api.v1.schemas import FlowListCreate, FlowListReadWithFolderName
from langflow.initial_setup.setup import STARTER_FOLDER_NAME
from langflow.services.database.models.flow.model import Flow, FlowCreate, FlowRead
import orjson
from sqlalchemy import update
from sqlmodel import Session, select

from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.folder.model import (
    Folder,
    FolderCreate,
    FolderRead,
    FolderReadWithFlows,
    FolderUpdate,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session

router = APIRouter(prefix="/folders", tags=["Folders"])


@router.post("/", response_model=FolderRead, status_code=201)
def create_folder(
    *,
    session: Session = Depends(get_session),
    folder: FolderCreate,
    current_user: User = Depends(get_current_active_user),
):
    try:
        new_folder = Folder.model_validate(folder, from_attributes=True)
        new_folder.user_id = current_user.id
        session.add(new_folder)
        session.commit()
        session.refresh(new_folder)

        if folder.components_list.__len__() > 0:
            update_statement_components = (
                update(Flow).where(Flow.id.in_(folder.components_list)).values(folder_id=new_folder.id)
            )
            session.exec(update_statement_components)
            session.commit()

        if folder.flows_list.__len__() > 0:
            update_statement_flows = update(Flow).where(Flow.id.in_(folder.flows_list)).values(folder_id=new_folder.id)
            session.exec(update_statement_flows)
            session.commit()

        return new_folder
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[FolderRead], status_code=200)
def read_folders(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    try:
        folders = session.exec(select(Folder).where(Folder.user_id == current_user.id)).all()
        return folders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/starter-projects", response_model=FolderReadWithFlows, status_code=200)
def read_starter_folders(*, session: Session = Depends(get_session)):
    try:
        folders = session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME)).first()
        return folders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{folder_id}", response_model=FolderReadWithFlows, status_code=200)
def read_folder(
    *,
    session: Session = Depends(get_session),
    folder_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    try:
        folder = session.exec(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        return folder
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Folder not found")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{folder_id}", response_model=FolderRead, status_code=200)
def update_folder(
    *,
    session: Session = Depends(get_session),
    folder_id: UUID,
    folder: FolderUpdate,  # Assuming FolderUpdate is a Pydantic model defining updatable fields
    current_user: User = Depends(get_current_active_user),
):
    try:
        existing_folder = session.exec(
            select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)
        ).first()
        if not existing_folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        folder_data = folder.model_dump(exclude_unset=True)
        for key, value in folder_data.items():
            if key != "components" and key != "flows":
                setattr(existing_folder, key, value)
        session.add(existing_folder)
        session.commit()
        session.refresh(existing_folder)

        if folder.components.__len__() > 0:
            update_statement_components = (
                update(Flow).where(Flow.id.in_(folder.components)).values(folder_id=existing_folder.id)
            )
            session.exec(update_statement_components)
            session.commit()

        if folder.flows.__len__() > 0:
            update_statement_flows = update(Flow).where(Flow.id.in_(folder.flows)).values(folder_id=existing_folder.id)
            session.exec(update_statement_flows)
            session.commit()

        return existing_folder

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{folder_id}", status_code=204)
def delete_folder(
    *,
    session: Session = Depends(get_session),
    folder_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    try:
        folder = session.exec(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        session.delete(folder)
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{folder_id}", response_model=FlowListReadWithFolderName, status_code=200)
async def download_file(
    *,
    session: Session = Depends(get_session),
    folder_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Download all flows as a file."""
    try:
        flows = session.exec(select(Flow).where(Flow.folder_id == folder_id, Folder.user_id == current_user.id)).all()
        folder_name = (
            session.exec(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)).first().name
        )
        if not flows:
            raise HTTPException(status_code=404, detail="Folder not found")
        return FlowListReadWithFolderName(flows=flows, folder_name=folder_name)
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Folder not found")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{folder_id}", response_model=List[FlowRead], status_code=201)
async def upload_file(
    *,
    session: Session = Depends(get_session),
    file: UploadFile = File(...),
    folder_id: UUID,
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
        flow.folder_id = folder_id

    return create_flows(session=session, flow_list=flow_list, current_user=current_user)
