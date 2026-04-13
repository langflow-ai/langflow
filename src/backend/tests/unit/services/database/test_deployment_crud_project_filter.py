from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    create_deployment,
    list_deployments_page,
)
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
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


@pytest.mark.asyncio
async def test_list_deployments_page_filters_by_project_id(async_session: AsyncSession):
    user, provider_account, project_a, project_b = await _seed_user_provider_and_projects(async_session)

    kept = await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        name=f"deployment-a-{uuid4()}",
        deployment_type=DeploymentType.AGENT,
    )
    await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_b.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        name=f"deployment-b-{uuid4()}",
        deployment_type=DeploymentType.AGENT,
    )

    rows = await list_deployments_page(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        offset=0,
        limit=20,
        project_id=project_a.id,
    )

    assert len(rows) == 1
    deployment, attached_count, matched_flow_versions = rows[0]
    assert deployment.id == kept.id
    assert deployment.project_id == project_a.id
    assert attached_count == 0
    assert matched_flow_versions == []


@pytest.mark.asyncio
async def test_count_deployments_by_provider_filters_by_project_id(async_session: AsyncSession):
    user, provider_account, project_a, project_b = await _seed_user_provider_and_projects(async_session)

    await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_a.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        name=f"deployment-a-{uuid4()}",
        deployment_type=DeploymentType.AGENT,
    )
    await create_deployment(
        async_session,
        user_id=user.id,
        project_id=project_b.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        name=f"deployment-b-{uuid4()}",
        deployment_type=DeploymentType.AGENT,
    )

    filtered_total = await count_deployments_by_provider(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
        project_id=project_a.id,
    )
    unfiltered_total = await count_deployments_by_provider(
        async_session,
        user_id=user.id,
        deployment_provider_account_id=provider_account.id,
    )

    assert filtered_total == 1
    assert unfiltered_total == 2
