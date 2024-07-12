from typing import Annotated, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from langflow.api.utils import check_langflow_version
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, get_store_service
from langflow.services.store.exceptions import CustomException
from langflow.services.store.schema import (
    CreateComponentResponse,
    DownloadComponentResponse,
    ListComponentResponseModel,
    StoreComponentCreate,
    TagResponse,
    UsersLikesResponse,
)
from langflow.services.store.service import StoreService

router = APIRouter(prefix="/store", tags=["Components Store"])


def get_user_store_api_key(
    user: User = Depends(auth_utils.get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    if not user.store_api_key:
        raise HTTPException(status_code=400, detail="You must have a store API key set.")
    try:
        decrypted = auth_utils.decrypt_api_key(user.store_api_key, settings_service)
        return decrypted
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to decrypt API key. Please set a new one.") from e


def get_optional_user_store_api_key(
    user: User = Depends(auth_utils.get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    if not user.store_api_key:
        return None
    try:
        decrypted = auth_utils.decrypt_api_key(user.store_api_key, settings_service)
        return decrypted
    except Exception as e:
        logger.error(f"Failed to decrypt API key: {e}")
        return user.store_api_key


@router.get("/check/")
def check_if_store_is_enabled(
    settings_service=Depends(get_settings_service),
):
    return {
        "enabled": settings_service.settings.store,
    }


@router.get("/check/api_key")
async def check_if_store_has_api_key(
    api_key: Optional[str] = Depends(get_optional_user_store_api_key),
    store_service: StoreService = Depends(get_store_service),
):
    if api_key is None:
        return {"has_api_key": False, "is_valid": False}

    try:
        is_valid = await store_service.check_api_key(api_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"has_api_key": api_key is not None, "is_valid": is_valid}


@router.post("/components/", response_model=CreateComponentResponse, status_code=201)
async def share_component(
    component: StoreComponentCreate,
    store_service: StoreService = Depends(get_store_service),
    store_api_key: str = Depends(get_user_store_api_key),
):
    try:
        await check_langflow_version(component)
        result = await store_service.upload(store_api_key, component)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/components/{component_id}", response_model=CreateComponentResponse, status_code=201)
async def update_shared_component(
    component_id: UUID,
    component: StoreComponentCreate,
    store_service: StoreService = Depends(get_store_service),
    store_api_key: str = Depends(get_user_store_api_key),
):
    try:
        await check_langflow_version(component)
        result = await store_service.update(store_api_key, component_id, component)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/components/", response_model=ListComponentResponseModel)
async def get_components(
    component_id: Annotated[Optional[str], Query()] = None,
    search: Annotated[Optional[str], Query()] = None,
    private: Annotated[Optional[bool], Query()] = None,
    is_component: Annotated[Optional[bool], Query()] = None,
    tags: Annotated[Optional[list[str]], Query()] = None,
    sort: Annotated[Union[list[str], None], Query()] = None,
    liked: Annotated[bool, Query()] = False,
    filter_by_user: Annotated[bool, Query()] = False,
    fields: Annotated[Optional[list[str]], Query()] = None,
    page: int = 1,
    limit: int = 10,
    store_service: StoreService = Depends(get_store_service),
    store_api_key: Optional[str] = Depends(get_optional_user_store_api_key),
):
    try:
        return await store_service.get_list_component_response_model(
            component_id=component_id,
            search=search,
            private=private,
            is_component=is_component,
            fields=fields,
            tags=tags,
            sort=sort,
            liked=liked,
            filter_by_user=filter_by_user,
            page=page,
            limit=limit,
            store_api_key=store_api_key,
        )
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/components/{component_id}", response_model=DownloadComponentResponse)
async def download_component(
    component_id: UUID,
    store_service: StoreService = Depends(get_store_service),
    store_api_key: str = Depends(get_user_store_api_key),
):
    try:
        component = await store_service.download(store_api_key, component_id)
    except CustomException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if component is None:
        raise HTTPException(status_code=400, detail="Component not found")

    return component


@router.get("/tags", response_model=List[TagResponse])
async def get_tags(
    store_service: StoreService = Depends(get_store_service),
):
    try:
        return await store_service.get_tags()
    except CustomException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/users/likes", response_model=List[UsersLikesResponse])
async def get_list_of_components_liked_by_user(
    store_service: StoreService = Depends(get_store_service),
    store_api_key: str = Depends(get_user_store_api_key),
):
    try:
        return await store_service.get_user_likes(store_api_key)
    except CustomException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/users/likes/{component_id}", response_model=UsersLikesResponse)
async def like_component(
    component_id: UUID,
    store_service: StoreService = Depends(get_store_service),
    store_api_key: str = Depends(get_user_store_api_key),
):
    try:
        result = await store_service.like_component(store_api_key, str(component_id))
        likes_count = await store_service.get_component_likes_count(str(component_id), store_api_key)

        return UsersLikesResponse(likes_count=likes_count, liked_by_user=result)
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
