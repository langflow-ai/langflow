from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import select

from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def get_provider_account_by_id(
    db: AsyncSession,
    *,
    provider_id: UUID | str,
    user_id: UUID | str,
) -> DeploymentProviderAccount | None:
    provider_uuid = _parse_uuid(provider_id, field_name="provider_id")
    user_uuid = _parse_uuid(user_id, field_name="user_id")

    stmt = select(DeploymentProviderAccount).where(
        DeploymentProviderAccount.id == provider_uuid,
        DeploymentProviderAccount.user_id == user_uuid,
    )
    return (await db.exec(stmt)).first()


async def list_provider_accounts(
    db: AsyncSession,
    *,
    user_id: UUID | str,
) -> list[DeploymentProviderAccount]:
    user_uuid = _parse_uuid(user_id, field_name="user_id")
    stmt = (
        select(DeploymentProviderAccount)
        .where(DeploymentProviderAccount.user_id == user_uuid)
        .order_by(DeploymentProviderAccount.created_at.desc())
    )
    return list((await db.exec(stmt)).all())


async def create_provider_account(
    db: AsyncSession,
    *,
    user_id: UUID | str,
    account_id: str | None,
    provider_key: str,
    provider_url: str,
    api_key: str,
) -> DeploymentProviderAccount:
    user_uuid = _parse_uuid(user_id, field_name="user_id")
    now = datetime.now(timezone.utc)
    try:
        encrypted_key = auth_utils.encrypt_api_key(api_key.strip())
    except Exception as e:
        msg = "Failed to encrypt API key -- check server encryption configuration"
        raise RuntimeError(msg) from e
    provider_account = DeploymentProviderAccount(
        user_id=user_uuid,
        account_id=account_id.strip() if account_id is not None else None,
        provider_key=provider_key.strip(),
        provider_url=provider_url.strip(),
        api_key=encrypted_key,
        created_at=now,
        updated_at=now,
    )
    db.add(provider_account)
    await db.flush()
    await db.refresh(provider_account)
    return provider_account


async def update_provider_account(
    db: AsyncSession,
    *,
    provider_account: DeploymentProviderAccount,
    account_id: str | None = None,
    provider_key: str | None = None,
    provider_url: str | None = None,
    api_key: str | None = None,
) -> DeploymentProviderAccount:
    if account_id is not None:
        provider_account.account_id = account_id.strip()
    if provider_key is not None:
        provider_account.provider_key = provider_key.strip()
    if provider_url is not None:
        provider_account.provider_url = provider_url.strip()
    if api_key is not None:
        try:
            provider_account.api_key = auth_utils.encrypt_api_key(api_key.strip())
        except Exception as e:
            msg = "Failed to encrypt API key -- check server encryption configuration"
            raise RuntimeError(msg) from e
    provider_account.updated_at = datetime.now(timezone.utc)
    db.add(provider_account)
    await db.flush()
    await db.refresh(provider_account)
    return provider_account


async def delete_provider_account(
    db: AsyncSession,
    *,
    provider_account: DeploymentProviderAccount,
) -> None:
    await db.delete(provider_account)
    await db.flush()


def _parse_uuid(value: UUID | str, *, field_name: str = "value") -> UUID:
    """Parse a UUID from a string or pass through a UUID.

    Raises ValueError with context if the string is not a valid UUID.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            msg = f"{field_name} must not be empty"
            raise ValueError(msg)
        try:
            return UUID(stripped)
        except ValueError:
            msg = f"{field_name} is not a valid UUID: {stripped!r}"
            raise ValueError(msg) from None
    return value
