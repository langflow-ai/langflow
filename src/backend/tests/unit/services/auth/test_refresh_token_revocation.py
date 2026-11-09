"""Native logout revocations survive sessions and retain independent logins."""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from langflow.services.auth.refresh_tokens import revoke_refresh_token
from langflow.services.auth.service import AuthService
from langflow.services.database.models.auth.refresh_token import RefreshTokenSession
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
        assert first_claims["sid"] != second_claims["sid"]
        await revoke_refresh_token(first["refresh_token"], db, settings)
        await revoke_refresh_token(first["refresh_token"], db, settings)
        await db.commit()

    await engine.dispose()
    restarted = AuthService(settings)
    async with AsyncSession(engine) as db:
        with pytest.raises(HTTPException) as exc:
            await restarted.create_refresh_token(first["refresh_token"], db)
        assert exc.value.status_code == 401
        rows = (await db.exec(select(RefreshTokenSession))).all()
        assert len(rows) == 1
        assert rows[0].session_digest == hashlib.sha256(f"{user.id}:{first_claims['sid']}".encode()).hexdigest()
        assert rows[0].revoked is True
        assert first["refresh_token"] not in str(rows[0].model_dump())
        assert (await restarted.create_refresh_token(second["refresh_token"], db))["access_token"]


@pytest.mark.parametrize("has_jti", [False, True])
async def test_legacy_refresh_tokens_require_fresh_login(token_store, has_jti):
    """A token without a session identifier cannot create an untracked login session."""
    engine, settings, user = token_store
    service = AuthService(settings)
    claims = {"sub": str(user.id), "type": "refresh"}
    if has_jti:
        claims["jti"] = str(uuid4())
    token = service.create_token(claims, timedelta(minutes=5))
    async with AsyncSession(engine) as db:
        with pytest.raises(HTTPException) as exc:
            await service.create_refresh_token(token, db)
        assert exc.value.status_code == 401
        await revoke_refresh_token(token, db, settings)
        await revoke_refresh_token(token, db, settings)
        await db.commit()
        assert not (await db.exec(select(RefreshTokenSession))).all()
        fresh = (await service.create_user_tokens(user.id, db))["refresh_token"]
        assert (await service.create_refresh_token(fresh, db))["access_token"]


@pytest.mark.parametrize("session_id", [None, "", 0, [], {}, "x" * 129])
async def test_malformed_session_identifiers_fail_closed(token_store, session_id):
    """Even a signed token needs a usable session identifier for native refresh."""
    engine, settings, user = token_store
    service = AuthService(settings)
    token = service.create_token({"sub": str(user.id), "type": "refresh", "sid": session_id}, timedelta(minutes=5))
    async with AsyncSession(engine) as db:
        with pytest.raises(HTTPException) as exc:
            await service.create_refresh_token(token, db)
        assert exc.value.status_code == 401
        await revoke_refresh_token(token, db, settings)
        await db.commit()
        assert not (await db.exec(select(RefreshTokenSession))).all()


@pytest.mark.parametrize(
    "case",
    ["malformed", "access", "expired", "wrong-signature", "missing-exp", "invalid-sub", "invalid-session"],
)
async def test_invalid_cookies_do_not_create_revocation_records(token_store, case):
    """Logout ignores invalid native cookies without trusting their claims."""
    engine, settings, user = token_store
    claims = {
        "sub": str(user.id),
        "type": "refresh",
        "sid": str(uuid4()),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
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
        elif case == "invalid-session":
            claims["sid"] = ["not-a-session-id"]
        token = jwt.encode(claims, key, algorithm=settings.auth_settings.ALGORITHM)
    async with AsyncSession(engine) as db:
        await revoke_refresh_token(token, db, settings)
        await db.commit()
        assert not (await db.exec(select(RefreshTokenSession))).all()


async def test_logout_cleanup_is_bounded_and_preserves_live_revocations(token_store):
    """Only a bounded batch of expired digests is removed during logout."""
    engine, settings, user = token_store
    service = AuthService(settings)
    now = datetime.now(timezone.utc)
    async with AsyncSession(engine) as db:
        db.add_all(
            [
                RefreshTokenSession(session_digest=f"{number:064x}", expires_at=now - timedelta(minutes=1))
                for number in range(201)
            ]
        )
        future_digest = "f" * 64
        db.add(RefreshTokenSession(session_digest=future_digest, expires_at=now + timedelta(days=1), revoked=True))
        await db.commit()
        token = (await service.create_user_tokens(user.id, db))["refresh_token"]
        await revoke_refresh_token(token, db, settings)
        await db.commit()
        rows = (await db.exec(select(RefreshTokenSession))).all()
        assert len(rows) == 103
        assert await db.get(RefreshTokenSession, future_digest) is not None


async def test_revocation_storage_failure_cannot_issue_tokens(token_store):
    """Unavailable revocation storage stops both logout and refresh."""
    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        token = (await service.create_user_tokens(user.id, db))["refresh_token"]
        await db.execute(text("DROP TABLE refresh_token_session"))
        await db.commit()
    async with AsyncSession(engine) as db:
        with pytest.raises(OperationalError):
            await revoke_refresh_token(token, db, settings)
    async with AsyncSession(engine) as db:
        with pytest.raises(OperationalError):
            await service.create_refresh_token(token, db)


@pytest.mark.parametrize("revoke_variant", [False, True])
async def test_equivalent_token_encodings_share_revocation(token_store, revoke_variant):
    """Equivalent verified JWT representations identify the same revoked credential."""
    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        original = (await service.create_user_tokens(user.id, db))["refresh_token"]
        equivalent = original + "="
        assert equivalent != original
        verification = {
            "key": settings.auth_settings.SECRET_KEY.get_secret_value(),
            "algorithms": [settings.auth_settings.ALGORITHM],
        }
        assert jwt.decode(original, **verification) == jwt.decode(equivalent, **verification)
        await revoke_refresh_token(equivalent if revoke_variant else original, db, settings)
        await db.commit()
        for token in (original, equivalent):
            with pytest.raises(HTTPException) as exc:
                await service.create_refresh_token(token, db)
            assert exc.value.status_code == 401
        await revoke_refresh_token(original if revoke_variant else equivalent, db, settings)
        await db.commit()
        assert len((await db.exec(select(RefreshTokenSession))).all()) == 1


@pytest.mark.parametrize("logout_original", [False, True])
async def test_rotation_then_logout_rejects_old_and_current_tokens(token_store, logout_original):
    """Logout revokes every generation and sibling while independent logins remain valid."""
    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        independent = (await service.create_user_tokens(user.id, db))["refresh_token"]
        original = (await service.create_user_tokens(user.id, db))["refresh_token"]
        replacement = (await service.create_refresh_token(original, db))["refresh_token"]
        sibling = (await service.create_refresh_token(original + "=", db))["refresh_token"]
        descendant = (await service.create_refresh_token(replacement, db))["refresh_token"]
        for token in (replacement, sibling, descendant):
            assert (
                jwt.decode(token, options={"verify_signature": False})["sid"]
                == jwt.decode(replacement, options={"verify_signature": False})["sid"]
            )
        await db.commit()
        await revoke_refresh_token(original if logout_original else descendant, db, settings)
        await db.commit()
        for token in (original, original + "=", replacement, replacement + "=", sibling, descendant):
            with pytest.raises(HTTPException) as exc:
                await service.create_refresh_token(token, db)
            assert exc.value.status_code == 401
        assert (await service.create_refresh_token(independent, db))["access_token"]


async def test_concurrent_refresh_requests_keep_the_same_session(token_store):
    """Browser tabs and API clients can exchange the same token concurrently."""
    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        token = (await service.create_user_tokens(user.id, db))["refresh_token"]

    async def exchange(candidate):
        async with AsyncSession(engine) as db:
            tokens = await service.create_refresh_token(candidate, db)
            await db.commit()
            return tokens["refresh_token"]

    first, second = await asyncio.gather(exchange(token), exchange(token + "="))
    assert first != second
    async with AsyncSession(engine) as db:
        rows = (await db.exec(select(RefreshTokenSession))).all()
        assert len(rows) == 1
        assert rows[0].revoked is False
        await revoke_refresh_token(first, db, settings)
        await db.commit()
        for candidate in (token, first, second):
            with pytest.raises(HTTPException) as exc:
                await service.create_refresh_token(candidate, db)
            assert exc.value.status_code == 401


async def test_failed_rotation_leaves_session_retryable(token_store, monkeypatch):
    """Failure to issue replacement tokens leaves the original exchange retryable."""
    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        token = (await service.create_user_tokens(user.id, db))["refresh_token"]
    async with AsyncSession(engine) as db:
        with monkeypatch.context() as patch:
            patch.setattr(service, "_create_session_tokens", Mock(side_effect=RuntimeError("issuance failed")))
            with pytest.raises(RuntimeError, match="issuance failed"):
                await service.create_refresh_token(token, db)
            await db.rollback()
    async with AsyncSession(engine) as db:
        assert not (await db.exec(select(RefreshTokenSession))).all()
        assert (await service.create_refresh_token(token, db))["access_token"]


async def test_expired_ancestor_logout_revokes_still_live_descendants(token_store):
    """An expired cookie cannot miss a replacement issued by an overlapping refresh."""
    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        original = (await service.create_user_tokens(user.id, db))["refresh_token"]
        descendant = (await service.create_refresh_token(original, db))["refresh_token"]
        claims = jwt.decode(original, options={"verify_signature": False})
        expired_ancestor = service.create_token(
            {"sub": str(user.id), "type": "refresh", "sid": claims["sid"]}, timedelta(seconds=-1)
        )
        await revoke_refresh_token(expired_ancestor, db, settings)
        await db.commit()
        with pytest.raises(HTTPException) as exc:
            await service.create_refresh_token(descendant, db)
        assert exc.value.status_code == 401


async def test_logout_wins_over_refresh_already_preparing_tokens(token_store, monkeypatch):
    """A refresh admitted before logout cannot revive its session after logout commits."""
    import langflow.services.auth.service as auth_module

    engine, settings, user = token_store
    service = AuthService(settings)
    async with AsyncSession(engine) as db:
        original = (await service.create_user_tokens(user.id, db))["refresh_token"]
    prepared = asyncio.Event()
    continue_refresh = asyncio.Event()
    register = auth_module.register_refresh_session

    async def paused_register(*args):
        prepared.set()
        await asyncio.wait_for(continue_refresh.wait(), timeout=5)
        return await register(*args)

    monkeypatch.setattr(auth_module, "register_refresh_session", paused_register)

    async def exchange():
        async with AsyncSession(engine) as db:
            with pytest.raises(HTTPException) as exc:
                await service.create_refresh_token(original, db)
            assert exc.value.status_code == 401

    pending = asyncio.create_task(exchange())
    try:
        await asyncio.wait_for(prepared.wait(), timeout=5)
        async with AsyncSession(engine) as db:
            await revoke_refresh_token(original, db, settings)
            await db.commit()
    finally:
        continue_refresh.set()
        await pending


@pytest.mark.parametrize(("initial_ttl", "replacement_ttl"), [(600, 3600), (3600, 600)])
async def test_logout_retains_revocation_until_longest_family_expiry(
    token_store, monkeypatch, initial_ttl, replacement_ttl
):
    """A TTL change cannot delete a session tombstone while an older generation remains usable."""
    import langflow.services.auth.refresh_tokens as refresh_module

    engine, settings, user = token_store
    service = AuthService(settings)
    monkeypatch.setattr(settings.auth_settings, "REFRESH_TOKEN_EXPIRE_SECONDS", initial_ttl)
    async with AsyncSession(engine) as db:
        original = (await service.create_user_tokens(user.id, db))["refresh_token"]
        monkeypatch.setattr(settings.auth_settings, "REFRESH_TOKEN_EXPIRE_SECONDS", replacement_ttl)
        replacement = (await service.create_refresh_token(original, db))["refresh_token"]
        await revoke_refresh_token(replacement, db, settings)
        await db.commit()
        row = (await db.exec(select(RefreshTokenSession))).one()
        longest_expiry = max(
            jwt.decode(token, options={"verify_signature": False})["exp"] for token in (original, replacement)
        )
        assert row.expires_at.replace(tzinfo=timezone.utc).timestamp() >= longest_expiry

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return (datetime.now(timezone.utc) + timedelta(seconds=1200)).astimezone(tz)

    monkeypatch.setattr(refresh_module, "datetime", Later)
    async with AsyncSession(engine) as db:
        unrelated = (await service.create_user_tokens(user.id, db))["refresh_token"]
        await revoke_refresh_token(unrelated, db, settings)
        await db.commit()
        for token in (original, replacement):
            with pytest.raises(HTTPException) as exc:
                await service.create_refresh_token(token, db)
            assert exc.value.status_code == 401
