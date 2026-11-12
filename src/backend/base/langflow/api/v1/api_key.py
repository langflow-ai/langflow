from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from lfx.services.authorization import AuthorizationMutation, AuthorizationMutationKind

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas import ApiKeyCreateRequest, ApiKeysResponse
from langflow.services.auth import utils as auth_utils
from langflow.services.auth.cookies import auth_cookie_name
from langflow.services.authorization.lifecycle import safe_identity_mutation_committed, stage_identity_mutation
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.lock_retry import is_database_lock_error, run_with_lock_retry, sanitize_database_error

# Assuming you have these methods in your service layer
from langflow.services.database.models.api_key.crud import (
    create_api_key,
    delete_api_key,
    get_api_keys,
    update_api_key_permissions,
)
from langflow.services.database.models.api_key.model import ApiKeyCreate, ApiKeyRead, UnmaskedApiKeyRead
from langflow.services.database.models.api_key.permissions import ApiKeyPermissionOptions, ApiKeyPermissionsUpdate
from langflow.services.database.models.api_key.policy import ensure_api_key_management_allowed
from langflow.services.deps import get_authorization_service, get_settings_service

API_KEY_CREATE_FAILED = "Failed to create the API key."
API_KEY_STORE_FAILED = "Failed to store the API key."
API_KEY_DELETE_FAILED = "Failed to delete the API key."

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
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/permission-options")
async def get_api_key_permission_options(current_user: CurrentActiveUser) -> ApiKeyPermissionOptions:
    try:
        ensure_api_key_management_allowed()
        auth_settings = get_settings_service().auth_settings
        if not auth_settings.AUTHZ_ENABLED or not auth_settings.API_KEY_SCOPES_ENABLED:
            return ApiKeyPermissionOptions()
        authorization = get_authorization_service()
        if not await authorization.supports_api_key_scopes():
            return ApiKeyPermissionOptions()
        options = await authorization.get_api_key_permission_options(user_id=current_user.id)
        return ApiKeyPermissionOptions.model_validate(options)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="API key permission options are unavailable") from exc


@router.patch("/{api_key_id}/permissions")
async def update_api_key_permissions_route(
    api_key_id: UUID,
    req: ApiKeyPermissionsUpdate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> ApiKeyRead:
    user_id = current_user.id
    try:
        updated = await update_api_key_permissions(
            db,
            api_key_id=api_key_id,
            user_id=user_id,
            permissions=req.permissions.model_dump(mode="json", exclude_unset=True)
            if req.permissions is not None
            else None,
        )
    except PermissionError as exc:
        await db.rollback()
        await audit_decision(
            user_id=user_id,
            action="api_key:permissions_update",
            obj=f"api_key:{api_key_id}",
            result="deny",
            details={"reason": "permission_policy_refused"},
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail="API Key not found") from exc

    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.API_KEY_PERMISSIONS_UPDATED,
        entity_id=api_key_id,
        actor_user_id=user_id,
        affected_user_ids=(user_id,),
        policy_relevant_fields=("permissions",),
    )
    authorization = get_authorization_service()
    try:
        await stage_identity_mutation(authorization, db, mutation)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update API key permissions") from exc
    await safe_identity_mutation_committed(authorization, mutation)
    await audit_decision(
        user_id=user_id,
        action="api_key:permissions_update",
        obj=f"api_key:{api_key_id}",
        result="allow",
        details={"event": "mutation", "restricted": updated.permissions is not None, "secret_material_in_event": False},
    )
    return updated


@router.post("/", include_in_schema=False)
async def create_api_key_route(
    req: ApiKeyCreate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> UnmaskedApiKeyRead:
    """Create a scoped API key.

    The insert runs inside :func:`run_with_lock_retry` because SQLite under WAL
    answers ``SQLITE_BUSY_SNAPSHOT`` to a connection that has already read, and
    refuses to invoke the busy handler for it, so ``busy_timeout`` cannot rescue
    the write. Only a fresh transaction can. ``PostgreSQL`` never matches the
    retry predicate, so this is inert there.
    """
    authorization_service = get_authorization_service()
    committed: AuthorizationMutation | None = None

    async def _create_attempt(_attempt: int) -> UnmaskedApiKeyRead:
        nonlocal committed
        try:
            created_key = await create_api_key(db, req, user_id=current_user.id)
        except PermissionError as e:
            await db.rollback()
            raise HTTPException(status_code=403, detail=str(e)) from e
        except Exception as e:
            # A lock conflict must reach the retry loop untouched: rolling back here
            # is pointless because the loop rolls back too, and wrapping it in an
            # HTTPException would make it look like a caller error, so the write
            # would never be retried against a fresh snapshot.
            if is_database_lock_error(e):
                raise
            await db.rollback()
            raise HTTPException(status_code=400, detail=sanitize_database_error(e, API_KEY_CREATE_FAILED)) from e

        mutation = AuthorizationMutation(
            kind=AuthorizationMutationKind.API_KEY_CREATED,
            entity_id=created_key.id,
            actor_user_id=current_user.id,
            affected_user_ids=(current_user.id,),
            policy_relevant_fields=("is_active", "expires_at"),
        )
        try:
            await db.flush()
            await stage_identity_mutation(authorization_service, db, mutation)
            await db.commit()
        except Exception as e:
            await db.rollback()
            msg = "Failed to finalize API key creation."
            raise HTTPException(status_code=500, detail=msg) from e
        # The retry loop may run this body more than once; only the mutation that
        # reached a commit describes the row that now exists.
        committed = mutation
        return created_key

    created_key = await run_with_lock_retry(_create_attempt, session=db, description="create_api_key")

    if committed is not None:
        await safe_identity_mutation_committed(authorization_service, committed)
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
    authorization_service = get_authorization_service()
    committed: AuthorizationMutation | None = None

    async def _delete_attempt(_attempt: int) -> None:
        nonlocal committed
        try:
            await delete_api_key(db, api_key_id, current_user.id)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            if is_database_lock_error(e):
                raise
            raise HTTPException(status_code=400, detail=sanitize_database_error(e, API_KEY_DELETE_FAILED)) from e

        mutation = AuthorizationMutation(
            kind=AuthorizationMutationKind.API_KEY_DELETED,
            entity_id=api_key_id,
            actor_user_id=current_user.id,
            affected_user_ids=(current_user.id,),
            policy_relevant_fields=("revoked",),
        )
        await db.flush()
        await stage_identity_mutation(authorization_service, db, mutation)
        await db.commit()
        # Only the attempt that reached a commit describes what the database holds.
        committed = mutation

    await run_with_lock_retry(_delete_attempt, session=db, description="delete_api_key")

    if committed is not None:
        await safe_identity_mutation_committed(authorization_service, committed)
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
    request: Request,
    response: Response,
    current_user: CurrentActiveUser,
    db: DbSession,
):
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings

    try:
        ensure_api_key_management_allowed()
        api_key = api_key_request.api_key

        # Encrypt the API key
        encrypted = auth_utils.encrypt_api_key(api_key)

        async def _store_attempt(_attempt: int) -> None:
            current_user.store_api_key = encrypted
            db.add(current_user)
            await db.commit()

        await run_with_lock_retry(_store_attempt, session=db, description="store_api_key")

        response.set_cookie(
            auth_cookie_name("apikey_tkn_lflw", request),
            encrypted,
            # Match the login cookie path so prefixed instances stay isolated.
            path=f"{request.app.root_path.strip().rstrip('/')}/",
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=None,  # Set to None to make it a session cookie
            domain=auth_settings.COOKIE_DOMAIN,
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        if is_database_lock_error(e):
            # Should be unreachable: the retry loop already exhausted its budget.
            raise HTTPException(status_code=503, detail=API_KEY_STORE_FAILED) from e
        raise HTTPException(status_code=400, detail=sanitize_database_error(e, API_KEY_STORE_FAILED)) from e

    return {"detail": "API Key saved"}
