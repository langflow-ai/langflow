from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.api.v1.deployments import list_deployments
from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper
from langflow.services.database.models.deployment.crud import create_deployment
from langflow.services.database.models.deployment.crud import get_deployment as get_deployment_db
from langflow.services.database.models.deployment_provider_account.crud import create_provider_account
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.utils import register_builtin_adapters
from lfx.services.adapters.deployment.schema import (
    DeploymentGetResult,
    DeploymentListResult,
    DeploymentType,
    ItemResult,
)

pytestmark = pytest.mark.noclient


@pytest.fixture
async def active_user(async_session):
    user = User(username=f"user-{uuid4()}", password="hashed", is_active=True)  # noqa: S106
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


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
        return DeploymentListResult(deployments=deployments)

    async def get(self, *, user_id, deployment_id, db):  # noqa: ARG002
        for deployment in self._deployments:
            if str(deployment.id) == str(deployment_id):
                provider_data = dict(deployment.provider_data or {})
                return DeploymentGetResult(
                    id=deployment.id,
                    name=deployment.name,
                    description=provider_data.get("description"),
                    type=deployment.type,
                    provider_data=provider_data,
                )
        return None


def _provider_deployment(
    deployment_id: str,
    name: str,
    *,
    display_name: str | None = None,
    description: str = "",
) -> ItemResult:
    now = datetime.now(timezone.utc)
    display_label = display_name if display_name is not None else name
    return ItemResult(
        id=deployment_id,
        name=name,
        type=DeploymentType.AGENT,
        provider_data={
            "name": name,
            "display_name": display_label,
            "description": description,
            "tool_ids": [],
            "environments": [],
        },
        created_at=now,
        updated_at=now,
    )


class _NoSnapshotBindingMapper(BaseDeploymentMapper):
    def extract_snapshot_bindings(self, provider_view):
        _ = provider_view
        return []

    def extract_snapshot_bindings_for_get(self, get_result, *, resource_key: str):
        _ = get_result, resource_key
        return []

    def extract_list_item_provider_data(self, provider_view):
        return {str(item.id): dict(item.provider_data) for item in provider_view.deployments}

    def extract_metadata_for_list(self, provider_view):
        return {
            str(item.id): {
                "display_name": item.provider_data["display_name"],
                "description": item.provider_data["description"],
            }
            for item in provider_view.deployments
        }

    def extract_metadata_for_get(self, get_result):
        return {
            "display_name": get_result.provider_data["display_name"],
            "description": get_result.provider_data["description"],
        }

    def shape_deployment_get_data(self, provider_data, *, name=None):  # noqa: ARG002
        return provider_data if isinstance(provider_data, dict) else None


@pytest.mark.asyncio
async def test_list_deployments_db_mode_syncs_display_name(async_session, active_user):
    """Integration test: DB-backed list syncs provider display_name into deployment rows."""
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

        deployment_alpha = await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            display_name="Agent Alpha",
            deployment_type=DeploymentType.AGENT,
        )
        deployment_beta = await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            display_name="Agent Beta",
            deployment_type=DeploymentType.AGENT,
        )
        deployment_gamma = await create_deployment(
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
        provider_items_by_resource_key = {
            deployment.resource_key: _provider_deployment(
                deployment.resource_key,
                f"tech-{idx}",
                display_name=deployment.display_name,
                description=deployment.description or "",
            )
            for idx, deployment in enumerate([deployment_alpha, deployment_beta, deployment_gamma], start=1)
        }

        async def mock_fetch_provider_resource_keys(*args, **kwargs):  # noqa: ARG001
            resource_keys = kwargs.get("resource_keys", [])
            return set(resource_keys), DeploymentListResult(
                deployments=[provider_items_by_resource_key[resource_key] for resource_key in resource_keys]
            )

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
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=False,
            )
            assert response.total == 3
            await async_session.commit()
            for deployment in (deployment_alpha, deployment_beta, deployment_gamma):
                await async_session.refresh(deployment)
            assert {
                deployment_alpha.display_name,
                deployment_beta.display_name,
                deployment_gamma.display_name,
            } == {"Agent Alpha", "Agent Beta", "Agent Gamma"}


@pytest.mark.asyncio
async def test_list_deployments_provider_mode_lists_entries(async_session, active_user):
    """Integration test: load_from_provider lists provider-owned deployment entries."""
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
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=True,
            )
            assert response.total == 2
            names = {entry["name"] for entry in response.provider_data["entries"]}
            assert names == {"Agent Alpha", "Agent Beta"}


@pytest.mark.asyncio
async def test_list_deployments_project_id_filter_db_mode(async_session, active_user):
    """Integration test: DB-backed list filters by project_id and syncs display_name."""
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
        deployment_alpha = await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project_a.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            display_name="Agent Alpha",
            deployment_type=DeploymentType.AGENT,
        )
        # Agent Beta in Project B
        deployment_beta = await create_deployment(
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
        provider_items_by_resource_key = {
            deployment.resource_key: _provider_deployment(
                deployment.resource_key,
                f"tech-{idx}",
                display_name=deployment.display_name,
                description=deployment.description or "",
            )
            for idx, deployment in enumerate([deployment_alpha, deployment_beta], start=1)
        }

        async def mock_fetch_provider_resource_keys(*args, **kwargs):  # noqa: ARG001
            resource_keys = kwargs.get("resource_keys", [])
            return set(resource_keys), DeploymentListResult(
                deployments=[provider_items_by_resource_key[resource_key] for resource_key in resource_keys]
            )

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
            response = await list_deployments(
                provider_id=provider_id,
                session=async_session,
                current_user=active_user,
                params=params,
                deployment_type=None,
                load_from_provider=False,
                project_id=project_a.id,
            )
            assert response.total == 1
            await async_session.commit()
            await async_session.refresh(deployment_alpha)
            assert deployment_alpha.display_name == "Agent Alpha"


@pytest.mark.asyncio
async def test_get_deployment_synced_updates_provider_metadata_in_db(async_session, active_user):
    project = Folder(name=f"project-get-sync-{uuid4()}", user_id=active_user.id)
    async_session.add(project)
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
    deployment = await create_deployment(
        async_session,
        user_id=active_user.id,
        project_id=project.id,
        deployment_provider_account_id=provider_account.id,
        resource_key=f"rk-{uuid4()}",
        display_name="Local stale name",
        description="Local stale description",
        deployment_type=DeploymentType.AGENT,
    )
    await async_session.commit()
    await async_session.refresh(deployment)
    original_updated_at = deployment.updated_at

    provider_deployment = _provider_deployment(
        deployment.resource_key,
        "technical-agent-name",
        display_name="Provider display name",
        description="Provider description",
    )

    from langflow.api.v1.mappers.deployments.helpers import get_deployment_synced

    synced_deployment, provider_result, attached_count = await get_deployment_synced(
        deployment_adapter=_FakeDeploymentAdapter([provider_deployment]),
        deployment_mapper=_NoSnapshotBindingMapper(),
        deployment=deployment,
        provider_key="watsonx-orchestrate",
        user_id=active_user.id,
        db=async_session,
    )
    await async_session.commit()

    fetched = await get_deployment_db(async_session, user_id=active_user.id, deployment_id=deployment.id)
    assert fetched is not None
    assert synced_deployment is deployment
    assert provider_result.id == deployment.resource_key
    assert attached_count == 0
    assert deployment.display_name == "Provider display name"
    assert deployment.description == "Provider description"
    assert fetched.display_name == "Provider display name"
    assert fetched.description == "Provider description"
    assert fetched.updated_at == original_updated_at


@pytest.mark.asyncio
async def test_list_deployments_syncs_provider_metadata_in_db(async_session, active_user):
    with patch("langflow.services.utils.FEATURE_FLAGS.wxo_deployments", new=True):
        register_builtin_adapters()

        project = Folder(name=f"project-list-sync-{uuid4()}", user_id=active_user.id)
        async_session.add(project)
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
        deployment = await create_deployment(
            async_session,
            user_id=active_user.id,
            project_id=project.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=f"rk-{uuid4()}",
            display_name="Local stale name",
            description="Local stale description",
            deployment_type=DeploymentType.AGENT,
        )
        await async_session.commit()
        await async_session.refresh(deployment)
        original_updated_at = deployment.updated_at
        provider_deployment = _provider_deployment(
            deployment.resource_key,
            "technical-agent-name",
            display_name="Provider display name",
            description="Provider description",
        )

        with (
            patch(
                "langflow.api.v1.deployments.resolve_deployment_adapter",
                return_value=_FakeDeploymentAdapter([provider_deployment]),
            ),
            patch(
                "langflow.api.v1.deployments.get_deployment_mapper",
                return_value=_NoSnapshotBindingMapper(),
            ),
        ):
            response = await list_deployments(
                provider_id=provider_account.id,
                session=async_session,
                current_user=active_user,
                params=SimpleNamespace(page=1, size=20),
                deployment_type=None,
                load_from_provider=False,
            )
        await async_session.commit()

        fetched = await get_deployment_db(async_session, user_id=active_user.id, deployment_id=deployment.id)
        assert fetched is not None
        assert response.total == 1
        assert response.deployments[0].description == "Provider description"
        assert fetched.display_name == "Provider display name"
        assert fetched.description == "Provider description"
        assert fetched.updated_at == original_updated_at
