from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from langflow.api.v1.schemas import ApiKeysResponse
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.api_key.api_key import (
    ApiKeyCreate,
    UnmaskedApiKeyRead,
)

# Assuming you have these methods in your service layer
from langflow.services.database.models.api_key.crud import (
    get_api_keys,
    create_api_key,
    delete_api_key,
)
from langflow.services.database.models.user.user import User
from langflow.services.getters import get_session
from sqlmodel import Session


router = APIRouter(tags=["APIKey"], prefix="/api_key")


@router.get("/", response_model=ApiKeysResponse)
def get_api_keys_route(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    try:
        delete_api_key(db, api_key_id)
        return {"detail": "API Key deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
