from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import select

from langflow.services.auth import utils as auth_utils
from langflow.services.auth.mcp_encryption import is_encrypted
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def get_provider_account_by_id_for_user(
    db: AsyncSession,
    *,
    provider_id: UUID | str,
    user_id: UUID | str,
) -> DeploymentProviderAccount | None:

    provider_uuid = get_uuid(provider_id)
    user_uuid = get_uuid(user_id)

    stmt = select(DeploymentProviderAccount).where(
        DeploymentProviderAccount.id == provider_uuid,
        DeploymentProviderAccount.user_id == user_uuid,
    )
    return (await db.exec(stmt)).first()


def get_uuid(value: UUID | str) -> UUID:
    """Get a UUID from a string or UUID."""
    return UUID(value) if isinstance(value, str) else value


async def list_provider_accounts_for_user(
    db: AsyncSession,
    *,
    user_id: UUID | str,
) -> list[DeploymentProviderAccount]:
    user_uuid = get_uuid(user_id)
    stmt = (
        select(DeploymentProviderAccount)
        .where(DeploymentProviderAccount.user_id == user_uuid)
        .order_by(DeploymentProviderAccount.registered_at.desc())
    )
    return list((await db.exec(stmt)).all())


async def create_provider_account_for_user(
    db: AsyncSession,
    *,
    user_id: UUID | str,
    account_id: str | None,
    provider_key: str,
    backend_url: str,
    api_key: str,
) -> DeploymentProviderAccount:
    user_uuid = get_uuid(user_id)
    now = datetime.now(timezone.utc)
    provider_account = DeploymentProviderAccount(
        user_id=user_uuid,
        account_id=account_id.strip() if account_id is not None else None,
        provider_key=provider_key.strip(),
        backend_url=backend_url.strip(),
        api_key=auth_utils.encrypt_api_key(api_key.strip()),
        registered_at=now,
        updated_at=now,
    )
    db.add(provider_account)
    await db.flush()
    await db.refresh(provider_account)
    return provider_account


async def update_provider_account_for_user(
    db: AsyncSession,
    *,
    provider_account: DeploymentProviderAccount,
    account_id: str | None = None,
    provider_key: str | None = None,
    backend_url: str | None = None,
    api_key: str | None = None,
) -> DeploymentProviderAccount:
    if account_id is not None:
        provider_account.account_id = account_id.strip()
    if provider_key is not None:
        provider_account.provider_key = provider_key.strip()
    if backend_url is not None:
        provider_account.backend_url = backend_url.strip()
    if api_key is not None:
        stripped = api_key.strip()
        provider_account.api_key = stripped if is_encrypted(stripped) else auth_utils.encrypt_api_key(stripped)
    provider_account.updated_at = datetime.now(timezone.utc)
    db.add(provider_account)
    await db.flush()
    await db.refresh(provider_account)
    return provider_account


async def delete_provider_account_for_user(
    db: AsyncSession,
    *,
    provider_account: DeploymentProviderAccount,
) -> None:
    await db.delete(provider_account)
    await db.flush()
