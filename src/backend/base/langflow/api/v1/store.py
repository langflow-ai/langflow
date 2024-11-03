import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from langflow.api.utils import CurrentActiveUser, check_langflow_version
from langflow.services.auth import utils as auth_utils
from langflow.services.deps import get_settings_service, get_store_service
from langflow.services.store.exceptions import CustomError
from langflow.services.store.schema import (
    CreateComponentResponse,
    DownloadComponentResponse,
    ListComponentResponseModel,
    StoreComponentCreate,
    TagResponse,
    UsersLikesResponse,
)

router = APIRouter(prefix="/store", tags=["Components Store"])


def get_user_store_api_key(user: CurrentActiveUser):
    if not user.store_api_key:
        raise HTTPException(status_code=400, detail="You must have a store API key set.")
    try:
        return auth_utils.decrypt_api_key(user.store_api_key, get_settings_service())
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to decrypt API key. Please set a new one.") from e


def get_optional_user_store_api_key(user: CurrentActiveUser):
    if not user.store_api_key:
        return None
    try:
        return auth_utils.decrypt_api_key(user.store_api_key, get_settings_service())
    except Exception:  # noqa: BLE001
        logger.exception("Failed to decrypt API key")
        return user.store_api_key


@router.get("/check/")
async def check_if_store_is_enabled():
    return {
        "enabled": get_settings_service().settings.store,
    }


@router.get("/check/api_key")
async def check_if_store_has_api_key(
    api_key: Annotated[str | None, Depends(get_optional_user_store_api_key)],
):
    if api_key is None:
        return {"has_api_key": False, "is_valid": False}

    try:
        is_valid = await get_store_service().check_api_key(api_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"has_api_key": api_key is not None, "is_valid": is_valid}


@router.post("/components/", response_model=CreateComponentResponse, status_code=201)
async def share_component(
    component: StoreComponentCreate,
    store_api_key: Annotated[str, Depends(get_user_store_api_key)],
) -> CreateComponentResponse:
    try:
        await asyncio.to_thread(check_langflow_version, component)
        return await get_store_service().upload(store_api_key, component)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/components/{component_id}", status_code=201)
async def update_shared_component(
    component_id: UUID,
    component: StoreComponentCreate,
    store_api_key: Annotated[str, Depends(get_user_store_api_key)],
) -> CreateComponentResponse:
    try:
        await asyncio.to_thread(check_langflow_version, component)
        return await get_store_service().update(store_api_key, component_id, component)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/components/")
async def get_components(
    *,
    component_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    private: Annotated[bool | None, Query()] = None,
    is_component: Annotated[bool | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    sort: Annotated[list[str] | None, Query()] = None,
    liked: Annotated[bool, Query()] = False,
    filter_by_user: Annotated[bool, Query()] = False,
    fields: Annotated[list[str] | None, Query()] = None,
    page: int = 1,
    limit: int = 10,
    store_api_key: Annotated[str | None, Depends(get_optional_user_store_api_key)],
) -> ListComponentResponseModel:
    try:
        return await get_store_service().get_list_component_response_model(
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
    except CustomError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/components/{component_id}", response_model=DownloadComponentResponse)
async def download_component(
    component_id: UUID,
    store_api_key: Annotated[str, Depends(get_user_store_api_key)],
) -> DownloadComponentResponse:
    try:
        component = await get_store_service().download(store_api_key, component_id)
    except CustomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if component is None:
        raise HTTPException(status_code=400, detail="Component not found")

    return component


@router.get("/tags", response_model=list[TagResponse])
async def get_tags():
    try:
        return await get_store_service().get_tags()
    except CustomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/users/likes", response_model=list[UsersLikesResponse])
async def get_list_of_components_liked_by_user(
    store_api_key: Annotated[str, Depends(get_user_store_api_key)],
):
    try:
        return await get_store_service().get_user_likes(store_api_key)
    except CustomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/users/likes/{component_id}")
async def like_component(
    component_id: UUID,
    store_api_key: Annotated[str, Depends(get_user_store_api_key)],
) -> UsersLikesResponse:
    try:
        store_service = get_store_service()
        result = await store_service.like_component(store_api_key, str(component_id))
        likes_count = await store_service.get_component_likes_count(str(component_id), store_api_key)

        return UsersLikesResponse(likes_count=likes_count, liked_by_user=result)
    except CustomError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
