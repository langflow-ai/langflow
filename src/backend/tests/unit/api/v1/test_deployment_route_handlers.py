"""Route-handler-level tests for deployment endpoints.

Covers the integration behaviour of the FastAPI route handlers:
- Rollback on commit failure (create / update)
- GET single-deployment synchronization (deployment-level and snapshot-level)
- Project-scoped flow-version validation (create / update)
- resolve_deployment_adapter edge cases
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.schemas.deployments import (
    DeploymentLlmListResponse,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountUpdateRequest,
    DeploymentUpdateRequest,
    SnapshotUpdateRequest,
)
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from lfx.services.adapters.deployment.exceptions import (
    AuthenticationError,
    DeploymentNotFoundError,
    ResourceConflictError,
    ServiceUnavailableError,
)
from lfx.services.adapters.deployment.schema import (
    ConfigListItem,
    ConfigListResult,
    DeploymentCreateResult,
    DeploymentListResult,
    DeploymentUpdateResult,
    ItemResult,
    SnapshotItem,
    SnapshotListResult,
)

ROUTES_MODULE = "langflow.api.v1.deployments"
HELPERS_MODULE = "langflow.api.v1.mappers.deployments.helpers"


# ---------------------------------------------------------------------------
# Shared factories
# ---------------------------------------------------------------------------


def _fake_provider_account(
    *,
    provider_key: str = DeploymentProviderKey.WATSONX_ORCHESTRATE,
    provider_url: str = "https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
    api_key: str = "encrypted-key",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        provider_key=provider_key,
        provider_url=provider_url,
        api_key=api_key,
    )


def _fake_deployment_row(**overrides) -> SimpleNamespace:
    return SimpleNamespace(
        id=overrides.get("id", uuid4()),
        resource_key=overrides.get("resource_key", "rk-1"),
        name=overrides.get("name", "test-deployment"),
        description=overrides.get("description"),
        deployment_type=overrides.get("deployment_type", "agent"),
        deployment_provider_account_id=overrides.get("deployment_provider_account_id", uuid4()),
        project_id=overrides.get("project_id", uuid4()),
        created_at=overrides.get("created_at"),
        updated_at=overrides.get("updated_at"),
    )


def _fake_user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _fake_attachment(*, provider_snapshot_id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        flow_version_id=uuid4(),
        provider_snapshot_id=provider_snapshot_id,
        deployment_id=uuid4(),
    )


# ---------------------------------------------------------------------------
# create_deployment: rollback on commit failure
# ---------------------------------------------------------------------------


class TestCreateDeploymentRollback:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.rollback_provider_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_snapshot_map_for_create", return_value={})
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_rollback_called_on_commit_failure(
        self,
        mock_get_pa,
        mock_name_exists,  # noqa: ARG002
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,  # noqa: ARG002
        mock_create_db,
        mock_resolve_snap,  # noqa: ARG002
        mock_attach,  # noqa: ARG002
        mock_rollback,
    ):
        """When session.commit() fails, rollback_provider_create is called."""
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        create_result = DeploymentCreateResult(
            id="provider-dep-1",
            provider_result={"app_ids": ["cfg-1"], "tools_with_refs": [{"tool_id": "tool-1", "source_ref": "fv-1"}]},
        )
        adapter.create.return_value = create_result
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_create_flow_version_ids.return_value = []
        mapper.util_existing_deployment_resource_key_for_create.return_value = None
        mapper.resolve_deployment_create = AsyncMock(return_value=MagicMock())
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        mock_create_db.return_value = _fake_deployment_row()

        session = AsyncMock()
        session.commit.side_effect = RuntimeError("DB commit failed")

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "test"
        payload.type = "agent"
        payload.description = None

        with pytest.raises(RuntimeError, match="DB commit failed"):
            await create_deployment(session=session, payload=payload, current_user=_fake_user())

        mock_rollback.assert_awaited_once()
        assert mock_rollback.call_args.kwargs["resource_id"] == create_result.id
        assert mock_rollback.call_args.kwargs["provider_result"] == create_result.provider_result

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.rollback_provider_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_snapshot_map_for_create", return_value={})
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_no_rollback_on_success(
        self,
        mock_get_pa,
        mock_name_exists,  # noqa: ARG002
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,  # noqa: ARG002
        mock_create_db,
        mock_resolve_snap,  # noqa: ARG002
        mock_attach,  # noqa: ARG002
        mock_rollback,
    ):
        """On successful commit, rollback is NOT called."""
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        create_result = DeploymentCreateResult(id="provider-dep-1")
        adapter.create.return_value = create_result
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_create_flow_version_ids.return_value = []
        mapper.util_existing_deployment_resource_key_for_create.return_value = None
        mapper.resolve_deployment_create = AsyncMock(return_value=MagicMock())
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        dep_row = _fake_deployment_row()
        mock_create_db.return_value = dep_row

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "test"
        payload.type = "agent"
        payload.description = None

        mapper.shape_deployment_create_result.return_value = MagicMock()
        await create_deployment(session=session, payload=payload, current_user=_fake_user())

        mock_rollback.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.rollback_provider_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_snapshot_map_for_create", return_value={})
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_deployment_by_resource_key", new_callable=AsyncMock, return_value=None)
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_existing_agent_mutation_commit_failure_uses_non_delete_rollback(
        self,
        mock_get_pa,
        mock_name_exists,  # noqa: ARG002
        mock_get_by_resource_key,  # noqa: ARG002
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,  # noqa: ARG002
        mock_create_db,
        mock_resolve_snap,  # noqa: ARG002
        mock_attach,  # noqa: ARG002
        mock_rollback,
    ):
        """Commit failure after existing-agent mutation triggers rollback without delete fallback."""
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        adapter.update.return_value = DeploymentUpdateResult(id="existing-agent-1", provider_result={"ok": True})
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_existing_deployment_resource_key_for_create.return_value = "existing-agent-1"
        mapper.util_should_mutate_provider_for_existing_deployment_create.return_value = True
        mapper.util_create_flow_version_ids.return_value = []
        mapper.resolve_deployment_update_for_existing_create = AsyncMock(return_value=MagicMock())
        mapper.util_create_result_from_existing_update.return_value = DeploymentCreateResult(
            id="existing-agent-1",
            provider_result={"app_ids": ["app-1"]},
        )
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        mock_create_db.return_value = _fake_deployment_row(resource_key="existing-agent-1")

        session = AsyncMock()
        session.commit.side_effect = RuntimeError("DB commit failed")

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "existing"
        payload.type = "agent"
        payload.description = "desc"

        with pytest.raises(RuntimeError, match="DB commit failed"):
            await create_deployment(session=session, payload=payload, current_user=_fake_user())

        mock_rollback.assert_awaited_once()
        assert mock_rollback.call_args.kwargs["resource_id"] == "existing-agent-1"
        assert mock_rollback.call_args.kwargs["allow_delete_fallback"] is False


# ---------------------------------------------------------------------------
# create_deployment: existing_agent_id behavior
# ---------------------------------------------------------------------------


class TestCreateDeploymentExistingAgent:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_deployment_by_resource_key", new_callable=AsyncMock, return_value=None)
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_existing_agent_without_mutation_skips_provider_calls(
        self,
        mock_get_pa,
        mock_name_exists,
        mock_get_by_resource_key,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,
        mock_create_db,
        mock_attach,
    ):
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_existing_deployment_resource_key_for_create.return_value = "existing-agent-1"
        mapper.util_should_mutate_provider_for_existing_deployment_create.return_value = False
        mapper.util_create_flow_version_ids.return_value = []
        mapper.util_create_result_from_existing_resource.return_value = DeploymentCreateResult(id="existing-agent-1")
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        dep_row = _fake_deployment_row(resource_key="existing-agent-1")
        mock_create_db.return_value = dep_row

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "existing"
        payload.type = "agent"
        payload.description = None

        mapper.shape_deployment_create_result.return_value = MagicMock()
        await create_deployment(session=session, payload=payload, current_user=_fake_user())

        _ = (mock_name_exists, mock_get_by_resource_key, mock_validate_fv, mock_attach)
        adapter.create.assert_not_awaited()
        adapter.update.assert_not_awaited()
        mapper.util_create_result_from_existing_resource.assert_called_once_with(
            existing_resource_key="existing-agent-1"
        )
        assert mock_create_db.call_args.kwargs["resource_key"] == "existing-agent-1"

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_deployment_by_resource_key", new_callable=AsyncMock, return_value=None)
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_existing_agent_with_mutation_uses_provider_update(
        self,
        mock_get_pa,
        mock_name_exists,
        mock_get_by_resource_key,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,
        mock_create_db,
        mock_attach,
    ):
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        adapter.update.return_value = DeploymentUpdateResult(id="existing-agent-1", provider_result={"ok": True})
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_existing_deployment_resource_key_for_create.return_value = "existing-agent-1"
        mapper.util_should_mutate_provider_for_existing_deployment_create.return_value = True
        mapper.util_create_flow_version_ids.return_value = []
        mapper.resolve_deployment_update_for_existing_create = AsyncMock(
            return_value=MagicMock(provider_data={"upsert_flows": []})
        )
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        dep_row = _fake_deployment_row(resource_key="existing-agent-1")
        mock_create_db.return_value = dep_row

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "existing"
        payload.type = "agent"
        payload.description = "desc"

        mapper.shape_deployment_create_result.return_value = MagicMock()
        await create_deployment(session=session, payload=payload, current_user=_fake_user())

        _ = (mock_name_exists, mock_get_by_resource_key, mock_validate_fv, mock_attach)
        adapter.create.assert_not_awaited()
        adapter.update.assert_awaited_once()
        mapper.resolve_deployment_update_for_existing_create.assert_awaited_once()
        assert adapter.update.call_args.kwargs["deployment_id"] == "existing-agent-1"

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_deployment_by_resource_key", new_callable=AsyncMock, return_value=None)
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_existing_agent_with_mutation_uses_mapper_create_result_normalizer(
        self,
        mock_get_pa,
        mock_name_exists,
        mock_get_by_resource_key,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,
        mock_create_db,
        mock_attach,
    ):
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        adapter.update.return_value = DeploymentUpdateResult(
            id="existing-agent-1",
            provider_result={"ok": True},
        )
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_existing_deployment_resource_key_for_create.return_value = "existing-agent-1"
        mapper.util_should_mutate_provider_for_existing_deployment_create.return_value = True
        mapper.util_create_flow_version_ids.return_value = []
        mapper.resolve_deployment_update_for_existing_create = AsyncMock(
            return_value=MagicMock(provider_data={"upsert_flows": []})
        )
        mapped_create_result = DeploymentCreateResult(id="existing-agent-1", provider_result={"ok": True})
        mapper.util_create_result_from_existing_update.return_value = mapped_create_result
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        dep_row = _fake_deployment_row(resource_key="existing-agent-1")
        mock_create_db.return_value = dep_row

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "existing"
        payload.type = "agent"
        payload.description = "desc"

        mapper.shape_deployment_create_result.return_value = MagicMock()
        await create_deployment(session=session, payload=payload, current_user=_fake_user())

        _ = (mock_name_exists, mock_get_by_resource_key, mock_validate_fv, mock_attach)
        adapter.create.assert_not_awaited()
        adapter.update.assert_awaited_once()
        mapper.resolve_deployment_update_for_existing_create.assert_awaited_once()
        assert adapter.update.call_args.kwargs["deployment_id"] == "existing-agent-1"
        mapper.util_create_result_from_existing_update.assert_called_once_with(
            existing_resource_key="existing-agent-1",
            result=adapter.update.return_value,
        )
        mapper.shape_deployment_create_result.assert_called_once_with(
            mapped_create_result,
            dep_row,
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        )

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_deployment_by_resource_key", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_existing_agent_conflict_when_resource_key_already_persisted(
        self,
        mock_get_pa,
        mock_name_exists,
        mock_get_by_resource_key,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_create_db,
    ):
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        mock_get_by_resource_key.return_value = _fake_deployment_row(resource_key="existing-agent-1")
        adapter = AsyncMock()
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_existing_deployment_resource_key_for_create.return_value = "existing-agent-1"
        mock_get_mapper.return_value = mapper

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "existing"
        payload.type = "agent"
        payload.description = None

        with pytest.raises(HTTPException) as exc_info:
            await create_deployment(session=AsyncMock(), payload=payload, current_user=_fake_user())

        assert exc_info.value.status_code == 409
        _ = mock_name_exists
        mock_create_db.assert_not_awaited()
        adapter.create.assert_not_awaited()
        adapter.update.assert_not_awaited()


# ---------------------------------------------------------------------------
# list_deployments: provider passthrough mode
# ---------------------------------------------------------------------------


class TestListDeploymentsLoadFromProvider:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_load_from_provider_bypasses_db_view(
        self,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_list_synced,
    ):
        from langflow.api.v1.deployments import list_deployments

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        adapter.list.return_value = DeploymentListResult(
            deployments=[ItemResult(id="agent-1", name="Agent 1", type="agent")]
        )
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        expected = MagicMock()
        mapper.shape_deployment_list_result.return_value = expected
        mock_get_mapper.return_value = mapper

        result = await list_deployments(
            provider_id=pa.id,
            session=AsyncMock(),
            current_user=_fake_user(),
            params=SimpleNamespace(page=2, size=50),
            deployment_type=None,
            load_from_provider=True,
            flow_version_ids=None,
        )

        assert result is expected
        mock_list_synced.assert_not_awaited()
        adapter.list.assert_awaited_once()
        mapper.shape_deployment_list_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_from_provider_rejects_flow_version_filters(self):
        from langflow.api.v1.deployments import list_deployments

        with pytest.raises(HTTPException) as exc_info:
            await list_deployments(
                provider_id=uuid4(),
                session=AsyncMock(),
                current_user=_fake_user(),
                params=SimpleNamespace(page=1, size=20),
                deployment_type=None,
                load_from_provider=True,
                flow_version_ids=[str(uuid4())],
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_load_from_provider_rejects_flow_ids_filter(self):
        from langflow.api.v1.deployments import list_deployments

        with pytest.raises(HTTPException) as exc_info:
            await list_deployments(
                provider_id=uuid4(),
                session=AsyncMock(),
                current_user=_fake_user(),
                params=SimpleNamespace(page=1, size=20),
                deployment_type=None,
                load_from_provider=True,
                flow_ids=[str(uuid4())],
            )
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# list_deployments: flow_ids filter
# ---------------------------------------------------------------------------


class TestListDeploymentsFlowIdsFilter:
    @pytest.mark.asyncio
    async def test_flow_ids_and_flow_version_ids_mutually_exclusive(self):
        from langflow.api.v1.deployments import list_deployments

        with pytest.raises(HTTPException) as exc_info:
            await list_deployments(
                provider_id=uuid4(),
                session=AsyncMock(),
                current_user=_fake_user(),
                params=SimpleNamespace(page=1, size=20),
                deployment_type=None,
                load_from_provider=False,
                flow_version_ids=[str(uuid4())],
                flow_ids=[str(uuid4())],
            )
        assert exc_info.value.status_code == 422
        assert "mutually exclusive" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.flow_version_ids_for_flows", new_callable=AsyncMock, return_value=[])
    async def test_flow_ids_no_versions_returns_empty(self, mock_fv_for_flows):
        from langflow.api.v1.deployments import list_deployments

        result = await list_deployments(
            provider_id=uuid4(),
            session=AsyncMock(),
            current_user=_fake_user(),
            params=SimpleNamespace(page=1, size=20),
            deployment_type=None,
            load_from_provider=False,
            flow_ids=[str(uuid4())],
        )

        assert result.deployments == []
        assert result.total == 0
        mock_fv_for_flows.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.flow_version_ids_for_flows", new_callable=AsyncMock)
    async def test_flow_ids_resolves_to_flow_version_ids(
        self,
        mock_fv_for_flows,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_list_synced,
    ):
        from langflow.api.v1.deployments import list_deployments

        fv_id = uuid4()
        mock_fv_for_flows.return_value = [fv_id]

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        mock_resolve_adapter.return_value = AsyncMock()

        mapper = MagicMock()
        mapper.shape_deployment_list_items.return_value = []
        mock_get_mapper.return_value = mapper

        mock_list_synced.return_value = ([], 0)

        await list_deployments(
            provider_id=pa.id,
            session=AsyncMock(),
            current_user=_fake_user(),
            params=SimpleNamespace(page=1, size=20),
            deployment_type=None,
            load_from_provider=False,
            flow_ids=[str(uuid4())],
        )

        mock_list_synced.assert_awaited_once()
        call_kwargs = mock_list_synced.call_args.kwargs
        assert call_kwargs["flow_version_ids"] == [fv_id]


# ---------------------------------------------------------------------------
# list_deployments: project_id filter
# ---------------------------------------------------------------------------


class TestListDeploymentsProjectIdFilter:
    @pytest.mark.asyncio
    async def test_load_from_provider_rejects_project_id(self):
        """project_id filtering is not supported when load_from_provider=true."""
        from langflow.api.v1.deployments import list_deployments

        with pytest.raises(HTTPException) as exc_info:
            await list_deployments(
                provider_id=uuid4(),
                session=AsyncMock(),
                current_user=_fake_user(),
                params=SimpleNamespace(page=1, size=20),
                deployment_type=None,
                load_from_provider=True,
                project_id=uuid4(),
            )
        assert exc_info.value.status_code == 422
        assert "project_id" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_project_id_threaded_to_synced(
        self,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_list_synced,
    ):
        """When project_id is supplied it is forwarded to list_deployments_synced."""
        from langflow.api.v1.deployments import list_deployments

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        mock_resolve_adapter.return_value = MagicMock()
        mapper = MagicMock()
        mapper.shape_deployment_list_items.return_value = []
        mock_get_mapper.return_value = mapper
        mock_list_synced.return_value = ([], 0)

        pid = uuid4()
        await list_deployments(
            provider_id=pa.id,
            session=AsyncMock(),
            current_user=_fake_user(),
            params=SimpleNamespace(page=1, size=20),
            deployment_type=None,
            load_from_provider=False,
            project_id=pid,
        )

        mock_list_synced.assert_awaited_once()
        assert mock_list_synced.call_args.kwargs["project_id"] == pid

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_project_id_none_when_omitted(
        self,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_list_synced,
    ):
        """When project_id is not supplied, None is forwarded (no filter)."""
        from langflow.api.v1.deployments import list_deployments

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        mock_resolve_adapter.return_value = MagicMock()
        mapper = MagicMock()
        mapper.shape_deployment_list_items.return_value = []
        mock_get_mapper.return_value = mapper
        mock_list_synced.return_value = ([], 0)

        await list_deployments(
            provider_id=pa.id,
            session=AsyncMock(),
            current_user=_fake_user(),
            params=SimpleNamespace(page=1, size=20),
            deployment_type=None,
            load_from_provider=False,
        )

        mock_list_synced.assert_awaited_once()
        assert mock_list_synced.call_args.kwargs["project_id"] is None


# ---------------------------------------------------------------------------
# config/snapshot passthrough listing routes
# ---------------------------------------------------------------------------


class TestConfigAndSnapshotListRoutes:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_list_configs_global_scope_uses_provider_id(
        self,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
    ):
        from langflow.api.v1.deployments import list_deployment_configs

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        adapter.list_configs.return_value = ConfigListResult(
            configs=[
                ConfigListItem(id="cfg-1", name="Config 1"),
                ConfigListItem(id="cfg-2", name="Config 2"),
            ],
            provider_result={},
        )
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        adapter_params = MagicMock()
        expected_response = MagicMock()
        mapper.resolve_config_list_adapter_params = AsyncMock(return_value=adapter_params)
        mapper.shape_config_list_result.return_value = expected_response
        mock_get_mapper.return_value = mapper

        result = await list_deployment_configs(
            provider_id=pa.id,
            deployment_id=None,
            page=1,
            size=10,
            session=AsyncMock(),
            current_user=_fake_user(),
        )

        assert result is expected_response
        mapper.resolve_config_list_adapter_params.assert_awaited_once_with(
            deployment_resource_key=None,
            provider_params=None,
            db=ANY,
        )
        call_params = adapter.list_configs.call_args.kwargs["params"]
        assert call_params is adapter_params
        mapper.shape_config_list_result.assert_called_once_with(
            adapter.list_configs.return_value,
            page=1,
            size=10,
        )

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.get_deployment_row_or_404", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_list_snapshots_deployment_scope_resolves_provider_from_deployment(
        self,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_get_deployment,
    ):
        from langflow.api.v1.deployments import list_deployment_snapshots

        pa = _fake_provider_account()
        deployment = _fake_deployment_row(resource_key="dep-key")
        deployment.deployment_provider_account_id = pa.id
        mock_get_deployment.return_value = deployment
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        adapter.list_snapshots.return_value = SnapshotListResult(
            snapshots=[
                SnapshotItem(id="tool-1", name="Tool 1"),
                SnapshotItem(id="tool-2", name="Tool 2"),
            ],
            provider_result={"deployment_id": "dep-1"},
        )
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        adapter_params = MagicMock()
        expected_response = MagicMock()
        mapper.resolve_snapshot_list_adapter_params = AsyncMock(return_value=adapter_params)
        mapper.shape_snapshot_list_result.return_value = expected_response
        mock_get_mapper.return_value = mapper

        result = await list_deployment_snapshots(
            provider_id=pa.id,
            deployment_id=deployment.id,
            page=1,
            size=10,
            session=AsyncMock(),
            current_user=_fake_user(),
        )

        assert result is expected_response
        mapper.resolve_snapshot_list_adapter_params.assert_awaited_once_with(
            deployment_resource_key="dep-key",
            provider_params=None,
            db=ANY,
        )
        call_params = adapter.list_snapshots.call_args.kwargs["params"]
        assert call_params is adapter_params
        mapper.shape_snapshot_list_result.assert_called_once_with(
            adapter.list_snapshots.return_value,
            page=1,
            size=10,
        )


# ---------------------------------------------------------------------------
# update_snapshot
# ---------------------------------------------------------------------------


class TestUpdateSnapshotRoute:
    @pytest.mark.asyncio
    @patch("langflow.services.database.models.flow_version.crud.get_flow_version_entry", new_callable=AsyncMock)
    @patch("langflow.services.database.models.deployment.crud.get_deployment", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.update_flow_version_by_provider_snapshot_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.get_attachment_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_updates_all_attachment_rows_for_snapshot(
        self,
        mock_get_attachment,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_update_rows,
        mock_get_deployment_row,
        mock_get_flow_version,
    ):
        from langflow.api.v1.deployments import update_snapshot

        user = _fake_user()
        flow_id = uuid4()
        target_flow_version_id = uuid4()
        attachment = SimpleNamespace(
            flow_version_id=uuid4(),
            deployment_id=uuid4(),
            provider_snapshot_id="tool-1",
        )
        deployment = _fake_deployment_row(
            id=attachment.deployment_id,
            deployment_provider_account_id=uuid4(),
        )
        provider_account = _fake_provider_account()
        provider_account.id = deployment.deployment_provider_account_id

        mock_get_attachment.return_value = attachment
        mock_get_deployment_row.return_value = deployment
        mock_get_flow_version.return_value = SimpleNamespace(id=target_flow_version_id, flow_id=flow_id, data={})
        mock_get_pa.return_value = provider_account
        adapter = AsyncMock()
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.resolve_snapshot_update_artifact.return_value = {"artifact": "payload"}
        mock_get_mapper.return_value = mapper
        mock_update_rows.return_value = 2

        session = AsyncMock()
        session.get.return_value = SimpleNamespace(id=flow_id)

        response = await update_snapshot(
            provider_snapshot_id=" tool-1 ",
            body=SnapshotUpdateRequest(flow_version_id=target_flow_version_id),
            session=session,
            current_user=user,
        )

        assert response.flow_version_id == target_flow_version_id
        assert response.provider_snapshot_id == "tool-1"
        mock_get_attachment.assert_awaited_once_with(
            session,
            user_id=user.id,
            provider_snapshot_id="tool-1",
        )
        mock_update_rows.assert_awaited_once_with(
            session,
            user_id=user.id,
            provider_snapshot_id="tool-1",
            flow_version_id=target_flow_version_id,
        )
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("langflow.services.database.models.flow_version.crud.get_flow_version_entry", new_callable=AsyncMock)
    @patch("langflow.services.database.models.deployment.crud.get_deployment", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.update_flow_version_by_provider_snapshot_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.get_attachment_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_commit_failure_attempts_provider_compensation(
        self,
        mock_get_attachment,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_update_rows,
        mock_get_deployment_row,
        mock_get_flow_version,
    ):
        from langflow.api.v1.deployments import update_snapshot

        user = _fake_user()
        flow_id = uuid4()
        previous_flow_version_id = uuid4()
        target_flow_version_id = uuid4()
        attachment = SimpleNamespace(
            flow_version_id=previous_flow_version_id,
            deployment_id=uuid4(),
            provider_snapshot_id="tool-1",
        )
        deployment = _fake_deployment_row(
            id=attachment.deployment_id,
            deployment_provider_account_id=uuid4(),
        )
        provider_account = _fake_provider_account()
        provider_account.id = deployment.deployment_provider_account_id

        target_version = SimpleNamespace(id=target_flow_version_id, flow_id=flow_id, data={"nodes": []})
        previous_version = SimpleNamespace(id=previous_flow_version_id, flow_id=flow_id, data={"nodes": []})
        mock_get_flow_version.side_effect = [target_version, previous_version]
        mock_get_attachment.return_value = attachment
        mock_get_deployment_row.return_value = deployment
        mock_get_pa.return_value = provider_account
        adapter = AsyncMock()
        adapter.update_snapshot.return_value = None
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.resolve_snapshot_update_artifact.side_effect = [{"artifact": "new"}, {"artifact": "previous"}]
        mock_get_mapper.return_value = mapper
        mock_update_rows.return_value = 2

        session = AsyncMock()
        session.get.return_value = SimpleNamespace(id=flow_id)
        session.commit.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            await update_snapshot(
                provider_snapshot_id="tool-1",
                body=SnapshotUpdateRequest(flow_version_id=target_flow_version_id),
                session=session,
                current_user=user,
            )

        session.commit.assert_awaited_once()
        session.rollback.assert_awaited_once()
        assert adapter.update_snapshot.await_count == 2


# ---------------------------------------------------------------------------
# list_deployment_flow_versions
# ---------------------------------------------------------------------------


class TestListDeploymentFlowVersionsRoute:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.list_deployment_flow_versions_synced", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_returns_paginated_flow_versions(
        self,
        mock_resolve,
        mock_list_flow_versions_synced,
    ):
        from langflow.api.v1.deployments import list_deployment_flow_versions

        deployment_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        rows = [(SimpleNamespace(provider_snapshot_id="tool-1", created_at=None), SimpleNamespace())]
        snapshot_result = SnapshotListResult(
            snapshots=[
                SnapshotItem(
                    id="tool-1",
                    name="Tool 1",
                    provider_data={"connections": {"cfg-1": "conn-1"}},
                )
            ]
        )
        mock_resolve.return_value = (deployment_row, adapter, mapper, "watsonx-orchestrate")
        mock_list_flow_versions_synced.return_value = (rows, 7, snapshot_result)
        mapper.shape_flow_version_list_result.return_value = SimpleNamespace(
            page=2,
            size=5,
            total=7,
            flow_versions=[
                SimpleNamespace(
                    provider_snapshot_id="tool-1",
                    provider_data={"app_ids": ["cfg-1"]},
                )
            ],
        )

        flow_id = uuid4()
        response = await list_deployment_flow_versions(
            deployment_id=deployment_row.id,
            session=AsyncMock(),
            current_user=_fake_user(),
            page=2,
            size=5,
            flow_ids=[flow_id],
        )

        assert response.page == 2
        assert response.size == 5
        assert response.total == 7
        assert len(response.flow_versions) == 1
        assert response.flow_versions[0].provider_snapshot_id == "tool-1"
        assert response.flow_versions[0].provider_data == {"app_ids": ["cfg-1"]}

        mock_list_flow_versions_synced.assert_awaited_once()
        helper_kwargs = mock_list_flow_versions_synced.call_args.kwargs
        assert helper_kwargs["provider_id"] == deployment_row.deployment_provider_account_id
        assert helper_kwargs["deployment_id"] == deployment_row.id
        assert helper_kwargs["page"] == 2
        assert helper_kwargs["size"] == 5
        assert helper_kwargs["flow_ids"] == [flow_id]
        mapper.shape_flow_version_list_result.assert_called_once_with(
            rows=rows,
            snapshot_result=snapshot_result,
            page=2,
            size=5,
            total=7,
        )


# ---------------------------------------------------------------------------
# provider account routes
# ---------------------------------------------------------------------------


class TestProviderAccountRoutes:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.update_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_update_provider_account_name_only_skips_credential_verification(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_update_provider_account,
    ):
        """PATCH skips credential verification when only name changes."""
        from langflow.api.v1.deployments import update_provider_account

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account
        mapper = MagicMock()
        mapper.resolve_provider_account_update.return_value = {"name": "renamed"}
        mock_get_mapper.return_value = mapper
        mock_update_provider_account.return_value = existing_account

        session = AsyncMock()
        await update_provider_account(
            provider_id=existing_account.id,
            session=session,
            payload=DeploymentProviderAccountUpdateRequest(name="renamed"),
            current_user=_fake_user(),
        )

        mapper.resolve_verify_credentials_for_update.assert_not_called()
        mock_resolve_adapter.assert_not_called()
        mock_update_provider_account.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.update_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_update_provider_account_verify_failure_returns_401(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_update_provider_account,
    ):
        """PATCH verifies new credentials before persisting them."""
        from langflow.api.v1.deployments import update_provider_account

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account

        mapper = MagicMock()
        mapper.resolve_verify_credentials_for_update.return_value = MagicMock()
        mock_get_mapper.return_value = mapper

        adapter = AsyncMock()
        adapter.verify_credentials.side_effect = AuthenticationError(
            message="bad creds",
            error_code="authentication_error",
        )
        mock_resolve_adapter.return_value = adapter

        with pytest.raises(HTTPException) as exc_info:
            await update_provider_account(
                provider_id=existing_account.id,
                session=AsyncMock(),
                payload=DeploymentProviderAccountUpdateRequest(provider_data={"api_key": "new-api-key"}),
                current_user=_fake_user(),
            )

        assert exc_info.value.status_code == 401
        mock_update_provider_account.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.create_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    async def test_create_provider_account_conflict_returns_409(
        self,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_create_provider_account,
    ):
        """POST converts duplicate provider-account conflicts into 409 responses."""
        from langflow.api.v1.deployments import create_provider_account

        mapper = MagicMock()
        mapper.resolve_verify_credentials_for_create.return_value = MagicMock()
        mapper.resolve_provider_account_create.return_value = MagicMock()
        mock_get_mapper.return_value = mapper

        adapter = AsyncMock()
        mock_resolve_adapter.return_value = adapter
        mock_create_provider_account.side_effect = ValueError("Provider account already exists")

        payload = DeploymentProviderAccountCreateRequest(
            name="prod",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            provider_data={
                "url": "https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
                "api_key": "api-key",  # pragma: allowlist secret
            },
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_provider_account(
                session=AsyncMock(),
                payload=payload,
                current_user=_fake_user(),
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Provider account is already tracked by user."

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.update_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_update_provider_account_conflict_returns_409(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_update_provider_account,
    ):
        """PATCH converts duplicate provider-account conflicts into 409 responses."""
        from langflow.api.v1.deployments import update_provider_account

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account

        mapper = MagicMock()
        mapper.resolve_verify_credentials_for_update.return_value = None
        mapper.resolve_provider_account_update.return_value = {"name": "prod"}
        mock_get_mapper.return_value = mapper
        mock_resolve_adapter.return_value = AsyncMock()
        mock_update_provider_account.side_effect = ValueError(
            "Provider account update conflicts with an existing record"
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_provider_account(
                provider_id=existing_account.id,
                session=AsyncMock(),
                payload=DeploymentProviderAccountUpdateRequest(name="prod"),
                current_user=_fake_user(),
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Provider account is already tracked by user."

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock, return_value=([], 1))
    @patch(f"{ROUTES_MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_delete_provider_account_rejects_when_deployments_exist(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_count_deployments,
        mock_list_synced,
        mock_delete_provider_account,
    ):
        """DELETE refuses to remove provider accounts that still own deployments."""
        from langflow.api.v1.deployments import delete_provider_account

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account
        mock_get_mapper.return_value = MagicMock()
        mock_resolve_adapter.return_value = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await delete_provider_account(
                provider_id=existing_account.id,
                session=AsyncMock(),
                current_user=_fake_user(),
            )

        assert exc_info.value.status_code == 409
        mock_count_deployments.assert_awaited_once()
        mock_list_synced.assert_awaited_once()
        mock_delete_provider_account.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock, return_value=([], 0))
    @patch(f"{ROUTES_MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_delete_provider_account_prunes_stale_rows_before_delete(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_count_deployments,
        mock_list_synced,
        mock_delete_provider_account,
    ):
        """DELETE can proceed when reconciliation shows only stale local deployments remain."""
        from langflow.api.v1.deployments import delete_provider_account

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account
        mock_get_mapper.return_value = MagicMock()
        mock_resolve_adapter.return_value = AsyncMock()
        session = AsyncMock()

        response = await delete_provider_account(
            provider_id=existing_account.id,
            session=session,
            current_user=_fake_user(),
        )

        assert response.status_code == 204
        mock_count_deployments.assert_awaited_once()
        mock_list_synced.assert_awaited_once()
        mock_delete_provider_account.assert_awaited_once_with(
            session,
            provider_account=existing_account,
        )


# ---------------------------------------------------------------------------
# update_deployment: rollback on commit failure
# ---------------------------------------------------------------------------


class TestUpdateDeploymentRollback:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.rollback_provider_update", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.update_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.apply_flow_version_patch_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_added_snapshot_bindings_for_update", return_value=[])
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_flow_version_patch_for_update", return_value=([], []))
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_rollback_called_on_commit_failure(
        self,
        mock_resolve_amm,
        mock_resolve_fvp,  # noqa: ARG002
        mock_validate_fv,  # noqa: ARG002
        mock_resolve_snap,  # noqa: ARG002
        mock_apply_patch,  # noqa: ARG002
        mock_update_db,  # noqa: ARG002
        mock_rollback,
    ):
        """When session.commit() fails, rollback_provider_update is called."""
        from langflow.api.v1.deployments import update_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        update_result = DeploymentUpdateResult(id="provider-dep-1")
        adapter.update.return_value = update_result
        mapper.resolve_deployment_update = AsyncMock(return_value=MagicMock())
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate")

        session = AsyncMock()
        session.commit.side_effect = RuntimeError("DB commit failed")

        payload = MagicMock()
        payload.name = None
        payload.description = None

        with pytest.raises(RuntimeError, match="DB commit failed"):
            await update_deployment(
                deployment_id=dep_row.id,
                session=session,
                payload=payload,
                current_user=_fake_user(),
            )

        mock_rollback.assert_awaited_once()
        assert mock_rollback.call_args.kwargs["deployment_db_id"] == dep_row.id
        assert mock_rollback.call_args.kwargs["deployment_resource_key"] == dep_row.resource_key
        assert (
            mock_rollback.call_args.kwargs["deployment_provider_account_id"] == dep_row.deployment_provider_account_id
        )

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.rollback_provider_update", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.update_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.apply_flow_version_patch_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_added_snapshot_bindings_for_update", return_value=[])
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_flow_version_patch_for_update", return_value=([], []))
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_no_rollback_on_success(
        self,
        mock_resolve_amm,
        mock_resolve_fvp,  # noqa: ARG002
        mock_validate_fv,  # noqa: ARG002
        mock_resolve_snap,  # noqa: ARG002
        mock_apply_patch,  # noqa: ARG002
        mock_update_db,  # noqa: ARG002
        mock_rollback,
    ):
        """On successful commit, rollback is NOT called."""
        from langflow.api.v1.deployments import update_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        update_result = DeploymentUpdateResult(id="provider-dep-1")
        adapter.update.return_value = update_result
        mapper.resolve_deployment_update = AsyncMock(return_value=MagicMock())
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate")

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.name = None
        payload.description = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
        )

        mock_rollback.assert_not_awaited()


class TestUpdateDeploymentAlreadyAttachedFiltering:
    """Bind operations for flow versions that already have DB attachments.

    These should not be passed to resolve_added_snapshot_bindings_for_update,
    since the adapter does not return new snapshot bindings for reused tools.
    """

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.apply_flow_version_patch_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_added_snapshot_bindings_for_update", return_value=[])
    @patch(f"{ROUTES_MODULE}.list_deployment_attachments_for_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_flow_version_patch_for_update")
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_already_attached_flow_versions_excluded_from_snapshot_resolution(
        self,
        mock_resolve_amm,
        mock_resolve_fvp,
        mock_validate_fv,  # noqa: ARG002
        mock_list_attachments,
        mock_resolve_snap,
        mock_apply_patch,  # noqa: ARG002
    ):
        """Only truly new flow version IDs are passed to snapshot resolution.

        When some bind flow version IDs already have DB attachments, only the
        truly new ones are passed to resolve_added_snapshot_bindings_for_update.
        """
        from langflow.api.v1.deployments import update_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        update_result = DeploymentUpdateResult(id="provider-dep-1")
        adapter.update.return_value = update_result
        mapper.resolve_deployment_update = AsyncMock(return_value=MagicMock())
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate")

        reused_fv_id = uuid4()
        new_fv_id = uuid4()
        mock_resolve_fvp.return_value = ([reused_fv_id, new_fv_id], [])

        mock_list_attachments.return_value = [
            SimpleNamespace(flow_version_id=reused_fv_id, provider_snapshot_id="existing-tool-1"),
        ]

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.name = None
        payload.description = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
        )

        mock_resolve_snap.assert_called_once()
        resolved_fv_ids = mock_resolve_snap.call_args.kwargs["added_flow_version_ids"]
        assert resolved_fv_ids == [new_fv_id]

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.apply_flow_version_patch_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_added_snapshot_bindings_for_update", return_value=[])
    @patch(f"{ROUTES_MODULE}.list_deployment_attachments_for_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_flow_version_patch_for_update")
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_all_flow_versions_already_attached_passes_empty_list(
        self,
        mock_resolve_amm,
        mock_resolve_fvp,
        mock_validate_fv,  # noqa: ARG002
        mock_list_attachments,
        mock_resolve_snap,
        mock_apply_patch,  # noqa: ARG002
    ):
        """An empty list is passed when all flow versions are already attached.

        When all bind flow versions already have attachments, an empty list
        is passed to resolve_added_snapshot_bindings_for_update.
        """
        from langflow.api.v1.deployments import update_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        update_result = DeploymentUpdateResult(id="provider-dep-1")
        adapter.update.return_value = update_result
        mapper.resolve_deployment_update = AsyncMock(return_value=MagicMock())
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate")

        fv_id_1 = uuid4()
        fv_id_2 = uuid4()
        mock_resolve_fvp.return_value = ([fv_id_1, fv_id_2], [])

        mock_list_attachments.return_value = [
            SimpleNamespace(flow_version_id=fv_id_1, provider_snapshot_id="tool-1"),
            SimpleNamespace(flow_version_id=fv_id_2, provider_snapshot_id="tool-2"),
        ]

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.name = None
        payload.description = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
        )

        resolved_fv_ids = mock_resolve_snap.call_args.kwargs["added_flow_version_ids"]
        assert resolved_fv_ids == []

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.apply_flow_version_patch_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_added_snapshot_bindings_for_update", return_value=[])
    @patch(f"{ROUTES_MODULE}.list_deployment_attachments_for_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_flow_version_patch_for_update")
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_no_existing_attachments_passes_all_flow_versions(
        self,
        mock_resolve_amm,
        mock_resolve_fvp,
        mock_validate_fv,  # noqa: ARG002
        mock_list_attachments,
        mock_resolve_snap,
        mock_apply_patch,  # noqa: ARG002
    ):
        """When no bind flow versions have existing attachments, all are passed through."""
        from langflow.api.v1.deployments import update_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        update_result = DeploymentUpdateResult(id="provider-dep-1")
        adapter.update.return_value = update_result
        mapper.resolve_deployment_update = AsyncMock(return_value=MagicMock())
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate")

        fv_id_1 = uuid4()
        fv_id_2 = uuid4()
        mock_resolve_fvp.return_value = ([fv_id_1, fv_id_2], [])

        mock_list_attachments.return_value = []

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.name = None
        payload.description = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
        )

        resolved_fv_ids = mock_resolve_snap.call_args.kwargs["added_flow_version_ids"]
        assert resolved_fv_ids == [fv_id_1, fv_id_2]


class TestUpdateDeploymentMetadataPersistence:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.update_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.apply_flow_version_patch_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_added_snapshot_bindings_for_update", return_value=[])
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_flow_version_patch_for_update", return_value=([], []))
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_explicit_null_description_is_persisted(
        self,
        mock_resolve_amm,
        mock_resolve_fvp,  # noqa: ARG002
        mock_validate_fv,  # noqa: ARG002
        mock_resolve_snap,  # noqa: ARG002
        mock_apply_patch,  # noqa: ARG002
        mock_update_db,
    ):
        """PATCH should persist an explicitly-cleared description alongside other spec updates."""
        from langflow.api.v1.deployments import update_deployment

        dep_row = _fake_deployment_row(name="old-name", description="old-description")
        updated_row = _fake_deployment_row(
            id=dep_row.id,
            resource_key=dep_row.resource_key,
            name="renamed",
            description=None,
            deployment_provider_account_id=dep_row.deployment_provider_account_id,
            project_id=dep_row.project_id,
        )
        adapter = AsyncMock()
        mapper = MagicMock()
        update_result = DeploymentUpdateResult(id="provider-dep-1")
        adapter.update.return_value = update_result
        mapper.resolve_deployment_update = AsyncMock(return_value=MagicMock())
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate")
        mock_update_db.return_value = updated_row

        session = AsyncMock()
        session.commit.return_value = None

        payload = DeploymentUpdateRequest.model_validate(
            {
                "name": "renamed",
                "description": None,
            }
        )

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
        )

        mock_update_db.assert_awaited_once()
        update_kwargs = mock_update_db.call_args.kwargs
        assert update_kwargs["name"] == "renamed"
        assert "description" in update_kwargs
        assert update_kwargs["description"] is None


# ---------------------------------------------------------------------------
# get_deployment: deployment-level sync
# ---------------------------------------------------------------------------


class TestGetDeploymentSync:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.list_deployment_attachments", new_callable=AsyncMock, return_value=[])
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_stale_row_deleted_when_provider_returns_not_found(
        self,
        mock_resolve,
        mock_delete_row,
        mock_list_att,  # noqa: ARG002
    ):
        """When the provider raises DeploymentNotFoundError, the DB row is deleted and 404 returned."""
        from langflow.api.v1.deployments import get_deployment
        from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        adapter.get.side_effect = DeploymentNotFoundError(message="gone")
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper(), "watsonx-orchestrate")

        user = _fake_user()
        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=user)

        assert exc_info.value.status_code == 404
        mock_delete_row.assert_awaited_once_with(session, user_id=user.id, deployment_id=dep_row.id)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_non_404_adapter_error_does_not_delete_row(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """When adapter.get() raises a non-404 DeploymentServiceError, the DB row is kept."""
        from langflow.api.v1.deployments import get_deployment
        from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        adapter.get.side_effect = AuthenticationError(message="bad creds", error_code="authentication_error")
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper(), "watsonx-orchestrate")

        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 401
        mock_delete_row.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_service_unavailable_returns_503(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """When adapter.get() raises ServiceUnavailableError, 503 is returned and row is kept."""
        from langflow.api.v1.deployments import get_deployment
        from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        adapter.get.side_effect = ServiceUnavailableError(message="provider down")
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper(), "watsonx-orchestrate")

        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 503
        mock_delete_row.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.list_deployment_attachments", new_callable=AsyncMock, return_value=[])
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_get_deployment_does_not_inject_resource_key_into_provider_data(
        self,
        mock_resolve,
        mock_list_att,  # noqa: ARG002
    ):
        from langflow.api.v1.deployments import get_deployment
        from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper

        created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        updated_at = datetime(2026, 1, 3, 4, 5, 6, tzinfo=timezone.utc)
        dep_row = _fake_deployment_row(
            resource_key="provider-rk-1",
            name="db-owned-name",
            description="db-owned-description",
            deployment_type="agent",
            created_at=created_at,
            updated_at=updated_at,
        )
        adapter = AsyncMock()
        provider_deployment = MagicMock()
        provider_deployment.name = "provider-owned-name"
        provider_deployment.description = "provider-owned-description"
        provider_deployment.type = "worker"
        provider_deployment.created_at = None
        provider_deployment.updated_at = None
        provider_deployment.model_dump.return_value = {
            "provider_data": {
                "llm": "virtual-model/bedrock/openai.gpt-oss-120b-1:0",
            }
        }
        adapter.get.return_value = provider_deployment
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper(), "watsonx-orchestrate")

        session = AsyncMock()
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.resource_key == "provider-rk-1"
        assert result.name == "db-owned-name"
        assert result.description == "db-owned-description"
        assert result.type == "agent"
        assert result.created_at == created_at
        assert result.updated_at == updated_at
        assert result.provider_data == {"llm": "virtual-model/bedrock/openai.gpt-oss-120b-1:0"}

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.fetch_provider_snapshot_keys", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_snapshot_sync_corrects_attached_count(
        self,
        mock_resolve,
        mock_list_att,
        mock_fetch_snap,
        mock_sync_snap,
    ):
        """Snapshot-level sync corrects the attached_count in the response."""
        from langflow.api.v1.deployments import get_deployment

        class _SnapshotMapper:
            @staticmethod
            def util_snapshot_ids_to_verify(attachments):
                return [
                    attachment.provider_snapshot_id for attachment in attachments if attachment.provider_snapshot_id
                ]

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        provider_deployment = MagicMock()
        provider_deployment.name = "deployed-agent"
        provider_deployment.description = "desc"
        provider_deployment.type = "agent"
        provider_deployment.created_at = None
        provider_deployment.updated_at = None
        provider_deployment.model_dump.return_value = {}
        adapter.get.return_value = provider_deployment
        mock_resolve.return_value = (dep_row, adapter, _SnapshotMapper(), "watsonx-orchestrate")

        att_good = _fake_attachment(provider_snapshot_id="snap-1")
        att_stale = _fake_attachment(provider_snapshot_id="snap-stale")
        mock_list_att.return_value = [att_good, att_stale]
        mock_fetch_snap.return_value = {"snap-1"}
        mock_sync_snap.return_value = {dep_row.id: 1}

        session = AsyncMock()
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.attached_count == 1
        mock_fetch_snap.assert_awaited_once()
        mock_sync_snap.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.fetch_provider_snapshot_keys", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_no_snapshot_sync_when_no_snapshot_ids(
        self,
        mock_resolve,
        mock_list_att,
        mock_fetch_snap,
        mock_sync_snap,
    ):
        """When no attachments have provider_snapshot_id, snapshot sync is skipped."""
        from langflow.api.v1.deployments import get_deployment

        class _SnapshotMapper:
            @staticmethod
            def util_snapshot_ids_to_verify(attachments):
                return [
                    attachment.provider_snapshot_id for attachment in attachments if attachment.provider_snapshot_id
                ]

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        provider_deployment = MagicMock()
        provider_deployment.name = "deployed-agent"
        provider_deployment.description = "desc"
        provider_deployment.type = "agent"
        provider_deployment.created_at = None
        provider_deployment.updated_at = None
        provider_deployment.model_dump.return_value = {}
        adapter.get.return_value = provider_deployment
        mock_resolve.return_value = (dep_row, adapter, _SnapshotMapper(), "watsonx-orchestrate")
        mock_list_att.return_value = [_fake_attachment(provider_snapshot_id=None)]

        session = AsyncMock()
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.attached_count == 1
        mock_fetch_snap.assert_not_awaited()
        mock_sync_snap.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.fetch_provider_snapshot_keys", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_snapshot_sync_error_falls_back_to_unverified_count(
        self,
        mock_resolve,
        mock_list_att,
        mock_fetch_snap,
        mock_sync_snap,
    ):
        """When snapshot-level sync raises, the response uses unverified attachment count."""
        from langflow.api.v1.deployments import get_deployment

        class _SnapshotMapper:
            @staticmethod
            def util_snapshot_ids_to_verify(attachments):
                return [
                    attachment.provider_snapshot_id for attachment in attachments if attachment.provider_snapshot_id
                ]

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        provider_deployment = MagicMock()
        provider_deployment.name = "deployed-agent"
        provider_deployment.description = "desc"
        provider_deployment.type = "agent"
        provider_deployment.created_at = None
        provider_deployment.updated_at = None
        provider_deployment.model_dump.return_value = {}
        adapter.get.return_value = provider_deployment
        mock_resolve.return_value = (dep_row, adapter, _SnapshotMapper(), "watsonx-orchestrate")

        att1 = _fake_attachment(provider_snapshot_id="snap-1")
        att2 = _fake_attachment(provider_snapshot_id="snap-2")
        mock_list_att.return_value = [att1, att2]
        mock_fetch_snap.side_effect = RuntimeError("provider down")

        session = AsyncMock()
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.attached_count == 2
        mock_sync_snap.assert_not_awaited()


# ---------------------------------------------------------------------------
# delete_deployment: stale-row cleanup + commit retry
# ---------------------------------------------------------------------------


class TestDeleteDeployment:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_from_deployment", new_callable=AsyncMock)
    async def test_provider_not_found_still_deletes_local_row(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """Delete is idempotent when the provider agent is already gone."""
        from langflow.api.v1.deployments import delete_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        adapter.delete.side_effect = DeploymentNotFoundError(message="gone")
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate")

        user = _fake_user()
        session = AsyncMock()

        response = await delete_deployment(deployment_id=dep_row.id, session=session, current_user=user)

        assert response.status_code == 204
        mock_delete_row.assert_awaited_once_with(session, user_id=user.id, deployment_id=dep_row.id)
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_from_deployment", new_callable=AsyncMock)
    async def test_non_404_provider_error_does_not_delete_local_row(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """Delete keeps the DB row when the provider call fails for non-404 reasons."""
        from langflow.api.v1.deployments import delete_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        adapter.delete.side_effect = AuthenticationError(message="bad creds", error_code="authentication_error")
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate")

        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await delete_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 401
        mock_delete_row.assert_not_awaited()
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_from_deployment", new_callable=AsyncMock)
    async def test_commit_failure_retries_local_cleanup_once(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """A failed local commit after provider delete triggers one cleanup retry."""
        from langflow.api.v1.deployments import delete_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate")

        user = _fake_user()
        session = AsyncMock()
        session.commit.side_effect = [RuntimeError("commit failed"), None]

        response = await delete_deployment(deployment_id=dep_row.id, session=session, current_user=user)

        assert response.status_code == 204
        assert mock_delete_row.await_count == 2
        session.rollback.assert_awaited_once()
        assert session.commit.await_count == 2

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_from_deployment", new_callable=AsyncMock)
    async def test_repeated_local_cleanup_failure_returns_500(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """If cleanup still fails after retry, the route surfaces a 500."""
        from langflow.api.v1.deployments import delete_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate")

        session = AsyncMock()
        session.commit.side_effect = [RuntimeError("commit failed"), RuntimeError("still failing")]

        with pytest.raises(HTTPException) as exc_info:
            await delete_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 500
        assert mock_delete_row.await_count == 2
        assert session.rollback.await_count == 2
        assert session.commit.await_count == 2

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_from_deployment", new_callable=AsyncMock)
    async def test_include_provider_true_calls_adapter_delete(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """include_provider=True (default) calls adapter.delete to remove provider resources."""
        from langflow.api.v1.deployments import delete_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate")

        user = _fake_user()
        session = AsyncMock()

        response = await delete_deployment(
            deployment_id=dep_row.id, session=session, current_user=user, include_provider=True
        )

        assert response.status_code == 204
        adapter.delete.assert_awaited_once()
        mock_delete_row.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_from_deployment", new_callable=AsyncMock)
    async def test_include_provider_false_skips_adapter_delete(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """include_provider=False skips the adapter entirely — only the DB row is removed."""
        from langflow.api.v1.deployments import delete_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate")

        user = _fake_user()
        session = AsyncMock()

        response = await delete_deployment(
            deployment_id=dep_row.id, session=session, current_user=user, include_provider=False
        )

        assert response.status_code == 204
        adapter.delete.assert_not_awaited()
        mock_delete_row.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_deployment: duplicate name returns 409
# ---------------------------------------------------------------------------


class TestCreateDeploymentDuplicateName:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=True)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_duplicate_name_returns_409(
        self,
        mock_get_pa,
        mock_name_exists,  # noqa: ARG002
    ):
        """When a deployment with the same name already exists, 409 is returned without calling the provider."""
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "duplicate-name"

        with pytest.raises(HTTPException) as exc_info:
            await create_deployment(session=AsyncMock(), payload=payload, current_user=_fake_user())

        assert exc_info.value.status_code == 409
        assert "duplicate-name" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=True)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_duplicate_name_does_not_call_provider(
        self,
        mock_get_pa,
        mock_name_exists,  # noqa: ARG002
        mock_resolve_adapter,
    ):
        """When name already exists, the provider adapter is never invoked."""
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "taken"

        with pytest.raises(HTTPException):
            await create_deployment(session=AsyncMock(), payload=payload, current_user=_fake_user())

        mock_resolve_adapter.assert_not_called()


# ---------------------------------------------------------------------------
# create_deployment: project-scoped flow version validation
# ---------------------------------------------------------------------------


class TestCreateDeploymentProjectValidation:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_validation_called_before_adapter(
        self,
        mock_get_pa,
        mock_name_exists,  # noqa: ARG002
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,
    ):
        """validate_project_scoped_flow_version_ids is called before the adapter create."""
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        fv_ids = [uuid4(), uuid4()]
        mapper.util_create_flow_version_ids.return_value = fv_ids
        mapper.util_existing_deployment_resource_key_for_create.return_value = None
        mock_get_mapper.return_value = mapper
        project_id = uuid4()
        mock_resolve_project.return_value = project_id

        mock_validate_fv.side_effect = HTTPException(status_code=404, detail="invalid")

        payload = MagicMock()
        payload.provider_id = pa.id

        with pytest.raises(HTTPException) as exc_info:
            await create_deployment(session=AsyncMock(), payload=payload, current_user=_fake_user())

        assert exc_info.value.status_code == 404
        mock_validate_fv.assert_awaited_once()
        call_kwargs = mock_validate_fv.call_args.kwargs
        assert call_kwargs["flow_version_ids"] == fv_ids
        assert call_kwargs["project_id"] == project_id
        adapter.create.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_empty_flow_version_ids_skips_validation(
        self,
        mock_get_pa,
        mock_name_exists,  # noqa: ARG002
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,
    ):
        """When the mapper returns no flow_version_ids, validation still runs (it short-circuits internally)."""
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        create_result = DeploymentCreateResult(id="prov-1")
        adapter.create.return_value = create_result
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_create_flow_version_ids.return_value = []
        mapper.util_existing_deployment_resource_key_for_create.return_value = None
        mapper.resolve_deployment_create = AsyncMock(return_value=MagicMock())
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.name = "test"
        payload.type = "agent"
        payload.description = None

        session = AsyncMock()
        session.commit.return_value = None

        with (
            patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock, return_value=_fake_deployment_row()),
            patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock),
        ):
            mapper.shape_deployment_create_result.return_value = MagicMock()
            await create_deployment(session=session, payload=payload, current_user=_fake_user())

        mock_validate_fv.assert_awaited_once()
        assert mock_validate_fv.call_args.kwargs["flow_version_ids"] == []


class TestCreateDeploymentSchemaValidation:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.deployment_name_exists", new_callable=AsyncMock, return_value=False)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_mapper_schema_validation_error_surfaces_422(
        self,
        mock_get_pa,
        mock_name_exists,  # noqa: ARG002
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,
    ):
        """Mapper-level schema failures on create surface as HTTP 422."""
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_create_flow_version_ids.return_value = [uuid4()]
        mapper.util_existing_deployment_resource_key_for_create.return_value = None
        mapper.resolve_deployment_create = AsyncMock(
            side_effect=HTTPException(
                status_code=422,
                detail="Invalid provider_data payload: simulated adapter validation failure",
            )
        )
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()

        payload = MagicMock()
        payload.provider_id = pa.id

        with pytest.raises(HTTPException) as exc_info:
            await create_deployment(session=AsyncMock(), payload=payload, current_user=_fake_user())

        assert exc_info.value.status_code == 422
        mock_validate_fv.assert_awaited_once()
        adapter.create.assert_not_awaited()


# ---------------------------------------------------------------------------
# update_deployment: project-scoped flow version validation
# ---------------------------------------------------------------------------


class TestUpdateDeploymentProjectValidation:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_flow_version_patch_for_update")
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_validation_called_before_adapter(
        self,
        mock_resolve_amm,
        mock_resolve_fvp,
        mock_validate_fv,
    ):
        """validate_project_scoped_flow_version_ids is called before the adapter update."""
        from langflow.api.v1.deployments import update_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        mapper.resolve_deployment_update = AsyncMock(return_value=MagicMock())
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate")

        add_ids = [uuid4()]
        remove_ids = [uuid4()]
        mock_resolve_fvp.return_value = (add_ids, remove_ids)

        mock_validate_fv.side_effect = HTTPException(status_code=404, detail="out of project")

        payload = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await update_deployment(
                deployment_id=dep_row.id,
                session=AsyncMock(),
                payload=payload,
                current_user=_fake_user(),
            )

        assert exc_info.value.status_code == 404
        mock_validate_fv.assert_awaited_once()
        assert mock_validate_fv.call_args.kwargs["project_id"] == dep_row.project_id
        adapter.update.assert_not_awaited()


# ---------------------------------------------------------------------------
# list_deployment_llms
# ---------------------------------------------------------------------------


class TestListDeploymentLlms:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_list_llms_returns_shaped_response(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
    ):
        from langflow.api.v1.deployments import list_deployment_llms

        provider_account = _fake_provider_account()
        mock_get_provider_account.return_value = provider_account

        adapter = AsyncMock()
        llm_result = SimpleNamespace(
            provider_result={"models": [{"model_name": "model-a"}, {"model_name": "model-b"}]},
        )
        adapter.list_llms.return_value = llm_result
        mock_resolve_adapter.return_value = adapter

        mapper = MagicMock()
        mapper.shape_llm_list_result.return_value = DeploymentLlmListResponse(
            provider_data={"models": [{"model_name": "model-a"}, {"model_name": "model-b"}]}
        )
        mock_get_mapper.return_value = mapper

        response = await list_deployment_llms(
            provider_id=provider_account.id,
            session=AsyncMock(),
            current_user=_fake_user(),
        )

        assert response == DeploymentLlmListResponse(
            provider_data={"models": [{"model_name": "model-a"}, {"model_name": "model-b"}]}
        )
        adapter.list_llms.assert_awaited_once()
        mapper.shape_llm_list_result.assert_called_once_with(llm_result)

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_list_llms_maps_adapter_error(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
    ):
        from langflow.api.v1.deployments import list_deployment_llms

        provider_account = _fake_provider_account()
        mock_get_provider_account.return_value = provider_account

        adapter = AsyncMock()
        adapter.list_llms.side_effect = ServiceUnavailableError(message="provider down")
        mock_resolve_adapter.return_value = adapter

        mapper = MagicMock()
        mock_get_mapper.return_value = mapper

        with pytest.raises(HTTPException) as exc_info:
            await list_deployment_llms(
                provider_id=provider_account.id,
                session=AsyncMock(),
                current_user=_fake_user(),
            )

        assert exc_info.value.status_code == 503
        mapper.shape_llm_list_result.assert_not_called()


# ---------------------------------------------------------------------------
# resolve_deployment_adapter
# ---------------------------------------------------------------------------


class TestResolveDeploymentAdapter:
    def test_empty_provider_key_raises_400(self):
        from langflow.api.v1.mappers.deployments.helpers import resolve_deployment_adapter

        with pytest.raises(HTTPException) as exc_info:
            resolve_deployment_adapter("")

        assert exc_info.value.status_code == 400
        assert "provider_key" in exc_info.value.detail.lower()

    def test_whitespace_only_provider_key_raises_400(self):
        from langflow.api.v1.mappers.deployments.helpers import resolve_deployment_adapter

        with pytest.raises(HTTPException) as exc_info:
            resolve_deployment_adapter("   ")

        assert exc_info.value.status_code == 400

    @patch(f"{HELPERS_MODULE}.get_deployment_adapter", return_value=None)
    def test_unknown_provider_key_raises_503(self, _mock_get):  # noqa: PT019
        from langflow.api.v1.mappers.deployments.helpers import resolve_deployment_adapter

        with pytest.raises(HTTPException) as exc_info:
            resolve_deployment_adapter("nonexistent_provider")

        assert exc_info.value.status_code == 503
        assert "nonexistent_provider" in exc_info.value.detail

    @patch(f"{HELPERS_MODULE}.get_deployment_adapter", side_effect=RuntimeError("registry boom"))
    def test_adapter_lookup_error_raises_500(self, _mock_get):  # noqa: PT019
        from langflow.api.v1.mappers.deployments.helpers import resolve_deployment_adapter

        with pytest.raises(HTTPException) as exc_info:
            resolve_deployment_adapter("bad_key")

        assert exc_info.value.status_code == 500

    @patch(f"{HELPERS_MODULE}.get_deployment_adapter")
    def test_valid_provider_key_returns_adapter(self, mock_get):
        from langflow.api.v1.mappers.deployments.helpers import resolve_deployment_adapter

        sentinel = MagicMock()
        mock_get.return_value = sentinel

        result = resolve_deployment_adapter("watsonx_orchestrate")

        assert result is sentinel
        mock_get.assert_called_once_with("watsonx_orchestrate")


# ---------------------------------------------------------------------------
# handle_adapter_errors: context manager integration
# ---------------------------------------------------------------------------


class TestHandleAdapterErrors:
    def test_maps_authentication_error_to_401(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors():
            raise AuthenticationError(message="bad creds", error_code="authentication_error")

        assert exc_info.value.status_code == 401
        assert "bad creds" in exc_info.value.detail

    def test_maps_service_unavailable_to_503(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors():
            raise ServiceUnavailableError(message="provider down")

        assert exc_info.value.status_code == 503

    def test_maps_not_found_to_404(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors():
            raise DeploymentNotFoundError(message="gone")

        assert exc_info.value.status_code == 404

    def test_maps_conflict_with_mapper_formatter(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        deployment_mapper = MagicMock()
        deployment_mapper.format_conflict_detail.return_value = "friendly detail"

        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors(mapper=deployment_mapper):
            raise ResourceConflictError(message="raw provider conflict")

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "friendly detail"
        deployment_mapper.format_conflict_detail.assert_called_once_with(
            "raw provider conflict",
            resource=None,
            resource_name=None,
        )

    def test_maps_conflict_passes_structured_resource_to_mapper_formatter(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        deployment_mapper = MagicMock()
        deployment_mapper.format_conflict_detail.return_value = "friendly detail"

        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors(mapper=deployment_mapper):
            raise ResourceConflictError(message="raw provider conflict", resource="tool")

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "friendly detail"
        deployment_mapper.format_conflict_detail.assert_called_once_with(
            "raw provider conflict",
            resource="tool",
            resource_name=None,
        )

    def test_maps_conflict_passes_structured_resource_name_to_mapper_formatter(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        deployment_mapper = MagicMock()
        deployment_mapper.format_conflict_detail.return_value = "friendly detail"

        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors(mapper=deployment_mapper):
            raise ResourceConflictError(
                message="raw provider conflict",
                resource="tool",
                resource_name="Simple_Agent",
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "friendly detail"
        deployment_mapper.format_conflict_detail.assert_called_once_with(
            "raw provider conflict",
            resource="tool",
            resource_name="Simple_Agent",
        )

    def test_maps_conflict_without_mapper_passthrough(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors():
            raise ResourceConflictError(message="raw provider conflict")

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "raw provider conflict"

    def test_passes_through_http_exception(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors():
            raise HTTPException(status_code=418, detail="teapot")

        assert exc_info.value.status_code == 418

    def test_maps_not_implemented_to_501(self):
        from langflow.api.v1.mappers.deployments.helpers import handle_adapter_errors

        msg = "nope"
        with pytest.raises(HTTPException) as exc_info, handle_adapter_errors():
            raise NotImplementedError(msg)

        assert exc_info.value.status_code == 501
