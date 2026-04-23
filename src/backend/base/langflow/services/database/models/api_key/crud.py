import binascii
import datetime
import hashlib
import os
import secrets
from typing import TYPE_CHECKING, Any
from uuid import UUID

from cryptography.fernet import InvalidToken
from lfx.log.logger import logger
from lfx.services.settings.ip_restriction import check_ip_restriction, validate_allowed_ips
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.auth import utils as auth_utils
from langflow.services.auth.exceptions import IpRestrictionError
from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate, ApiKeyRead, UnmaskedApiKeyRead
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from sqlmodel.sql.expression import SelectOfScalar


def hash_api_key(api_key: str) -> str:
    """One-way SHA-256 hash of a plaintext API key for indexed lookup."""
    return hashlib.sha256(api_key.encode()).hexdigest()


async def get_api_keys(session: AsyncSession, user_id: UUID) -> list[ApiKeyRead]:
    """Get all API keys for a user with decrypted values."""
    query: SelectOfScalar = select(ApiKey).where(ApiKey.user_id == user_id)
    api_key_objects = (await session.exec(query)).all()

    api_keys = []
    for api_key_obj in api_key_objects:
        data = api_key_obj.model_dump()

        api_key = data.get("api_key")
        if api_key:
            try:
                actual_key = auth_utils.decrypt_api_key(api_key)
            except (ValueError, TypeError, InvalidToken, UnicodeDecodeError, AttributeError, binascii.Error):
                actual_key = api_key
            # decrypt_api_key returns "" on failure; fall back to stored value
            if not actual_key:
                actual_key = api_key
        else:
            actual_key = api_key

        data["api_key"] = actual_key
        api_keys.append(ApiKeyRead.model_validate(data))

    return api_keys


async def create_api_key(session: AsyncSession, api_key_create: ApiKeyCreate, user_id: UUID) -> UnmaskedApiKeyRead:
    # Reject malformed IP allow-lists up front so invalid patterns never reach the DB.
    normalized_allowed_ips = validate_allowed_ips(api_key_create.allowed_ips)

    # Generate a random API key with 32 bytes of randomness
    generated_api_key = f"sk-{secrets.token_urlsafe(32)}"

    stored_api_key = auth_utils.encrypt_api_key(generated_api_key)

    api_key = ApiKey(
        api_key=stored_api_key,
        api_key_hash=hash_api_key(generated_api_key),
        name=api_key_create.name,
        user_id=user_id,
        created_at=api_key_create.created_at or datetime.datetime.now(datetime.timezone.utc),
        allowed_ips=normalized_allowed_ips,
    )

    session.add(api_key)
    await session.flush()
    await session.refresh(api_key)
    unmasked = UnmaskedApiKeyRead.model_validate(api_key, from_attributes=True)
    unmasked.api_key = generated_api_key
    return unmasked


async def delete_api_key(session: AsyncSession, api_key_id: UUID, user_id: UUID) -> None:
    api_key = await session.get(ApiKey, api_key_id)
    if api_key is None:
        msg = "API Key not found"
        raise ValueError(msg)
    if api_key.user_id != user_id:
        msg = "API Key not found"
        raise ValueError(msg)
    await session.delete(api_key)


async def check_key(session: AsyncSession, api_key: str, client_ip: str | None = None) -> User | None:
    """Check if the API key is valid and the caller's IP is permitted.

    Validates API keys based on the LANGFLOW_API_KEY_SOURCE setting:
    - 'db': Validates against database-stored API keys (default)
    - 'env': Validates against the LANGFLOW_API_KEY environment variable,
             falls back to database if env validation fails

    IP restriction precedence:
    1. If ``LANGFLOW_API_IP_RESTRICTION`` is set, it is the single source of
       truth and applies to every API-key request (db- or env-sourced).
    2. Otherwise the per-key ``allowed_ips`` column is consulted (db path only).

    When *client_ip* is ``None`` and a restriction exists (either global or
    per-key), the check fails closed (returns ``None``) to prevent bypasses
    from unknown contexts.
    """
    settings_service = get_settings_service()
    api_key_source = settings_service.auth_settings.API_KEY_SOURCE
    global_ip_restriction = getattr(settings_service.auth_settings, "API_IP_RESTRICTION", None)

    # Global env-level IP gate — applies to every API-key authentication.
    if global_ip_restriction and not check_ip_restriction(global_ip_restriction, client_ip):
        logger.warning(
            "API request rejected by LANGFLOW_API_IP_RESTRICTION: client IP %s is not in the allow-list",
            client_ip,
        )
        raise IpRestrictionError(client_ip)

    # If a global restriction is active, the per-key ``allowed_ips`` is ignored.
    # Pass None downstream to skip the per-key check.
    downstream_ip = None if global_ip_restriction else client_ip

    if api_key_source == "env":
        user = await _check_key_from_env(session, api_key, settings_service, _client_ip=downstream_ip)
        if user is not None:
            return user
        # Fallback to database if env validation fails
    return await _check_key_from_db(session, api_key, settings_service, client_ip=downstream_ip)


async def _check_key_from_db(
    session: AsyncSession,
    api_key: str,
    settings_service,
    client_ip: str | None = None,
) -> User | None:
    """Validate API key against the database.

    Uses hash-based O(1) lookup first. Falls back to decrypt-and-compare
    for legacy keys that don't have a hash yet, and backfills the hash on match.
    """
    if not api_key:
        return None

    incoming_hash = hash_api_key(api_key)

    # Fast path: O(1) indexed lookup by hash
    query = select(ApiKey).where(ApiKey.api_key_hash == incoming_hash)
    matches = (await session.exec(query)).all()

    if len(matches) == 1:
        api_key_obj = matches[0]
        if not check_ip_restriction(api_key_obj.allowed_ips, client_ip):
            logger.warning("API key %s rejected: client IP %s not in allowed list", str(api_key_obj.id), client_ip)
            raise IpRestrictionError(client_ip)
        if settings_service.settings.disable_track_apikey_usage is not True:
            api_key_obj.total_uses += 1
            api_key_obj.last_used_at = datetime.datetime.now(datetime.timezone.utc)
            session.add(api_key_obj)
            await session.flush()
        return await session.get(User, api_key_obj.user_id)

    if len(matches) > 1:
        key_ids = [str(m.id) for m in matches]
        logger.error(
            "Data integrity violation: %d API keys share hash %s (key IDs: %s). Refusing to authenticate.",
            len(matches),
            incoming_hash[:12] + "...",
            ", ".join(key_ids),
        )
        return None

    # Slow path: legacy keys without hash (plaintext from 1.6.x or encrypted without hash)
    query = select(ApiKey).where(ApiKey.api_key_hash.is_(None))  # type: ignore[union-attr]
    legacy_keys = (await session.exec(query)).all()

    for api_key_obj in legacy_keys:
        stored_value = api_key_obj.api_key
        if stored_value is None:
            continue

        # decrypt_api_key returns "" on failure (never raises for decryption errors)
        if stored_value == api_key:
            matched = True
        else:
            candidate = auth_utils.decrypt_api_key(stored_value)
            matched = candidate == api_key

        if matched:
            if not check_ip_restriction(api_key_obj.allowed_ips, client_ip):
                logger.warning("API key %s rejected: client IP %s not in allowed list", str(api_key_obj.id), client_ip)
                raise IpRestrictionError(client_ip)
            # Backfill hash for future O(1) lookups
            api_key_obj.api_key_hash = incoming_hash
            if settings_service.settings.disable_track_apikey_usage is not True:
                api_key_obj.total_uses += 1
                api_key_obj.last_used_at = datetime.datetime.now(datetime.timezone.utc)
            session.add(api_key_obj)
            await session.flush()
            return await session.get(User, api_key_obj.user_id)

    return None


async def _check_key_from_env(
    session: AsyncSession,
    api_key: str,
    settings_service,
    _client_ip: str | None = None,
) -> User | None:
    """Validate API key against the environment variable.

    When API_KEY_SOURCE='env', the x-api-key header is validated against
    LANGFLOW_API_KEY environment variable. If valid, returns the superuser for authorization.
    IP restriction is not applied to env-sourced keys (no DB record to check).
    """
    from langflow.services.database.models.user.crud import get_user_by_username

    env_api_key = os.getenv("LANGFLOW_API_KEY")
    if not env_api_key:
        return None

    # Compare the provided API key with the environment variable
    if api_key != env_api_key:
        return None

    # Return the superuser for authorization purposes
    superuser_username = settings_service.auth_settings.SUPERUSER
    user = await get_user_by_username(session, superuser_username)
    if user and user.is_active:
        return user
    return None


def _api_key_read_with_decrypted_key(api_key_obj: ApiKey) -> ApiKeyRead:
    data = api_key_obj.model_dump()
    raw_key = data.get("api_key", "")
    if raw_key:
        try:
            actual_key = auth_utils.decrypt_api_key(raw_key)
        except Exception:  # noqa: BLE001
            actual_key = raw_key
        if not actual_key:
            actual_key = raw_key
        data["api_key"] = actual_key
    return ApiKeyRead.model_validate(data)


async def update_api_key(
    session: AsyncSession,
    api_key_id: UUID,
    user_id: UUID,
    updates: dict[str, Any],
) -> ApiKeyRead:
    """Update mutable fields on an API key (``name``, ``allowed_ips``).

    Only the owner of the key (matched by ``user_id``) may update it.
    ``updates`` should be a non-empty dict of fields to change (typically from
    ``ApiKeyUpdateRequest.model_dump(exclude_unset=True)``).
    """
    api_key_obj = await session.get(ApiKey, api_key_id)
    if api_key_obj is None or api_key_obj.user_id != user_id:
        msg = "API Key not found"
        raise ValueError(msg)

    if not updates:
        return _api_key_read_with_decrypted_key(api_key_obj)

    if "name" in updates:
        name_val = updates["name"]
        api_key_obj.name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if "allowed_ips" in updates:
        api_key_obj.allowed_ips = validate_allowed_ips(updates["allowed_ips"])

    session.add(api_key_obj)
    await session.flush()
    await session.refresh(api_key_obj)

    return _api_key_read_with_decrypted_key(api_key_obj)


async def regenerate_api_key(
    session: AsyncSession,
    api_key_id: UUID,
    user_id: UUID,
) -> UnmaskedApiKeyRead:
    """Replace the secret value with a new random key. Returns the plaintext once (like create)."""
    api_key_obj = await session.get(ApiKey, api_key_id)
    if api_key_obj is None or api_key_obj.user_id != user_id:
        msg = "API Key not found"
        raise ValueError(msg)

    generated_api_key = f"sk-{secrets.token_urlsafe(32)}"
    api_key_obj.api_key = auth_utils.encrypt_api_key(generated_api_key)
    api_key_obj.api_key_hash = hash_api_key(generated_api_key)

    session.add(api_key_obj)
    await session.flush()
    await session.refresh(api_key_obj)
    unmasked = UnmaskedApiKeyRead.model_validate(api_key_obj, from_attributes=True)
    unmasked.api_key = generated_api_key
    return unmasked
