from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderKey,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    count_attachments_by_deployment_ids,
    create_deployment_attachment,
    delete_deployment_attachment,
    delete_deployment_attachments_by_deployment_id,
    get_deployment_attachment,
    list_attachments_by_deployment_ids,
    list_attachments_for_flow_with_provider_info,
    list_deployment_attachments,
    list_deployment_attachments_for_flow_version_ids,
    update_deployment_attachment_provider_snapshot_id,
)
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
        name="test-provider-account",
        provider_url="https://provider.example.com",
        api_key="encrypted-value",  # pragma: allowlist secret
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return acct


@pytest.fixture
async def deployment(
    db: AsyncSession,
    user: User,
    folder: Folder,
    provider_account: DeploymentProviderAccount,
) -> Deployment:
    d = Deployment(
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-1",
        name="test-deployment",
        deployment_type=DeploymentType.AGENT,
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


@pytest.fixture
async def flow(db: AsyncSession, user: User, folder: Folder) -> Flow:
    f = Flow(
        id=uuid4(),
        name="test-flow",
        user_id=user.id,
        folder_id=folder.id,
        data={"nodes": [], "edges": []},
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


@pytest.fixture
async def flow_version(db: AsyncSession, user: User, flow: Flow) -> FlowVersion:
    fv = FlowVersion(
        flow_id=flow.id,
        user_id=user.id,
        version_number=1,
        data={"nodes": [], "edges": []},
    )
    db.add(fv)
    await db.commit()
    await db.refresh(fv)
    return fv


@pytest.mark.asyncio
class TestCreateDeploymentAttachment:
    async def test_create_happy_path(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        att = await create_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
            provider_snapshot_id="snap-1",
        )
        await db.commit()

        assert att.id is not None
        assert att.user_id == user.id
        assert att.flow_version_id == flow_version.id
        assert att.deployment_id == deployment.id
        assert att.provider_snapshot_id == "snap-1"
        assert att.created_at is not None

    async def test_create_without_snapshot_id(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        att = await create_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        await db.commit()

        assert att.provider_snapshot_id is None

    async def test_create_duplicate_raises_value_error(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        await create_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        await db.commit()

        with pytest.raises(ValueError, match="Attachment conflicts with an existing record"):
            await create_deployment_attachment(
                db,
                user_id=user.id,
                flow_version_id=flow_version.id,
                deployment_id=deployment.id,
            )


@pytest.mark.asyncio
class TestGetDeploymentAttachment:
    async def test_get_existing(self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment):
        await create_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        await db.commit()

        result = await get_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        assert result is not None
        assert result.flow_version_id == flow_version.id

    async def test_get_nonexistent_returns_none(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        result = await get_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        assert result is None

    async def test_get_wrong_user_returns_none(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        await create_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        await db.commit()

        other_user = User(username="other", password=_TEST_PASSWORD, is_active=True)
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        result = await get_deployment_attachment(
            db,
            user_id=other_user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        assert result is None


@pytest.mark.asyncio
class TestListDeploymentAttachments:
    async def test_list_ordered_by_created_at(self, db: AsyncSession, user: User, flow: Flow, deployment: Deployment):
        fv1 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=2, data={})
        fv2 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=3, data={})
        db.add_all([fv1, fv2])
        await db.commit()
        await db.refresh(fv1)
        await db.refresh(fv2)

        await create_deployment_attachment(db, user_id=user.id, flow_version_id=fv1.id, deployment_id=deployment.id)
        await db.commit()
        await create_deployment_attachment(db, user_id=user.id, flow_version_id=fv2.id, deployment_id=deployment.id)
        await db.commit()

        results = await list_deployment_attachments(db, user_id=user.id, deployment_id=deployment.id)
        assert len(results) == 2
        assert results[0].flow_version_id == fv1.id
        assert results[1].flow_version_id == fv2.id

    async def test_list_empty(self, db: AsyncSession, user: User, deployment: Deployment):
        results = await list_deployment_attachments(db, user_id=user.id, deployment_id=deployment.id)
        assert results == []


@pytest.mark.asyncio
class TestListDeploymentAttachmentsForFlowVersionIds:
    async def test_filters_by_flow_version_ids(self, db: AsyncSession, user: User, flow: Flow, deployment: Deployment):
        fv1 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=2, data={})
        fv2 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=3, data={})
        fv3 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=4, data={})
        db.add_all([fv1, fv2, fv3])
        await db.commit()
        await db.refresh(fv1)
        await db.refresh(fv2)
        await db.refresh(fv3)

        for fv in [fv1, fv2, fv3]:
            await create_deployment_attachment(db, user_id=user.id, flow_version_id=fv.id, deployment_id=deployment.id)
        await db.commit()

        results = await list_deployment_attachments_for_flow_version_ids(
            db,
            user_id=user.id,
            deployment_id=deployment.id,
            flow_version_ids=[fv1.id, fv3.id],
        )
        assert len(results) == 2
        returned_fv_ids = {r.flow_version_id for r in results}
        assert returned_fv_ids == {fv1.id, fv3.id}

    async def test_empty_flow_version_ids_returns_empty(self, db: AsyncSession, user: User, deployment: Deployment):
        results = await list_deployment_attachments_for_flow_version_ids(
            db,
            user_id=user.id,
            deployment_id=deployment.id,
            flow_version_ids=[],
        )
        assert results == []


@pytest.mark.asyncio
class TestDeleteDeploymentAttachment:
    async def test_delete_existing(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()

        count = await delete_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        assert count == 1

    async def test_delete_nonexistent_returns_zero(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        count = await delete_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        assert count == 0


@pytest.mark.asyncio
class TestUpdateDeploymentAttachmentProviderSnapshotId:
    async def test_update_snapshot_id(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        att = await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()

        assert att.provider_snapshot_id is None

        updated = await update_deployment_attachment_provider_snapshot_id(
            db, attachment=att, provider_snapshot_id="snap-new"
        )
        await db.commit()

        assert updated.provider_snapshot_id == "snap-new"

    async def test_clear_snapshot_id(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        att = await create_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
            provider_snapshot_id="snap-old",
        )
        await db.commit()

        updated = await update_deployment_attachment_provider_snapshot_id(db, attachment=att, provider_snapshot_id=None)
        await db.commit()

        assert updated.provider_snapshot_id is None


@pytest.mark.asyncio
class TestDeleteDeploymentAttachmentsByDeploymentId:
    async def test_delete_all_for_deployment(self, db: AsyncSession, user: User, flow: Flow, deployment: Deployment):
        fv1 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=2, data={})
        fv2 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=3, data={})
        db.add_all([fv1, fv2])
        await db.commit()
        await db.refresh(fv1)
        await db.refresh(fv2)

        await create_deployment_attachment(db, user_id=user.id, flow_version_id=fv1.id, deployment_id=deployment.id)
        await create_deployment_attachment(db, user_id=user.id, flow_version_id=fv2.id, deployment_id=deployment.id)
        await db.commit()

        count = await delete_deployment_attachments_by_deployment_id(db, user_id=user.id, deployment_id=deployment.id)
        assert count == 2

        remaining = await list_deployment_attachments(db, user_id=user.id, deployment_id=deployment.id)
        assert remaining == []

    async def test_delete_none_returns_zero(self, db: AsyncSession, user: User, deployment: Deployment):
        count = await delete_deployment_attachments_by_deployment_id(db, user_id=user.id, deployment_id=deployment.id)
        assert count == 0


@pytest.mark.asyncio
class TestListAttachmentsByDeploymentIds:
    async def test_list_across_deployments(
        self,
        db: AsyncSession,
        user: User,
        flow_version: FlowVersion,
        deployment: Deployment,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        d2 = Deployment(
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-2",
            name="deploy-2",
        )
        db.add(d2)
        await db.commit()
        await db.refresh(d2)

        fv2 = FlowVersion(flow_id=flow_version.flow_id, user_id=user.id, version_number=2, data={})
        db.add(fv2)
        await db.commit()
        await db.refresh(fv2)

        await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await create_deployment_attachment(db, user_id=user.id, flow_version_id=fv2.id, deployment_id=d2.id)
        await db.commit()

        results = await list_attachments_by_deployment_ids(db, user_id=user.id, deployment_ids=[deployment.id, d2.id])
        assert len(results) == 2

    async def test_empty_deployment_ids_returns_empty(self, db: AsyncSession, user: User):
        results = await list_attachments_by_deployment_ids(db, user_id=user.id, deployment_ids=[])
        assert results == []


@pytest.mark.asyncio
class TestListAttachmentsForFlowWithProviderInfo:
    async def test_returns_tuples_with_provider_info(
        self,
        db: AsyncSession,
        user: User,
        flow: Flow,
        flow_version: FlowVersion,
        deployment: Deployment,
        provider_account: DeploymentProviderAccount,
    ):
        await create_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
            provider_snapshot_id="snap-1",
        )
        await db.commit()

        results = await list_attachments_for_flow_with_provider_info(db, user_id=user.id, flow_ids=[flow.id])
        assert len(results) == 1
        attachment, provider_account_id, provider_key = results[0]
        assert attachment.flow_version_id == flow_version.id
        assert provider_account_id == provider_account.id
        assert provider_key == DeploymentProviderKey.WATSONX_ORCHESTRATE

    async def test_no_attachments_returns_empty(self, db: AsyncSession, user: User, flow: Flow):
        results = await list_attachments_for_flow_with_provider_info(db, user_id=user.id, flow_ids=[flow.id])
        assert results == []

    async def test_multiple_versions_same_flow(
        self,
        db: AsyncSession,
        user: User,
        flow: Flow,
        flow_version: FlowVersion,
        deployment: Deployment,
        provider_account: DeploymentProviderAccount,  # noqa: ARG002
    ):
        fv2 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=2, data={})
        db.add(fv2)
        await db.commit()
        await db.refresh(fv2)

        await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()
        await create_deployment_attachment(db, user_id=user.id, flow_version_id=fv2.id, deployment_id=deployment.id)
        await db.commit()

        results = await list_attachments_for_flow_with_provider_info(db, user_id=user.id, flow_ids=[flow.id])
        assert len(results) == 2


@pytest.mark.asyncio
class TestCountAttachmentsByDeploymentIds:
    async def test_count_distinct_flow_versions(
        self,
        db: AsyncSession,
        user: User,
        flow: Flow,
        flow_version: FlowVersion,
        deployment: Deployment,
    ):
        fv2 = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=2, data={})
        db.add(fv2)
        await db.commit()
        await db.refresh(fv2)

        await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await create_deployment_attachment(db, user_id=user.id, flow_version_id=fv2.id, deployment_id=deployment.id)
        await db.commit()

        counts = await count_attachments_by_deployment_ids(db, user_id=user.id, deployment_ids=[deployment.id])
        assert counts == {deployment.id: 2}

    async def test_empty_deployment_ids_returns_empty_dict(self, db: AsyncSession, user: User):
        counts = await count_attachments_by_deployment_ids(db, user_id=user.id, deployment_ids=[])
        assert counts == {}

    async def test_deployment_with_no_attachments_not_in_result(
        self, db: AsyncSession, user: User, deployment: Deployment
    ):
        counts = await count_attachments_by_deployment_ids(db, user_id=user.id, deployment_ids=[deployment.id])
        assert deployment.id not in counts


@pytest.mark.asyncio
class TestCascadeDeletes:
    async def test_cascade_on_deployment_delete(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        att = await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()
        att_id = att.id

        await db.delete(deployment)
        await db.commit()

        stmt = select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == att_id)
        assert (await db.exec(stmt)).first() is None

    async def test_cascade_on_flow_version_delete(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        att = await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()
        att_id = att.id

        await db.delete(flow_version)
        await db.commit()

        stmt = select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == att_id)
        assert (await db.exec(stmt)).first() is None

    async def test_cascade_on_user_delete(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        att = await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()
        att_id = att.id

        await db.delete(user)
        await db.commit()

        stmt = select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == att_id)
        assert (await db.exec(stmt)).first() is None


@pytest.mark.asyncio
class TestUserScoping:
    async def test_other_user_cannot_list(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()

        other_user = User(username="other", password=_TEST_PASSWORD, is_active=True)
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        results = await list_deployment_attachments(db, user_id=other_user.id, deployment_id=deployment.id)
        assert results == []

    async def test_other_user_cannot_get(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()

        other_user = User(username="other2", password=_TEST_PASSWORD, is_active=True)
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        result = await get_deployment_attachment(
            db,
            user_id=other_user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        assert result is None

    async def test_other_user_cannot_delete(
        self, db: AsyncSession, user: User, flow_version: FlowVersion, deployment: Deployment
    ):
        await create_deployment_attachment(
            db, user_id=user.id, flow_version_id=flow_version.id, deployment_id=deployment.id
        )
        await db.commit()

        other_user = User(username="other3", password=_TEST_PASSWORD, is_active=True)
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        count = await delete_deployment_attachment(
            db,
            user_id=other_user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        assert count == 0

        original = await get_deployment_attachment(
            db,
            user_id=user.id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
        )
        assert original is not None
