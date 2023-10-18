from datetime import timezone
from typing import List, TYPE_CHECKING, Optional
from uuid import UUID
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.flow.flow import Flow
from langflow.services.database.models.user.user import User
from langflow.services.deps import (
    get_session,
    get_store_service,
    get_settings_service,
)
from langflow.services.store.schema import ComponentResponse

from sqlmodel import Session, select
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from langflow.services.store.service import StoreService


router = APIRouter(prefix="/store", tags=["Components Store"])


@router.post("/", response_model=ComponentResponse)
def create_component(
    component: Flow,
    store_service: StoreService = Depends(get_store_service),
    user=Depends(auth_utils.get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    try:
        api_key = user.store_api_key
        decrypted = auth_utils.decrypt_api_key(api_key, settings_service)
        return store_service.upload(decrypted, component.dict())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{component_id}", response_model=ComponentResponse)
def read_component(
    component_id: UUID,
    store_service: StoreService = Depends(get_store_service),
    user: User = Depends(auth_utils.get_current_active_user),
    session=Depends(get_session),
):
    if not user.store_api_key:
        raise HTTPException(
            status_code=400, detail="You must have a store API key set."
        )
    # If the component is from the store, we need to get it from the store
    try:
        api_key = user.store_api_key
        component = store_service.get(api_key, component_id)
        if component is not None:
            # Turn component into a Flow
            required_fields = ["data", "name", "description", "is_component"]
            if all(field in component for field in required_fields):
                component = Flow(
                    name=component["name"],
                    description=component["description"],
                    data=component["data"],
                    user_id=user.id,
                )
                session.add(component)
                session.commit()
                session.refresh(component)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if component is None:
        raise HTTPException(status_code=400, detail="Component not found")
    return component


@router.get("/", response_model=List[ComponentResponse])
def list_components(
    page: int = 1,
    limit: int = 10,
    store_service: StoreService = Depends(get_store_service),
    user=Depends(auth_utils.get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    if user.store_api_key:
        decrypted = auth_utils.decrypt_api_key(user.store_api_key, settings_service)
    else:
        decrypted = None
    return store_service.list_components(decrypted, page, limit)


@router.get("/search", response_model=List[ComponentResponse])
async def search_endpoint(
    api_key: Optional[str] = Query(None),
    query: str = Query(...),
    page: int = Query(1),
    limit: int = Query(10),
    status: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    sort_by: Optional[str] = Query("likes"),
    sort: Optional[List[str]] = Query(None),
    fields: Optional[List[str]] = Query(None),
    store_service: "StoreService" = Depends(get_store_service),
):
    try:
        return await store_service.search(
            api_key=api_key,
            query=query,
            page=page,
            limit=limit,
            status=status,
            tags=tags,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort=sort,
            fields=fields,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )
