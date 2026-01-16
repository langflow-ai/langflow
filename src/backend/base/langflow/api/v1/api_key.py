from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas import ApiKeyCreateRequest, ApiKeysResponse
from langflow.services.auth import utils as auth_utils

# Assuming you have these methods in your service layer
from langflow.services.database.models.api_key.crud import create_api_key, delete_api_key
from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate, ApiKeyRead, UnmaskedApiKeyRead
from langflow.services.deps import get_settings_service

router = APIRouter(tags=["APIKey"], prefix="/api_key")


@router.get("/")
async def get_api_keys_route(
    db: DbSession,
    current_user: CurrentActiveUser,
) -> ApiKeysResponse:
    try:
        user_id = current_user.id
        settings_service = get_settings_service()

        query = select(ApiKey).where(ApiKey.user_id == user_id)
        api_key_objects = (await db.exec(query)).all()

        api_keys = []
        for api_key_obj in api_key_objects:
            data = api_key_obj.model_dump()

            if data.get("api_key"):
                try:
                    actual_key = auth_utils.decrypt_api_key(data["api_key"], settings_service=settings_service)
                except (ValueError, TypeError):
                    # Fallback to plain-text for legacy entries or invalid encrypted values
                    actual_key = data.get("api_key")
            else:
                actual_key = data.get("api_key")

            data["api_key"] = actual_key
            api_key_read = ApiKeyRead.model_validate(data)
            api_keys.append(api_key_read)

        return ApiKeysResponse(total_count=len(api_keys), user_id=user_id, api_keys=api_keys)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/")
async def create_api_key_route(
    req: ApiKeyCreate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> UnmaskedApiKeyRead:
    try:
        user_id = current_user.id
        return await create_api_key(db, req, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{api_key_id}")
async def delete_api_key_route(
    api_key_id: UUID,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        await delete_api_key(db, api_key_id, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"detail": "API Key deleted"}


@router.post("/store")
async def save_store_api_key(
    api_key_request: ApiKeyCreateRequest,
    response: Response,
    current_user: CurrentActiveUser,
    db: DbSession,
):
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings

    try:
        api_key = api_key_request.api_key

        # Encrypt the API key
        encrypted = auth_utils.encrypt_api_key(api_key, settings_service=settings_service)
        current_user.store_api_key = encrypted
        db.add(current_user)
        await db.commit()

        response.set_cookie(
            "apikey_tkn_lflw",
            encrypted,
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=None,  # Set to None to make it a session cookie
            domain=auth_settings.COOKIE_DOMAIN,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"detail": "API Key saved"}
