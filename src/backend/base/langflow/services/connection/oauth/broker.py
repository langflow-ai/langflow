"""One-time consent and worker-local OAuth exchanges under database locks."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from sqlalchemy import update
from sqlmodel import col

from langflow.services.auth import utils as auth_utils
from langflow.services.authorization import ConnectionAction, ensure_connection_permission
from langflow.services.connection.oauth import providers
from langflow.services.connection.oauth.config import OAuthError, get_oauth_settings
from langflow.services.connection.oauth.locking import lock_connection
from langflow.services.database.models.connection import ConnectionSecret
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.connection import Connection


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def start(
    session: AsyncSession, *, row: Connection, user_id: UUID, registration_id: str, scopes: list[str]
) -> tuple[str, str, str]:
    registration = get_oauth_settings().registration(registration_id)
    if registration.provider != row.provider_key:
        msg = "OAuth registration does not match this connection's provider."
        raise OAuthError(msg)
    expected_identity = "bot" if registration.profile == "bot" else "user_delegated"
    if row.executing_identity.get("identity") != expected_identity:
        msg = "OAuth registration does not match this connection's identity type."
        raise OAuthError(msg)
    if not scopes or not set(scopes) <= set(registration.scopes):
        msg = "Requested scopes are outside the configured registration."
        raise OAuthError(msg)
    if registration.provider == "google" and registration.allowed_tenants and not {"openid", "email"} <= set(scopes):
        msg = "Google tenant restrictions require openid and email scopes."
        raise OAuthError(msg)
    state, browser, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    binding = await session.get(ConnectionOAuth, row.id)
    if binding is None:
        binding = ConnectionOAuth(
            connection_id=row.id,
            user_id=user_id,
            registration_id=registration_id,
            config_digest=registration.fingerprint(),
            expires_at=datetime.now(timezone.utc),
        )
    binding.generation = uuid4()
    binding.user_id = user_id
    binding.registration_id = registration_id
    binding.config_digest = registration.fingerprint()
    binding.state_digest = digest(state)
    binding.browser_digest = digest(browser)
    binding.encrypted_verifier = auth_utils.encrypt_api_key(verifier)
    binding.scopes = scopes
    binding.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    session.add(binding)
    await session.flush()
    return providers.authorization_url(registration, state=state, verifier=verifier, scopes=scopes), state, browser


async def complete(*, provider: str, state: str, browser: str, code: str | None, denied: bool) -> None:
    # Commit consumption separately, including when the provider rejects an expired
    # code or PKCE verifier. No request failure can roll the state back into use.
    async with session_scope() as session:
        consumed = await session.execute(
            update(ConnectionOAuth)
            .where(
                col(ConnectionOAuth.state_digest) == digest(state),
                col(ConnectionOAuth.browser_digest) == digest(browser),
            )
            .values(state_digest=None, browser_digest=None)
            .returning(ConnectionOAuth)
        )
        binding = consumed.scalar_one_or_none()
        if binding is None:
            msg = "OAuth callback is invalid, expired, or already used."
            raise OAuthError(msg)
        values = binding.model_dump()
        binding.encrypted_verifier = None
        session.add(binding)
    if denied or not code or _aware(values["expires_at"]) <= datetime.now(timezone.utc):
        msg = "OAuth authorization was denied or expired. Start again."
        raise OAuthError(msg)
    registration = get_oauth_settings().registration(values["registration_id"])
    if registration.provider != provider or registration.fingerprint() != values["config_digest"]:
        msg = "OAuth registration changed or is not configured for this provider."
        raise OAuthError(msg)
    async with session_scope() as session:
        row = await lock_connection(session, values["connection_id"])
        binding = await session.get(ConnectionOAuth, values["connection_id"])
        if row is None or binding is None or binding.generation != values["generation"]:
            msg = "OAuth authorization was superseded or revoked. Start again."
            raise OAuthError(msg)
        user = await session.get(User, values["user_id"])
        if user is None or not user.is_active:
            msg = "OAuth initiating user is no longer active."
            raise OAuthError(msg)
        await ensure_connection_permission(
            user, ConnectionAction.WRITE, connection_id=row.id, connection_owner_id=row.owner_id
        )
        verifier = auth_utils.decrypt_api_key(values["encrypted_verifier"])
        if not verifier:
            msg = "OAuth verifier is unavailable. Start again."
            raise OAuthError(msg)
        payload, scopes, account = await providers.exchange(
            registration, code=code, verifier=verifier, previous_scopes=values["scopes"]
        )
        payload["oauth"] = {
            "registration_id": binding.registration_id,
            "config_digest": binding.config_digest,
            "generation": str(binding.generation),
        }
        await store_tokens(session, row, payload, scopes)
        if account:
            row.executing_identity = {**row.executing_identity, "account": account}
            session.add(row)


async def store_tokens(session: AsyncSession, row: Connection, payload: dict, scopes: list[str]) -> None:
    from langflow.services.connection.service import _encrypt_credential_payload

    secret = await session.get(ConnectionSecret, row.id)
    if secret is None:
        secret = ConnectionSecret(connection_id=row.id, encrypted_payload="")
    secret.encrypted_payload = _encrypt_credential_payload(json.dumps(payload))
    row.granted_scopes = scopes
    row.status = "ready"
    row.health = "healthy"
    row.health_checked_at = datetime.now(timezone.utc)
    row.updated_at = row.health_checked_at
    session.add(secret)
    session.add(row)
    await session.flush()


async def refresh_if_needed(
    session: AsyncSession, row: Connection, payload: dict, *, rejected_token_digest: str | None = None
) -> dict:
    from langflow.services.connection.service import _parse_expiry

    oauth = payload.get("oauth")
    if not oauth:
        return payload
    binding = await session.get(ConnectionOAuth, row.id)
    if binding is None or str(binding.generation) != oauth.get("generation"):
        msg = "OAuth authorization was superseded or revoked. Reconnect."
        raise OAuthError(msg)
    registration = get_oauth_settings().registration(oauth["registration_id"])
    if registration.provider != row.provider_key or registration.fingerprint() != oauth["config_digest"]:
        msg = "OAuth registration changed. Reconnect the connection."
        raise OAuthError(msg)
    expiry = _parse_expiry(payload.get("expires_at"))
    rejected = rejected_token_digest is not None and secrets.compare_digest(
        rejected_token_digest, digest(payload["access_token"])
    )
    if not rejected and (expiry is None or expiry > datetime.now(timezone.utc) + timedelta(seconds=60)):
        return payload
    if not payload.get("refresh_token"):
        msg = "OAuth authorization expired. Reconnect the connection."
        raise OAuthError(msg)
    refreshed, scopes, _ = await providers.exchange(
        registration, refresh_token=payload["refresh_token"], previous_scopes=row.granted_scopes
    )
    refreshed["oauth"] = oauth
    await store_tokens(session, row, refreshed, scopes)
    return refreshed


async def revoke(
    session: AsyncSession, row: Connection
) -> Literal["revoked", "unsupported", "failed", "not_applicable"]:
    from langflow.services.connection.service import _decrypt_credential_payload

    binding = await session.get(ConnectionOAuth, row.id)
    if binding is not None:
        await session.delete(binding)
    secret = await session.get(ConnectionSecret, row.id)
    if secret is None:
        return "not_applicable"
    try:
        payload = _decrypt_credential_payload(secret.encrypted_payload)
        oauth = payload.get("oauth")
        if not oauth:
            return "not_applicable"
        registration = get_oauth_settings().registration(oauth["registration_id"])
        if registration.fingerprint() != oauth["config_digest"]:
            return "failed"
        return "revoked" if await providers.revoke(registration, payload) else "unsupported"
    except (OAuthError, ValueError, KeyError, TypeError, RuntimeError):
        # Local revocation must commit even if a provider is unavailable, a
        # registration was removed, or the old envelope cannot be decrypted.
        return "failed"
