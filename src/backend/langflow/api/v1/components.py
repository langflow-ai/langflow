from typing import List
from uuid import UUID
from langflow.database.models.component import Component
from langflow.database.base import get_session
from sqlmodel import Session, select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError


COMPONENT_NOT_FOUND = "Component not found"

router = APIRouter(prefix="/components", tags=["Components"])


@router.post("/", response_model=Component)
def create_component(component: Component, db: Session = Depends(get_session)):
    try:
        db.add(component)
        db.commit()
        db.refresh(component)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="A component with the same id already exists.",
        ) from e
    return component


@router.get("/{component_id}", response_model=Component)
def read_component(component_id: UUID, db: Session = Depends(get_session)):
    if component := db.get(Component, component_id):
        return component
    else:
        raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)


@router.get("/", response_model=List[Component])
def read_components(skip: int = 0, limit: int = 50, db: Session = Depends(get_session)):
    return db.execute(select(Component).offset(skip).limit(limit)).fetchall()


@router.patch("/{component_id}", response_model=Component)
def update_component(
    component_id: UUID, component: Component, db: Session = Depends(get_session)
):
    db_component = db.get(Component, component_id)
    if not db_component:
        raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)
    component_data = component.dict(exclude_unset=True)
    for key, value in component_data.items():
        setattr(db_component, key, value)
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
    return {"detail": "Component deleted"}


# @router.post("/", response_model=ComponentRead, status_code=201)
# def create(*, session: Session = Depends(get_session), component: ComponentCreate):
#     db = Component.from_orm(component)
#     session.add(db)
#     session.commit()
#     session.refresh(db)

#     return db


# @router.get("/", response_model=list[ComponentRead], status_code=200)
# def read_all(*, session: Session = Depends(get_session)):
#     try:
#         sql = select(Component)
#         components = session.exec(sql).all()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e)) from e

#     return [jsonable_encoder(component) for component in components]


# @router.get("/{id}", response_model=ComponentRead, status_code=200)
# def read(*, session: Session = Depends(get_session), id: UUID):
#     if component := session.get(Component, id):
#         return component
#     else:
#         raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)


# @router.patch("/{id}", response_model=ComponentRead, status_code=200)
# def update(
#     *, session: Session = Depends(get_session), id: UUID, component: ComponentUpdate
# ):
#     db = session.get(Component, id)
#     if not db:
#         raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)

#     data = component.dict(exclude_unset=True)

#     if settings.remove_api_keys:
#         data = remove_api_keys(data)

#     for key, value in data.items():
#         setattr(db, key, value)

#     session.add(db)
#     session.commit()
#     session.refresh(db)

#     return db


# @router.delete("/{id}", status_code=200)
# def delete(*, session: Session = Depends(get_session), id: UUID):
#     component = session.get(Component, id)

#     if not component:
#         raise HTTPException(status_code=404, detail=COMPONENT_NOT_FOUND)

#     session.delete(component)
#     session.commit()

#     return {"message": "Component deleted successfully"}
