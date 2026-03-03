from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from cryptography.fernet import InvalidToken
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.utils import parse_uuid

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def get_provider_account_by_id(
    db: AsyncSession,
    *,
    provider_id: UUID | str,
    user_id: UUID | str,
) -> DeploymentProviderAccount | None:
    provider_uuid = parse_uuid(provider_id, field_name="provider_id")
    user_uuid = parse_uuid(user_id, field_name="user_id")

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
    user_uuid = parse_uuid(user_id, field_name="user_id")
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
    provider_tenant_id: str | None,
    provider_key: str,
    provider_url: str,
    api_key: str,
) -> DeploymentProviderAccount:
    user_uuid = parse_uuid(user_id, field_name="user_id")
    now = datetime.now(timezone.utc)
    try:
        encrypted_key = auth_utils.encrypt_api_key(api_key.strip())
    except (ValueError, InvalidToken) as e:
        msg = "Failed to encrypt API key -- check server encryption configuration"
        await logger.aerror(msg)
        raise RuntimeError(msg) from e
    provider_account = DeploymentProviderAccount(
        user_id=user_uuid,
        provider_tenant_id=provider_tenant_id.strip() if provider_tenant_id is not None else None,
        provider_key=provider_key.strip(),
        provider_url=provider_url.strip(),
        api_key=encrypted_key,
        created_at=now,
        updated_at=now,
    )
    db.add(provider_account)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        msg = (
            f"Provider account already exists "
            f"(provider_url={provider_url!r}, provider_tenant_id={provider_tenant_id!r})"
        )
        raise ValueError(msg) from exc
    await db.refresh(provider_account)
    return provider_account


async def update_provider_account(
    db: AsyncSession,
    *,
    provider_account: DeploymentProviderAccount,
    provider_tenant_id: str | None = None,
    provider_key: str | None = None,
    provider_url: str | None = None,
    api_key: str | None = None,
) -> DeploymentProviderAccount:
    if provider_tenant_id is not None:
        provider_account.provider_tenant_id = provider_tenant_id.strip()
    if provider_key is not None:
        stripped = provider_key.strip()
        if not stripped:
            msg = "provider_key must not be empty"
            raise ValueError(msg)
        provider_account.provider_key = stripped
    if provider_url is not None:
        stripped = provider_url.strip()
        if not stripped:
            msg = "provider_url must not be empty"
            raise ValueError(msg)
        provider_account.provider_url = stripped
    if api_key is not None:
        try:
            provider_account.api_key = auth_utils.encrypt_api_key(api_key.strip())
        except (ValueError, InvalidToken) as e:
            msg = "Failed to encrypt API key -- check server encryption configuration"
            await logger.aerror(msg)
            raise RuntimeError(msg) from e
    provider_account.updated_at = datetime.now(timezone.utc)
    db.add(provider_account)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        msg = "Provider account update conflicts with an existing record"
        raise ValueError(msg) from exc
    await db.refresh(provider_account)
    return provider_account


async def delete_provider_account(
    db: AsyncSession,
    *,
    provider_account: DeploymentProviderAccount,
) -> None:
    await db.delete(provider_account)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await logger.aerror("Failed to delete provider account id=%s", provider_account.id)
        msg = "Failed to delete provider account"
        raise ValueError(msg) from exc
