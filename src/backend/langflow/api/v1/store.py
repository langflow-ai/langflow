import warnings
from typing import Annotated, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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
from langflow.services.store.utils import get_lf_version_from_pypi

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


@router.get("/check/")
def check_if_store_is_enabled(
    settings_service=Depends(get_settings_service),
):
    return {
        "enabled": settings_service.settings.STORE,
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
    store_api_Key: str = Depends(get_user_store_api_key),
):
    try:
        # Verify if this is the latest version of Langflow
        # If not, raise an error
        if not component.last_tested_version:
            # Get the local version of Langflow
            from langflow import __version__ as current_version

            component.last_tested_version = current_version
        langflow_version = get_lf_version_from_pypi()
        if langflow_version is None:
            raise HTTPException(
                status_code=500,
                detail="Unable to verify the latest version of Langflow",
            )
        elif langflow_version != component.last_tested_version:
            # If the user is using an older version of Langflow, we need to raise an error
            # raise ValueError(
            warnings.warn(
                f"Your version of Langflow ({component.last_tested_version}) is outdated."
                f" Please update to the latest version ({langflow_version}) and try again."
            )

        result = await store_service.upload(store_api_Key, component)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/components/{component_id}", response_model=CreateComponentResponse, status_code=201)
async def update_component(
    component_id: UUID,
    component: StoreComponentCreate,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_user_store_api_key),
):
    try:
        # Verify if this is the latest version of Langflow
        # If not, raise an error
        if not component.last_tested_version:
            # Get the local version of Langflow
            from langflow import __version__ as current_version

            component.last_tested_version = current_version
        langflow_version = get_lf_version_from_pypi()
        if langflow_version is None:
            raise HTTPException(
                status_code=500,
                detail="Unable to verify the latest version of Langflow",
            )
        elif langflow_version != component.last_tested_version:
            # If the user is using an older version of Langflow, we need to raise an error
            # raise ValueError(
            warnings.warn(
                f"Your version of Langflow ({component.last_tested_version}) is outdated."
                f" Please update to the latest version ({langflow_version}) and try again."
            )

        result = await store_service.update(store_api_Key, component_id, component)
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
    store_api_Key: Optional[str] = Depends(get_optional_user_store_api_key),
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
            store_api_key=store_api_Key,
        )
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/components/{component_id}", response_model=DownloadComponentResponse)
async def download_component(
    component_id: UUID,
    store_service: StoreService = Depends(get_store_service),
    store_api_Key: str = Depends(get_user_store_api_key),
):
    try:
        component = await store_service.download(store_api_Key, component_id)
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
    store_api_Key: str = Depends(get_user_store_api_key),
):
    try:
        return await store_service.get_user_likes(store_api_Key)
    except CustomException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        likes_count = await store_service.get_component_likes_count(str(component_id), store_api_Key)

        return UsersLikesResponse(likes_count=likes_count, liked_by_user=result)
    except CustomException as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
