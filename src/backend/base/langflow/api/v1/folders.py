from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from langflow.api.v1.flows import create_flows
from langflow.api.v1.schemas import FlowListCreate, FlowListReadWithFolderName
from langflow.initial_setup.setup import STARTER_FOLDER_NAME
from langflow.services.database.models.flow.model import Flow, FlowCreate, FlowRead
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
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
        folder.flows = session.exec(select(Flow).where(Flow.folder_id == folder_id)).all()
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

        concat_folder_components = folder.components + folder.flows

        flows_ids = session.exec(select(Flow.id).where(Flow.folder_id == existing_folder.id)).all()

        excluded_flows = list(set(flows_ids) - set(concat_folder_components))

        my_collection_folder = session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME)).first()
        if my_collection_folder:
            update_statement_my_collection = (
                update(Flow).where(Flow.id.in_(excluded_flows)).values(folder_id=my_collection_folder.id)
            )
            session.exec(update_statement_my_collection)
            session.commit()

        if concat_folder_components.__len__() > 0:
            update_statement_components = (
                update(Flow).where(Flow.id.in_(concat_folder_components)).values(folder_id=existing_folder.id)
            )
            session.exec(update_statement_components)
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
        flows = session.exec(select(Flow).where(Flow.folder_id == folder_id, Folder.user_id == current_user.id)).all()
        for flow in flows:
            session.delete(flow)
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
    """Download all flows from folder."""
    try:
        flows = session.exec(
            select(Flow).distinct().join(Folder).where(Flow.folder_id == folder_id, Folder.user_id == current_user.id)
        ).all()
        folder_name = (
            session.exec(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)).first().name
        )
        folder_description = (
            session.exec(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id))
            .first()
            .description
        )
        if not flows:
            flows = []
        return FlowListReadWithFolderName(flows=flows, folder_name=folder_name, folder_description=folder_description)
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Folder not found")
        raise HTTPException(status_code=500, detail=str(e))


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

    if data.__len__() == 0:
        raise HTTPException(status_code=400, detail="No flows found in the file")

    folder_results = session.exec(
        select(Folder).where(Folder.name.like(f"{data['folder_name']}%"), Folder.user_id == current_user.id)
    )
    existing_folder_names = [folder.name for folder in folder_results]

    if existing_folder_names.__len__() > 0:
        data["folder_name"] = f"{data['folder_name']} ({existing_folder_names.__len__() + 1})"

    folder = FolderCreate(name=data["folder_name"], description=data["folder_description"])

    new_folder = Folder.model_validate(folder, from_attributes=True)
    new_folder.id = None
    new_folder.user_id = current_user.id
    session.add(new_folder)
    session.commit()
    session.refresh(new_folder)

    del data["folder_name"]
    del data["folder_description"]

    if "flows" in data:
        flow_list = FlowListCreate(flows=[FlowCreate(**flow) for flow in data["flows"]])
    else:
        raise HTTPException(status_code=400, detail="No flows found in the data")
    # Now we set the user_id for all flows
    for flow in flow_list.flows:
        flow.user_id = current_user.id
        flow.folder_id = new_folder.id

    return create_flows(session=session, flow_list=flow_list, current_user=current_user)
