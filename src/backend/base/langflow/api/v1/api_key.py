from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from lfx.services.authorization import AuthorizationMutation, AuthorizationMutationKind

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas import ApiKeyCreateRequest, ApiKeysResponse
from langflow.services.auth import utils as auth_utils
from langflow.services.authorization.lifecycle import safe_identity_mutation_committed, stage_identity_mutation
from langflow.services.authorization.utils import audit_decision

# Assuming you have these methods in your service layer
from langflow.services.database.models.api_key.crud import create_api_key, delete_api_key, get_api_keys
from langflow.services.database.models.api_key.model import ApiKeyCreate, UnmaskedApiKeyRead
from langflow.services.deps import get_authorization_service, get_settings_service

router = APIRouter(tags=["APIKey"], prefix="/api_key")


@router.get("/", include_in_schema=False)
async def get_api_keys_route(
    db: DbSession,
    current_user: CurrentActiveUser,
) -> ApiKeysResponse:
    try:
        user_id = current_user.id
        api_keys = await get_api_keys(db, user_id)
        return ApiKeysResponse(total_count=len(api_keys), user_id=user_id, api_keys=api_keys)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/", include_in_schema=False)
async def create_api_key_route(
    req: ApiKeyCreate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> UnmaskedApiKeyRead:
    try:
        user_id = current_user.id
        created_key = await create_api_key(db, req, user_id=user_id)
    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e

    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.API_KEY_CREATED,
        entity_id=created_key.id,
        actor_user_id=current_user.id,
        affected_user_ids=(current_user.id,),
        policy_relevant_fields=("is_active", "expires_at"),
    )
    authorization_service = get_authorization_service()
    try:
        await db.flush()
        await stage_identity_mutation(authorization_service, db, mutation)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to finalize API key creation.") from e

    await safe_identity_mutation_committed(authorization_service, mutation)
    await audit_decision(
        user_id=current_user.id,
        action="api_key:create",
        obj=f"api_key:{created_key.id}",
        result="allow",
        details={"secret_material_in_event": False},
    )
    return created_key


@router.delete("/{api_key_id}", include_in_schema=False)
async def delete_api_key_route(
    api_key_id: UUID,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        await delete_api_key(db, api_key_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.API_KEY_DELETED,
        entity_id=api_key_id,
        actor_user_id=current_user.id,
        affected_user_ids=(current_user.id,),
        policy_relevant_fields=("revoked",),
    )
    authorization_service = get_authorization_service()
    await db.flush()
    await stage_identity_mutation(authorization_service, db, mutation)
    await db.commit()
    await safe_identity_mutation_committed(authorization_service, mutation)
    await audit_decision(
        user_id=current_user.id,
        action="api_key:delete",
        obj=f"api_key:{api_key_id}",
        result="allow",
        details={"revocation": "effective_after_commit"},
    )
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
