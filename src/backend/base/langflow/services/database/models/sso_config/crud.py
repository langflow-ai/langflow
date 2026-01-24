"""CRUD operations for SSO configuration."""

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.sso_config.model import SSOConfig, SSOConfigUpdate


async def get_active_sso_config(db: AsyncSession) -> SSOConfig | None:
    """Get the active SSO configuration.

    For single-tenant deployments, returns the first enabled config.
    For multi-tenant (future), this would filter by workspace/tenant.

    Args:
        db: Database session

    Returns:
        Active SSOConfig or None if SSO is not configured
    """
    statement = select(SSOConfig).where(SSOConfig.enabled == True).limit(1)  # noqa: E712
    result = await db.exec(statement)
    return result.first()


async def get_sso_config_by_id(db: AsyncSession, config_id: UUID) -> SSOConfig | None:
    """Get SSO configuration by ID.

    Args:
        db: Database session
        config_id: Configuration ID

    Returns:
        SSOConfig or None if not found
    """
    statement = select(SSOConfig).where(SSOConfig.id == config_id)
    result = await db.exec(statement)
    return result.first()


async def get_all_sso_configs(db: AsyncSession) -> list[SSOConfig]:
    """Get all SSO configurations.

    Args:
        db: Database session

    Returns:
        List of all SSOConfig records
    """
    statement = select(SSOConfig)
    result = await db.exec(statement)
    return list(result.all())


async def create_sso_config(
    db: AsyncSession,
    config_data: dict,
    created_by: UUID | None = None,
) -> SSOConfig:
    """Create a new SSO configuration.

    Args:
        db: Database session
        config_data: Configuration data
        created_by: User ID who created the config

    Returns:
        Created SSOConfig
    """
    config = SSOConfig(**config_data, created_by=created_by, updated_by=created_by)
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def update_sso_config(
    db: AsyncSession,
    config_id: UUID,
    config_update: SSOConfigUpdate,
    updated_by: UUID | None = None,
) -> SSOConfig | None:
    """Update an existing SSO configuration.

    Args:
        db: Database session
        config_id: Configuration ID to update
        config_update: Update data
        updated_by: User ID who updated the config

    Returns:
        Updated SSOConfig or None if not found
    """
    config = await get_sso_config_by_id(db, config_id)
    if not config:
        return None

    # Update fields
    update_data = config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)

    # Update metadata
    config.updated_at = datetime.now(timezone.utc)
    if updated_by:
        config.updated_by = updated_by

    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def delete_sso_config(db: AsyncSession, config_id: UUID) -> bool:
    """Delete an SSO configuration.

    Args:
        db: Database session
        config_id: Configuration ID to delete

    Returns:
        True if deleted, False if not found
    """
    config = await get_sso_config_by_id(db, config_id)
    if not config:
        return False

    await db.delete(config)
    await db.commit()
    return True


async def disable_all_sso_configs(db: AsyncSession) -> int:
    """Disable all SSO configurations.

    Useful when switching back to password-based auth or when
    troubleshooting SSO issues.

    Args:
        db: Database session

    Returns:
        Number of configs disabled
    """
    statement = select(SSOConfig).where(SSOConfig.enabled == True)  # noqa: E712
    result = await db.exec(statement)
    configs = result.all()

    count = 0
    for config in configs:
        config.enabled = False
        config.updated_at = datetime.now(timezone.utc)
        db.add(config)
        count += 1

    await db.commit()
    return count
