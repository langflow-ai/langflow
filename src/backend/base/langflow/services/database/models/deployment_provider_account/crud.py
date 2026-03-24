from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from cryptography.fernet import InvalidToken
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.utils import normalize_string_or_none, parse_uuid

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

_UNSET = object()


def _strip_or_raise(value: str, field_name: str) -> str:
    """Return *value* stripped of whitespace, or raise if blank."""
    stripped = value.strip()
    if not stripped:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    return stripped


def _encrypt_api_key(raw: str) -> str:
    """Encrypt an API key, raising ``RuntimeError`` on failure."""
    stripped = raw.strip()
    if not stripped:
        msg = "api_key must not be empty"
        raise ValueError(msg)
    try:
        return auth_utils.encrypt_api_key(stripped)
    except (ValueError, InvalidToken, TypeError, AttributeError) as e:
        msg = "Failed to encrypt API key -- check server encryption configuration"
        raise RuntimeError(msg) from e


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
    offset: int = 0,
    limit: int | None = None,
) -> list[DeploymentProviderAccount]:
    user_uuid = parse_uuid(user_id, field_name="user_id")
    stmt = (
        select(DeploymentProviderAccount)
        .where(DeploymentProviderAccount.user_id == user_uuid)
        .order_by(col(DeploymentProviderAccount.created_at).desc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await db.exec(stmt)).all())


async def count_provider_accounts(
    db: AsyncSession,
    *,
    user_id: UUID | str,
) -> int:
    from sqlmodel import func

    user_uuid = parse_uuid(user_id, field_name="user_id")
    stmt = select(func.count(DeploymentProviderAccount.id)).where(
        DeploymentProviderAccount.user_id == user_uuid,
    )
    return int((await db.exec(stmt)).one() or 0)


async def create_provider_account(
    db: AsyncSession,
    *,
    user_id: UUID | str,
    name: str,
    provider_tenant_id: str | None,
    provider_key: str,
    provider_url: str,
    api_key: str,
) -> DeploymentProviderAccount:
    user_uuid = parse_uuid(user_id, field_name="user_id")

    # The model has its own field validators, but pre-checking here gives
    # clearer errors and avoids constructing the object.
    name_s = _strip_or_raise(name, "name")
    provider_key_s = _strip_or_raise(provider_key, "provider_key")
    provider_url_s = _strip_or_raise(provider_url, "provider_url")

    now = datetime.now(timezone.utc)
    try:
        encrypted_key = _encrypt_api_key(api_key)
    except RuntimeError:
        await logger.aerror(
            "Encryption failed creating provider account (user_id=%s, provider_url=%s)",
            user_id,
            provider_url,
        )
        raise
    provider_account = DeploymentProviderAccount(
        user_id=user_uuid,
        name=name_s,
        provider_tenant_id=normalize_string_or_none(provider_tenant_id),
        provider_key=provider_key_s,
        provider_url=provider_url_s,
        api_key=encrypted_key,
        created_at=now,
        updated_at=now,
    )
    db.add(provider_account)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await logger.aerror(
            "IntegrityError creating provider account (user_id=%s, name=%s, provider_url=%s, provider_tenant_id=%s)",
            user_uuid,
            name_s,
            provider_url_s,
            provider_tenant_id,
        )
        msg = (
            f"Provider account already exists "
            f"(name={name!r}, provider_url={provider_url!r}, provider_tenant_id={provider_tenant_id!r})"
        )
        raise ValueError(msg) from exc
    await db.refresh(provider_account)
    return provider_account


async def update_provider_account(
    db: AsyncSession,
    *,
    provider_account: DeploymentProviderAccount,
    name: str | None = None,
    provider_tenant_id: str | None = _UNSET,  # type: ignore[assignment]
    provider_key: str | None = None,
    provider_url: str | None = None,
    api_key: str | None = None,
) -> DeploymentProviderAccount:
    if name is not None:
        provider_account.name = _strip_or_raise(name, "name")
    if provider_tenant_id is not _UNSET:
        provider_account.provider_tenant_id = normalize_string_or_none(provider_tenant_id)  # type: ignore[arg-type]
    if provider_key is not None:
        provider_account.provider_key = _strip_or_raise(provider_key, "provider_key")
    if provider_url is not None:
        provider_account.provider_url = _strip_or_raise(provider_url, "provider_url")
    if api_key is not None:
        try:
            provider_account.api_key = _encrypt_api_key(api_key)
        except RuntimeError:
            await logger.aerror(
                "Encryption failed updating provider account id=%s",
                provider_account.id,
            )
            raise
    provider_account.updated_at = datetime.now(timezone.utc)
    db.add(provider_account)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await logger.aerror("IntegrityError updating provider account id=%s", provider_account.id)
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
        msg = f"Failed to delete provider account id={provider_account.id}"
        raise ValueError(msg) from exc
