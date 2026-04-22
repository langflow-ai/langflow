from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import (
    create_deployment,
    delete_deployment_by_id,
    delete_deployment_by_resource_key,
    delete_deployments_by_ids,
    deployment_name_exists,
    get_deployment,
    list_deployments_page,
    update_deployment,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderKey,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.adapters.deployment.schema import DeploymentType
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Mock helper (for pure-validation tests that raise before touching DB)
# ---------------------------------------------------------------------------


def _make_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


class _ExecResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


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
        name="provider-1",
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
async def test_list_deployments_page_attachment_count_only_counts_live_flow_versions():
    db = _make_db()
    db.exec = AsyncMock(return_value=_ExecResult([]))
    await list_deployments_page(
        db,
        user_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        offset=0,
        limit=20,
    )

    # String-match on compiled SQL because these tests use mocked sessions.
    statement_text = str(db.exec.await_args.args[0]).lower()
    assert "join flow_version" in statement_text


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
    lookup_result = MagicMock()
    lookup_result.first.return_value = uuid4()
    attachment_delete_result = MagicMock()
    attachment_delete_result.rowcount = 3
    mock_result = MagicMock()
    mock_result.rowcount = None
    db.exec.side_effect = [lookup_result, attachment_delete_result, mock_result]

    with patch("langflow.services.database.models.deployment.crud.logger") as mock_logger:
        mock_logger.aerror = AsyncMock()
        count = await delete_deployment_by_resource_key(
            db,
            user_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="rk-1",
        )

    assert count == 0
    assert db.exec.await_count == 3
    lookup_stmt = str(db.exec.await_args_list[0].args[0]).lower()
    attachment_stmt = str(db.exec.await_args_list[1].args[0]).lower()
    deployment_stmt = str(db.exec.await_args_list[2].args[0]).lower()
    assert "select deployment.id" in lookup_stmt
    assert "delete from flow_version_deployment_attachment" in attachment_stmt
    assert "delete from deployment" in deployment_stmt
    mock_logger.aerror.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_by_resource_key_missing_row_skips_attachment_delete():
    db = _make_db()
    lookup_result = MagicMock()
    lookup_result.first.return_value = None
    deployment_delete_result = MagicMock()
    deployment_delete_result.rowcount = 0
    db.exec.side_effect = [lookup_result, deployment_delete_result]

    with patch("langflow.services.database.models.deployment.crud.logger") as mock_logger:
        mock_logger.aerror = AsyncMock()
        count = await delete_deployment_by_resource_key(
            db,
            user_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="rk-missing",
        )

    assert count == 0
    assert db.exec.await_count == 2
    lookup_stmt = str(db.exec.await_args_list[0].args[0]).lower()
    deployment_stmt = str(db.exec.await_args_list[1].args[0]).lower()
    assert "select deployment.id" in lookup_stmt
    assert "delete from deployment" in deployment_stmt
    assert "flow_version_deployment_attachment" not in deployment_stmt
    mock_logger.aerror.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_by_id_none_rowcount_logs_error():
    db = _make_db()
    attachment_delete_result = MagicMock()
    attachment_delete_result.rowcount = 1
    mock_result = MagicMock()
    mock_result.rowcount = None
    db.exec.side_effect = [attachment_delete_result, mock_result]

    with patch("langflow.services.database.models.deployment.crud.logger") as mock_logger:
        mock_logger.aerror = AsyncMock()
        count = await delete_deployment_by_id(
            db,
            user_id=uuid4(),
            deployment_id=uuid4(),
        )

    assert count == 0
    assert db.exec.await_count == 2
    attachment_stmt = str(db.exec.await_args_list[0].args[0]).lower()
    deployment_stmt = str(db.exec.await_args_list[1].args[0]).lower()
    assert "delete from flow_version_deployment_attachment" in attachment_stmt
    assert "delete from deployment" in deployment_stmt
    mock_logger.aerror.assert_awaited_once()


# ---------------------------------------------------------------------------
# FK-disabled safety test (real SQLite, FK off)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_by_id_prunes_attachments_when_fk_disabled():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _disable_fk(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as db:
        user = User(username="fk-off-user", password=_TEST_PASSWORD, is_active=True)
        db.add(user)
        await db.flush()

        folder = Folder(name="fk-off-folder", user_id=user.id)
        db.add(folder)
        await db.flush()

        provider_account = DeploymentProviderAccount(
            user_id=user.id,
            provider_tenant_id="tenant-fk-off",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            name="provider-fk-off",
            provider_url="https://provider-fk-off.example.com",
            api_key="encrypted-value",  # pragma: allowlist secret
        )
        db.add(provider_account)
        await db.flush()

        deployment = Deployment(
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-fk-off",
            name="deployment-fk-off",
            deployment_type=DeploymentType.AGENT,
        )
        db.add(deployment)
        await db.flush()

        flow = Flow(
            name="flow-fk-off",
            user_id=user.id,
            folder_id=folder.id,
            data={"nodes": [], "edges": []},
        )
        db.add(flow)
        await db.flush()

        flow_version = FlowVersion(
            flow_id=flow.id,
            user_id=user.id,
            version_number=1,
            data={"nodes": [], "edges": []},
        )
        db.add(flow_version)
        await db.flush()

        attachment = FlowVersionDeploymentAttachment(
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
            provider_snapshot_id="snapshot-fk-off",
        )
        db.add(attachment)
        await db.commit()

        deleted = await delete_deployment_by_id(db, user_id=user.id, deployment_id=deployment.id)
        await db.commit()
        assert deleted == 1

        deployment_row = (await db.exec(select(Deployment).where(Deployment.id == deployment.id))).first()
        attachment_row = (
            await db.exec(
                select(FlowVersionDeploymentAttachment).where(
                    FlowVersionDeploymentAttachment.deployment_id == deployment.id
                )
            )
        ).first()
        assert deployment_row is None
        assert attachment_row is None

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# In-memory SQLite tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_deployment_strips_whitespace(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    assert folder.id is not None
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
    assert folder.id is not None
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
async def test_delete_by_id_removes_attached_rows_with_fk_on(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    flow = Flow(name="flow-del-id", user_id=user.id, folder_id=folder.id, data={"nodes": [], "edges": []})
    db.add(flow)
    await db.flush()

    flow_version_1 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=1, data={"nodes": [], "edges": []})
    flow_version_2 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=2, data={"nodes": [], "edges": []})
    db.add_all([flow_version_1, flow_version_2])
    await db.flush()

    deployment = await create_deployment(
        db,
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-delete-id",
        name="delete-id",
        deployment_type=DeploymentType.AGENT,
    )
    await db.flush()

    db.add_all(
        [
            FlowVersionDeploymentAttachment(
                user_id=user.id,
                flow_version_id=flow_version_1.id,
                deployment_id=deployment.id,
                provider_snapshot_id="snap-del-id-1",
            ),
            FlowVersionDeploymentAttachment(
                user_id=user.id,
                flow_version_id=flow_version_2.id,
                deployment_id=deployment.id,
                provider_snapshot_id="snap-del-id-2",
            ),
        ]
    )
    await db.commit()

    deleted = await delete_deployment_by_id(db, user_id=user.id, deployment_id=deployment.id)
    await db.commit()
    assert deleted == 1

    deployment_row = (await db.exec(select(Deployment).where(Deployment.id == deployment.id))).first()
    attachment_rows = (
        await db.exec(
            select(FlowVersionDeploymentAttachment).where(
                FlowVersionDeploymentAttachment.deployment_id == deployment.id
            )
        )
    ).all()
    assert deployment_row is None
    assert attachment_rows == []


@pytest.mark.asyncio
async def test_delete_by_ids_removes_multiple_deployments_and_attached_rows(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    flow = Flow(name="flow-del-ids", user_id=user.id, folder_id=folder.id, data={"nodes": [], "edges": []})
    db.add(flow)
    await db.flush()

    flow_version_1 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=1, data={"nodes": [], "edges": []})
    flow_version_2 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=2, data={"nodes": [], "edges": []})
    db.add_all([flow_version_1, flow_version_2])
    await db.flush()

    deployment_1 = await create_deployment(
        db,
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-delete-ids-1",
        name="delete-ids-1",
        deployment_type=DeploymentType.AGENT,
    )
    deployment_2 = await create_deployment(
        db,
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-delete-ids-2",
        name="delete-ids-2",
        deployment_type=DeploymentType.AGENT,
    )
    await db.flush()

    db.add_all(
        [
            FlowVersionDeploymentAttachment(
                user_id=user.id,
                flow_version_id=flow_version_1.id,
                deployment_id=deployment_1.id,
                provider_snapshot_id="snap-del-ids-1",
            ),
            FlowVersionDeploymentAttachment(
                user_id=user.id,
                flow_version_id=flow_version_2.id,
                deployment_id=deployment_2.id,
                provider_snapshot_id="snap-del-ids-2",
            ),
        ]
    )
    await db.commit()

    deleted = await delete_deployments_by_ids(
        db,
        user_id=user.id,
        deployment_ids=[deployment_1.id, deployment_2.id],
    )
    await db.commit()
    assert deleted == 2

    deployment_rows = (
        await db.exec(select(Deployment).where(Deployment.id.in_([deployment_1.id, deployment_2.id])))
    ).all()
    attachment_rows = (
        await db.exec(
            select(FlowVersionDeploymentAttachment).where(
                FlowVersionDeploymentAttachment.deployment_id.in_([deployment_1.id, deployment_2.id])
            )
        )
    ).all()
    assert deployment_rows == []
    assert attachment_rows == []


@pytest.mark.asyncio
async def test_delete_by_resource_key_removes_attached_rows_with_fk_on(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    flow = Flow(name="flow-del-rk", user_id=user.id, folder_id=folder.id, data={"nodes": [], "edges": []})
    db.add(flow)
    await db.flush()

    flow_version = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=1, data={"nodes": [], "edges": []})
    db.add(flow_version)
    await db.flush()

    deployment = await create_deployment(
        db,
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-delete-rk",
        name="delete-rk",
        deployment_type=DeploymentType.AGENT,
    )
    await db.flush()

    db.add(
        FlowVersionDeploymentAttachment(
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
            provider_snapshot_id="snap-del-rk-1",
        )
    )
    await db.commit()

    deleted = await delete_deployment_by_resource_key(
        db,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-delete-rk",
    )
    await db.commit()
    assert deleted == 1

    deployment_row = (await db.exec(select(Deployment).where(Deployment.id == deployment.id))).first()
    attachment_rows = (
        await db.exec(
            select(FlowVersionDeploymentAttachment).where(
                FlowVersionDeploymentAttachment.deployment_id == deployment.id
            )
        )
    ).all()
    assert deployment_row is None
    assert attachment_rows == []


@pytest.mark.asyncio
async def test_deployment_name_exists_returns_true_when_found(
    db: AsyncSession, user: User, folder: Folder, provider_account: DeploymentProviderAccount
):
    assert folder.id is not None
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
    assert folder.id is not None
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
