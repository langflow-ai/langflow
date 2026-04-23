from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas import ApiKeyCreateRequest, ApiKeysResponse, ApiKeyUpdateRequest
from langflow.services.auth import utils as auth_utils
from langflow.services.auth.utils import get_client_ip

# Assuming you have these methods in your service layer
from langflow.services.database.models.api_key.crud import (
    create_api_key,
    delete_api_key,
    get_api_keys,
    update_api_key_allowed_ips,
)
from langflow.services.database.models.api_key.model import ApiKeyCreate, ApiKeyRead, UnmaskedApiKeyRead
from langflow.services.deps import get_settings_service

router = APIRouter(tags=["APIKey"], prefix="/api_key")


@router.get("/", include_in_schema=False)
async def get_api_keys_route(
    db: DbSession,
    current_user: CurrentActiveUser,
) -> ApiKeysResponse:
    try:
        user_id = current_user.id
        api_keys = await get_api_keys(db, user_id)
        auth_settings = get_settings_service().auth_settings
        env_restriction = getattr(auth_settings, "API_IP_RESTRICTION", None)
        return ApiKeysResponse(
            total_count=len(api_keys),
            user_id=user_id,
            api_keys=api_keys,
            env_ip_restriction_enabled=bool(env_restriction),
            env_ip_restriction=env_restriction or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/client-ip", include_in_schema=False)
async def get_client_ip_route(
    request: Request,
    _current_user: CurrentActiveUser,
) -> dict:
    """Return the client IP address as seen by the server."""
    ip = get_client_ip(request)
    return {"ip": ip}


@router.post("/", include_in_schema=False)
async def create_api_key_route(
    req: ApiKeyCreate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> UnmaskedApiKeyRead:
    try:
        user_id = current_user.id
        return await create_api_key(db, req, user_id=user_id)
    except ValueError as e:
        # ValueError from validate_allowed_ips → malformed allow-list pattern.
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/{api_key_id}", include_in_schema=False)
async def update_api_key_route(
    api_key_id: UUID,
    req: ApiKeyUpdateRequest,
    db: DbSession,
    current_user: CurrentActiveUser,
) -> ApiKeyRead:
    """Update mutable fields of an API key (currently: ``allowed_ips``)."""
    try:
        return await update_api_key_allowed_ips(db, api_key_id, current_user.id, req.allowed_ips)
    except ValueError as e:
        # "API Key not found" → 404; malformed allow-list pattern → 422.
        detail = str(e)
        status_code = 404 if "not found" in detail.lower() else 422
        raise HTTPException(status_code=status_code, detail=detail) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{api_key_id}", include_in_schema=False)
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


@router.post("/store", include_in_schema=False)
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
        encrypted = auth_utils.encrypt_api_key(api_key)
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
