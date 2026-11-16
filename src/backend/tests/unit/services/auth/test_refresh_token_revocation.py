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
from sqlalchemy import delete, text, update
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
        rows = (await db.exec(select(RefreshTokenSession).where(RefreshTokenSession.revoked))).all()
        assert len(rows) == 1
        assert rows[0].session_digest == hashlib.sha256(f"{user.id}:{first_claims['sid']}".encode()).hexdigest()
        assert rows[0].revoked is True
        assert rows[0].user_id == user.id
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
                RefreshTokenSession(
                    session_digest=f"{number:064x}", user_id=user.id, expires_at=now - timedelta(minutes=1)
                )
                for number in range(201)
            ]
        )
        future_digest = "f" * 64
        db.add(
            RefreshTokenSession(
                session_digest=future_digest, user_id=user.id, expires_at=now + timedelta(days=1), revoked=True
            )
        )
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
    async with AsyncSession(engine) as db:
        with pytest.raises(OperationalError):
            await service.create_user_tokens(user.id, db)


async def test_builder_erasure_batches_sessions_without_removing_other_users(token_store):
    from langflow.services.data_subjects.builder_account_steps import erase_refresh_sessions
    from langflow.services.data_subjects.context import EraseContext

    engine, _settings, user = token_store
    other_id = uuid4()
    other = User(id=other_id, username="other-session-owner", password="unused", is_active=True)  # noqa: S106
    async with AsyncSession(engine) as db:
        db.add(other)
        await db.flush()
        db.add_all(
            RefreshTokenSession(
                session_digest=f"{number:064x}",
                user_id=user.id if number < 501 else other_id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                revoked=bool(number % 2),
            )
            for number in range(502)
        )
        await db.commit()
        context = EraseContext(request_id=uuid4(), subject_user_id=user.id)
        assert await erase_refresh_sessions(db, context) == 500
        assert await erase_refresh_sessions(db, context) == 1
        assert await erase_refresh_sessions(db, context) == 0
        await db.commit()
        remaining = (await db.exec(select(RefreshTokenSession))).one()
        assert remaining.user_id == other_id


async def test_new_user_session_uses_the_login_transaction(token_store):
    """JIT users may be flushed but uncommitted when the login issues tokens."""
    engine, settings, _user = token_store
    service = AuthService(settings)
    user_id = uuid4()
    async with AsyncSession(engine) as db:
        pending_user = User(
            id=user_id,
            username="pending-login-user",
            password="unused",  # noqa: S106  # pragma: allowlist secret
            is_active=True,
        )
        db.add(pending_user)
        await db.flush()
        tokens = await asyncio.wait_for(service.create_user_tokens(user_id, db, update_last_login=True), timeout=5)
        assert tokens["refresh_token"]
        session = (await db.exec(select(RefreshTokenSession).where(RefreshTokenSession.user_id == user_id))).one()
        assert session.revoked is False
        assert pending_user.last_login_at is not None
        await db.rollback()

    async with AsyncSession(engine) as db:
        assert await db.get(User, user_id) is None
        assert not (await db.exec(select(RefreshTokenSession).where(RefreshTokenSession.user_id == user_id))).all()


@pytest.mark.parametrize("delete_owner", [False, True])
async def test_paused_login_cannot_recreate_sessions_after_builder_erasure(token_store, monkeypatch, delete_owner):
    import langflow.services.auth.service as auth_module
    from langflow.services.data_subjects.builder_account_steps import erase_refresh_sessions
    from langflow.services.data_subjects.context import EraseContext

    engine, settings, user = token_store
    service = AuthService(settings)
    user_id = user.id
    async with AsyncSession(engine) as db:
        await service.create_user_tokens(user_id, db)
        await db.commit()
    ready, resume = asyncio.Event(), asyncio.Event()
    create_session = auth_module.create_refresh_session

    async def paused_create(*args):
        ready.set()
        await asyncio.wait_for(resume.wait(), timeout=5)
        return await create_session(*args)

    monkeypatch.setattr(auth_module, "create_refresh_session", paused_create)

    async def login():
        async with AsyncSession(engine) as db:
            with pytest.raises(HTTPException) as exc:
                await service.create_user_tokens(user_id, db, update_last_login=True)
            assert exc.value.status_code == 401
            await db.commit()

    pending = asyncio.create_task(login())
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        async with AsyncSession(engine) as db:
            await db.exec(update(User).where(User.id == user_id).values(is_active=False))
            await db.commit()
            context = EraseContext(request_id=uuid4(), subject_user_id=user_id)
            assert await erase_refresh_sessions(db, context) == 1
            assert await erase_refresh_sessions(db, context) == 0
            if delete_owner:
                await db.exec(delete(User).where(User.id == user_id))
            await db.commit()
    finally:
        resume.set()
        await pending

    async with AsyncSession(engine) as db:
        assert not (await db.exec(select(RefreshTokenSession))).all()
        owner = await db.get(User, user_id)
        if delete_owner:
            assert owner is None
        else:
            assert owner.is_active is False


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
        await db.commit()

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
        await db.commit()
    async with AsyncSession(engine) as db:
        with monkeypatch.context() as patch:
            patch.setattr(service, "_create_session_tokens", Mock(side_effect=RuntimeError("issuance failed")))
            with pytest.raises(RuntimeError, match="issuance failed"):
                await service.create_refresh_token(token, db)
            await db.rollback()
    async with AsyncSession(engine) as db:
        rows = (await db.exec(select(RefreshTokenSession))).all()
        assert len(rows) == 1
        assert rows[0].revoked is False
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
        await db.commit()
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


@pytest.mark.parametrize("prune_tombstone", [False, True])
async def test_first_refresh_cannot_revive_session_after_expired_logout(token_store, monkeypatch, prune_tombstone):
    """A paused first refresh cannot recreate a logged-out session after expiry and cleanup."""
    import langflow.services.auth.refresh_tokens as refresh_module
    import langflow.services.auth.service as auth_module

    engine, settings, user = token_store
    service = AuthService(settings)
    monkeypatch.setattr(settings.auth_settings, "REFRESH_TOKEN_EXPIRE_SECONDS", 60)
    async with AsyncSession(engine) as db:
        original = (await service.create_user_tokens(user.id, db))["refresh_token"]
        await db.commit()
    claims = jwt.decode(original, options={"verify_signature": False})
    digest = hashlib.sha256(f"{user.id}:{claims['sid']}".encode()).hexdigest()
    prepared = asyncio.Event()
    continue_refresh = asyncio.Event()
    register = auth_module.register_refresh_session
    issue_tokens = service._create_session_tokens
    minted_tokens = []

    def capture_tokens(*args):
        tokens = issue_tokens(*args)
        minted_tokens.append(tokens["refresh_token"])
        return tokens

    async def paused_register(*args):
        prepared.set()
        await asyncio.wait_for(continue_refresh.wait(), timeout=5)
        return await register(*args)

    monkeypatch.setattr(service, "_create_session_tokens", capture_tokens)
    monkeypatch.setattr(auth_module, "register_refresh_session", paused_register)
    monkeypatch.setattr(settings.auth_settings, "REFRESH_TOKEN_EXPIRE_SECONDS", 3600)

    async def exchange():
        async with AsyncSession(engine) as db:
            with pytest.raises(HTTPException) as exc:
                await service.create_refresh_token(original, db)
            assert exc.value.status_code == 401

    pending = asyncio.create_task(exchange())
    try:
        await asyncio.wait_for(prepared.wait(), timeout=5)
        logout_time = datetime.fromtimestamp(claims["exp"] + 1, timezone.utc)
        clock_time = logout_time

        class ControlledClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return clock_time.astimezone(tz)

        monkeypatch.setattr(refresh_module, "datetime", ControlledClock)
        # The pending replacement used a longer TTL than the logout request.
        monkeypatch.setattr(settings.auth_settings, "REFRESH_TOKEN_EXPIRE_SECONDS", 600)
        async with AsyncSession(engine) as db:
            await revoke_refresh_token(original, db, settings)
            await db.commit()
            row = await db.get(RefreshTokenSession, digest)
            assert row.revoked is True
            retained_until = row.expires_at.replace(tzinfo=timezone.utc)
            assert retained_until >= logout_time + timedelta(seconds=600)

        if prune_tombstone:
            clock_time = retained_until + timedelta(seconds=1)
            monkeypatch.setattr(settings.auth_settings, "REFRESH_TOKEN_EXPIRE_SECONDS", 7200)
            monkeypatch.setattr(auth_module, "register_refresh_session", register)
            async with AsyncSession(engine) as db:
                unrelated = (await service.create_user_tokens(user.id, db))["refresh_token"]
                await db.commit()
                # Another live session triggers the real bounded cleanup query.
                assert (await service.create_refresh_token(unrelated, db))["access_token"]
                await db.commit()
                assert await db.get(RefreshTokenSession, digest) is None
    finally:
        continue_refresh.set()
        await pending

    monkeypatch.setattr(auth_module, "register_refresh_session", register)
    async with AsyncSession(engine) as db:
        # The replacement is cryptographically valid but its session stays revoked or absent.
        with pytest.raises(HTTPException) as exc:
            await service.create_refresh_token(minted_tokens[0], db)
        assert exc.value.status_code == 401


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
