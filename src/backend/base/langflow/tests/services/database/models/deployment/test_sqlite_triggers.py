from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langflow.services.database.models.deployment.exceptions import (
    DeploymentGuardError,
    parse_deployment_guard_error,
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
from sqlalchemy import delete, event, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from types import ModuleType

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret
_MIGRATION_FILE = "97c9a98c9c01_deployment_guard_triggers.py"
_MIGRATION_PATH = Path(__file__).resolve().parents[5] / "alembic" / "versions" / _MIGRATION_FILE


def _load_migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deployment_guard_triggers_migration", _MIGRATION_PATH)
    if spec is None or spec.loader is None:
        msg = f"Unable to load migration module at {_MIGRATION_PATH}"
        raise RuntimeError(msg)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration_step(sync_connection, *, upgrade: bool) -> None:
    migration_module = _load_migration_module()
    operations = Operations(MigrationContext.configure(sync_connection))
    original_op = migration_module.op
    migration_module.op = operations
    try:
        if upgrade:
            migration_module._upgrade_sqlite()
        else:
            migration_module._downgrade_sqlite()
    finally:
        migration_module.op = original_op


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
        await conn.run_sync(lambda sync_conn: _run_migration_step(sync_conn, upgrade=True))
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session
    async with db_engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: _run_migration_step(sync_conn, upgrade=False))
        await conn.run_sync(SQLModel.metadata.drop_all)
    await db_engine.dispose()


@pytest.fixture
async def user(db: AsyncSession) -> User:
    row = User(username="testuser", password=_TEST_PASSWORD, is_active=True)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.fixture
async def source_project(db: AsyncSession, user: User) -> Folder:
    row = Folder(name="source-project", user_id=user.id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.fixture
async def target_project(db: AsyncSession, user: User) -> Folder:
    row = Folder(name="target-project", user_id=user.id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.fixture
async def flow(db: AsyncSession, user: User, source_project: Folder) -> Flow:
    row = Flow(
        name="flow-1",
        user_id=user.id,
        folder_id=source_project.id,
        data={"nodes": [], "edges": []},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.fixture
async def flow_version(db: AsyncSession, user: User, flow: Flow) -> FlowVersion:
    row = FlowVersion(
        flow_id=flow.id,
        user_id=user.id,
        version_number=1,
        data={"nodes": [], "edges": []},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.fixture
async def provider_account(db: AsyncSession, user: User) -> DeploymentProviderAccount:
    row = DeploymentProviderAccount(
        user_id=user.id,
        provider_tenant_id="tenant-1",
        provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        name="provider-1",
        provider_url="https://provider-1.example.com",
        api_key="encrypted-value",  # pragma: allowlist secret
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.fixture
async def other_provider_account(db: AsyncSession, user: User) -> DeploymentProviderAccount:
    row = DeploymentProviderAccount(
        user_id=user.id,
        provider_tenant_id="tenant-2",
        provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        name="provider-2",
        provider_url="https://provider-2.example.com",
        api_key="encrypted-value-2",  # pragma: allowlist secret
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.fixture
async def deployment(
    db: AsyncSession,
    user: User,
    source_project: Folder,
    provider_account: DeploymentProviderAccount,
) -> Deployment:
    row = Deployment(
        user_id=user.id,
        project_id=source_project.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-1",
        name="deployment-1",
        deployment_type=DeploymentType.AGENT,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _create_attachment(
    db: AsyncSession, *, user_id, flow_version_id, deployment_id
) -> FlowVersionDeploymentAttachment:
    row = FlowVersionDeploymentAttachment(
        user_id=user_id,
        flow_version_id=flow_version_id,
        deployment_id=deployment_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


def _assert_guard(exc: IntegrityError, expected_code: str, expected_detail: str) -> None:
    assert f"DEPLOYMENT_GUARD:{expected_code}:" in str(exc)
    parsed = parse_deployment_guard_error(exc)
    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.detail == expected_detail


async def _execute_and_commit(db: AsyncSession, statement) -> None:
    await db.exec(statement)
    await db.commit()


@pytest.mark.asyncio
async def test_trigger_blocks_flow_version_delete_when_deployed(
    db: AsyncSession,
    user: User,
    flow_version: FlowVersion,
    deployment: Deployment,
) -> None:
    await _create_attachment(
        db,
        user_id=user.id,
        flow_version_id=flow_version.id,
        deployment_id=deployment.id,
    )

    with pytest.raises(IntegrityError) as exc_info:
        await _execute_and_commit(db, delete(FlowVersion).where(FlowVersion.id == flow_version.id))
    await db.rollback()

    _assert_guard(
        exc_info.value,
        "FLOW_VERSION_DEPLOYED",
        "Cannot delete flow version because it is attached to one or more deployments. "
        "Detach it from all deployments first.",
    )


@pytest.mark.asyncio
async def test_trigger_blocks_project_delete_when_deployments_exist(
    db: AsyncSession,
    source_project: Folder,
    deployment: Deployment,  # noqa: ARG001
) -> None:
    with pytest.raises(IntegrityError) as exc_info:
        await _execute_and_commit(db, delete(Folder).where(Folder.id == source_project.id))
    await db.rollback()

    _assert_guard(
        exc_info.value,
        "PROJECT_HAS_DEPLOYMENTS",
        "Cannot delete project because it contains one or more deployments. Remove all deployments first.",
    )


@pytest.mark.asyncio
async def test_trigger_blocks_flow_move_when_deployed_in_source_project(
    db: AsyncSession,
    user: User,
    flow: Flow,
    flow_version: FlowVersion,
    deployment: Deployment,
    target_project: Folder,
) -> None:
    await _create_attachment(
        db,
        user_id=user.id,
        flow_version_id=flow_version.id,
        deployment_id=deployment.id,
    )

    with pytest.raises(IntegrityError) as exc_info:
        await _execute_and_commit(db, update(Flow).where(Flow.id == flow.id).values(folder_id=target_project.id))
    await db.rollback()

    _assert_guard(
        exc_info.value,
        "FLOW_DEPLOYED_IN_PROJECT",
        "Cannot move flow to a different project because it has versions deployed in the current project. "
        "Detach deployed versions first.",
    )


@pytest.mark.asyncio
async def test_trigger_blocks_deployment_project_move(
    db: AsyncSession,
    deployment: Deployment,
    target_project: Folder,
) -> None:
    with pytest.raises(IntegrityError) as exc_info:
        await _execute_and_commit(
            db, update(Deployment).where(Deployment.id == deployment.id).values(project_id=target_project.id)
        )
    await db.rollback()

    _assert_guard(
        exc_info.value,
        "DEPLOYMENT_PROJECT_MOVE",
        "Cannot move deployment to a different project. Re-create it in the target project instead.",
    )


@pytest.mark.asyncio
async def test_trigger_blocks_deployment_provider_account_move(
    db: AsyncSession,
    deployment: Deployment,
    other_provider_account: DeploymentProviderAccount,
) -> None:
    with pytest.raises(IntegrityError) as exc_info:
        await _execute_and_commit(
            db,
            update(Deployment)
            .where(Deployment.id == deployment.id)
            .values(deployment_provider_account_id=other_provider_account.id),
        )
    await db.rollback()

    _assert_guard(
        exc_info.value,
        "DEPLOYMENT_PROVIDER_ACCOUNT_MOVE",
        "Cannot move deployment to a different deployment provider account. "
        "Re-create it under the target provider account instead.",
    )
