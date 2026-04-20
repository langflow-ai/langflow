from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import update_deployment
from langflow.services.database.models.deployment.exceptions import DeploymentGuardError
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment.orm_guards import (
    ensure_attachment_project_match,
    ensure_deployment_immutable_fields,
    ensure_flow_move_allowed,
    ensure_flow_moves_allowed,
    ensure_provider_account_identity_immutable,
)
from langflow.services.database.models.deployment_provider_account.crud import update_provider_account
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderKey,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.crud import create_deployment_attachment
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.adapters.deployment.schema import DeploymentType
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _create_sqlite_engine() -> AsyncEngine:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    return _create_sqlite_engine()


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


@pytest.mark.asyncio
async def test_flow_move_guard_allows_noop(db: AsyncSession, flow: Flow) -> None:
    await ensure_flow_move_allowed(
        db,
        flow_id=flow.id,
        old_folder_id=flow.folder_id,
        new_folder_id=flow.folder_id,
    )


@pytest.mark.asyncio
async def test_flow_move_guard_blocks_when_flow_is_deployed(
    db: AsyncSession,
    user: User,
    flow: Flow,
    flow_version: FlowVersion,
    deployment: Deployment,
    target_project: Folder,
) -> None:
    _ = target_project
    await create_deployment_attachment(
        db,
        user_id=user.id,
        flow_version_id=flow_version.id,
        deployment_id=deployment.id,
        provider_snapshot_id="snapshot-1",
    )
    await db.commit()

    with pytest.raises(DeploymentGuardError) as exc_info:
        await ensure_flow_move_allowed(
            db,
            flow_id=flow.id,
            old_folder_id=flow.folder_id,
            new_folder_id=target_project.id,
        )

    assert exc_info.value.code == "FLOW_DEPLOYED_IN_PROJECT"


@pytest.mark.asyncio
async def test_flow_moves_guard_allows_empty_batch(db: AsyncSession, target_project: Folder) -> None:
    await ensure_flow_moves_allowed(
        db,
        flow_folder_pairs=[],
        new_folder_id=target_project.id,
    )


@pytest.mark.asyncio
async def test_flow_moves_guard_allows_when_all_moves_are_noop(db: AsyncSession, flow: Flow) -> None:
    await ensure_flow_moves_allowed(
        db,
        flow_folder_pairs=[(flow.id, flow.folder_id)],
        new_folder_id=flow.folder_id,
    )


@pytest.mark.asyncio
async def test_flow_moves_guard_blocks_when_any_group_has_deployed_flow(
    db: AsyncSession,
    user: User,
    flow: Flow,
    flow_version: FlowVersion,
    deployment: Deployment,
    target_project: Folder,
) -> None:
    other_source_project = Folder(name="source-project-2", user_id=user.id)
    db.add(other_source_project)
    await db.commit()
    await db.refresh(other_source_project)

    undeployed_flow = Flow(
        name="flow-2",
        user_id=user.id,
        folder_id=other_source_project.id,
        data={"nodes": [], "edges": []},
        updated_at=_utcnow_naive(),
    )
    db.add(undeployed_flow)
    await db.commit()
    await db.refresh(undeployed_flow)

    undeployed_flow_version = FlowVersion(
        flow_id=undeployed_flow.id,
        user_id=user.id,
        version_number=1,
        data={"nodes": [], "edges": []},
    )
    db.add(undeployed_flow_version)
    await db.commit()
    await db.refresh(undeployed_flow_version)

    await create_deployment_attachment(
        db,
        user_id=user.id,
        flow_version_id=flow_version.id,
        deployment_id=deployment.id,
        provider_snapshot_id="snapshot-batch",
    )
    await db.commit()

    with pytest.raises(DeploymentGuardError) as exc_info:
        await ensure_flow_moves_allowed(
            db,
            flow_folder_pairs=[
                (flow.id, flow.folder_id),
                (undeployed_flow.id, undeployed_flow.folder_id),
            ],
            new_folder_id=target_project.id,
        )

    assert exc_info.value.code == "FLOW_DEPLOYED_IN_PROJECT"


def test_deployment_immutable_field_guard_blocks_project_move(deployment: Deployment, target_project: Folder) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        ensure_deployment_immutable_fields(
            old_project_id=deployment.project_id,
            new_project_id=target_project.id,
            old_deployment_type=deployment.deployment_type,
            new_deployment_type=deployment.deployment_type,
            old_resource_key=deployment.resource_key,
            new_resource_key=deployment.resource_key,
            old_provider_account_id=deployment.deployment_provider_account_id,
            new_provider_account_id=deployment.deployment_provider_account_id,
        )

    assert exc_info.value.code == "DEPLOYMENT_PROJECT_MOVE"


def test_deployment_immutable_field_guard_blocks_type_update(deployment: Deployment) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        ensure_deployment_immutable_fields(
            old_project_id=deployment.project_id,
            new_project_id=deployment.project_id,
            old_deployment_type=deployment.deployment_type,
            new_deployment_type=cast("DeploymentType", "changed-type"),
            old_resource_key=deployment.resource_key,
            new_resource_key=deployment.resource_key,
            old_provider_account_id=deployment.deployment_provider_account_id,
            new_provider_account_id=deployment.deployment_provider_account_id,
        )

    assert exc_info.value.code == "DEPLOYMENT_TYPE_UPDATE"


def test_deployment_immutable_field_guard_blocks_resource_key_update(deployment: Deployment) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        ensure_deployment_immutable_fields(
            old_project_id=deployment.project_id,
            new_project_id=deployment.project_id,
            old_deployment_type=deployment.deployment_type,
            new_deployment_type=deployment.deployment_type,
            old_resource_key=deployment.resource_key,
            new_resource_key="rk-updated",
            old_provider_account_id=deployment.deployment_provider_account_id,
            new_provider_account_id=deployment.deployment_provider_account_id,
        )

    assert exc_info.value.code == "DEPLOYMENT_RESOURCE_KEY_UPDATE"


def test_deployment_immutable_field_guard_blocks_provider_account_move(deployment: Deployment) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        ensure_deployment_immutable_fields(
            old_project_id=deployment.project_id,
            new_project_id=deployment.project_id,
            old_deployment_type=deployment.deployment_type,
            new_deployment_type=deployment.deployment_type,
            old_resource_key=deployment.resource_key,
            new_resource_key=deployment.resource_key,
            old_provider_account_id=deployment.deployment_provider_account_id,
            new_provider_account_id=uuid4(),
        )

    assert exc_info.value.code == "DEPLOYMENT_PROVIDER_ACCOUNT_MOVE"


def test_deployment_immutable_field_guard_allows_noop(deployment: Deployment) -> None:
    ensure_deployment_immutable_fields(
        old_project_id=deployment.project_id,
        new_project_id=deployment.project_id,
        old_deployment_type=deployment.deployment_type,
        new_deployment_type=deployment.deployment_type,
        old_resource_key=deployment.resource_key,
        new_resource_key=deployment.resource_key,
        old_provider_account_id=deployment.deployment_provider_account_id,
        new_provider_account_id=deployment.deployment_provider_account_id,
    )


def test_provider_identity_guard_blocks_changes(provider_account: DeploymentProviderAccount) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        ensure_provider_account_identity_immutable(
            old_provider_key=provider_account.provider_key,
            new_provider_key=provider_account.provider_key,
            old_provider_tenant_id=provider_account.provider_tenant_id,
            new_provider_tenant_id=provider_account.provider_tenant_id,
            old_provider_url=provider_account.provider_url,
            new_provider_url="https://provider-renamed.example.com",
        )

    assert exc_info.value.code == "DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE"


def test_provider_identity_guard_blocks_provider_key_changes(provider_account: DeploymentProviderAccount) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        ensure_provider_account_identity_immutable(
            old_provider_key=provider_account.provider_key,
            new_provider_key=cast("DeploymentProviderKey", "changed-provider-key"),
            old_provider_tenant_id=provider_account.provider_tenant_id,
            new_provider_tenant_id=provider_account.provider_tenant_id,
            old_provider_url=provider_account.provider_url,
            new_provider_url=provider_account.provider_url,
        )

    assert exc_info.value.code == "DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE"


def test_provider_identity_guard_blocks_provider_tenant_id_changes(provider_account: DeploymentProviderAccount) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        ensure_provider_account_identity_immutable(
            old_provider_key=provider_account.provider_key,
            new_provider_key=provider_account.provider_key,
            old_provider_tenant_id=provider_account.provider_tenant_id,
            new_provider_tenant_id="tenant-updated",
            old_provider_url=provider_account.provider_url,
            new_provider_url=provider_account.provider_url,
        )

    assert exc_info.value.code == "DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE"


def test_provider_identity_guard_allows_noop(provider_account: DeploymentProviderAccount) -> None:
    ensure_provider_account_identity_immutable(
        old_provider_key=provider_account.provider_key,
        new_provider_key=provider_account.provider_key,
        old_provider_tenant_id=provider_account.provider_tenant_id,
        new_provider_tenant_id=provider_account.provider_tenant_id,
        old_provider_url=provider_account.provider_url,
        new_provider_url=provider_account.provider_url,
    )


@pytest.mark.asyncio
async def test_crud_update_deployment_blocks_project_move(
    db: AsyncSession,
    deployment: Deployment,
    target_project: Folder,
) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        await update_deployment(db, deployment=deployment, project_id=target_project.id)

    assert exc_info.value.code == "DEPLOYMENT_PROJECT_MOVE"


@pytest.mark.asyncio
async def test_crud_update_deployment_blocks_type_update(
    db: AsyncSession,
    deployment: Deployment,
) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        await update_deployment(
            db,
            deployment=deployment,
            deployment_type=cast("DeploymentType", "changed-type"),
        )

    assert exc_info.value.code == "DEPLOYMENT_TYPE_UPDATE"


@pytest.mark.asyncio
async def test_crud_update_provider_account_blocks_identity_update(
    db: AsyncSession,
    provider_account: DeploymentProviderAccount,
) -> None:
    with pytest.raises(DeploymentGuardError) as exc_info:
        await update_provider_account(
            db,
            provider_account=provider_account,
            provider_url="https://provider-renamed.example.com",
        )

    assert exc_info.value.code == "DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE"


@pytest.mark.asyncio
async def test_attachment_project_match_blocks_cross_project_directly(
    db: AsyncSession,
    user: User,
    target_project: Folder,
    flow_version: FlowVersion,
    provider_account: DeploymentProviderAccount,
) -> None:
    deployment_in_other_project = Deployment(
        user_id=user.id,
        project_id=target_project.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-direct-block",
        name="deployment-direct-block",
        deployment_type=DeploymentType.AGENT,
    )
    db.add(deployment_in_other_project)
    await db.commit()
    await db.refresh(deployment_in_other_project)

    with pytest.raises(DeploymentGuardError) as exc_info:
        await ensure_attachment_project_match(
            db,
            flow_version_id=flow_version.id,
            deployment_id=deployment_in_other_project.id,
        )

    assert exc_info.value.code == "CROSS_PROJECT_ATTACHMENT"


@pytest.mark.asyncio
async def test_attachment_project_match_allows_same_project_directly(
    db: AsyncSession,
    flow_version: FlowVersion,
    deployment: Deployment,
) -> None:
    await ensure_attachment_project_match(
        db,
        flow_version_id=flow_version.id,
        deployment_id=deployment.id,
    )


@pytest.mark.asyncio
async def test_attachment_create_blocks_cross_project(
    db: AsyncSession,
    user: User,
    target_project: Folder,
    flow_version: FlowVersion,
    provider_account: DeploymentProviderAccount,
) -> None:
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

    with pytest.raises(DeploymentGuardError) as exc_info:
        await create_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment_in_other_project.id,
            provider_snapshot_id="snapshot-2",
        )

    assert exc_info.value.code == "CROSS_PROJECT_ATTACHMENT"


@pytest.mark.asyncio
async def test_attachment_create_succeeds_same_project(
    db: AsyncSession,
    user: User,
    flow_version: FlowVersion,
    deployment: Deployment,
) -> None:
    row = await create_deployment_attachment(
        db,
        user_id=user.id,
        flow_version_id=flow_version.id,
        deployment_id=deployment.id,
        provider_snapshot_id="snapshot-3",
    )
    await db.commit()
    assert row.id is not None
