from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import InvalidToken
from langflow.services.database.models.deployment_provider_account.crud import (
    create_provider_account,
    delete_provider_account,
    get_provider_account_by_id,
    list_provider_accounts,
    update_provider_account,
)
from sqlalchemy.exc import IntegrityError

MODEL_CLASS = "langflow.services.database.models.deployment_provider_account.crud.DeploymentProviderAccount"
CRUD_AUTH = "langflow.services.database.models.deployment_provider_account.crud.auth_utils"
CRUD_LOGGER = "langflow.services.database.models.deployment_provider_account.crud.logger"


def _make_db() -> AsyncMock:
    """Create a mock AsyncSession with common async methods."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _make_provider_account(**overrides) -> MagicMock:
    """Create a mock provider account with sensible defaults for testing."""
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "provider_tenant_id": "tenant-1",
        "provider_key": "watsonx",
        "provider_url": "https://example.com",
        "api_key": "encrypted-key",  # pragma: allowlist secret
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# --- get_provider_account_by_id ---


@pytest.mark.asyncio
async def test_get_provider_account_by_id_found():
    db = _make_db()
    mock_acct = MagicMock()
    mock_result = MagicMock()
    mock_result.first.return_value = mock_acct
    db.exec.return_value = mock_result

    result = await get_provider_account_by_id(db, provider_id=uuid4(), user_id=uuid4())

    assert result is mock_acct


@pytest.mark.asyncio
async def test_get_provider_account_by_id_not_found():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    db.exec.return_value = mock_result

    result = await get_provider_account_by_id(db, provider_id=uuid4(), user_id=uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_provider_account_by_id_invalid_uuid_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="provider_id is not a valid UUID"):
        await get_provider_account_by_id(db, provider_id="not-a-uuid", user_id=uuid4())


# --- list_provider_accounts ---


@pytest.mark.asyncio
async def test_list_provider_accounts_returns_list():
    db = _make_db()
    mock_items = [MagicMock(), MagicMock()]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_items
    db.exec.return_value = mock_result

    result = await list_provider_accounts(db, user_id=uuid4())

    assert result == mock_items
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_provider_accounts_empty():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    db.exec.return_value = mock_result

    result = await list_provider_accounts(db, user_id=uuid4())

    assert result == []


# --- create_provider_account ---


@pytest.mark.asyncio
async def test_create_provider_account_success():
    db = _make_db()

    with (
        patch(CRUD_AUTH) as mock_auth,
        patch(MODEL_CLASS) as mock_cls,
    ):
        mock_auth.encrypt_api_key.return_value = "encrypted"
        mock_obj = MagicMock()
        mock_obj.provider_key = "watsonx"
        mock_obj.api_key = "encrypted"  # pragma: allowlist secret
        mock_cls.return_value = mock_obj

        result = await create_provider_account(
            db,
            user_id=uuid4(),
            provider_tenant_id="tenant-1",
            provider_key="watsonx",
            provider_url="https://example.com",
            api_key="test-token",  # pragma: allowlist secret
        )

    db.add.assert_called_once_with(mock_obj)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(mock_obj)
    assert result is mock_obj
    assert result.provider_key == "watsonx"
    assert result.api_key == "encrypted"  # pragma: allowlist secret
    mock_auth.encrypt_api_key.assert_called_once_with("test-token")


@pytest.mark.asyncio
async def test_create_provider_account_strips_whitespace():
    db = _make_db()

    with (
        patch(CRUD_AUTH) as mock_auth,
        patch(MODEL_CLASS) as mock_cls,
    ):
        mock_auth.encrypt_api_key.return_value = "encrypted"
        mock_cls.return_value = MagicMock()

        await create_provider_account(
            db,
            user_id=uuid4(),
            provider_tenant_id="  tenant-1  ",
            provider_key="  watsonx  ",
            provider_url="  https://example.com  ",
            api_key="  test-token  ",  # pragma: allowlist secret
        )

    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["provider_tenant_id"] == "tenant-1"
    assert call_kwargs["provider_key"] == "watsonx"
    assert call_kwargs["provider_url"] == "https://example.com"
    mock_auth.encrypt_api_key.assert_called_once_with("test-token")


@pytest.mark.asyncio
async def test_create_provider_account_none_tenant_id():
    db = _make_db()

    with (
        patch(CRUD_AUTH) as mock_auth,
        patch(MODEL_CLASS) as mock_cls,
    ):
        mock_auth.encrypt_api_key.return_value = "encrypted"
        mock_cls.return_value = MagicMock()

        await create_provider_account(
            db,
            user_id=uuid4(),
            provider_tenant_id=None,
            provider_key="watsonx",
            provider_url="https://example.com",
            api_key="test-token",  # pragma: allowlist secret
        )

    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["provider_tenant_id"] is None


@pytest.mark.asyncio
async def test_create_provider_account_blank_tenant_id_normalizes_to_none():
    db = _make_db()

    with (
        patch(CRUD_AUTH) as mock_auth,
        patch(MODEL_CLASS) as mock_cls,
    ):
        mock_auth.encrypt_api_key.return_value = "encrypted"
        mock_cls.return_value = MagicMock()

        await create_provider_account(
            db,
            user_id=uuid4(),
            provider_tenant_id="   ",
            provider_key="watsonx",
            provider_url="https://example.com",
            api_key="test-token",  # pragma: allowlist secret
        )

    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["provider_tenant_id"] is None


@pytest.mark.asyncio
async def test_create_provider_account_empty_provider_key_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="provider_key must not be empty"):
        await create_provider_account(
            db,
            user_id=uuid4(),
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
            provider_tenant_id=None,
            provider_key="watsonx",
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
            provider_tenant_id=None,
            provider_key="watsonx",
            provider_url="https://example.com",
            api_key="   ",  # pragma: allowlist secret
        )


@pytest.mark.asyncio
async def test_create_provider_account_integrity_error_raises_value_error():
    db = _make_db()
    db.flush.side_effect = IntegrityError("dup", params=None, orig=Exception())

    with (
        patch(CRUD_AUTH) as mock_auth,
        patch(MODEL_CLASS),
        patch(CRUD_LOGGER) as mock_logger,
    ):
        mock_auth.encrypt_api_key.return_value = "encrypted"
        mock_logger.aerror = AsyncMock()
        with pytest.raises(ValueError, match="Provider account already exists"):
            await create_provider_account(
                db,
                user_id=uuid4(),
                provider_tenant_id=None,
                provider_key="watsonx",
                provider_url="https://example.com",
                api_key="test-token",  # pragma: allowlist secret
            )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_provider_account_encryption_value_error():
    db = _make_db()

    with (
        patch(CRUD_AUTH) as mock_auth,
        patch(CRUD_LOGGER) as mock_logger,
    ):
        mock_auth.encrypt_api_key.side_effect = ValueError("bad key")
        mock_logger.aerror = AsyncMock()
        with pytest.raises(RuntimeError, match="Failed to encrypt API key"):
            await create_provider_account(
                db,
                user_id=uuid4(),
                provider_tenant_id=None,
                provider_key="watsonx",
                provider_url="https://example.com",
                api_key="test-token",  # pragma: allowlist secret
            )


@pytest.mark.asyncio
async def test_create_provider_account_encryption_invalid_token():
    db = _make_db()

    with (
        patch(CRUD_AUTH) as mock_auth,
        patch(CRUD_LOGGER) as mock_logger,
    ):
        mock_auth.encrypt_api_key.side_effect = InvalidToken()
        mock_logger.aerror = AsyncMock()
        with pytest.raises(RuntimeError, match="Failed to encrypt API key"):
            await create_provider_account(
                db,
                user_id=uuid4(),
                provider_tenant_id=None,
                provider_key="watsonx",
                provider_url="https://example.com",
                api_key="test-token",  # pragma: allowlist secret
            )


# --- update_provider_account ---


@pytest.mark.asyncio
async def test_update_provider_account_success():
    db = _make_db()
    acct = _make_provider_account()

    with patch(CRUD_AUTH) as mock_auth:
        mock_auth.encrypt_api_key.return_value = "new-encrypted"
        result = await update_provider_account(
            db,
            provider_account=acct,
            provider_tenant_id="new-tenant",
            provider_key="new-key",
            provider_url="https://new.example.com",
            api_key="updated-token",  # pragma: allowlist secret
        )

    assert result.provider_tenant_id == "new-tenant"
    assert result.provider_key == "new-key"
    assert result.provider_url == "https://new.example.com"
    assert result.api_key == "new-encrypted"  # pragma: allowlist secret
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_provider_account_no_changes():
    db = _make_db()
    acct = _make_provider_account()
    original_key = acct.provider_key

    result = await update_provider_account(db, provider_account=acct)

    assert result.provider_key == original_key
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_provider_account_set_tenant_to_none():
    db = _make_db()
    acct = _make_provider_account(provider_tenant_id="old-tenant")

    await update_provider_account(db, provider_account=acct, provider_tenant_id=None)

    assert acct.provider_tenant_id is None


@pytest.mark.asyncio
async def test_update_provider_account_empty_tenant_normalizes_to_none():
    db = _make_db()
    acct = _make_provider_account(provider_tenant_id="old-tenant")

    await update_provider_account(db, provider_account=acct, provider_tenant_id="   ")

    assert acct.provider_tenant_id is None


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


@pytest.mark.asyncio
async def test_update_provider_account_integrity_error_raises_value_error():
    db = _make_db()
    db.flush.side_effect = IntegrityError("dup", params=None, orig=Exception())
    acct = _make_provider_account()

    with patch(CRUD_LOGGER) as mock_logger:
        mock_logger.aerror = AsyncMock()
        with pytest.raises(ValueError, match="conflicts with an existing record"):
            await update_provider_account(db, provider_account=acct, provider_tenant_id="new-tenant")

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_provider_account_encryption_error():
    db = _make_db()
    acct = _make_provider_account()

    with (
        patch(CRUD_AUTH) as mock_auth,
        patch(CRUD_LOGGER) as mock_logger,
    ):
        mock_auth.encrypt_api_key.side_effect = ValueError("bad key")
        mock_logger.aerror = AsyncMock()
        with pytest.raises(RuntimeError, match="Failed to encrypt API key"):
            await update_provider_account(
                db,
                provider_account=acct,
                api_key="updated-token",  # pragma: allowlist secret
            )


# --- delete_provider_account ---


@pytest.mark.asyncio
async def test_delete_provider_account_success():
    db = _make_db()
    acct = _make_provider_account()

    await delete_provider_account(db, provider_account=acct)

    db.delete.assert_awaited_once_with(acct)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_provider_account_integrity_error_raises_value_error():
    db = _make_db()
    db.flush.side_effect = IntegrityError("fk", params=None, orig=Exception())
    acct = _make_provider_account()

    with patch(CRUD_LOGGER) as mock_logger:
        mock_logger.aerror = AsyncMock()
        with pytest.raises(ValueError, match="Failed to delete provider account"):
            await delete_provider_account(db, provider_account=acct)

    db.rollback.assert_awaited_once()
