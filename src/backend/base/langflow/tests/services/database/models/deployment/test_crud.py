from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import (
    create_deployment,
    delete_deployment_by_id,
    delete_deployment_by_resource_key,
    get_deployment,
)
from sqlalchemy.exc import IntegrityError

DEPLOYMENT_CLASS = "langflow.services.database.models.deployment.crud.Deployment"


def _make_db() -> AsyncMock:
    """Create a mock AsyncSession with common async methods."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_create_deployment_success():
    db = _make_db()
    uid = uuid4()
    pid = uuid4()
    dpid = uuid4()

    with patch(DEPLOYMENT_CLASS) as mock_cls:
        mock_row = MagicMock()
        mock_row.resource_key = "rk-1"
        mock_row.name = "my-deploy"
        mock_cls.return_value = mock_row

        result = await create_deployment(
            db,
            user_id=uid,
            project_id=pid,
            deployment_provider_account_id=dpid,
            resource_key="rk-1",
            name="my-deploy",
        )

    db.add.assert_called_once_with(mock_row)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(mock_row)
    assert result is mock_row


@pytest.mark.asyncio
async def test_create_deployment_strips_whitespace():
    db = _make_db()

    with patch(DEPLOYMENT_CLASS) as mock_cls:
        mock_cls.return_value = MagicMock()

        await create_deployment(
            db,
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="  rk-1  ",
            name="  my-deploy  ",
        )

    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["resource_key"] == "rk-1"
    assert call_kwargs["name"] == "my-deploy"


@pytest.mark.asyncio
async def test_create_deployment_integrity_error_raises_value_error():
    db = _make_db()
    db.flush.side_effect = IntegrityError("dup", params=None, orig=Exception())

    with patch(DEPLOYMENT_CLASS), pytest.raises(ValueError, match="Deployment already exists"):
        await create_deployment(
            db,
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="rk-1",
            name="my-deploy",
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_deployment_invalid_uuid_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="deployment_id is not a valid UUID"):
        await get_deployment(db, user_id=uuid4(), deployment_id="not-a-uuid")


@pytest.mark.asyncio
async def test_delete_by_resource_key_returns_rowcount():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    db.exec.return_value = mock_result

    count = await delete_deployment_by_resource_key(
        db,
        user_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        resource_key="rk-1",
    )

    assert count == 1


@pytest.mark.asyncio
async def test_delete_by_resource_key_none_rowcount_logs_warning():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.rowcount = None
    db.exec.return_value = mock_result

    with patch("langflow.services.database.models.deployment.crud.logger") as mock_logger:
        mock_logger.awarning = AsyncMock()
        count = await delete_deployment_by_resource_key(
            db,
            user_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="rk-1",
        )

    assert count == 0
    mock_logger.awarning.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_by_id_returns_rowcount():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    db.exec.return_value = mock_result

    count = await delete_deployment_by_id(
        db,
        user_id=uuid4(),
        deployment_id=uuid4(),
    )

    assert count == 1


@pytest.mark.asyncio
async def test_delete_by_id_none_rowcount_logs_warning():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.rowcount = None
    db.exec.return_value = mock_result

    with patch("langflow.services.database.models.deployment.crud.logger") as mock_logger:
        mock_logger.awarning = AsyncMock()
        count = await delete_deployment_by_id(
            db,
            user_id=uuid4(),
            deployment_id=uuid4(),
        )

    assert count == 0
    mock_logger.awarning.assert_awaited_once()
