from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    create_deployment,
    delete_deployment_by_id,
    delete_deployment_by_resource_key,
    get_deployment,
    get_deployment_by_resource_key,
    list_deployments_page,
    update_deployment,
)
from sqlalchemy.exc import IntegrityError

DEPLOYMENT_CLASS = "langflow.services.database.models.deployment.crud.Deployment"


def _make_db() -> AsyncMock:
    """Create a mock AsyncSession with common async methods."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


# --- create_deployment ---


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
async def test_create_deployment_empty_resource_key_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="resource_key must not be empty"):
        await create_deployment(
            db,
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="   ",
            name="my-deploy",
        )


@pytest.mark.asyncio
async def test_create_deployment_empty_name_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="name must not be empty"):
        await create_deployment(
            db,
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="rk-1",
            name="",
        )


@pytest.mark.asyncio
async def test_create_deployment_integrity_error_raises_value_error():
    db = _make_db()
    db.flush.side_effect = IntegrityError("dup", params=None, orig=Exception())

    with (
        patch(DEPLOYMENT_CLASS),
        patch("langflow.services.database.models.deployment.crud.logger") as mock_logger,
    ):
        mock_logger.aerror = AsyncMock()
        with pytest.raises(ValueError, match="Deployment conflicts with an existing record"):
            await create_deployment(
                db,
                user_id=uuid4(),
                project_id=uuid4(),
                deployment_provider_account_id=uuid4(),
                resource_key="rk-1",
                name="my-deploy",
            )

    db.rollback.assert_awaited_once()


# --- get_deployment ---


@pytest.mark.asyncio
async def test_get_deployment_invalid_uuid_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="deployment_id is not a valid UUID"):
        await get_deployment(db, user_id=uuid4(), deployment_id="not-a-uuid")


@pytest.mark.asyncio
async def test_get_deployment_found():
    db = _make_db()
    mock_deployment = MagicMock()
    mock_result = MagicMock()
    mock_result.first.return_value = mock_deployment
    db.exec.return_value = mock_result

    result = await get_deployment(db, user_id=uuid4(), deployment_id=uuid4())

    assert result is mock_deployment


@pytest.mark.asyncio
async def test_get_deployment_not_found():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    db.exec.return_value = mock_result

    result = await get_deployment(db, user_id=uuid4(), deployment_id=uuid4())

    assert result is None


# --- get_deployment_by_resource_key ---


@pytest.mark.asyncio
async def test_get_deployment_by_resource_key_found():
    db = _make_db()
    mock_deployment = MagicMock()
    mock_result = MagicMock()
    mock_result.first.return_value = mock_deployment
    db.exec.return_value = mock_result

    result = await get_deployment_by_resource_key(
        db,
        user_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        resource_key="rk-1",
    )

    assert result is mock_deployment


@pytest.mark.asyncio
async def test_get_deployment_by_resource_key_not_found():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    db.exec.return_value = mock_result

    result = await get_deployment_by_resource_key(
        db,
        user_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        resource_key="nonexistent",
    )

    assert result is None


# --- list_deployments_page ---


@pytest.mark.asyncio
async def test_list_deployments_page_negative_offset_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="offset must be greater than or equal to 0"):
        await list_deployments_page(
            db,
            user_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            offset=-1,
            limit=10,
        )


@pytest.mark.asyncio
async def test_list_deployments_page_zero_limit_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="limit must be greater than 0"):
        await list_deployments_page(
            db,
            user_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            offset=0,
            limit=0,
        )


@pytest.mark.asyncio
async def test_list_deployments_page_negative_limit_raises():
    db = _make_db()

    with pytest.raises(ValueError, match="limit must be greater than 0"):
        await list_deployments_page(
            db,
            user_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            offset=0,
            limit=-5,
        )


@pytest.mark.asyncio
async def test_list_deployments_page_returns_list():
    db = _make_db()
    mock_items = [MagicMock(), MagicMock()]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_items
    db.exec.return_value = mock_result

    result = await list_deployments_page(
        db,
        user_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        offset=0,
        limit=10,
    )

    assert result == mock_items
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_deployments_page_empty():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    db.exec.return_value = mock_result

    result = await list_deployments_page(
        db,
        user_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        offset=0,
        limit=10,
    )

    assert result == []


# --- count_deployments_by_provider ---


@pytest.mark.asyncio
async def test_count_deployments_by_provider_returns_int():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.one.return_value = 5
    db.exec.return_value = mock_result

    result = await count_deployments_by_provider(
        db,
        user_id=uuid4(),
        deployment_provider_account_id=uuid4(),
    )

    assert result == 5


@pytest.mark.asyncio
async def test_count_deployments_by_provider_returns_zero():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.one.return_value = 0
    db.exec.return_value = mock_result

    result = await count_deployments_by_provider(
        db,
        user_id=uuid4(),
        deployment_provider_account_id=uuid4(),
    )

    assert result == 0


# --- delete_deployment_by_resource_key ---


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
async def test_delete_by_resource_key_none_rowcount_logs_error():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.rowcount = None
    db.exec.return_value = mock_result

    with patch("langflow.services.database.models.deployment.crud.logger") as mock_logger:
        mock_logger.aerror = AsyncMock()
        count = await delete_deployment_by_resource_key(
            db,
            user_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="rk-1",
        )

    assert count == 0
    mock_logger.aerror.assert_awaited_once()


# --- delete_deployment_by_id ---


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
async def test_delete_by_id_none_rowcount_logs_error():
    db = _make_db()
    mock_result = MagicMock()
    mock_result.rowcount = None
    db.exec.return_value = mock_result

    with patch("langflow.services.database.models.deployment.crud.logger") as mock_logger:
        mock_logger.aerror = AsyncMock()
        count = await delete_deployment_by_id(
            db,
            user_id=uuid4(),
            deployment_id=uuid4(),
        )

    assert count == 0
    mock_logger.aerror.assert_awaited_once()


# --- update_deployment ---


def _make_deployment(**overrides) -> MagicMock:
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "project_id": uuid4(),
        "deployment_provider_account_id": uuid4(),
        "resource_key": "rk-1",
        "name": "my-deploy",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.mark.asyncio
async def test_update_deployment_name():
    db = _make_db()
    deploy = _make_deployment()

    result = await update_deployment(db, deployment=deploy, name="new-name")

    assert result.name == "new-name"
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_deployment_project_id():
    db = _make_db()
    deploy = _make_deployment()
    new_pid = uuid4()

    result = await update_deployment(db, deployment=deploy, project_id=new_pid)

    assert result.project_id == new_pid
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_deployment_no_changes():
    db = _make_db()
    deploy = _make_deployment()
    original_name = deploy.name

    result = await update_deployment(db, deployment=deploy)

    assert result.name == original_name
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_deployment_empty_name_raises():
    db = _make_db()
    deploy = _make_deployment()

    with pytest.raises(ValueError, match="name must not be empty"):
        await update_deployment(db, deployment=deploy, name="   ")


@pytest.mark.asyncio
async def test_update_deployment_strips_whitespace():
    db = _make_db()
    deploy = _make_deployment()

    await update_deployment(db, deployment=deploy, name="  new-name  ")

    assert deploy.name == "new-name"


@pytest.mark.asyncio
async def test_update_deployment_integrity_error_raises_value_error():
    db = _make_db()
    db.flush.side_effect = IntegrityError("dup", params=None, orig=Exception())
    deploy = _make_deployment()

    with patch("langflow.services.database.models.deployment.crud.logger") as mock_logger:
        mock_logger.aerror = AsyncMock()
        with pytest.raises(ValueError, match="conflicts with an existing record"):
            await update_deployment(db, deployment=deploy, name="duplicate-name")

    db.rollback.assert_awaited_once()
