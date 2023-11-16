from typing import Annotated, Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from httpx import HTTPStatusError
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.user.user import User
from langflow.services.deps import get_settings_service, get_store_service
from langflow.services.store.schema import (
    ComponentResponse,
    DownloadComponentResponse,
    ListComponentResponse,
    ListComponentResponseModel,
    StoreComponentCreate,
    TagResponse,
    UsersLikesResponse,
)
from langflow.services.store.service import StoreService, user_data_context
from langflow.services.store.utils import get_lf_version_from_pypi, update_components_with_user_data

router = APIRouter(prefix="/store", tags=["Components Store"])


def get_user_store_api_key(
    user: User = Depends(auth_utils.get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    if not user.store_api_key:
        raise HTTPException(status_code=400, detail="You must have a store API key set.")
    decrypted = auth_utils.decrypt_api_key(user.store_api_key, settings_service)
    return decrypted


def get_optional_user_store_api_key(
    user: User = Depends(auth_utils.get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    if not user.store_api_key:
        return None
    decrypted = auth_utils.decrypt_api_key(user.store_api_key, settings_service)
    return decrypted


@router.get("/check")
def check_if_store_is_enabled(
    settings_service=Depends(get_settings_service),
):
    return {
        "enabled": settings_service.settings.STORE,
    }


@router.get("/check/api_key")
def check_if_store_has_api_key(
    api_key=Depends(get_optional_user_store_api_key),
):
    return {
        "has_api_key": api_key is not None,
    }


@router.post("/components/", response_model=ComponentResponse, status_code=201)
def create_component(
    component: StoreComponentCreate,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_user_store_api_key),
):
    try:
        # Verify if this is the latest version of Langflow
        # If not, raise an error
        langflow_version = get_lf_version_from_pypi()
        if langflow_version is None:
            raise HTTPException(
                status_code=500,
                detail="Unable to verify the latest version of Langflow",
            )
        elif langflow_version != component.last_tested_version:
            # If the user is using an older version of Langflow, we need to raise an error
            raise ValueError(
                f"Your version of Langflow ({component.last_tested_version}) is outdated."
                " Please update to the latest version ({langflow_version}) and try again."
            )

        return store_service.upload(store_api_Key, component)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/components/", response_model=ListComponentResponseModel)
async def get_components(
    search: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    is_component: Annotated[Optional[bool], Query()] = None,
    tags: Annotated[Optional[list[str]], Query()] = None,
    sort: Annotated[Union[list[str], None], Query()] = None,
    liked: Annotated[bool, Query()] = False,
    page: int = 1,
    limit: int = 10,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: Optional[str] = Depends(get_optional_user_store_api_key),
):
    try:
        with user_data_context(api_key=store_api_Key, store_service=store_service):
            filter_conditions: List[Dict[str, Any]] = store_service.build_filter_conditions(
                search=search,
                status=status,
                tags=tags,
                is_component=is_component,
                liked=liked,
                api_key=store_api_Key,
            )
            result: List[ListComponentResponse] = []
            authorized = False
            try:
                result = await store_service.query_components(
                    api_key=store_api_Key, page=page, limit=limit, sort=sort, filter_conditions=filter_conditions
                )
            except HTTPStatusError as exc:
                if exc.response.status_code == 403:
                    raise ValueError("You are not authorized to access this public resource")
            try:
                if result:
                    if len(result) >= limit:
                        comp_count = await store_service.count_components(
                            api_key=store_api_Key,
                            filter_conditions=filter_conditions,
                        )
                    else:
                        comp_count = len(result)
                else:
                    comp_count = 0
            except HTTPStatusError as exc:
                if exc.response.status_code == 403:
                    raise ValueError("You are not authorized to access this public resource")

            if store_api_Key and result:
                # Now, from the result, we need to get the components
                # the user likes and set the liked_by_user to True
                try:
                    updated_result = await update_components_with_user_data(
                        result, store_service, store_api_Key, liked=liked
                    )
                    authorized = True
                    result = updated_result
                except Exception:
                    # If we get an error here, it means the user is not authorized
                    authorized = False
        return ListComponentResponseModel(results=result, authorized=authorized, count=comp_count)
    except Exception as exc:
        if isinstance(exc, HTTPStatusError):
            if exc.response.status_code == 403:
                raise HTTPException(status_code=403, detail="Forbidden")
        elif isinstance(exc, ValueError):
            raise HTTPException(status_code=403, detail=str(exc))

        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/components/{component_id}", response_model=DownloadComponentResponse)
async def download_component(
    component_id: UUID,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_user_store_api_key),
):
    # If the component is from the store, we need to get it from the store

    try:
        component = await store_service.download(store_api_Key, component_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if component is None:
        raise HTTPException(status_code=400, detail="Component not found")

    return component


@router.get("/tags", response_model=List[TagResponse])
async def get_tags(
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_optional_user_store_api_key),
):
    try:
        return await store_service.get_tags(store_api_Key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/users/likes", response_model=List[UsersLikesResponse])
async def get_list_of_components_liked_by_user(
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_user_store_api_key),
):
    try:
        return await store_service.get_user_likes(store_api_Key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/users/likes/{component_id}", response_model=UsersLikesResponse)
async def like_component(
    component_id: UUID,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_user_store_api_key),
):
    try:
        result = await store_service.like_component(store_api_Key, str(component_id))
        likes_count = await store_service.get_component_likes_count(store_api_Key, str(component_id))

        return UsersLikesResponse(likes_count=likes_count, liked_by_user=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
