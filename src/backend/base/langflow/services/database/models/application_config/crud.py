from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .model import ApplicationConfig


async def get_config_by_key(session: AsyncSession, key: str) -> ApplicationConfig | None:
    """Get application config by key.

    Args:
        session: Database session
        key: Configuration key (e.g., 'app-logo')

    Returns:
        ApplicationConfig if found, None otherwise
    """
    statement = select(ApplicationConfig).where(ApplicationConfig.key == key)
    result = await session.exec(statement)
    return result.first()


async def upsert_config(
    session: AsyncSession,
    key: str,
    value: str,
    updated_by: UUID,
    description: str | None = None,
) -> ApplicationConfig:
    """Create or update application config.

    Args:
        session: Database session
        key: Configuration key
        value: Configuration value
        updated_by: User ID who is updating
        description: Optional description

    Returns:
        Updated or created ApplicationConfig
    """
    config = await get_config_by_key(session, key)

    if config:
        # Update existing config
        config.value = value
        config.updated_by = updated_by
        config.updated_at = datetime.now(timezone.utc)
        if description is not None:
            config.description = description
    else:
        # Create new config
        config = ApplicationConfig(key=key, value=value, updated_by=updated_by, description=description)
        session.add(config)

    await session.commit()
    await session.refresh(config)
    return config
