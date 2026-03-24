from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import (
    create_deployment,
    delete_deployment_by_id,
    delete_deployment_by_resource_key,
    deployment_name_exists,
    get_deployment,
    list_deployments_page,
    update_deployment,
)
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderKey,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.adapters.deployment.schema import DeploymentType
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Mock helper (for pure-validation tests that raise before touching DB)
# ---------------------------------------------------------------------------


def _make_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# In-memory SQLite fixtures
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


@pytest.fixture
async def folder(db: AsyncSession, user: User) -> Folder:
    f = Folder(name="test-project", user_id=user.id)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


@pytest.fixture
async def provider_account(db: AsyncSession, user: User) -> DeploymentProviderAccount:
    acct = DeploymentProviderAccount(
        user_id=user.id,
        provider_tenant_id="tenant-1",
        provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        provider_url="https://provider.example.com",
        api_key="encrypted-value",  # pragma: allowlist secret
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return acct


# ---------------------------------------------------------------------------
# Pure-validation tests (raise before any DB call)
# ---------------------------------------------------------------------------


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
            deployment_type=DeploymentType.AGENT,
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
            deployment_type=DeploymentType.AGENT,
        )


@pytest.mark.asyncio
async def test_get_deployment_invalid_uuid_raises():
    db = _make_db()
    with pytest.raises(ValueError, match="deployment_id is not a valid UUID"):
        await get_deployment(db, user_id=uuid4(), deployment_id="not-a-uuid")


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
async def test_update_deployment_empty_name_raises():
    db = _make_db()
    deploy = MagicMock()
    with pytest.raises(ValueError, match="name must not be empty"):
        await update_deployment(db, deployment=deploy, name="   ")


# ---------------------------------------------------------------------------
# Mock-based tests (can't trigger with real SQLite)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# In-memory SQLite tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_deployment_strips_whitespace(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    row = await create_deployment(
        db,
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="  rk-1  ",
        name="  my-deploy  ",
        deployment_type=DeploymentType.AGENT,
    )
    await db.commit()

    fetched = await get_deployment(db, user_id=user.id, deployment_id=row.id)
    assert fetched is not None
    assert fetched.resource_key == "rk-1"
    assert fetched.name == "my-deploy"


@pytest.mark.asyncio
async def test_update_deployment_strips_whitespace(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    row = await create_deployment(
        db,
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-1",
        name="original",
        deployment_type=DeploymentType.AGENT,
    )
    await db.commit()

    updated = await update_deployment(db, deployment=row, name="  new-name  ")
    await db.commit()

    fetched = await get_deployment(db, user_id=user.id, deployment_id=updated.id)
    assert fetched is not None
    assert fetched.name == "new-name"


@pytest.mark.asyncio
async def test_deployment_name_exists_returns_true_when_found(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    await create_deployment(
        db,
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-1",
        name="existing-deploy",
        deployment_type=DeploymentType.AGENT,
    )
    await db.commit()

    result = await deployment_name_exists(
        db,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        name="existing-deploy",
    )
    assert result is True


@pytest.mark.asyncio
async def test_deployment_name_exists_returns_false_when_not_found(
    db: AsyncSession, user: User, provider_account: DeploymentProviderAccount
):
    result = await deployment_name_exists(
        db,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        name="nonexistent",
    )
    assert result is False


@pytest.mark.asyncio
async def test_deployment_name_exists_strips_whitespace(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    await create_deployment(
        db,
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-1",
        name="my-deploy",
        deployment_type=DeploymentType.AGENT,
    )
    await db.commit()

    result = await deployment_name_exists(
        db,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        name="  my-deploy  ",
    )
    assert result is True
