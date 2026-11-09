"""Native logout revocations survive sessions and retain independent logins."""

import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from langflow.services.auth.refresh_tokens import revoke_refresh_token
from langflow.services.auth.service import AuthService
from langflow.services.database.models.auth.refresh_token import RevokedRefreshToken
from langflow.services.database.models.user.model import User
from lfx.services.settings.auth import AuthSettings
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def token_store(tmp_path):
    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr("test-refresh-revocation-signing-key")  # pragma: allowlist secret
    settings.AUTO_LOGIN = False
    service_settings = SimpleNamespace(auth_settings=settings, settings=SimpleNamespace(config_dir=str(tmp_path)))
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'revocations.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    user = User(id=uuid4(), username="revocation-user", password="unused", is_active=True)  # noqa: S106 - fixture hash
    async with AsyncSession(engine, expire_on_commit=False) as db:
        db.add(user)
        await db.commit()
    yield engine, service_settings, user
    await engine.dispose()


async def test_revocation_survives_new_service_and_database_session(token_store):
    """A committed digest stops replay while another login remains usable."""
    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        first = await service.create_user_tokens(user.id, db)
        second = await service.create_user_tokens(user.id, db)
        assert first["refresh_token"] != second["refresh_token"]
        first_claims = jwt.decode(first["refresh_token"], options={"verify_signature": False})
        second_claims = jwt.decode(second["refresh_token"], options={"verify_signature": False})
        assert first_claims["jti"] != second_claims["jti"]
        await revoke_refresh_token(first["refresh_token"], db, settings)
        await revoke_refresh_token(first["refresh_token"], db, settings)
        await db.commit()

    await engine.dispose()
    restarted = AuthService(settings)
    async with AsyncSession(engine) as db:
        with pytest.raises(HTTPException) as exc:
            await restarted.create_refresh_token(first["refresh_token"], db)
        assert exc.value.status_code == 401
        assert (await restarted.create_refresh_token(second["refresh_token"], db))["access_token"]
        rows = (await db.exec(select(RevokedRefreshToken))).all()
        assert len(rows) == 1
        assert rows[0].token_digest == hashlib.sha256(first["refresh_token"].encode()).hexdigest()
        assert first["refresh_token"] not in str(rows[0].model_dump())


async def test_legacy_refresh_token_without_jti_can_be_revoked(token_store):
    """Tokens issued before token IDs were added still honor logout."""
    engine, settings, user = token_store
    service = AuthService(settings)
    token = service.create_token({"sub": str(user.id), "type": "refresh"}, timedelta(minutes=5))
    async with AsyncSession(engine) as db:
        assert (await service.create_refresh_token(token, db))["access_token"]
        await revoke_refresh_token(token, db, settings)
        await db.commit()
        with pytest.raises(HTTPException) as exc:
            await service.create_refresh_token(token, db)
        assert exc.value.status_code == 401


@pytest.mark.parametrize("case", ["malformed", "access", "expired", "wrong-signature", "missing-exp", "invalid-sub"])
async def test_invalid_cookies_do_not_create_revocation_records(token_store, case):
    """Logout ignores invalid native cookies without trusting their claims."""
    engine, settings, user = token_store
    claims = {"sub": str(user.id), "type": "refresh", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    key = settings.auth_settings.SECRET_KEY.get_secret_value()
    if case == "malformed":
        token = "invalid-cookie"  # noqa: S105 - malformed credential fixture
    else:
        if case == "access":
            claims["type"] = "access"
        elif case == "expired":
            claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        elif case == "wrong-signature":
            key = "untrusted-refresh-token-signing-key-for-tests"  # pragma: allowlist secret
        elif case == "missing-exp":
            del claims["exp"]
        elif case == "invalid-sub":
            claims["sub"] = "not-a-user-id"
        token = jwt.encode(claims, key, algorithm=settings.auth_settings.ALGORITHM)
    async with AsyncSession(engine) as db:
        await revoke_refresh_token(token, db, settings)
        await db.commit()
        assert not (await db.exec(select(RevokedRefreshToken))).all()


async def test_logout_cleanup_is_bounded_and_preserves_live_revocations(token_store):
    """Only a bounded batch of expired digests is removed during logout."""
    engine, settings, user = token_store
    service = AuthService(settings)
    now = datetime.now(timezone.utc)
    async with AsyncSession(engine) as db:
        db.add_all(
            [
                RevokedRefreshToken(token_digest=f"{number:064x}", expires_at=now - timedelta(minutes=1))
                for number in range(201)
            ]
        )
        future_digest = "f" * 64
        db.add(RevokedRefreshToken(token_digest=future_digest, expires_at=now + timedelta(days=1)))
        await db.commit()
        token = (await service.create_user_tokens(user.id, db))["refresh_token"]
        await revoke_refresh_token(token, db, settings)
        await db.commit()
        rows = (await db.exec(select(RevokedRefreshToken))).all()
        assert len(rows) == 103
        assert await db.get(RevokedRefreshToken, future_digest) is not None


async def test_revocation_storage_failure_cannot_issue_tokens(token_store):
    """Unavailable revocation storage stops both logout and refresh."""
    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        token = (await service.create_user_tokens(user.id, db))["refresh_token"]
        await db.execute(text("DROP TABLE revoked_refresh_token"))
        await db.commit()
    async with AsyncSession(engine) as db:
        with pytest.raises(OperationalError):
            await revoke_refresh_token(token, db, settings)
    async with AsyncSession(engine) as db:
        with pytest.raises(OperationalError):
            await service.create_refresh_token(token, db)
