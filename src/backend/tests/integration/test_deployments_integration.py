from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.api.v1.deployments import list_deployments
from langflow.services.database.models.deployment.crud import create_deployment
from langflow.services.database.models.deployment_provider_account.crud import create_provider_account
from langflow.services.database.models.folder.model import Folder
from langflow.services.utils import register_builtin_adapters
from lfx.services.adapters.deployment.schema import DeploymentType


@pytest.mark.asyncio
async def test_list_deployments_names_filter_db_mode(async_session, active_user):
    """Integration test: GET /deployments?names= filters correctly in DB mode."""
    with patch("langflow.services.utils.FEATURE_FLAGS.wxo_deployments", new=True):
        # Manually register adapters since app initialization might have skipped it
        register_builtin_adapters()

        # Seed data
        project_a = Folder(name=f"project-a-{uuid4()}", user_id=active_user.id)
        async_session.add(project_a)
        await async_session.commit()

        provider_account = await create_provider_account(
            async_session,
            user_id=active_user.id,
            name=f"provider-{uuid4()}",
            provider_key="watsonx-orchestrate",
            provider_url="https://api.example.com",
            provider_tenant_id="tenant-1",
            api_key="secret",  # pragma: allowlist secret
        )

        await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            name="Agent Alpha",
            deployment_type=DeploymentType.AGENT,
        )
        await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            name="Agent Beta",
            deployment_type=DeploymentType.AGENT,
        )
        await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            name="Agent Gamma",
            deployment_type=DeploymentType.AGENT,
        )
        provider_id = provider_account.id

        params = SimpleNamespace(page=1, size=20)

        # Mock fetch_provider_resource_keys to return all keys so they aren't deleted
        async def mock_fetch_provider_resource_keys(*args, **kwargs):  # noqa: ARG001
            return kwargs.get("resource_keys", [])

        with patch(
            "langflow.api.v1.mappers.deployments.helpers.fetch_provider_resource_keys",
            new_callable=AsyncMock,
            side_effect=mock_fetch_provider_resource_keys,
        ):
            # 1. Fetch without names filter
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=False,
                names=None,
            )
            assert response.total == 3
            names = {d.name for d in response.deployments}
            assert names == {"Agent Alpha", "Agent Beta", "Agent Gamma"}

            # 2. Fetch with single name filter
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=False,
                names=["Agent Alpha"],
            )
            assert response.total == 1
            assert response.deployments[0].name == "Agent Alpha"

            # 3. Fetch with multiple names filter
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=False,
                names=["Agent Alpha", "Agent Beta"],
            )
            assert response.total == 2
            names = {d.name for d in response.deployments}
            assert names == {"Agent Alpha", "Agent Beta"}

        # 4. Fetch with non-existent name
        response = await list_deployments(
            provider_id=provider_id,
            session=async_session,
            current_user=active_user,
            params=params,
            deployment_type=None,
            load_from_provider=False,
            names=["NonExistent"],
        )
        assert response.total == 0
        assert len(response.deployments) == 0


@pytest.mark.asyncio
async def test_list_deployments_names_filter_provider_mode(async_session, active_user):
    """Integration test: GET /deployments?names= filters correctly in provider mode."""
    with patch("langflow.services.utils.FEATURE_FLAGS.wxo_deployments", new=True):
        register_builtin_adapters()

        project_a = Folder(name=f"project-a-{uuid4()}", user_id=active_user.id)
        async_session.add(project_a)
        await async_session.commit()

        provider_account = await create_provider_account(
            async_session,
            user_id=active_user.id,
            name=f"provider-{uuid4()}",
            provider_key="watsonx-orchestrate",
            provider_url="https://api.example.com",
            provider_tenant_id="tenant-1",
            api_key="secret",  # pragma: allowlist secret
        )
        provider_id = provider_account.id
        params = SimpleNamespace(page=1, size=20)

        # Mock the adapter's list method directly
        async def mock_adapter_list(user_id, db, params):  # noqa: ARG001
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            # Simulate provider returning only what matches the names filter
            all_agents = [
                SimpleNamespace(
                    id="p-1",
                    name="Agent Alpha",
                    description="",
                    type=DeploymentType.AGENT,
                    provider_data={},
                    created_at=now,
                    updated_at=now,
                ),
                SimpleNamespace(
                    id="p-2",
                    name="Agent Beta",
                    description="",
                    type=DeploymentType.AGENT,
                    provider_data={},
                    created_at=now,
                    updated_at=now,
                ),
            ]
            if params and params.deployment_names:
                all_agents = [a for a in all_agents if a.name in params.deployment_names]

            return SimpleNamespace(deployments=all_agents, total=len(all_agents), provider_data={})

        with patch(
            "langflow.services.adapters.deployment.watsonx_orchestrate.WatsonxOrchestrateDeploymentService.list",
            new_callable=AsyncMock,
            side_effect=mock_adapter_list,
        ):
            # 1. Fetch without names filter
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=True,
                names=None,
            )
            assert response.total == 2
            names = {d["name"] for d in response.provider_data["entries"]}
            assert names == {"Agent Alpha", "Agent Beta"}

            # 2. Fetch with single name filter
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=True,
                names=["Agent Alpha"],
            )
            assert response.total == 1
            assert response.provider_data["entries"][0]["name"] == "Agent Alpha"


@pytest.mark.asyncio
async def test_list_deployments_names_filter_combined(async_session, active_user):
    """Integration test: GET /deployments?names= combined with project_id."""
    with patch("langflow.services.utils.FEATURE_FLAGS.wxo_deployments", new=True):
        register_builtin_adapters()

        project_a = Folder(name=f"project-a-{uuid4()}", user_id=active_user.id)
        project_b = Folder(name=f"project-b-{uuid4()}", user_id=active_user.id)
        async_session.add(project_a)
        async_session.add(project_b)
        await async_session.commit()

        provider_account = await create_provider_account(
            async_session,
            user_id=active_user.id,
            name=f"provider-{uuid4()}",
            provider_key="watsonx-orchestrate",
            provider_url="https://api.example.com",
            provider_tenant_id="tenant-1",
            api_key="secret",  # pragma: allowlist secret
        )

        # Agent Alpha in Project A
        await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            name="Agent Alpha",
            deployment_type=DeploymentType.AGENT,
        )
        # Agent Beta in Project B
        await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_b.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            name="Agent Beta",
            deployment_type=DeploymentType.AGENT,
        )

        provider_id = provider_account.id
        params = SimpleNamespace(page=1, size=20)

        async def mock_fetch_provider_resource_keys(*args, **kwargs):  # noqa: ARG001
            return kwargs.get("resource_keys", [])

        with patch(
            "langflow.api.v1.mappers.deployments.helpers.fetch_provider_resource_keys",
            new_callable=AsyncMock,
            side_effect=mock_fetch_provider_resource_keys,
        ):
            # Fetch with name filter AND project_id filter
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=False,
                names=["Agent Alpha", "Agent Beta"],
                project_id=project_a.id,
            )
            assert response.total == 1
            assert response.deployments[0].name == "Agent Alpha"
