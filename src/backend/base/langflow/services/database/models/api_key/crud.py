import datetime
import secrets
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate, ApiKeyRead, UnmaskedApiKeyRead
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope

if TYPE_CHECKING:
    from sqlmodel.sql.expression import SelectOfScalar


async def get_api_keys(session: AsyncSession, user_id: UUID) -> list[ApiKeyRead]:
    query: SelectOfScalar = select(ApiKey).where(ApiKey.user_id == user_id)
    api_keys = (await session.exec(query)).all()
    return [ApiKeyRead.model_validate(api_key) for api_key in api_keys]


async def create_api_key(session: AsyncSession, api_key_create: ApiKeyCreate, user_id: UUID) -> UnmaskedApiKeyRead:
    # Generate a random API key with 32 bytes of randomness
    generated_api_key = f"sk-{secrets.token_urlsafe(32)}"

    api_key = ApiKey(
        api_key=generated_api_key,
        name=api_key_create.name,
        user_id=user_id,
        created_at=api_key_create.created_at or datetime.datetime.now(datetime.timezone.utc),
    )

    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    unmasked = UnmaskedApiKeyRead.model_validate(api_key, from_attributes=True)
    unmasked.api_key = generated_api_key
    return unmasked


async def delete_api_key(session: AsyncSession, api_key_id: UUID) -> None:
    api_key = await session.get(ApiKey, api_key_id)
    if api_key is None:
        msg = "API Key not found"
        raise ValueError(msg)
    await session.delete(api_key)
    await session.commit()


async def check_key(session: AsyncSession, api_key: str) -> User | None:
    """Check if the API key is valid."""
    query: SelectOfScalar = select(ApiKey).options(selectinload(ApiKey.user)).where(ApiKey.api_key == api_key)
    api_key_object: ApiKey | None = (await session.exec(query)).first()
    if api_key_object is not None:
        settings_service = get_settings_service()
        if settings_service.settings.disable_track_apikey_usage is not True:
            await update_total_uses(api_key_object.id)
        return api_key_object.user
    return None


async def update_total_uses(api_key_id: UUID):
    """Update the total uses and last used at."""
    async with session_scope() as session:
        new_api_key = await session.get(ApiKey, api_key_id)
        if new_api_key is None:
            msg = "API Key not found"
            raise ValueError(msg)
        new_api_key.total_uses += 1
        new_api_key.last_used_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(new_api_key)
        await session.commit()
