"""In-memory SQLite integration tests for orphan attachment cleanup.

Verifies that orphan detection and pruning works against a real database
with foreign keys enabled — guards, CRUD counts, and version pruning all
correctly distinguish live vs. orphaned attachment rows.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.api.utils.flow_utils import cascade_delete_flow
from langflow.services.database.models.deployment.crud import list_deployments_page
from langflow.services.database.models.deployment.guards import (
    check_flow_has_deployed_versions,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderKey,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.crud import (
    create_flow_version_entry,
    get_flow_versions_with_provider_status,
    has_deployment_attachments,
)
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    count_attachments_by_deployment_ids,
    count_deployment_attachments,
    delete_orphan_attachments_for_flow_ids,
    delete_orphan_attachments_for_project,
)
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Fixtures
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
async def flow(db: AsyncSession, user: User, folder: Folder) -> Flow:
    f = Flow(name="test-flow", user_id=user.id, folder_id=folder.id)
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
        name="test-provider",
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
        name="my-deployment",
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def _create_version(db: AsyncSession, flow: Flow, user: User, n: int = 1) -> FlowVersion:
    fv = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=n, data={"nodes": []})
    db.add(fv)
    await db.commit()
    await db.refresh(fv)
    return fv


async def _attach(
    db: AsyncSession,
    user: User,
    version: FlowVersion,
    deployment: Deployment,
    snapshot_id: str = "snap-1",
) -> FlowVersionDeploymentAttachment:
    att = FlowVersionDeploymentAttachment(
        user_id=user.id,
        flow_version_id=version.id,
        deployment_id=deployment.id,
        provider_snapshot_id=snapshot_id,
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return att


async def _make_orphan_attachment(
    db: AsyncSession,
    user: User,
    version: FlowVersion,
    snapshot_id: str = "orphan-snap",
) -> FlowVersionDeploymentAttachment:
    """Insert an attachment row pointing to a non-existent deployment.

    FK enforcement is temporarily disabled so the row can be written, then
    re-enabled to simulate legacy data from pre-FK-enforcement environments.
    """
    fake_deployment_id = uuid4()
    await db.exec(text("PRAGMA foreign_keys=OFF"))
    att = FlowVersionDeploymentAttachment(
        user_id=user.id,
        flow_version_id=version.id,
        deployment_id=fake_deployment_id,
        provider_snapshot_id=snapshot_id,
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    await db.exec(text("PRAGMA foreign_keys=ON"))
    return att


# ===========================================================================
# Guard: check_flow_has_deployed_versions
# ===========================================================================


@pytest.mark.asyncio
class TestGuardOrphanPruning:
    async def test_guard_allows_when_no_attachments(self, db: AsyncSession, flow: Flow, user: User):
        await _create_version(db, flow, user)
        await check_flow_has_deployed_versions(db, flow_id=flow.id)

    async def test_guard_raises_for_live_attachment(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment
    ):
        from langflow.services.database.models.deployment.exceptions import DeploymentGuardError

        version = await _create_version(db, flow, user)
        await _attach(db, user, version, deployment)

        with pytest.raises(DeploymentGuardError):
            await check_flow_has_deployed_versions(db, flow_id=flow.id)

    async def test_guard_prunes_orphan_and_allows_delete(self, db: AsyncSession, flow: Flow, user: User):
        version = await _create_version(db, flow, user)
        orphan = await _make_orphan_attachment(db, user, version)

        await check_flow_has_deployed_versions(db, flow_id=flow.id)

        stmt = select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == orphan.id)
        assert (await db.exec(stmt)).first() is None

    async def test_guard_prunes_orphan_but_raises_when_live_also_exists(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment
    ):
        from langflow.services.database.models.deployment.exceptions import DeploymentGuardError

        version = await _create_version(db, flow, user)
        await _attach(db, user, version, deployment)
        await _make_orphan_attachment(db, user, version, snapshot_id="orphan-2")

        with pytest.raises(DeploymentGuardError):
            await check_flow_has_deployed_versions(db, flow_id=flow.id)


# ===========================================================================
# cascade_delete_flow
# ===========================================================================


@pytest.mark.asyncio
class TestCascadeDeleteFlow:
    async def test_deletes_related_rows_under_fk_enforcement(self, db: AsyncSession, flow: Flow, user: User):
        version = await _create_version(db, flow, user)

        trace = TraceTable(name="trace-1", flow_id=flow.id, session_id="session-1")
        db.add(trace)
        await db.flush()

        span = SpanTable(name="span-1", trace_id=trace.id)
        message = MessageTable(
            sender="user",
            sender_name="User",
            session_id="session-1",
            text="hello",
            flow_id=flow.id,
        )
        transaction = TransactionTable(vertex_id="vertex-1", status="ok", flow_id=flow.id)
        vertex_build = VertexBuildTable(id="vertex-1", valid=True, flow_id=flow.id)
        db.add_all([span, message, transaction, vertex_build])
        await db.commit()

        await cascade_delete_flow(db, flow.id)
        await db.commit()

        assert (await db.exec(select(Flow).where(Flow.id == flow.id))).first() is None
        assert (await db.exec(select(FlowVersion).where(FlowVersion.id == version.id))).first() is None
        assert (await db.exec(select(TraceTable).where(TraceTable.id == trace.id))).first() is None
        assert (await db.exec(select(SpanTable).where(SpanTable.id == span.id))).first() is None
        assert (await db.exec(select(MessageTable).where(MessageTable.flow_id == flow.id))).all() == []
        assert (await db.exec(select(TransactionTable).where(TransactionTable.flow_id == flow.id))).all() == []
        assert (await db.exec(select(VertexBuildTable).where(VertexBuildTable.flow_id == flow.id))).all() == []

    async def test_deletes_flow_when_only_orphan_attachments_exist(self, db: AsyncSession, flow: Flow, user: User):
        version = await _create_version(db, flow, user)
        orphan = await _make_orphan_attachment(db, user, version, snapshot_id="orphan-only")

        await cascade_delete_flow(db, flow.id)
        await db.commit()

        assert (await db.exec(select(Flow).where(Flow.id == flow.id))).first() is None
        assert (await db.exec(select(FlowVersion).where(FlowVersion.id == version.id))).first() is None
        assert (
            await db.exec(
                select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == orphan.id)
            )
        ).first() is None


# ===========================================================================
# has_deployment_attachments
# ===========================================================================


@pytest.mark.asyncio
class TestHasDeploymentAttachments:
    async def test_returns_true_for_live_attachment(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment
    ):
        version = await _create_version(db, flow, user)
        await _attach(db, user, version, deployment)

        assert await has_deployment_attachments(db, version.id, user_id=user.id) is True

    async def test_returns_false_and_prunes_orphan(self, db: AsyncSession, flow: Flow, user: User):
        version = await _create_version(db, flow, user)
        orphan = await _make_orphan_attachment(db, user, version)

        assert await has_deployment_attachments(db, version.id, user_id=user.id) is False

        stmt = select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == orphan.id)
        assert (await db.exec(stmt)).first() is None

    async def test_returns_false_when_no_attachments(self, db: AsyncSession, flow: Flow, user: User):
        version = await _create_version(db, flow, user)
        assert await has_deployment_attachments(db, version.id, user_id=user.id) is False


# ===========================================================================
# count_* CRUD functions exclude orphans
# ===========================================================================


@pytest.mark.asyncio
class TestCountFunctionsExcludeOrphans:
    async def test_count_by_deployment_ids_excludes_orphan_version(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment
    ):
        """Attachment pointing to a deleted flow_version should not be counted."""
        version = await _create_version(db, flow, user)
        await _attach(db, user, version, deployment)

        counts = await count_attachments_by_deployment_ids(db, user_id=user.id, deployment_ids=[deployment.id])
        assert counts[deployment.id] == 1

        # Delete the version (FK cascades delete the attachment in a real DB).
        # The count should drop to 0.
        await db.delete(version)
        await db.commit()

        counts = await count_attachments_by_deployment_ids(db, user_id=user.id, deployment_ids=[deployment.id])
        assert counts[deployment.id] == 0

    async def test_count_deployment_attachments_excludes_orphan_version(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment
    ):
        version = await _create_version(db, flow, user)
        await _attach(db, user, version, deployment)

        total = await count_deployment_attachments(db, user_id=user.id, deployment_id=deployment.id)
        assert total == 1

        await db.delete(version)
        await db.commit()

        total = await count_deployment_attachments(db, user_id=user.id, deployment_id=deployment.id)
        assert total == 0


# ===========================================================================
# delete_orphan_attachments_for_flow_ids
# ===========================================================================


@pytest.mark.asyncio
class TestDeleteOrphanAttachmentsForFlowIds:
    async def test_deletes_orphan_leaves_live(self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment):
        version = await _create_version(db, flow, user)
        live = await _attach(db, user, version, deployment)
        orphan = await _make_orphan_attachment(db, user, version, snapshot_id="orphan-snap")

        deleted = await delete_orphan_attachments_for_flow_ids(db, user_id=user.id, flow_ids=[flow.id])
        await db.commit()

        assert deleted == 1

        stmt = select(FlowVersionDeploymentAttachment.id)
        remaining = (await db.exec(stmt)).all()
        assert live.id in remaining
        assert orphan.id not in remaining

    async def test_no_op_when_no_orphans(self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment):
        version = await _create_version(db, flow, user)
        await _attach(db, user, version, deployment)

        deleted = await delete_orphan_attachments_for_flow_ids(db, user_id=user.id, flow_ids=[flow.id])
        assert deleted == 0

    async def test_empty_flow_ids_returns_zero(self, db: AsyncSession, user: User):
        deleted = await delete_orphan_attachments_for_flow_ids(db, user_id=user.id, flow_ids=[])
        assert deleted == 0

    async def test_scopes_deletion_by_user(self, db: AsyncSession, user: User, flow: Flow):
        version = await _create_version(db, flow, user)
        own_orphan = await _make_orphan_attachment(db, user, version, snapshot_id="self-orphan")

        other_user = User(username="other-user", password=_TEST_PASSWORD, is_active=True)
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        other_folder = Folder(name="other-user-project", user_id=other_user.id)
        db.add(other_folder)
        await db.commit()
        await db.refresh(other_folder)

        other_flow = Flow(name="other-user-flow", user_id=other_user.id, folder_id=other_folder.id)
        db.add(other_flow)
        await db.commit()
        await db.refresh(other_flow)

        other_version = await _create_version(db, other_flow, other_user)
        other_orphan = await _make_orphan_attachment(db, other_user, other_version, snapshot_id="other-orphan")

        deleted = await delete_orphan_attachments_for_flow_ids(db, user_id=user.id, flow_ids=[flow.id])
        await db.commit()
        assert deleted == 1

        remaining_ids = (
            await db.exec(
                select(FlowVersionDeploymentAttachment.id).where(
                    FlowVersionDeploymentAttachment.id.in_([own_orphan.id, other_orphan.id])
                )
            )
        ).all()
        assert own_orphan.id not in remaining_ids
        assert other_orphan.id in remaining_ids


# ===========================================================================
# delete_orphan_attachments_for_project
# ===========================================================================


@pytest.mark.asyncio
class TestDeleteOrphanAttachmentsForProject:
    async def test_deletes_orphan_scoped_to_project(
        self, db: AsyncSession, flow: Flow, user: User, folder: Folder, deployment: Deployment
    ):
        version = await _create_version(db, flow, user)
        live = await _attach(db, user, version, deployment)
        orphan = await _make_orphan_attachment(db, user, version, snapshot_id="proj-orphan")

        deleted = await delete_orphan_attachments_for_project(db, user_id=user.id, project_id=folder.id)
        await db.commit()

        assert deleted == 1

        stmt = select(FlowVersionDeploymentAttachment.id)
        remaining = (await db.exec(stmt)).all()
        assert live.id in remaining
        assert orphan.id not in remaining

    async def test_does_not_touch_other_projects(self, db: AsyncSession, flow: Flow, user: User, folder: Folder):  # noqa: ARG002
        version = await _create_version(db, flow, user)
        await _make_orphan_attachment(db, user, version)

        other_folder = Folder(name="other-project", user_id=user.id)
        db.add(other_folder)
        await db.commit()
        await db.refresh(other_folder)

        deleted = await delete_orphan_attachments_for_project(db, user_id=user.id, project_id=other_folder.id)
        assert deleted == 0

    async def test_project_cleanup_scopes_by_user(self, db: AsyncSession, user: User, folder: Folder, flow: Flow):
        own_version = await _create_version(db, flow, user)
        own_orphan = await _make_orphan_attachment(db, user, own_version, snapshot_id="own-project-orphan")

        other_user = User(username="project-other-user", password=_TEST_PASSWORD, is_active=True)
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        other_folder = Folder(name="project-other-folder", user_id=other_user.id)
        db.add(other_folder)
        await db.commit()
        await db.refresh(other_folder)

        other_flow = Flow(name="project-other-flow", user_id=other_user.id, folder_id=other_folder.id)
        db.add(other_flow)
        await db.commit()
        await db.refresh(other_flow)

        other_version = await _create_version(db, other_flow, other_user)
        other_orphan = await _make_orphan_attachment(db, other_user, other_version, snapshot_id="other-project-orphan")

        deleted = await delete_orphan_attachments_for_project(db, user_id=user.id, project_id=folder.id)
        await db.commit()
        assert deleted == 1

        remaining_ids = (
            await db.exec(
                select(FlowVersionDeploymentAttachment.id).where(
                    FlowVersionDeploymentAttachment.id.in_([own_orphan.id, other_orphan.id])
                )
            )
        ).all()
        assert own_orphan.id not in remaining_ids
        assert other_orphan.id in remaining_ids


# ===========================================================================
# Version pruning respects live deployments only
# ===========================================================================


@pytest.mark.asyncio
class TestVersionPruningRespectsLiveDeployments:
    async def test_orphan_attachment_does_not_pin_version_during_pruning(
        self, db: AsyncSession, flow: Flow, user: User
    ):
        """A version with only orphan attachments should be prunable."""
        settings_mock = SimpleNamespace(settings=SimpleNamespace(max_flow_version_entries_per_flow=1))
        with patch(
            "langflow.services.database.models.flow_version.crud.get_settings_service",
            return_value=settings_mock,
        ):
            v1 = await _create_version(db, flow, user, n=1)
            await _make_orphan_attachment(db, user, v1, snapshot_id="pin-orphan")

            await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
            await db.commit()

        stmt = select(FlowVersion).where(FlowVersion.flow_id == flow.id)
        remaining = (await db.exec(stmt)).all()
        assert len(remaining) == 1, "Orphan attachment should not have pinned v1"
        assert remaining[0].version_number == 2

    async def test_live_attachment_pins_version_during_pruning(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment
    ):
        """A version with a live attachment must survive pruning."""
        settings_mock = SimpleNamespace(settings=SimpleNamespace(max_flow_version_entries_per_flow=1))
        with patch(
            "langflow.services.database.models.flow_version.crud.get_settings_service",
            return_value=settings_mock,
        ):
            v1 = await _create_version(db, flow, user, n=1)
            await _attach(db, user, v1, deployment)

            await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
            await db.commit()

        stmt = select(FlowVersion).where(FlowVersion.flow_id == flow.id).order_by(FlowVersion.version_number)
        remaining = (await db.exec(stmt)).all()
        assert len(remaining) == 2, "Live attachment should have pinned v1"
        assert remaining[0].version_number == 1
        assert remaining[1].version_number == 2


# ===========================================================================
# Pruning cleans attachment children (no doubly-orphan attachments form)
# ===========================================================================


@pytest.mark.asyncio
class TestVersionPruningCleansOrphanAttachments:
    """Source-fix coverage for prune cleanup.

    attachment children for the versions it removes, otherwise stale
    orphan-deployment attachments would survive as doubly-orphaned rows
    (deployment AND flow_version both missing). No existing cleanup helper
    catches that shape, so the only place to plug it is at the formation site.
    """

    @pytest.fixture(autouse=True)
    def _patch_max_entries(self, request):
        """Allow each test to set max_flow_version_entries_per_flow via marker."""
        max_entries = getattr(request, "param", 1)
        with patch(
            "langflow.services.database.models.flow_version.crud.get_settings_service",
            return_value=SimpleNamespace(settings=SimpleNamespace(max_flow_version_entries_per_flow=max_entries)),
        ):
            yield

    async def test_prune_deletes_orphan_attachment_alongside_version(self, db: AsyncSession, flow: Flow, user: User):
        """A version that gets pruned must also have its orphan attachment removed."""
        v1 = await _create_version(db, flow, user, n=1)
        orphan = await _make_orphan_attachment(db, user, v1, snapshot_id="orphan-pruned")

        await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
        await db.commit()

        # v1 was pruned (only v2 remains)
        versions = (await db.exec(select(FlowVersion).where(FlowVersion.flow_id == flow.id))).all()
        assert len(versions) == 1
        assert versions[0].version_number == 2

        # Crucially: the orphan attachment is gone too — no doubly-orphan formed.
        remaining_attachment = (
            await db.exec(
                select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == orphan.id)
            )
        ).first()
        assert remaining_attachment is None

    async def test_prune_with_no_attachments_is_unchanged(self, db: AsyncSession, flow: Flow, user: User):
        """The fast-path (no attachments to clean) must still prune the version."""
        await _create_version(db, flow, user, n=1)

        await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
        await db.commit()

        versions = (await db.exec(select(FlowVersion).where(FlowVersion.flow_id == flow.id))).all()
        assert len(versions) == 1
        assert versions[0].version_number == 2

    async def test_prune_preserves_live_attachment_and_its_version(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment
    ):
        """A live-deployed version must not be pruned, and its attachment must stay."""
        v1 = await _create_version(db, flow, user, n=1)
        live = await _attach(db, user, v1, deployment, snapshot_id="snap-live")

        await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
        await db.commit()

        versions = (
            await db.exec(
                select(FlowVersion).where(FlowVersion.flow_id == flow.id).order_by(FlowVersion.version_number)
            )
        ).all()
        assert [v.version_number for v in versions] == [1, 2]

        live_remaining = (
            await db.exec(select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == live.id))
        ).first()
        assert live_remaining is not None

    async def test_prune_mixed_attachment_states_in_single_pass(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment
    ):
        """Versions with no/orphan attachments are pruned together; live ones survive.

        max_entries=1 so we keep only the newest non-deployed version (plus all
        deployed ones). Setup builds 4 versions with mixed attachment states,
        then create_flow_version_entry adds v5 and prunes.
        """
        v1 = await _create_version(db, flow, user, n=1)  # no attachment
        v2 = await _create_version(db, flow, user, n=2)  # orphan attachment
        v3 = await _create_version(db, flow, user, n=3)  # live attachment
        v4 = await _create_version(db, flow, user, n=4)  # no attachment

        live = await _attach(db, user, v3, deployment, snapshot_id="mixed-live")
        orphan = await _make_orphan_attachment(db, user, v2, snapshot_id="mixed-orphan")

        await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
        await db.commit()

        # Only v3 (live-deployed) and v5 (newest, just created) survive — v1,
        # v2, v4 are pruned.
        remaining_version_numbers = sorted(
            v.version_number for v in (await db.exec(select(FlowVersion).where(FlowVersion.flow_id == flow.id))).all()
        )
        assert remaining_version_numbers == [3, 5]

        # The live attachment stays because v3 stayed.
        assert (
            await db.exec(select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == live.id))
        ).first() is not None

        # The orphan attachment was reaped along with v2 — no doubly-orphan formed.
        assert (
            await db.exec(
                select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == orphan.id)
            )
        ).first() is None

        # And there are no doubly-orphan rows lurking anywhere.
        doubly_orphans = (
            await db.exec(
                select(FlowVersionDeploymentAttachment.id)
                .outerjoin(
                    FlowVersion,
                    FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id,
                )
                .where(FlowVersion.id.is_(None))
            )
        ).all()
        assert doubly_orphans == []

        # Touch v4 reference so the linter doesn't complain about unused vars.
        assert v1.version_number == 1
        assert v4.version_number == 4

    async def test_prune_does_not_touch_attachments_for_other_flows(
        self, db: AsyncSession, flow: Flow, folder: Folder, user: User, deployment: Deployment
    ):
        """Pruning flow A must not delete attachments belonging to flow B."""
        v1_a = await _create_version(db, flow, user, n=1)
        await _make_orphan_attachment(db, user, v1_a, snapshot_id="flow-a-orphan")

        other_flow = Flow(name="other-flow", user_id=user.id, folder_id=folder.id)
        db.add(other_flow)
        await db.commit()
        await db.refresh(other_flow)

        v1_b = await _create_version(db, other_flow, user, n=1)
        live_b = await _attach(db, user, v1_b, deployment, snapshot_id="flow-b-live")
        orphan_b = await _make_orphan_attachment(db, user, v1_b, snapshot_id="flow-b-orphan")

        await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
        await db.commit()

        # Flow B's attachments are untouched.
        assert (
            await db.exec(
                select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == live_b.id)
            )
        ).first() is not None
        assert (
            await db.exec(
                select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == orphan_b.id)
            )
        ).first() is not None

        # Flow B's version is untouched.
        assert (await db.exec(select(FlowVersion).where(FlowVersion.id == v1_b.id))).first() is not None

    async def test_prune_does_not_touch_attachments_for_other_users(self, db: AsyncSession, flow: Flow, user: User):
        """Pruning user A's flow must not delete user B's attachments."""
        v1 = await _create_version(db, flow, user, n=1)
        await _make_orphan_attachment(db, user, v1, snapshot_id="user-a-orphan")

        other_user = User(username="prune-other-user", password=_TEST_PASSWORD, is_active=True)
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        other_folder = Folder(name="prune-other-folder", user_id=other_user.id)
        db.add(other_folder)
        await db.commit()
        await db.refresh(other_folder)

        other_flow = Flow(name="prune-other-flow", user_id=other_user.id, folder_id=other_folder.id)
        db.add(other_flow)
        await db.commit()
        await db.refresh(other_flow)

        other_v1 = await _create_version(db, other_flow, other_user, n=1)
        other_orphan = await _make_orphan_attachment(db, other_user, other_v1, snapshot_id="user-b-orphan")

        await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
        await db.commit()

        # User B's row is untouched.
        assert (
            await db.exec(
                select(FlowVersionDeploymentAttachment).where(FlowVersionDeploymentAttachment.id == other_orphan.id)
            )
        ).first() is not None
        assert (await db.exec(select(FlowVersion).where(FlowVersion.id == other_v1.id))).first() is not None

    async def test_repeated_snapshots_never_accumulate_doubly_orphans(self, db: AsyncSession, flow: Flow, user: User):
        """Stress test repeated snapshot cycles with a stale orphan attachment.

        converge to zero doubly-orphan rows.
        """
        v1 = await _create_version(db, flow, user, n=1)
        await _make_orphan_attachment(db, user, v1, snapshot_id="legacy-orphan")

        for _ in range(10):
            await create_flow_version_entry(db, flow.id, user.id, data={"nodes": []})
            await db.commit()

        doubly_orphans = (
            await db.exec(
                select(FlowVersionDeploymentAttachment.id)
                .outerjoin(
                    FlowVersion,
                    FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id,
                )
                .where(FlowVersion.id.is_(None))
            )
        ).all()
        assert doubly_orphans == []


# ===========================================================================
# list_deployments_page excludes orphan flow-version attachments from counts
# ===========================================================================


@pytest.mark.asyncio
class TestListDeploymentsPageAttachmentCount:
    async def test_counts_only_live_flow_version_attachments(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment, provider_account
    ):
        v1 = await _create_version(db, flow, user, n=1)
        await _attach(db, user, v1, deployment)

        page = await list_deployments_page(
            db,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            offset=0,
            limit=10,
        )
        assert len(page) == 1
        dep, attached_count, _matched = page[0]
        assert dep.id == deployment.id
        assert attached_count == 1

    async def test_orphan_flow_version_attachment_excluded_from_count(
        self, db: AsyncSession, flow: Flow, user: User, deployment: Deployment, provider_account
    ):
        v1 = await _create_version(db, flow, user, n=1)
        await _attach(db, user, v1, deployment)

        v2 = await _create_version(db, flow, user, n=2)
        await _attach(db, user, v2, deployment, snapshot_id="snap-2")

        page = await list_deployments_page(
            db,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            offset=0,
            limit=10,
        )
        _, count_before, _ = page[0]
        assert count_before == 2

        # Delete v2, leaving an orphan attachment (FK cascade cleans it in
        # real environments, but verify the join-based count is resilient).
        await db.delete(v2)
        await db.commit()

        page = await list_deployments_page(
            db,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            offset=0,
            limit=10,
        )
        _, count_after, _ = page[0]
        assert count_after == 1


# ===========================================================================
# Provider-scoped deployment status uses live deployments only
# ===========================================================================


@pytest.mark.asyncio
class TestGetFlowVersionsWithProviderStatus:
    async def test_live_attachment_marks_version_as_deployed(
        self,
        db: AsyncSession,
        flow: Flow,
        user: User,
        deployment: Deployment,
        provider_account: DeploymentProviderAccount,
    ):
        v1 = await _create_version(db, flow, user, n=1)
        await _attach(db, user, v1, deployment)

        rows = await get_flow_versions_with_provider_status(
            db,
            flow.id,
            user.id,
            provider_account_id=provider_account.id,
        )
        assert len(rows) == 1
        version, is_deployed = rows[0]
        assert version.id == v1.id
        assert is_deployed is True

    async def test_orphan_attachment_does_not_mark_version_as_deployed(
        self, db: AsyncSession, flow: Flow, user: User, provider_account: DeploymentProviderAccount
    ):
        v1 = await _create_version(db, flow, user, n=1)
        await _make_orphan_attachment(db, user, v1)

        rows = await get_flow_versions_with_provider_status(
            db,
            flow.id,
            user.id,
            provider_account_id=provider_account.id,
        )
        assert len(rows) == 1
        _, is_deployed = rows[0]
        assert is_deployed is False

    async def test_mixed_live_and_orphan_only_live_counts(
        self,
        db: AsyncSession,
        flow: Flow,
        user: User,
        deployment: Deployment,
        provider_account: DeploymentProviderAccount,
    ):
        v1 = await _create_version(db, flow, user, n=1)
        await _attach(db, user, v1, deployment)

        v2 = await _create_version(db, flow, user, n=2)
        await _make_orphan_attachment(db, user, v2)

        rows = await get_flow_versions_with_provider_status(
            db,
            flow.id,
            user.id,
            provider_account_id=provider_account.id,
        )
        by_id = {version.id: is_deployed for version, is_deployed in rows}
        assert by_id[v1.id] is True
        assert by_id[v2.id] is False
