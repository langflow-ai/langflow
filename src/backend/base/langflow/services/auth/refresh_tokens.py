"""Persist native refresh-session revocation across workers and restarts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from sqlalchemy import case, delete, false, insert, literal, update
from sqlmodel import col, select

from langflow.services.database.models.auth.refresh_token import RefreshTokenSession
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession

_EXPIRED_SESSION_BATCH_SIZE = 100
_MAX_SESSION_ID_LENGTH = 128


def refresh_session_id(payload: dict[str, Any]) -> str:
    """Require a session identifier on a previously verified native refresh JWT."""
    session_id = payload.get("sid")
    if not isinstance(session_id, str) or not session_id or len(session_id) > _MAX_SESSION_ID_LENGTH:
        msg = "Invalid refresh session"
        raise ValueError(msg)
    return session_id


def _session_digest(session_id: str, user_id: str) -> str:
    return hashlib.sha256(f"{UUID(user_id)}:{session_id}".encode()).hexdigest()


async def create_refresh_session(session_id: str, user_id: str, expires_at: datetime, db: AsyncSession) -> bool:
    """Persist a login only while its native owner remains active in this transaction."""
    statement = (
        insert(RefreshTokenSession)
        .from_select(
            ["session_digest", "user_id", "expires_at", "revoked"],
            select(
                literal(_session_digest(session_id, user_id)),
                col(User.id),
                literal(expires_at, type_=RefreshTokenSession.__table__.c.expires_at.type),
                false(),
            ).where(User.id == UUID(user_id), col(User.is_active).is_(True)),
        )
        .returning(col(RefreshTokenSession.session_digest))
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none() is not None


async def register_refresh_session(session_id: str, user_id: str, expires_at: datetime, db: AsyncSession) -> bool:
    """Extend a live session atomically without consuming any refresh token.

    Logout and refresh write the same row. Once logout commits, even a refresh
    already in progress cannot clear its revocation or recreate a pruned session.
    """
    statement = (
        update(RefreshTokenSession)
        .where(
            col(RefreshTokenSession.session_digest) == _session_digest(session_id, user_id),
            col(RefreshTokenSession.revoked).is_(False),
        )
        .values(
            expires_at=case(
                (col(RefreshTokenSession.expires_at) < expires_at, expires_at),
                else_=col(RefreshTokenSession.expires_at),
            )
        )
        .returning(col(RefreshTokenSession.session_digest))
    )
    result = await db.execute(statement)
    live = result.scalar_one_or_none() is not None
    if live:
        await _prune_expired_sessions(db)
    return live


async def revoke_refresh_token(token: str, db: AsyncSession, settings: SettingsService) -> None:
    """Revoke a valid native login session and leave malformed cookies harmless."""
    from langflow.services.auth.utils import get_jwt_verification_key

    try:
        payload = jwt.decode(
            token,
            get_jwt_verification_key(settings),
            algorithms=[settings.auth_settings.ALGORITHM],
            # An expired ancestor may still have live descendants from a refresh
            # that overlapped expiry. Verify its signature before revoking them.
            options={"require": ["exp", "sub"], "verify_exp": False},
        )
        if payload.get("type") != "refresh":
            return
        digest = _session_digest(refresh_session_id(payload), payload["sub"])
        expires_at = max(
            datetime.fromtimestamp(float(payload["exp"]), timezone.utc),
            datetime.now(timezone.utc) + timedelta(seconds=settings.auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS),
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError, OverflowError):
        return

    statement = (
        update(RefreshTokenSession)
        .where(col(RefreshTokenSession.session_digest) == digest)
        .values(
            revoked=True,
            expires_at=case(
                (col(RefreshTokenSession.expires_at) < expires_at, expires_at),
                else_=col(RefreshTokenSession.expires_at),
            ),
        )
    )
    await db.execute(statement)
    await _prune_expired_sessions(db)


async def _prune_expired_sessions(db: AsyncSession) -> None:
    """Bound cleanup work per request without removing unexpired session revocations."""
    now = datetime.now(timezone.utc)
    expired = await db.exec(
        select(RefreshTokenSession.session_digest)
        .where(col(RefreshTokenSession.expires_at) <= now)
        .order_by(col(RefreshTokenSession.expires_at))
        .limit(_EXPIRED_SESSION_BATCH_SIZE)
    )
    expired_digests = list(expired)
    if expired_digests:
        await db.execute(
            delete(RefreshTokenSession).where(
                col(RefreshTokenSession.session_digest).in_(expired_digests),
                col(RefreshTokenSession.expires_at) <= now,
            )
        )
