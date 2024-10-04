from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session

from langflow.api.v1.schemas import ApiKeyCreateRequest, ApiKeysResponse
from langflow.services.auth import utils as auth_utils

# Assuming you have these methods in your service layer
from langflow.services.database.models.api_key.crud import create_api_key, delete_api_key, get_api_keys
from langflow.services.database.models.api_key.model import ApiKeyCreate, UnmaskedApiKeyRead
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session, get_settings_service

if TYPE_CHECKING:
    pass

router = APIRouter(tags=["APIKey"], prefix="/api_key")


@router.get("/", response_model=ApiKeysResponse)
def get_api_keys_route(
    db: Session = Depends(get_session),
    current_user: User = Depends(auth_utils.get_current_active_user),
):
    try:
        user_id = current_user.id
        keys = get_api_keys(db, user_id)

        return ApiKeysResponse(total_count=len(keys), user_id=user_id, api_keys=keys)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/", response_model=UnmaskedApiKeyRead)
def create_api_key_route(
    req: ApiKeyCreate,
    current_user: User = Depends(auth_utils.get_current_active_user),
    db: Session = Depends(get_session),
):
    try:
        user_id = current_user.id
        return create_api_key(db, req, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{api_key_id}")
def delete_api_key_route(
    api_key_id: UUID,
    current_user=Depends(auth_utils.get_current_active_user),
    db: Session = Depends(get_session),
):
    try:
        delete_api_key(db, api_key_id)
        return {"detail": "API Key deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/store")
def save_store_api_key(
    api_key_request: ApiKeyCreateRequest,
    response: Response,
    current_user: User = Depends(auth_utils.get_current_active_user),
    db: Session = Depends(get_session),
    settings_service=Depends(get_settings_service),
):
    auth_settings = settings_service.auth_settings

    try:
        api_key = api_key_request.api_key

        # Encrypt the API key
        encrypted = auth_utils.encrypt_api_key(api_key, settings_service=settings_service)
        current_user.store_api_key = encrypted
        db.add(current_user)
        db.commit()

        response.set_cookie(
            "apikey_tkn_lflw",
            encrypted,
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=None,  # Set to None to make it a session cookie
            domain=auth_settings.COOKIE_DOMAIN,
        )

        return {"detail": "API Key saved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/store")
def delete_store_api_key(
    current_user: User = Depends(auth_utils.get_current_active_user),
    db: Session = Depends(get_session),
):
    try:
        current_user.store_api_key = None
        db.commit()
        return {"detail": "API Key deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
