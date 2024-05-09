from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
            setattr(existing_folder, key, value)
        session.add(existing_folder)
        session.commit()
        session.refresh(existing_folder)
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
