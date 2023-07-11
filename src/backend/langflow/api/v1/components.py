from uuid import UUID
from langflow.settings import settings
from langflow.api.utils import remove_api_keys
from langflow.database.models.component import (
    Component,
    ComponentCreate,
    ComponentRead,
    ComponentUpdate,
)
from langflow.database.base import get_session
from sqlmodel import Session, select
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder


COMPONENT_NOT_FOUND = "Component not found"

router = APIRouter(prefix="/components", tags=["Components"])


@router.post("/", response_model=ComponentRead, status_code=201)
def create(*, session: Session = Depends(get_session), component: ComponentCreate):
    db = Component.from_orm(component)
    session.add(db)
    session.commit()
    session.refresh(db)

    return db


@router.get("/", response_model=list[ComponentRead], status_code=200)
def read_all(*, session: Session = Depends(get_session)):
    try:
        sql = select(Component)
        components = session.exec(sql).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return [jsonable_encoder(component) for component in components]


@router.get("/{id}", response_model=ComponentRead, status_code=200)
def read(*, session: Session = Depends(get_session), id: UUID):
    if component := session.get(Component, id):
        return component
    else:
        raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)


@router.patch("/{id}", response_model=ComponentRead, status_code=200)
def update(
    *, session: Session = Depends(get_session), id: UUID, component: ComponentUpdate
):
    db = session.get(Component, id)
    if not db:
        raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)

    data = component.dict(exclude_unset=True)

    if settings.remove_api_keys:
        data = remove_api_keys(data)

    for key, value in data.items():
        setattr(db, key, value)

    session.add(db)
    session.commit()
    session.refresh(db)

    return db


@router.delete("/{id}", status_code=200)
def delete(*, session: Session = Depends(get_session), id: UUID):
    component = session.get(Component, id)

    if not component:
        raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)

    session.delete(component)
    session.commit()

    return {"message": "Component deleted successfully"}
