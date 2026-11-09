"""Persist native refresh token revocation across workers and restarts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.services.database.models.auth.refresh_token import RevokedRefreshToken

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession

_EXPIRED_REVOCATION_BATCH_SIZE = 100


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def is_refresh_token_revoked(token: str, db: AsyncSession) -> bool:
    """Return whether a refresh token has been revoked by logout."""
    return await db.get(RevokedRefreshToken, _token_digest(token)) is not None


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
        expires_at = datetime.fromtimestamp(payload["exp"], timezone.utc)
    except (InvalidTokenError, KeyError, TypeError, ValueError, OverflowError):
        return

    expired = await db.exec(
        select(RevokedRefreshToken.token_digest)
        .where(col(RevokedRefreshToken.expires_at) <= datetime.now(timezone.utc))
        .order_by(col(RevokedRefreshToken.expires_at))
        .limit(_EXPIRED_REVOCATION_BATCH_SIZE)
    )
    expired_digests = list(expired)
    if expired_digests:
        await db.execute(delete(RevokedRefreshToken).where(col(RevokedRefreshToken.token_digest).in_(expired_digests)))

    digest = _token_digest(token)
    if await db.get(RevokedRefreshToken, digest) is not None:
        return
    try:
        async with db.begin_nested():
            db.add(RevokedRefreshToken(token_digest=digest, expires_at=expires_at))
            await db.flush()
    except IntegrityError:
        # Concurrent logout requests may revoke the same token.
        if await db.get(RevokedRefreshToken, digest) is None:
            raise
