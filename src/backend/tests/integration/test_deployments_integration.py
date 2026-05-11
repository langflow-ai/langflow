from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.deployments import list_deployments
from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper
from langflow.services.database.models.deployment.crud import create_deployment
from langflow.services.database.models.deployment_provider_account.crud import create_provider_account
from langflow.services.database.models.folder.model import Folder
from langflow.services.utils import register_builtin_adapters
from lfx.services.adapters.deployment.schema import DeploymentType


class _FakeDeploymentAdapter:
    def __init__(self, deployments):
        self._deployments = deployments

    async def list(self, *, user_id, db, params=None):  # noqa: ARG002
        deployments = list(self._deployments)
        deployment_ids = {str(value) for value in (getattr(params, "deployment_ids", None) or [])}
        if deployment_ids:
            deployments = [deployment for deployment in deployments if str(deployment.id) in deployment_ids]
        deployment_names = set(getattr(params, "deployment_names", None) or [])
        if deployment_names:
            deployments = [deployment for deployment in deployments if deployment.name in deployment_names]
        return SimpleNamespace(deployments=deployments)


def _provider_deployment(deployment_id: str, name: str):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=deployment_id,
        name=name,
        description="",
        type=DeploymentType.AGENT,
        provider_data={"tool_ids": [], "environments": []},
        created_at=now,
        updated_at=now,
    )


class _NoSnapshotBindingMapper(BaseDeploymentMapper):
    def extract_snapshot_bindings(self, provider_view):
        _ = provider_view
        return []


@pytest.mark.asyncio
async def test_list_deployments_names_filter_db_mode(async_session, active_user):
    """Integration test: DB mode returns display_name and rejects provider-name filters."""
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
            display_name="Agent Alpha",
            deployment_type=DeploymentType.AGENT,
        )
        await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            display_name="Agent Beta",
            deployment_type=DeploymentType.AGENT,
        )
        await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            display_name="Agent Gamma",
            deployment_type=DeploymentType.AGENT,
        )
        provider_id = provider_account.id

        params = SimpleNamespace(page=1, size=20)

        # Mock fetch_provider_resource_keys to return all keys so they aren't deleted
        async def mock_fetch_provider_resource_keys(*args, **kwargs):  # noqa: ARG001
            resource_keys = kwargs.get("resource_keys", [])
            return set(resource_keys), SimpleNamespace(deployments=[])

        with (
            patch(
                "langflow.api.v1.mappers.deployments.helpers.fetch_provider_resource_keys",
                new_callable=AsyncMock,
                side_effect=mock_fetch_provider_resource_keys,
            ),
            patch(
                "langflow.api.v1.deployments.resolve_deployment_adapter",
                return_value=SimpleNamespace(),
            ),
            patch(
                "langflow.api.v1.deployments.get_deployment_mapper",
                return_value=_NoSnapshotBindingMapper(),
            ),
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
            names = {d.display_name for d in response.deployments}
            assert names == {"Agent Alpha", "Agent Beta", "Agent Gamma"}

            # 2. Provider technical-name filters are provider-only after local rows moved to display_name.
            with pytest.raises(HTTPException) as exc_info:
                await list_deployments(
                    provider_id=provider_id,
                    session=async_session,
                    current_user=active_user,
                    params=params,
                    deployment_type=None,
                    load_from_provider=False,
                    names=["Agent Alpha"],
                )
            assert exc_info.value.status_code == 422
            assert (
                exc_info.value.detail
                == "names filtering is only supported when loading deployments directly from the provider."
            )


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

        fake_adapter = _FakeDeploymentAdapter(
            [
                _provider_deployment("p-1", "Agent Alpha"),
                _provider_deployment("p-2", "Agent Beta"),
            ]
        )
        with (
            patch(
                "langflow.api.v1.deployments.resolve_deployment_adapter",
                return_value=fake_adapter,
            ),
            patch(
                "langflow.api.v1.deployments.get_deployment_mapper",
                return_value=_NoSnapshotBindingMapper(),
            ),
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
    """Integration test: DB mode rejects provider-name filters even with project_id."""
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
            display_name="Agent Alpha",
            deployment_type=DeploymentType.AGENT,
        )
        # Agent Beta in Project B
        await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_b.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            display_name="Agent Beta",
            deployment_type=DeploymentType.AGENT,
        )

        provider_id = provider_account.id
        params = SimpleNamespace(page=1, size=20)

        async def mock_fetch_provider_resource_keys(*args, **kwargs):  # noqa: ARG001
            resource_keys = kwargs.get("resource_keys", [])
            return set(resource_keys), SimpleNamespace(deployments=[])

        with (
            patch(
                "langflow.api.v1.mappers.deployments.helpers.fetch_provider_resource_keys",
                new_callable=AsyncMock,
                side_effect=mock_fetch_provider_resource_keys,
            ),
            patch(
                "langflow.api.v1.deployments.resolve_deployment_adapter",
                return_value=SimpleNamespace(),
            ),
            patch(
                "langflow.api.v1.deployments.get_deployment_mapper",
                return_value=_NoSnapshotBindingMapper(),
            ),
        ):
            # Project filtering remains local; provider technical-name filtering does not.
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=False,
                names=None,
                project_id=project_a.id,
            )
            assert response.total == 1
            assert response.deployments[0].display_name == "Agent Alpha"

            with pytest.raises(HTTPException) as exc_info:
                await list_deployments(
                    provider_id=provider_id,
                    session=async_session,
                    current_user=active_user,
                    params=params,
                    deployment_type=None,
                    load_from_provider=False,
                    names=["Agent Alpha", "Agent Beta"],
                    project_id=project_a.id,
                )
            assert exc_info.value.status_code == 422
            assert (
                exc_info.value.detail
                == "names filtering is only supported when loading deployments directly from the provider."
            )
