"""Refresh database credentials at long-lived transport operation boundaries."""

from __future__ import annotations

from fastapi import HTTPException
from lfx.services.authorization import AuthorizationPrincipal

from langflow.services.auth.context import AuthCredentialContext, get_current_auth_context, set_current_auth_context
from langflow.services.authorization.audit import audit_decision
from langflow.services.database.models.api_key.crud import (
    _external_access_ceiling_blocks_user,
    _is_expired,
    _scoped_key_can_authenticate,
)
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_settings_service, session_scope


async def refresh_database_api_key_user(user: User | UserRead) -> User | UserRead:
    """Reload the current key and owner before a new operation, without a secret."""
    credential = get_current_auth_context()
    if (
        credential is None
        or credential.method != "api_key"
        or credential.api_key_source == "env"  # pragma: allowlist secret
    ):
        return user
    async with session_scope() as session:
        key = await session.get(ApiKey, credential.api_key_id) if credential.api_key_id is not None else None
        owner = await session.get(User, key.user_id if key is not None else user.id)
        valid = (
            key is not None
            and key.is_active
            and not _is_expired(key.expires_at)
            and owner is not None
            and owner.is_active
            and owner.id == user.id
            and not await _external_access_ceiling_blocks_user(session, owner, get_settings_service())
            and await _scoped_key_can_authenticate(key, get_settings_service())
        )
        owner_id = owner.id if owner is not None else None
        if valid:
            fresh = AuthCredentialContext(
                method="api_key",
                api_key_id=key.id,
                api_key_source="db",  # pragma: allowlist secret
                api_key_restricted=key.permissions is not None,
                api_key_permissions=key.permissions,
            )
            owner_snapshot = UserRead.model_validate(owner, from_attributes=True)
    if not valid:
        await audit_decision(
            user_id=owner_id,
            principal=AuthorizationPrincipal(actor_type="api_key", actor_id=credential.api_key_id, user_id=owner_id),
            action="api_key:authenticate",
            obj=f"api_key:{credential.api_key_id}",
            result="deny",
            details={"reason": "api_key_credential_authorization_invalid"},
        )
        raise HTTPException(status_code=403, detail="API key authorization is no longer valid")
    set_current_auth_context(fresh)
    return owner_snapshot
