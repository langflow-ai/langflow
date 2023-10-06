from datetime import timezone
from typing import List
from uuid import UUID
from langflow.services.database.models.component import Component, ComponentModel
from langflow.services.getters import get_session
from sqlmodel import Session, select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from datetime import datetime


COMPONENT_NOT_FOUND = "Component not found"
COMPONENT_ALREADY_EXISTS = "A component with the same id already exists."
COMPONENT_DELETED = "Component deleted"


router = APIRouter(prefix="/components", tags=["Components"])


@router.post("/", response_model=Component)
def create_component(component: ComponentModel, db: Session = Depends(get_session)):
    db_component = Component(**component.dict())
    try:
        db.add(db_component)
        db.commit()
        db.refresh(db_component)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=COMPONENT_ALREADY_EXISTS,
        ) from e
    return db_component


@router.get("/{component_id}", response_model=Component)
def read_component(component_id: UUID, db: Session = Depends(get_session)):
    if component := db.get(Component, component_id):
        return component
    else:
        raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)


@router.get("/", response_model=List[Component])
def read_components(skip: int = 0, limit: int = 50, db: Session = Depends(get_session)):
    query = select(Component)
    query = query.offset(skip).limit(limit)

    return db.execute(query).fetchall()


@router.patch("/{component_id}", response_model=Component)
def update_component(
    component_id: UUID, component: ComponentModel, db: Session = Depends(get_session)
):
    db_component = db.get(Component, component_id)
    if not db_component:
        raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)
    component_data = component.dict(exclude_unset=True)

    for key, value in component_data.items():
        setattr(db_component, key, value)

    db_component.update_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_component)
    return db_component


@router.delete("/{component_id}")
def delete_component(component_id: UUID, db: Session = Depends(get_session)):
    component = db.get(Component, component_id)
    if not component:
        raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)
    db.delete(component)
    db.commit()
    return {"detail": COMPONENT_DELETED}
