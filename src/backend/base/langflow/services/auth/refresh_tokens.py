"""Persist native refresh token revocation across workers and restarts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from jwt.utils import base64url_decode, base64url_encode
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import col, select

from langflow.services.database.models.auth.refresh_token import RevokedRefreshToken

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession

_EXPIRED_REVOCATION_BATCH_SIZE = 100


def _token_digest(token: str) -> str:
    """Hash a canonical representation of a previously verified native JWT."""
    canonical = b".".join(base64url_encode(base64url_decode(segment)) for segment in token.split("."))
    return hashlib.sha256(canonical).hexdigest()


async def consume_refresh_token(token: str, expires_at: datetime, db: AsyncSession) -> bool:
    """Atomically consume a verified token and report whether this request won."""
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = (
        insert(RevokedRefreshToken)
        .values(token_digest=_token_digest(token), expires_at=expires_at)
        .on_conflict_do_nothing(index_elements=["token_digest"])
        .returning(col(RevokedRefreshToken.token_digest))
    )
    result = await db.execute(statement)
    if result.scalar_one_or_none() is None:
        return False

    expired = await db.exec(
        select(RevokedRefreshToken.token_digest)
        .where(col(RevokedRefreshToken.expires_at) <= datetime.now(timezone.utc))
        .order_by(col(RevokedRefreshToken.expires_at))
        .limit(_EXPIRED_REVOCATION_BATCH_SIZE)
    )
    expired_digests = list(expired)
    if expired_digests:
        await db.execute(delete(RevokedRefreshToken).where(col(RevokedRefreshToken.token_digest).in_(expired_digests)))
    return True


async def revoke_refresh_token(token: str, db: AsyncSession, settings: SettingsService) -> None:
    """Revoke a valid native refresh token and leave malformed cookies harmless."""
    from langflow.services.auth.utils import get_jwt_verification_key

    try:
        payload = jwt.decode(
            token,
            get_jwt_verification_key(settings),
            algorithms=[settings.auth_settings.ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        if payload.get("type") != "refresh":
            return
        UUID(payload["sub"])
        expires_at = datetime.fromtimestamp(float(payload["exp"]), timezone.utc)
    except (InvalidTokenError, KeyError, TypeError, ValueError, OverflowError):
        return

    await consume_refresh_token(token, expires_at, db)
