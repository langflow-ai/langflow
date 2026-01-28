import binascii
import datetime
import os
import secrets
from typing import TYPE_CHECKING
from uuid import UUID

from cryptography.fernet import InvalidToken
from sqlmodel import select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate, ApiKeyRead, UnmaskedApiKeyRead
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from sqlmodel.sql.expression import SelectOfScalar


async def get_api_keys(session: AsyncSession, user_id: UUID) -> list[ApiKeyRead]:
    """Get all API keys for a user with decrypted values."""
    settings_service = get_settings_service()
    query: SelectOfScalar = select(ApiKey).where(ApiKey.user_id == user_id)
    api_key_objects = (await session.exec(query)).all()

    fernet = auth_utils.get_fernet(settings_service)
    api_keys = []
    for api_key_obj in api_key_objects:
        data = api_key_obj.model_dump()

        api_key = data.get("api_key")
        if api_key:
            try:
                actual_key = auth_utils.decrypt_api_key(api_key, settings_service=settings_service, fernet_obj=fernet)
            except (ValueError, TypeError, InvalidToken, UnicodeDecodeError, AttributeError, binascii.Error):
                # Fallback to stored value for legacy entries
                actual_key = api_key
        else:
            actual_key = api_key

        data["api_key"] = actual_key
        api_keys.append(ApiKeyRead.model_validate(data))

    return api_keys


async def create_api_key(session: AsyncSession, api_key_create: ApiKeyCreate, user_id: UUID) -> UnmaskedApiKeyRead:
    # Generate a random API key with 32 bytes of randomness
    generated_api_key = f"sk-{secrets.token_urlsafe(32)}"

    settings_service = get_settings_service()

    stored_api_key = auth_utils.encrypt_api_key(generated_api_key, settings_service=settings_service)

    api_key = ApiKey(
        api_key=stored_api_key,
        name=api_key_create.name,
        user_id=user_id,
        created_at=api_key_create.created_at or datetime.datetime.now(datetime.timezone.utc),
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


async def check_key(session: AsyncSession, api_key: str) -> User | None:
    """Check if the API key is valid.

    Validates API keys based on the LANGFLOW_API_KEY_SOURCE setting:
    - 'db': Validates against database-stored API keys (default)
    - 'env': Validates against the LANGFLOW_API_KEY environment variable,
             falls back to database if env validation fails
    """
    settings_service = get_settings_service()
    api_key_source = settings_service.auth_settings.API_KEY_SOURCE

    if api_key_source == "env":
        user = await _check_key_from_env(session, api_key, settings_service)
        if user is not None:
            return user
        # Fallback to database if env validation fails
    return await _check_key_from_db(session, api_key, settings_service)


async def _check_key_from_db(session: AsyncSession, api_key: str, settings_service) -> User | None:
    """Validate API key against the database."""
    query = select(ApiKey.id, ApiKey.api_key, ApiKey.user_id)
    rows = (await session.exec(query)).all()  # list of tuples (id, api_key, user_id)

    if not rows:
        return None

    fernet = auth_utils.get_fernet(settings_service)

    for api_key_id, stored_value, user_id in rows:
        if stored_value is None:
            continue

        if stored_value == api_key:
            matched = True
        else:
            try:
                candidate = auth_utils.decrypt_api_key(
                    stored_value, settings_service=settings_service, fernet_obj=fernet
                )
            except (ValueError, TypeError, InvalidToken):
                candidate = stored_value
            matched = candidate == api_key

        if matched:
            if settings_service.settings.disable_track_apikey_usage is not True:
                await session.exec(
                    update(ApiKey)
                    .where(ApiKey.id == api_key_id)
                    .values(
                        total_uses=ApiKey.total_uses + 1,
                        last_used_at=datetime.datetime.now(datetime.timezone.utc),
                    )
                )
            return await session.get(User, user_id)

    return None


async def _check_key_from_env(session: AsyncSession, api_key: str, settings_service) -> User | None:
    """Validate API key against the environment variable.

    When API_KEY_SOURCE='env', the x-api-key header is validated against
    LANGFLOW_API_KEY environment variable. If valid, returns the superuser for authorization.
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
