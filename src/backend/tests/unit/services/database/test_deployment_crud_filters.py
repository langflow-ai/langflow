from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    create_deployment,
    list_deployments_by_ids,
    list_deployments_page,
)
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.crud import create_deployment_attachment
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.adapters.deployment.schema import DeploymentType
from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_user_provider_and_projects(async_session: AsyncSession):
    user = User(
        username=f"user-{uuid4()}",
        password=f"hashed-{uuid4()}",
        is_active=True,
    )
    project_a = Folder(
        name=f"project-a-{uuid4()}",
        user_id=user.id,
    )
    project_b = Folder(
        name=f"project-b-{uuid4()}",
        user_id=user.id,
    )
    provider_account = DeploymentProviderAccount(
        user_id=user.id,
        name=f"provider-{uuid4()}",
        provider_tenant_id=None,
        provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
        api_key="encrypted-api-key",  # pragma: allowlist secret
    )

    async_session.add(user)
    async_session.add(project_a)
    async_session.add(project_b)
    async_session.add(provider_account)
    await async_session.commit()

    return user, provider_account, project_a, project_b


async def _seed_flow_and_version(async_session: AsyncSession, user_id, project_id):
    flow = Flow(name=f"flow-{uuid4()}", user_id=user_id, folder_id=project_id, data={"nodes": [], "edges": []})
    async_session.add(flow)
    await async_session.commit()
    flow_version = FlowVersion(flow_id=flow.id, user_id=user_id, version_number=1, data={"nodes": [], "edges": []})
    async_session.add(flow_version)
    await async_session.commit()
    return flow, flow_version


@pytest.mark.asyncio
async def test_local_deployment_queries_filter_project_and_flow_versions(async_session: AsyncSession):
    user, provider_account, project_a, project_b = await _seed_user_provider_and_projects(async_session)

    _flow_a, fv_a = await _seed_flow_and_version(async_session, user.id, project_a.id)
    _flow_b, fv_b = await _seed_flow_and_version(async_session, user.id, project_b.id)

    # Seed deployments
    dep_a = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        display_name="A",
        deployment_type=DeploymentType.AGENT,
    )
    dep_b1 = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        display_name="B",
        deployment_type=DeploymentType.AGENT,
    )
    dep_b2 = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_b.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        display_name="C",
        deployment_type=DeploymentType.AGENT,
    )

    # Attach flow versions
    await create_deployment_attachment(
        async_session,
        user_id=user.id,
        deployment_id=dep_a.id,
        flow_version_id=fv_a.id,
        provider_snapshot_id="snap-a",
    )
    await create_deployment_attachment(
        async_session,
        user_id=user.id,
        deployment_id=dep_b1.id,
        flow_version_id=fv_a.id,
        provider_snapshot_id="snap-b1",
    )
    await create_deployment_attachment(
        async_session,
        user_id=user.id,
        deployment_id=dep_b2.id,
        flow_version_id=fv_b.id,
        provider_snapshot_id="snap-b2",
    )

    async def assert_deployments(expected_ids, project_id=None, flow_version_ids=None):
        page = await list_deployments_page(
            async_session,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            offset=0,
            limit=10,
            project_id=project_id,
            flow_version_ids=flow_version_ids,
        )
        count = await count_deployments_by_provider(
            async_session,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            project_id=project_id,
            flow_version_ids=flow_version_ids,
        )
        assert count == len(expected_ids)
        assert {d[0].id for d in page} == set(expected_ids)

    all_ids = [dep_a.id, dep_b1.id, dep_b2.id]

    await assert_deployments(all_ids)
    await assert_deployments([dep_a.id, dep_b1.id], project_id=project_a.id)
    await assert_deployments([dep_b2.id], project_id=project_b.id)
    await assert_deployments([dep_a.id, dep_b1.id], flow_version_ids=[fv_a.id])
    await assert_deployments([dep_b2.id], flow_version_ids=[fv_b.id])
    await assert_deployments([dep_a.id, dep_b1.id], project_id=project_a.id, flow_version_ids=[fv_a.id])

    # Pagination interaction
    page = await list_deployments_page(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        offset=0,
        limit=1,
    )
    assert len(page) == 1
    count = await count_deployments_by_provider(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
    )
    assert count == 3


@pytest.mark.asyncio
async def test_list_deployments_by_ids_aggregates_matched_flow_versions(async_session: AsyncSession):
    user, provider_account, project_a, _project_b = await _seed_user_provider_and_projects(async_session)
    _flow, fv_keep = await _seed_flow_and_version(async_session, user.id, project_a.id)
    _flow_other, fv_other = await _seed_flow_and_version(async_session, user.id, project_a.id)

    matching = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        display_name="matching",
        deployment_type=DeploymentType.AGENT,
    )
    other = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        display_name="other",
        deployment_type=DeploymentType.AGENT,
    )
    await create_deployment_attachment(
        async_session,
        user_id=user.id,
        deployment_id=matching.id,
        flow_version_id=fv_keep.id,
        provider_snapshot_id="snap-keep",
    )
    await create_deployment_attachment(
        async_session,
        user_id=user.id,
        deployment_id=other.id,
        flow_version_id=fv_other.id,
        provider_snapshot_id="snap-other",
    )

    rows = await list_deployments_by_ids(
        async_session,
        deployments=[matching, other],
        flow_version_ids=[fv_keep.id],
    )

    assert len(rows) == 1
    assert rows[0].deployment.id == matching.id
    assert rows[0].attached_count == 1
    assert rows[0].matched_flow_versions == [(fv_keep.id, "snap-keep")]


@pytest.mark.asyncio
async def test_list_deployments_by_ids_includes_shared_owner_rows(async_session: AsyncSession):
    """Owner comes from each ORM row; attachment counts follow that owner."""
    owner, provider_account, project_a, _project_b = await _seed_user_provider_and_projects(async_session)
    _flow, fv = await _seed_flow_and_version(async_session, owner.id, project_a.id)
    shared = await create_deployment(
        async_session,
        user_id=owner.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        display_name="shared",
        deployment_type=DeploymentType.AGENT,
    )
    await create_deployment_attachment(
        async_session,
        user_id=owner.id,
        deployment_id=shared.id,
        flow_version_id=fv.id,
        provider_snapshot_id="snap-shared",
    )

    rows = await list_deployments_by_ids(
        async_session,
        deployments=[shared],
        flow_version_ids=[fv.id],
    )

    assert len(rows) == 1
    assert rows[0].deployment.id == shared.id
    assert rows[0].deployment.user_id == owner.id
    assert rows[0].matched_flow_versions == [(fv.id, "snap-shared")]


@pytest.mark.asyncio
async def test_list_deployments_by_ids_orders_like_page(async_session: AsyncSession):
    """SQL order matches list_deployments_page even when ids are reversed."""
    from datetime import datetime, timedelta, timezone

    user, provider_account, project_a, _project_b = await _seed_user_provider_and_projects(async_session)
    older = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-older-{uuid4()}",
        display_name="older",
        deployment_type=DeploymentType.AGENT,
    )
    newer = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-newer-{uuid4()}",
        display_name="newer",
        deployment_type=DeploymentType.AGENT,
    )
    base = datetime.now(timezone.utc)
    older.created_at = base
    newer.created_at = base + timedelta(seconds=1)
    async_session.add(older)
    async_session.add(newer)
    await async_session.flush()

    rows = await list_deployments_by_ids(
        async_session,
        # Intentionally reverse of page order (older first).
        deployments=[older, newer],
    )

    assert [row.deployment.id for row in rows] == [newer.id, older.id]


@pytest.mark.asyncio
async def test_local_deployment_queries_filter_deployment_type(async_session: AsyncSession):
    """list/count honor deployment_type so type-scoped sync can prune safely."""
    from sqlalchemy import text

    user, provider_account, project_a, _project_b = await _seed_user_provider_and_projects(async_session)

    dep_agent = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-agent-{uuid4()}",
        display_name="Agent",
        deployment_type=DeploymentType.AGENT,
    )
    dep_other = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-other-{uuid4()}",
        display_name="Other",
        deployment_type=DeploymentType.AGENT,
    )
    # Seed a second local type outside the enum catalog so filtering is observable
    # without expanding DeploymentType for production.
    await async_session.execute(
        text("UPDATE deployment SET deployment_type = :deployment_type WHERE id = :id"),
        {"deployment_type": "other", "id": dep_other.id.hex},
    )
    await async_session.commit()
    async_session.expunge(dep_other)

    page = await list_deployments_page(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        offset=0,
        limit=10,
        deployment_type=DeploymentType.AGENT,
    )
    count = await count_deployments_by_provider(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        deployment_type=DeploymentType.AGENT,
    )
    assert count == 1
    assert [row.id for row, _, _ in page] == [dep_agent.id]

    unfiltered_count = await count_deployments_by_provider(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
    )
    assert unfiltered_count == 2
    other_still_present = await async_session.execute(
        text("SELECT 1 FROM deployment WHERE id = :id AND deployment_type = 'other'"),
        {"id": dep_other.id.hex},
    )
    assert other_still_present.first() is not None


@pytest.mark.asyncio
async def test_create_deployment_stores_microsecond_precision_on_sqlite(async_session: AsyncSession):
    """ORM creates must write DateTime bind strings, not SQLite whole-second now()."""
    from sqlalchemy import text

    user, provider_account, project_a, _project_b = await _seed_user_provider_and_projects(async_session)
    dep = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        display_name="Timed",
        deployment_type=DeploymentType.AGENT,
    )
    await async_session.commit()
    row = (
        await async_session.execute(
            text("SELECT quote(created_at), quote(updated_at) FROM deployment WHERE id = :id"),
            {"id": dep.id.hex},
        )
    ).one()
    assert "." in row[0], f"created_at missing fractional seconds: {row[0]}"
    assert "." in row[1], f"updated_at missing fractional seconds: {row[1]}"


@pytest.mark.asyncio
async def test_list_deployments_page_keyset_tiebreaks_on_identical_created_at(
    async_session: AsyncSession,
):
    """Identical created_at values require the id tie-break for the next page."""
    from datetime import datetime, timezone

    from langflow.services.database.models.deployment.model import Deployment
    from sqlmodel import col, update

    user, provider_account, project_a, _project_b = await _seed_user_provider_and_projects(async_session)

    newer = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-newer-{uuid4()}",
        display_name="Newer",
        deployment_type=DeploymentType.AGENT,
    )
    older = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-older-{uuid4()}",
        display_name="Older",
        deployment_type=DeploymentType.AGENT,
    )
    same_second = datetime(2026, 7, 9, 21, 0, 0, tzinfo=timezone.utc)
    await async_session.execute(
        update(Deployment).where(col(Deployment.id).in_([newer.id, older.id])).values(created_at=same_second)
    )
    await async_session.commit()
    async_session.expunge(newer)
    async_session.expunge(older)

    page1 = await list_deployments_page(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        offset=0,
        limit=1,
    )
    assert len(page1) == 1
    cursor_row = page1[0][0]
    assert cursor_row.created_at is not None
    assert cursor_row.created_at.microsecond == 0

    page2 = await list_deployments_page(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        limit=1,
        cursor_created_at=cursor_row.created_at,
        cursor_exclude_id=cursor_row.id,
    )
    assert len(page2) == 1
    assert page2[0][0].id != cursor_row.id
    assert {page1[0][0].id, page2[0][0].id} == {newer.id, older.id}


@pytest.mark.asyncio
async def test_list_deployments_page_keyset_after_rewriting_whole_second_sqlite_strings(
    async_session: AsyncSession,
):
    """Legacy whole-second SQLite strings must keyset correctly after DateTime rewrite."""
    import importlib

    from sqlalchemy import text

    mig = importlib.import_module("langflow.alembic.versions.a8f3c2d1e4b5_rewrite_deployment_sqlite_timestamps")

    user, provider_account, project_a, _project_b = await _seed_user_provider_and_projects(async_session)

    newer = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-newer-{uuid4()}",
        display_name="Newer",
        deployment_type=DeploymentType.AGENT,
    )
    older = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-older-{uuid4()}",
        display_name="Older",
        deployment_type=DeploymentType.AGENT,
    )
    # Reproduce the historical SQLite store shape (no fractional seconds).
    await async_session.execute(
        text("UPDATE deployment SET created_at = '2026-07-09 21:00:00' WHERE id IN (:a, :b)"),
        {"a": newer.id.hex, "b": older.id.hex},
    )
    await async_session.commit()

    raw = (
        await async_session.execute(
            text("SELECT quote(created_at) FROM deployment WHERE id = :id"),
            {"id": newer.id.hex},
        )
    ).one()
    assert raw[0] == "'2026-07-09 21:00:00'"

    # Without rewrite, keyset would re-include the cursor via string '<'.
    conn = await async_session.connection()
    await conn.run_sync(
        lambda sync_conn: mig._rewrite_table_timestamps(sync_conn, "deployment", ("created_at", "updated_at"))
    )
    await async_session.commit()
    async_session.expunge(newer)
    async_session.expunge(older)

    rewritten = (
        await async_session.execute(
            text("SELECT quote(created_at) FROM deployment WHERE id = :id"),
            {"id": newer.id.hex},
        )
    ).one()
    assert rewritten[0] == "'2026-07-09 21:00:00.000000'"

    page1 = await list_deployments_page(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        offset=0,
        limit=1,
    )
    cursor_row = page1[0][0]
    page2 = await list_deployments_page(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        limit=1,
        cursor_created_at=cursor_row.created_at,
        cursor_exclude_id=cursor_row.id,
    )
    assert page2[0][0].id != cursor_row.id
    assert {page1[0][0].id, page2[0][0].id} == {newer.id, older.id}
