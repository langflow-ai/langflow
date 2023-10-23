from typing import List, Optional
from uuid import UUID
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.flow.flow import FlowCreate, FlowRead
from langflow.services.database.models.user.user import User
from langflow.services.deps import (
    get_session,
    get_store_service,
    get_settings_service,
)
from langflow.services.store.schema import ComponentResponse, StoreComponentCreate

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime

from langflow.services.store.service import StoreService


router = APIRouter(prefix="/store", tags=["Components Store"])


def get_user_store_api_key(user: User = Depends(auth_utils.get_current_active_user)):
    if not user.store_api_key:
        raise HTTPException(
            status_code=400, detail="You must have a store API key set."
        )
    return user.store_api_key


def get_optional_user_store_api_key(
    user: User = Depends(auth_utils.get_current_active_user),
):
    return user.store_api_key


@router.post("/components/", response_model=ComponentResponse)
def create_component(
    component: StoreComponentCreate,
    store_service: StoreService = Depends(get_store_service),
    settings_service=Depends(get_settings_service),
    store_api_Key: str = Depends(get_user_store_api_key),
):
    try:
        decrypted = auth_utils.decrypt_api_key(store_api_Key, settings_service)
        return store_service.upload(decrypted, component.dict())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/components/", response_model=List[ComponentResponse])
def list_components(
    page: int = 1,
    limit: int = 10,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_optional_user_store_api_key),
    settings_service=Depends(get_settings_service),
):
    try:
        fields = ["id", "name", "description", "user_created"]
        if store_api_Key:
            decrypted = auth_utils.decrypt_api_key(store_api_Key, settings_service)
        else:
            decrypted = None
        result = store_service.list_components(decrypted, page, limit, fields=fields)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/components/{component_id}", response_model=ComponentResponse)
def read_component(
    component_id: UUID,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_user_store_api_key),
    settings_service=Depends(get_settings_service),
    session=Depends(get_session),
):
    # If the component is from the store, we need to get it from the store

    try:
        decrypted = auth_utils.decrypt_api_key(store_api_Key, settings_service)
        component = store_service.get(decrypted, component_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if component is None:
        raise HTTPException(status_code=400, detail="Component not found")

    return component


@router.post("/components/{component_id}/fork", response_model=FlowRead)
def fork_component(
    component_id: UUID,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_user_store_api_key),
    settings_service=Depends(get_settings_service),
    user: User = Depends(auth_utils.get_current_active_user),
    session=Depends(get_session),
):
    # If the component is from the store, we need to get it from the store
    try:
        decrypted = auth_utils.decrypt_api_key(store_api_Key, settings_service)
        component = store_service.get(decrypted, component_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if component is None:
        raise HTTPException(status_code=400, detail="Component not found")

    # Now we need to get the component id and put it in StoreComponentCreate.parent
    parent_id = component.id
    new_component = StoreComponentCreate(
        name=component.name,
        data=component.data,
        parent=parent_id,
        description=component.description,
        tags=component.tags,
    )

    try:
        created_component = store_service.upload(decrypted, new_component.dict())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if created_component is None:
        raise HTTPException(status_code=500, detail="Component not created")

    # Now save it locally
    db_component = FlowCreate(
        name=created_component.name,
        data=created_component.data,
        description=created_component.description,
        user_id=user.id,
    )
    session.add(db_component)
    session.commit()
    session.refresh(db_component)
    return db_component


@router.get("/search", response_model=List[ComponentResponse])
async def search_endpoint(
    query: str = Query(...),
    page: int = Query(1),
    limit: int = Query(10),
    status: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    sort: Optional[List[str]] = Query(None),
    fields: Optional[List[str]] = Query(None),
    store_service: "StoreService" = Depends(get_store_service),
    store_api_Key: str = Depends(get_optional_user_store_api_key),
):
    try:
        return store_service.search(
            api_key=store_api_Key,
            query=query,
            page=page,
            limit=limit,
            status=status,
            tags=tags,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            fields=fields,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
