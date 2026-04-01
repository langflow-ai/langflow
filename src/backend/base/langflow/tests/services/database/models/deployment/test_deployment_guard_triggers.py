"""Deployment guard trigger tests — runs against both SQLite and PostgreSQL.

SQLite runs always (in-memory).  PostgreSQL runs when the env var
``TEST_DEPLOYMENT_GUARD_PG_URL`` is set to an async PostgreSQL connection string,
e.g.::

    TEST_DEPLOYMENT_GUARD_PG_URL="postgresql+asyncpg://u:p@host:5432/db" \
        uv run pytest .../test_deployment_guard_triggers.py -v

Both ``asyncpg`` and ``psycopg`` (psycopg3) have been validated as async
drivers.  The production app uses ``psycopg``.

If PostgreSQL is running in a Docker container on the host while tests run
inside another container (e.g. a devcontainer), use ``host.docker.internal``
instead of ``localhost`` for ``<host>``.
"""

from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timezone
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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from types import ModuleType

    from sqlalchemy.ext.asyncio import AsyncEngine

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret
_MIGRATION_FILE = "97c9a98c9c01_deployment_guard_triggers.py"
_MIGRATION_PATH = Path(__file__).resolve().parents[5] / "alembic" / "versions" / _MIGRATION_FILE
_PG_URL = os.environ.get("TEST_DEPLOYMENT_GUARD_PG_URL")


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
    dialect = sync_connection.dialect.name
    operations = Operations(MigrationContext.configure(sync_connection))
    original_op = migration_module.op
    migration_module.op = operations
    try:
        if dialect == "postgresql":
            (migration_module._upgrade_postgresql if upgrade else migration_module._downgrade_postgresql)()
        else:
            (migration_module._upgrade_sqlite if upgrade else migration_module._downgrade_sqlite)()
    finally:
        migration_module.op = original_op


def _create_sqlite_engine() -> AsyncEngine:
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


def _pg_connect_args() -> dict:
    """Return driver-appropriate connect_args to set the session timezone to UTC."""
    if _PG_URL and "+asyncpg" in _PG_URL:
        return {"server_settings": {"timezone": "UTC"}}
    return {"options": "-c timezone=utc"}


def _create_pg_engine() -> AsyncEngine:
    return create_async_engine(
        _PG_URL,
        isolation_level="READ COMMITTED",
        connect_args=_pg_connect_args(),
    )


_engine_params = [
    pytest.param("sqlite", id="sqlite"),
]
if _PG_URL:
    _engine_params.append(pytest.param("pg", id="pg"))


@pytest.fixture(name="db_engine", params=_engine_params)
def db_engine_fixture(request):
    if request.param == "pg":
        return _create_pg_engine()
    return _create_sqlite_engine()


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


# ── Fixtures ─────────────────────────────────────────────────────────


def _utcnow_naive() -> datetime:
    """Naive UTC timestamp compatible with both asyncpg and aiosqlite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
async def user(db: AsyncSession) -> User:
    now = _utcnow_naive()
    row = User(username="testuser", password=_TEST_PASSWORD, is_active=True, create_at=now, updated_at=now)
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
        updated_at=_utcnow_naive(),
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


# ── Helpers ──────────────────────────────────────────────────────────


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


def _assert_guard(exc: DBAPIError, expected_code: str, expected_detail: str) -> None:
    assert f"DEPLOYMENT_GUARD:{expected_code}:" in str(exc)
    parsed = parse_deployment_guard_error(exc)
    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.detail == expected_detail


async def _execute_and_commit(db: AsyncSession, statement) -> None:
    await db.exec(statement)
    await db.commit()


# ── Happy-path tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_flow_version_delete_succeeds_without_attachment(
    db: AsyncSession,
    flow_version: FlowVersion,
) -> None:
    """Deleting a flow version with no deployment attachment must succeed."""
    await _execute_and_commit(db, delete(FlowVersion).where(FlowVersion.id == flow_version.id))
    result = (await db.exec(select(FlowVersion).where(FlowVersion.id == flow_version.id))).first()
    assert result is None


@pytest.mark.asyncio
async def test_project_delete_succeeds_without_deployments(
    db: AsyncSession,
    source_project: Folder,
    flow: Flow,  # noqa: ARG001
) -> None:
    """Deleting a project with no deployments must succeed (flows remain orphaned or re-assigned)."""
    await db.exec(update(Flow).where(Flow.folder_id == source_project.id).values(folder_id=None))
    await _execute_and_commit(db, delete(Folder).where(Folder.id == source_project.id))
    result = (await db.exec(select(Folder).where(Folder.id == source_project.id))).first()
    assert result is None


@pytest.mark.asyncio
async def test_flow_move_succeeds_without_deployment_in_source_project(
    db: AsyncSession,
    flow: Flow,
    target_project: Folder,
) -> None:
    """Moving a flow that has no deployments in the source project must succeed."""
    await _execute_and_commit(db, update(Flow).where(Flow.id == flow.id).values(folder_id=target_project.id))
    moved = (await db.exec(select(Flow).where(Flow.id == flow.id))).first()
    assert moved is not None
    assert moved.folder_id == target_project.id


@pytest.mark.asyncio
async def test_deployment_name_update_succeeds(
    db: AsyncSession,
    deployment: Deployment,
) -> None:
    """Updating non-guarded columns on deployment must succeed."""
    await _execute_and_commit(db, update(Deployment).where(Deployment.id == deployment.id).values(name="renamed"))
    updated = (await db.exec(select(Deployment).where(Deployment.id == deployment.id))).first()
    assert updated is not None
    assert updated.name == "renamed"


@pytest.mark.asyncio
async def test_same_project_attachment_succeeds(
    db: AsyncSession,
    user: User,
    flow_version: FlowVersion,
    deployment: Deployment,
) -> None:
    """Attaching a flow version to a deployment in the same project must succeed."""
    attachment = await _create_attachment(
        db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
    )
    assert attachment.id is not None


# ── Guard tests ──────────────────────────────────────────────────────


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

    with pytest.raises(DBAPIError) as exc_info:
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
    with pytest.raises(DBAPIError) as exc_info:
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

    with pytest.raises(DBAPIError) as exc_info:
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
    with pytest.raises(DBAPIError) as exc_info:
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
    with pytest.raises(DBAPIError) as exc_info:
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


@pytest.mark.asyncio
async def test_trigger_blocks_cross_project_attachment(
    db: AsyncSession,
    user: User,
    target_project: Folder,
    flow_version: FlowVersion,
    provider_account: DeploymentProviderAccount,
) -> None:
    """Attaching a flow version to a deployment in a different project must be blocked."""
    deployment_in_other_project = Deployment(
        user_id=user.id,
        project_id=target_project.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-other",
        name="deployment-other",
        deployment_type=DeploymentType.AGENT,
    )
    db.add(deployment_in_other_project)
    await db.commit()
    await db.refresh(deployment_in_other_project)

    with pytest.raises(DBAPIError) as exc_info:
        await _create_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment_in_other_project.id
        )
    await db.rollback()

    _assert_guard(
        exc_info.value,
        "CROSS_PROJECT_ATTACHMENT",
        "Cannot attach a flow version to a deployment in a different project.",
    )


# ── No-op (same-value) update tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_deployment_project_update_with_same_value_succeeds(
    db: AsyncSession,
    deployment: Deployment,
) -> None:
    """Updating project_id to its current value must not trigger the guard."""
    await _execute_and_commit(
        db,
        update(Deployment).where(Deployment.id == deployment.id).values(project_id=deployment.project_id),
    )
    row = (await db.exec(select(Deployment).where(Deployment.id == deployment.id))).first()
    assert row is not None
    assert row.project_id == deployment.project_id


@pytest.mark.asyncio
async def test_deployment_provider_account_update_with_same_value_succeeds(
    db: AsyncSession,
    deployment: Deployment,
) -> None:
    """Updating deployment_provider_account_id to its current value must not trigger the guard."""
    await _execute_and_commit(
        db,
        update(Deployment)
        .where(Deployment.id == deployment.id)
        .values(deployment_provider_account_id=deployment.deployment_provider_account_id),
    )
    row = (await db.exec(select(Deployment).where(Deployment.id == deployment.id))).first()
    assert row is not None
    assert row.deployment_provider_account_id == deployment.deployment_provider_account_id


@pytest.mark.asyncio
async def test_flow_folder_update_with_same_value_succeeds_when_deployed(
    db: AsyncSession,
    user: User,
    flow: Flow,
    flow_version: FlowVersion,
    deployment: Deployment,
) -> None:
    """Updating folder_id to its current value must succeed even when the flow is deployed."""
    await _create_attachment(db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id)
    await _execute_and_commit(
        db,
        update(Flow).where(Flow.id == flow.id).values(folder_id=flow.folder_id),
    )
    row = (await db.exec(select(Flow).where(Flow.id == flow.id))).first()
    assert row is not None
    assert row.folder_id == flow.folder_id


# ── Flow move to NULL folder_id ──────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_blocks_flow_move_to_null_folder_when_deployed(
    db: AsyncSession,
    user: User,
    flow: Flow,
    flow_version: FlowVersion,
    deployment: Deployment,
) -> None:
    """Moving a deployed flow to NULL folder_id is still a project change and must be blocked."""
    await _create_attachment(db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id)
    with pytest.raises(DBAPIError) as exc_info:
        await _execute_and_commit(
            db,
            update(Flow).where(Flow.id == flow.id).values(folder_id=None),
        )
    await db.rollback()

    _assert_guard(
        exc_info.value,
        "FLOW_DEPLOYED_IN_PROJECT",
        "Cannot move flow to a different project because it has versions deployed in the current project. "
        "Detach deployed versions first.",
    )


# ── Post-detachment / post-removal success paths ────────────────────


@pytest.mark.asyncio
async def test_flow_version_delete_succeeds_after_detachment(
    db: AsyncSession,
    user: User,
    flow_version: FlowVersion,
    deployment: Deployment,
) -> None:
    """After removing the attachment, deleting the flow version must succeed."""
    attachment = await _create_attachment(
        db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
    )

    await _execute_and_commit(
        db,
        delete(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == attachment.id),
    )

    await _execute_and_commit(db, delete(FlowVersion).where(FlowVersion.id == flow_version.id))
    result = (await db.exec(select(FlowVersion).where(FlowVersion.id == flow_version.id))).first()
    assert result is None


@pytest.mark.asyncio
async def test_project_delete_succeeds_after_removing_deployments(
    db: AsyncSession,
    source_project: Folder,
    deployment: Deployment,
) -> None:
    """After removing all deployments, deleting the project must succeed."""
    await _execute_and_commit(db, delete(Deployment).where(Deployment.id == deployment.id))

    await db.exec(update(Flow).where(Flow.folder_id == source_project.id).values(folder_id=None))
    await _execute_and_commit(db, delete(Folder).where(Folder.id == source_project.id))
    result = (await db.exec(select(Folder).where(Folder.id == source_project.id))).first()
    assert result is None


# ── Multiple attachments / multiple deployments ──────────────────────


@pytest.mark.asyncio
async def test_trigger_blocks_flow_version_delete_with_multiple_attachments(
    db: AsyncSession,
    user: User,
    source_project: Folder,
    flow_version: FlowVersion,
    deployment: Deployment,
    provider_account: DeploymentProviderAccount,
) -> None:
    """A flow version attached to multiple deployments must still be blocked."""
    second_deployment = Deployment(
        user_id=user.id,
        project_id=source_project.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-2",
        name="deployment-2",
        deployment_type=DeploymentType.AGENT,
    )
    db.add(second_deployment)
    await db.commit()
    await db.refresh(second_deployment)

    await _create_attachment(db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id)
    await _create_attachment(db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=second_deployment.id)

    with pytest.raises(DBAPIError):
        await _execute_and_commit(db, delete(FlowVersion).where(FlowVersion.id == flow_version.id))
    await db.rollback()


@pytest.mark.asyncio
async def test_trigger_blocks_project_delete_with_multiple_deployments(
    db: AsyncSession,
    user: User,
    source_project: Folder,
    deployment: Deployment,  # noqa: ARG001
    provider_account: DeploymentProviderAccount,
) -> None:
    """A project with multiple deployments must still be blocked."""
    second_deployment = Deployment(
        user_id=user.id,
        project_id=source_project.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-3",
        name="deployment-3",
        deployment_type=DeploymentType.AGENT,
    )
    db.add(second_deployment)
    await db.commit()

    with pytest.raises(DBAPIError):
        await _execute_and_commit(db, delete(Folder).where(Folder.id == source_project.id))
    await db.rollback()


# ── Downgrade removes triggers ───────────────────────────────────────


@pytest.mark.asyncio
async def test_downgrade_removes_triggers(
    db_engine,
) -> None:
    """Guard must block before downgrade and allow after downgrade."""
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.run_sync(lambda c: _run_migration_step(c, upgrade=True))

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        now = _utcnow_naive()
        user = User(username="downgrade-user", password=_TEST_PASSWORD, is_active=True, create_at=now, updated_at=now)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        project = Folder(name="downgrade-project", user_id=user.id)
        session.add(project)
        await session.commit()
        await session.refresh(project)

        provider = DeploymentProviderAccount(
            user_id=user.id,
            provider_tenant_id="tenant-dg",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            name="provider-dg",
            provider_url="https://provider-dg.example.com",
            api_key="encrypted-dg",  # pragma: allowlist secret
        )
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        dep = Deployment(
            user_id=user.id,
            project_id=project.id,
            deployment_provider_account_id=provider.id,
            resource_key="rk-dg",
            name="deployment-dg",
            deployment_type=DeploymentType.AGENT,
        )
        session.add(dep)
        await session.commit()

    # Verify the guard IS active before downgrade
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        with pytest.raises(DBAPIError):
            await _execute_and_commit(session, delete(Folder).where(Folder.id == project.id))
        await session.rollback()

    async with db_engine.begin() as conn:
        await conn.run_sync(lambda c: _run_migration_step(c, upgrade=False))

    # After downgrade, the same operation must succeed
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        await session.exec(delete(Deployment).where(Deployment.project_id == project.id))
        await session.exec(update(Flow).where(Flow.folder_id == project.id).values(folder_id=None))
        await _execute_and_commit(session, delete(Folder).where(Folder.id == project.id))
        result = (await session.exec(select(Folder).where(Folder.id == project.id))).first()
        assert result is None

    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await db_engine.dispose()
