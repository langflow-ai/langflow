from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    create_deployment,
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
