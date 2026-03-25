from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import InvalidToken
from langflow.services.database.models.deployment_provider_account.crud import (
    create_provider_account,
    delete_provider_account,
    update_provider_account,
)
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderKey,
)
from langflow.services.database.models.user.model import User
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

_ENCRYPT_TARGET = "langflow.services.database.models.deployment_provider_account.crud.auth_utils"
_CRUD_LOGGER = "langflow.services.database.models.deployment_provider_account.crud.logger"
_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Helpers for pure-validation (mock-based) tests
# ---------------------------------------------------------------------------


def _make_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _make_provider_account(**overrides) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "name": "staging",
        "provider_tenant_id": "tenant-1",
        "provider_key": "watsonx-orchestrate",
        "provider_url": "https://example.com",
        "api_key": "encrypted-key",  # pragma: allowlist secret
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Fixtures for real in-memory SQLite tests
# ---------------------------------------------------------------------------


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(name="db")
async def db_fixture(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await db_engine.dispose()


@pytest.fixture
async def user(db: AsyncSession) -> User:
    u = User(username="testuser", password=_TEST_PASSWORD, is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# Pure-validation tests (raise before touching DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_provider_account_by_id_invalid_uuid_raises():
    from langflow.services.database.models.deployment_provider_account.crud import get_provider_account_by_id

    db = _make_db()
    with pytest.raises(ValueError, match="provider_id is not a valid UUID"):
        await get_provider_account_by_id(db, provider_id="not-a-uuid", user_id=uuid4())


@pytest.mark.asyncio
async def test_create_provider_account_empty_name_raises():
    db = _make_db()
    with pytest.raises(ValueError, match="name must not be empty"):
        await create_provider_account(
            db,
            user_id=uuid4(),
            name="",
            provider_tenant_id=None,
            provider_key="watsonx-orchestrate",
            provider_url="https://example.com",
            api_key="test-token",  # pragma: allowlist secret
        )


@pytest.mark.asyncio
async def test_create_provider_account_whitespace_name_raises():
    db = _make_db()
    with pytest.raises(ValueError, match="name must not be empty"):
        await create_provider_account(
            db,
            user_id=uuid4(),
            name="   ",
            provider_tenant_id=None,
            provider_key="watsonx-orchestrate",
            provider_url="https://example.com",
            api_key="test-token",  # pragma: allowlist secret
        )


@pytest.mark.asyncio
async def test_create_provider_account_empty_provider_key_raises():
    db = _make_db()
    with pytest.raises(ValueError, match="provider_key must not be empty"):
        await create_provider_account(
            db,
            user_id=uuid4(),
            name="staging",
            provider_tenant_id=None,
            provider_key="   ",
            provider_url="https://example.com",
            api_key="test-token",  # pragma: allowlist secret
        )


@pytest.mark.asyncio
async def test_create_provider_account_empty_provider_url_raises():
    db = _make_db()
    with pytest.raises(ValueError, match="provider_url must not be empty"):
        await create_provider_account(
            db,
            user_id=uuid4(),
            name="staging",
            provider_tenant_id=None,
            provider_key="watsonx-orchestrate",
            provider_url="",
            api_key="test-token",  # pragma: allowlist secret
        )


@pytest.mark.asyncio
async def test_create_provider_account_empty_api_key_raises():
    db = _make_db()
    with pytest.raises(ValueError, match="api_key must not be empty"):
        await create_provider_account(
            db,
            user_id=uuid4(),
            name="staging",
            provider_tenant_id=None,
            provider_key="watsonx-orchestrate",
            provider_url="https://example.com",
            api_key="   ",  # pragma: allowlist secret
        )


@pytest.mark.asyncio
async def test_update_provider_account_empty_name_raises():
    db = _make_db()
    acct = _make_provider_account()
    with pytest.raises(ValueError, match="name must not be empty"):
        await update_provider_account(db, provider_account=acct, name="")


@pytest.mark.asyncio
async def test_update_provider_account_whitespace_name_raises():
    db = _make_db()
    acct = _make_provider_account()
    with pytest.raises(ValueError, match="name must not be empty"):
        await update_provider_account(db, provider_account=acct, name="   ")


@pytest.mark.asyncio
async def test_update_provider_account_empty_provider_key_raises():
    db = _make_db()
    acct = _make_provider_account()
    with pytest.raises(ValueError, match="provider_key must not be empty"):
        await update_provider_account(db, provider_account=acct, provider_key="")


@pytest.mark.asyncio
async def test_update_provider_account_whitespace_provider_key_raises():
    db = _make_db()
    acct = _make_provider_account()
    with pytest.raises(ValueError, match="provider_key must not be empty"):
        await update_provider_account(db, provider_account=acct, provider_key="   ")


@pytest.mark.asyncio
async def test_update_provider_account_empty_provider_url_raises():
    db = _make_db()
    acct = _make_provider_account()
    with pytest.raises(ValueError, match="provider_url must not be empty"):
        await update_provider_account(db, provider_account=acct, provider_url="")


@pytest.mark.asyncio
async def test_update_provider_account_empty_api_key_raises():
    db = _make_db()
    acct = _make_provider_account()
    with pytest.raises(ValueError, match="api_key must not be empty"):
        await update_provider_account(db, provider_account=acct, api_key="   ")  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Mock-based tests (encryption errors / hard-to-trigger edge cases)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_provider_account_encryption_value_error():
    db = _make_db()
    with (
        patch(_ENCRYPT_TARGET) as mock_auth,
        patch(_CRUD_LOGGER) as mock_logger,
    ):
        mock_auth.encrypt_api_key.side_effect = ValueError("bad key")
        mock_logger.aerror = AsyncMock()
        with pytest.raises(RuntimeError, match="Failed to encrypt API key"):
            await create_provider_account(
                db,
                user_id=uuid4(),
                name="staging",
                provider_tenant_id=None,
                provider_key="watsonx-orchestrate",
                provider_url="https://example.com",
                api_key="test-token",  # pragma: allowlist secret
            )


@pytest.mark.asyncio
async def test_create_provider_account_encryption_invalid_token():
    db = _make_db()
    with (
        patch(_ENCRYPT_TARGET) as mock_auth,
        patch(_CRUD_LOGGER) as mock_logger,
    ):
        mock_auth.encrypt_api_key.side_effect = InvalidToken()
        mock_logger.aerror = AsyncMock()
        with pytest.raises(RuntimeError, match="Failed to encrypt API key"):
            await create_provider_account(
                db,
                user_id=uuid4(),
                name="staging",
                provider_tenant_id=None,
                provider_key="watsonx-orchestrate",
                provider_url="https://example.com",
                api_key="test-token",  # pragma: allowlist secret
            )


@pytest.mark.asyncio
async def test_update_provider_account_encryption_error():
    db = _make_db()
    acct = _make_provider_account()
    with (
        patch(_ENCRYPT_TARGET) as mock_auth,
        patch(_CRUD_LOGGER) as mock_logger,
    ):
        mock_auth.encrypt_api_key.side_effect = ValueError("bad key")
        mock_logger.aerror = AsyncMock()
        with pytest.raises(RuntimeError, match="Failed to encrypt API key"):
            await update_provider_account(
                db,
                provider_account=acct,
                api_key="updated-token",  # pragma: allowlist secret
            )


@pytest.mark.asyncio
async def test_delete_provider_account_integrity_error_raises_value_error():
    db = _make_db()
    db.flush.side_effect = IntegrityError("fk", params=None, orig=Exception())
    acct = _make_provider_account()
    with patch(_CRUD_LOGGER) as mock_logger:
        mock_logger.aerror = AsyncMock()
        with pytest.raises(ValueError, match="Failed to delete provider account"):
            await delete_provider_account(db, provider_account=acct)
    db.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Real in-memory SQLite tests
# ---------------------------------------------------------------------------


async def _create_account(db, user, **overrides):
    defaults = {
        "user_id": user.id,
        "name": "staging",
        "provider_tenant_id": "tenant-1",
        "provider_key": "watsonx-orchestrate",
        "provider_url": "https://example.com",
        "api_key": "raw-token",  # pragma: allowlist secret
    }
    defaults.update(overrides)
    with patch(_ENCRYPT_TARGET) as mock_auth:
        mock_auth.encrypt_api_key.return_value = "enc-token"
        return await create_provider_account(db, **defaults)


@pytest.mark.asyncio
async def test_create_provider_account_strips_whitespace(db, user):
    acct = await _create_account(
        db,
        user,
        name="  staging  ",
        provider_tenant_id="  tenant-1  ",
        provider_key="  watsonx-orchestrate  ",
        provider_url="  https://example.com  ",
        api_key="  raw-token  ",  # pragma: allowlist secret
    )
    assert acct.name == "staging"
    assert acct.provider_tenant_id == "tenant-1"
    assert acct.provider_key == DeploymentProviderKey.WATSONX_ORCHESTRATE
    assert acct.provider_url == "https://example.com"


@pytest.mark.asyncio
async def test_create_provider_account_none_tenant_id(db, user):
    acct = await _create_account(db, user, provider_tenant_id=None)
    assert acct.provider_tenant_id is None


@pytest.mark.asyncio
async def test_create_provider_account_blank_tenant_id_normalizes_to_none(db, user):
    acct = await _create_account(db, user, provider_tenant_id="   ")
    assert acct.provider_tenant_id is None


@pytest.mark.asyncio
async def test_update_provider_account_set_tenant_to_none(db, user):
    acct = await _create_account(db, user, name="set-tenant-none", provider_tenant_id="old-tenant")
    updated = await update_provider_account(db, provider_account=acct, provider_tenant_id=None)
    assert updated.provider_tenant_id is None


@pytest.mark.asyncio
async def test_update_provider_account_empty_tenant_normalizes_to_none(db, user):
    acct = await _create_account(db, user, name="empty-tenant", provider_tenant_id="old-tenant")
    updated = await update_provider_account(db, provider_account=acct, provider_tenant_id="   ")
    assert updated.provider_tenant_id is None


@pytest.mark.asyncio
async def test_create_provider_account_duplicate_name_per_provider_raises(db, user):
    await _create_account(db, user, name="prod")
    with pytest.raises(ValueError, match="Provider account already exists"):
        await _create_account(db, user, name="prod", provider_url="https://other.example.com")


@pytest.mark.asyncio
async def test_create_provider_account_same_name_same_provider_allowed_for_different_users(db, user):
    other_user = User(username="otheruser", password=_TEST_PASSWORD, is_active=True)
    db.add(other_user)
    await db.commit()
    await db.refresh(other_user)

    first = await _create_account(db, user, name="prod", provider_url="https://example.com")
    second = await _create_account(db, other_user, name="prod", provider_url="https://example.com")

    assert first.name == "prod"
    assert second.name == "prod"
    assert first.user_id != second.user_id
