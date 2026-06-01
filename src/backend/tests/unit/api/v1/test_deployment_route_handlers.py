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
from langflow.api.v1.deployments import DeploymentTelemetryCtx
from langflow.api.v1.mappers.deployments.contracts import ProviderSnapshotBinding
from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper
from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentListItem,
    DeploymentLlmListResponse,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountUpdateRequest,
    DeploymentUpdateRequest,
    SnapshotUpdateRequest,
)
from langflow.services.database.models.deployment.exceptions import DeploymentGuardError
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
    DeploymentGetResult,
    DeploymentListParams,
    DeploymentListResult,
    DeploymentType,
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
    provider_tenant_id: str | None = "tenant-1",
    user_id=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        # ``user_id`` is read by ``list_deployment_configs`` to pick the
        # provider namespace for adapter calls; default to a random UUID
        # so tests that don't care about the owner still pass.
        user_id=user_id if user_id is not None else uuid4(),
        provider_key=provider_key,
        provider_url=provider_url,
        api_key=api_key,
        provider_tenant_id=provider_tenant_id,
    )


def _fake_deployment_row(**overrides) -> SimpleNamespace:
    return SimpleNamespace(
        id=overrides.get("id", uuid4()),
        # ``user_id`` and ``workspace_id`` are read by ensure_deployment_permission
        # on every guarded deployment handler — keep the fixture in sync with the
        # real Deployment model so tests don't trip the authz layer with
        # AttributeError. None values are valid (owner override skipped,
        # workspace domain falls back to "*").
        user_id=overrides.get("user_id", uuid4()),
        workspace_id=overrides.get("workspace_id"),
        resource_key=overrides.get("resource_key", "rk-1"),
        display_name=overrides.get("display_name", overrides.get("name", "test-deployment")),
        description=overrides.get("description"),
        deployment_type=overrides.get("deployment_type", "agent"),
        deployment_provider_account_id=overrides.get("deployment_provider_account_id", uuid4()),
        project_id=overrides.get("project_id", uuid4()),
        created_at=overrides.get("created_at"),
        updated_at=overrides.get("updated_at"),
    )


def _fake_user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _fake_telemetry() -> DeploymentTelemetryCtx:
    return DeploymentTelemetryCtx()


def _fake_attachment(*, provider_snapshot_id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        flow_version_id=uuid4(),
        provider_snapshot_id=provider_snapshot_id,
        deployment_id=uuid4(),
    )


class _AsyncNoopSavepoint:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


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
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_rollback_called_on_commit_failure(
        self,
        mock_get_pa,
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
            type=DeploymentType.AGENT,
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
        payload.display_name = "test"
        payload.type = "agent"
        payload.description = None

        with pytest.raises(RuntimeError, match="DB commit failed"):
            await create_deployment(
                session=session, payload=payload, current_user=_fake_user(), telemetry=_fake_telemetry()
            )

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
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_no_rollback_on_success(
        self,
        mock_get_pa,
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
        create_result = DeploymentCreateResult(id="provider-dep-1", type=DeploymentType.AGENT)
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
        payload.display_name = "test"
        payload.type = "agent"
        payload.description = None

        mapper.shape_deployment_create_result.return_value = MagicMock()
        await create_deployment(
            session=session, payload=payload, current_user=_fake_user(), telemetry=_fake_telemetry()
        )

        mock_rollback.assert_not_awaited()


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
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_existing_agent_without_mutation_skips_provider_calls(
        self,
        mock_get_pa,
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
        adapter.get.return_value = DeploymentGetResult(
            id="existing-agent-1",
            name="agent_technical_name",
            type="agent",
        )
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_existing_deployment_resource_key_for_create.return_value = "existing-agent-1"
        mapper.util_create_flow_version_ids.return_value = []
        mapper.util_create_result_from_existing_resource.return_value = DeploymentCreateResult(
            id="existing-agent-1",
            type=DeploymentType.AGENT,
        )
        deployment_to_create = SimpleNamespace(resource_key="existing-agent-1")
        mapper.resolve_deployment_model_from_existing_resource_for_create.return_value = deployment_to_create
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        dep_row = _fake_deployment_row(resource_key="existing-agent-1")
        mock_create_db.return_value = dep_row

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.display_name = "existing"
        payload.type = "agent"
        payload.description = None

        mapper.shape_deployment_create_result.return_value = MagicMock()
        await create_deployment(
            session=session, payload=payload, current_user=_fake_user(), telemetry=_fake_telemetry()
        )

        _ = (mock_get_by_resource_key, mock_validate_fv, mock_attach)
        adapter.create.assert_not_awaited()
        adapter.update.assert_not_awaited()
        adapter.get.assert_awaited_once_with(
            deployment_id="existing-agent-1",
            deployment_type=payload.type,
            user_id=ANY,
            db=session,
        )
        mapper.util_create_result_from_existing_resource.assert_called_once_with(
            existing_resource=adapter.get.return_value,
        )
        assert mock_create_db.call_args.kwargs["deployment"] is deployment_to_create

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_existing_agent_with_extra_provider_field_rejected_before_provider_lookup(
        self,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_resolve_project,
        mock_validate_fv,
        mock_create_db,
    ):
        from langflow.api.v1.deployments import create_deployment

        pa = _fake_provider_account()
        mock_get_pa.return_value = pa
        adapter = AsyncMock()
        mock_resolve_adapter.return_value = adapter
        mock_get_mapper.return_value = WatsonxOrchestrateDeploymentMapper()
        mock_resolve_project.return_value = uuid4()
        payload = DeploymentCreateRequest(
            provider_id=pa.id,
            type="agent",
            provider_data={
                "existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46",
                "connections": [],
            },
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_deployment(
                session=AsyncMock(), payload=payload, current_user=_fake_user(), telemetry=_fake_telemetry()
            )

        assert exc_info.value.status_code == 422
        assert "cannot include fields that update the wxO agent" in str(exc_info.value.detail)
        adapter.get.assert_not_awaited()
        adapter.create.assert_not_awaited()
        adapter.update.assert_not_awaited()
        mock_validate_fv.assert_not_awaited()
        mock_create_db.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_deployment_by_resource_key", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_existing_agent_conflict_when_resource_key_already_persisted(
        self,
        mock_get_pa,
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
        payload.display_name = "existing"
        payload.type = "agent"
        payload.description = None

        with pytest.raises(HTTPException) as exc_info:
            await create_deployment(
                session=AsyncMock(), payload=payload, current_user=_fake_user(), telemetry=_fake_telemetry()
            )

        assert exc_info.value.status_code == 409
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
        resolved_params = DeploymentListParams(provider_params={"environment": "draft"})
        mapper.resolve_deployment_list_adapter_params = AsyncMock(return_value=resolved_params)
        mapper.shape_deployment_list_result.return_value = expected
        mapper.resolve_load_from_provider_deployment_list_params.return_value = {"environment": "draft"}
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
        # The route handler must forward the mapper-supplied provider_params
        # (e.g. WXO's `{"environment": "draft"}`) into resolve_deployment_list_adapter_params,
        # otherwise the load_from_provider filter is silently dropped.
        mapper.resolve_deployment_list_adapter_params.assert_awaited_once()
        resolve_kwargs = mapper.resolve_deployment_list_adapter_params.await_args.kwargs
        assert resolve_kwargs["provider_params"] == {"environment": "draft"}
        adapter.list.assert_awaited_once()
        list_call_kwargs = adapter.list.await_args.kwargs
        assert list_call_kwargs["params"] is resolved_params
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

        mock_list_synced.return_value = ([], 0, {})

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
        mock_list_synced.return_value = ([], 0, {})

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
        mock_list_synced.return_value = ([], 0, {})

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
# list_deployments: provider metadata sync
# ---------------------------------------------------------------------------


class TestListDeploymentsMetadataSync:
    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{HELPERS_MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.delete_unbound_attachments", new_callable=AsyncMock, return_value=0)
    @patch(f"{HELPERS_MODULE}.update_deployment_metadata_batch", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.list_deployments_page", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_provider_description_passed_and_display_name_stays_in_provider_data(
        self,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_list_page,
        mock_fetch_keys,
        mock_update_metadata_batch,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,
    ):
        from langflow.api.v1.deployments import list_deployments
        from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper

        class _Mapper(BaseDeploymentMapper):
            def extract_snapshot_bindings(self, provider_view):
                _ = provider_view
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

            def shape_deployment_list_items(
                self,
                *,
                rows_with_counts,
                has_flow_filter=False,
                provider_key,
                provider_data_by_resource_key=None,
            ):
                _ = has_flow_filter
                return [
                    DeploymentListItem(
                        id=row.id,
                        provider_id=row.deployment_provider_account_id,
                        provider_key=provider_key,
                        resource_key=row.resource_key,
                        type=row.deployment_type,
                        description=row.description,
                        attached_count=attached_count,
                        provider_data=provider_data_by_resource_key[row.resource_key],
                    )
                    for row, attached_count, _matched in rows_with_counts
                ]

        pa = _fake_provider_account()
        row = _fake_deployment_row(resource_key="agent-1", description="old")
        long_description = "x" * 501
        provider_view = SimpleNamespace(
            deployments=[
                SimpleNamespace(
                    id="agent-1",
                    provider_data={
                        "display_name": "Provider Label",
                        "description": long_description,
                    },
                )
            ]
        )

        def _apply_metadata_batch(*_args, **kwargs):
            update = kwargs["deployment_updates"][0]
            update.langflow_db_row.display_name = update.display_name
            update.langflow_db_row.description = update.description

        mock_get_pa.return_value = pa
        mock_resolve_adapter.return_value = AsyncMock()
        mock_get_mapper.return_value = _Mapper()
        mock_list_page.return_value = [(row, 0, [])]
        mock_fetch_keys.return_value = ({"agent-1"}, provider_view)
        mock_count_attachments.return_value = {row.id: 0}
        mock_update_metadata_batch.side_effect = _apply_metadata_batch

        result = await list_deployments(
            provider_id=pa.id,
            session=MagicMock(begin_nested=MagicMock(return_value=_AsyncNoopSavepoint())),
            current_user=_fake_user(),
            params=SimpleNamespace(page=1, size=20),
            deployment_type=None,
        )

        assert result.deployments[0].description == long_description
        assert result.deployments[0].provider_data["display_name"] == "Provider Label"
        assert not hasattr(result.deployments[0], "display_name")
        mock_update_metadata_batch.assert_awaited_once()
        mock_delete_unbound.assert_awaited_once()
        mock_count.assert_awaited_once()


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

        owner_id = uuid4()
        actor = _fake_user()
        deployment.user_id = owner_id
        result = await list_deployment_snapshots(
            provider_id=pa.id,
            deployment_id=deployment.id,
            page=1,
            size=10,
            session=AsyncMock(),
            current_user=actor,
        )

        assert result is expected_response
        mock_get_pa.assert_awaited_once_with(
            provider_id=pa.id,
            user_id=owner_id,
            db=ANY,
        )
        mapper.resolve_snapshot_list_adapter_params.assert_awaited_once_with(
            deployment_resource_key="dep-key",
            provider_params=None,
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
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_attachments_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_updates_all_attachment_rows_for_snapshot(
        self,
        mock_list_attachments,
        mock_validate_fv,
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
        # ``update_snapshot`` filters the candidate set to attachments owned
        # by the actor when share-aware fetch is off. Pin the owner to the
        # actor's id so the OSS pass-through path keeps the row.
        deployment = _fake_deployment_row(
            user_id=user.id,
            deployment_provider_account_id=uuid4(),
        )
        attachment = SimpleNamespace(
            flow_version_id=uuid4(),
            deployment_id=deployment.id,
            provider_snapshot_id="tool-1",
            user_id=user.id,
        )
        provider_account = _fake_provider_account()
        provider_account.id = deployment.deployment_provider_account_id

        mock_list_attachments.return_value = [attachment]
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
            telemetry=_fake_telemetry(),
        )

        assert response.flow_version_id == target_flow_version_id
        assert response.provider_snapshot_id == "tool-1"
        mock_list_attachments.assert_awaited_once_with(
            session,
            provider_snapshot_id="tool-1",
        )
        mock_validate_fv.assert_awaited_once_with(
            flow_version_ids=[target_flow_version_id],
            user_id=user.id,
            project_id=deployment.project_id,
            db=session,
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
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_attachments_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_commit_failure_attempts_provider_compensation(
        self,
        mock_list_attachments,
        mock_validate_fv,
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
        deployment = _fake_deployment_row(
            user_id=user.id,
            deployment_provider_account_id=uuid4(),
        )
        attachment = SimpleNamespace(
            flow_version_id=previous_flow_version_id,
            deployment_id=deployment.id,
            provider_snapshot_id="tool-1",
            user_id=user.id,
        )
        provider_account = _fake_provider_account()
        provider_account.id = deployment.deployment_provider_account_id

        target_version = SimpleNamespace(id=target_flow_version_id, flow_id=flow_id, data={"nodes": []})
        previous_version = SimpleNamespace(id=previous_flow_version_id, flow_id=flow_id, data={"nodes": []})
        mock_get_flow_version.side_effect = [target_version, previous_version]
        mock_list_attachments.return_value = [attachment]
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
                telemetry=_fake_telemetry(),
            )

        session.commit.assert_awaited_once()
        session.rollback.assert_awaited_once()
        mock_validate_fv.assert_awaited_once_with(
            flow_version_ids=[target_flow_version_id],
            user_id=user.id,
            project_id=deployment.project_id,
            db=session,
        )
        assert adapter.update_snapshot.await_count == 2

    @pytest.mark.asyncio
    @patch("langflow.services.database.models.flow_version.crud.get_flow_version_entry", new_callable=AsyncMock)
    @patch("langflow.services.database.models.deployment.crud.get_deployment", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_attachments_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_project_scope_validation_runs_before_provider_update(
        self,
        mock_list_attachments,
        mock_validate_fv,
        mock_get_pa,
        mock_resolve_adapter,
        mock_get_deployment_row,
        mock_get_flow_version,
    ):
        from langflow.api.v1.deployments import update_snapshot

        user = _fake_user()
        target_flow_version_id = uuid4()
        attachment = SimpleNamespace(
            flow_version_id=uuid4(),
            deployment_id=uuid4(),
            provider_snapshot_id="tool-1",
            user_id=user.id,
        )
        deployment = _fake_deployment_row(id=attachment.deployment_id, user_id=user.id)
        mock_list_attachments.return_value = [attachment]
        mock_get_deployment_row.return_value = deployment
        mock_get_flow_version.return_value = SimpleNamespace(id=target_flow_version_id, flow_id=uuid4(), data={})
        mock_validate_fv.side_effect = HTTPException(status_code=404, detail="out of project")

        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await update_snapshot(
                provider_snapshot_id="tool-1",
                body=SnapshotUpdateRequest(flow_version_id=target_flow_version_id),
                session=session,
                current_user=user,
                telemetry=_fake_telemetry(),
            )

        assert exc_info.value.status_code == 404
        mock_validate_fv.assert_awaited_once_with(
            flow_version_ids=[target_flow_version_id],
            user_id=user.id,
            project_id=deployment.project_id,
            db=session,
        )
        mock_get_pa.assert_not_awaited()
        mock_resolve_adapter.assert_not_called()

    # ----- Share-aware / owner-group branches ----- #
    #
    # ``update_snapshot`` now groups candidate attachments by owner,
    # authorizes each owner's full set, and decides between 404 / success /
    # 409 based on how many owner groups authorize. These tests pin each
    # branch so a regression in the authorization walk surfaces here.

    @staticmethod
    def _share_aware_authz() -> MagicMock:
        """Stub authorization service that opts into cross-user fetch."""
        stub = MagicMock()
        stub.supports_cross_user_fetch = AsyncMock(return_value=True)
        stub.is_enabled = AsyncMock(return_value=True)
        return stub

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.ensure_deployment_permission", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.get_authorization_service")
    @patch("langflow.services.database.models.deployment.crud.get_deployment", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_attachments_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_share_aware_zero_authorized_groups_returns_404(
        self,
        mock_list_attachments,
        mock_get_deployment_row,
        mock_get_authz,
        mock_ensure_perm,
    ):
        """Share-aware: candidates from two owners; neither authorizes → 404 (no info leak)."""
        from langflow.api.v1.deployments import update_snapshot

        user = _fake_user()
        alice_id = uuid4()
        bob_id = uuid4()
        alice_dep = _fake_deployment_row(user_id=alice_id)
        bob_dep = _fake_deployment_row(user_id=bob_id)
        mock_list_attachments.return_value = [
            SimpleNamespace(
                flow_version_id=uuid4(),
                deployment_id=alice_dep.id,
                provider_snapshot_id="tool-1",
                user_id=alice_id,
            ),
            SimpleNamespace(
                flow_version_id=uuid4(),
                deployment_id=bob_dep.id,
                provider_snapshot_id="tool-1",
                user_id=bob_id,
            ),
        ]
        deps_by_id = {alice_dep.id: alice_dep, bob_dep.id: bob_dep}

        async def _resolve(_session, *, user_id, deployment_id):  # noqa: ARG001
            return deps_by_id.get(deployment_id)

        mock_get_deployment_row.side_effect = _resolve
        mock_get_authz.return_value = self._share_aware_authz()
        # Every authorization attempt denies — every owner group fails.
        mock_ensure_perm.side_effect = HTTPException(status_code=403, detail="denied")

        with pytest.raises(HTTPException) as exc_info:
            await update_snapshot(
                provider_snapshot_id="tool-1",
                body=SnapshotUpdateRequest(flow_version_id=uuid4()),
                session=AsyncMock(),
                current_user=user,
                telemetry=_fake_telemetry(),
            )
        assert exc_info.value.status_code == 404
        # UUID-privacy: the response must NOT distinguish "no such snapshot"
        # from "snapshot exists but owners other than you have it".
        assert "tool-1" in exc_info.value.detail
        assert "owner" not in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch("langflow.services.database.models.flow_version.crud.get_flow_version_entry", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.update_flow_version_by_provider_snapshot_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.ensure_deployment_permission", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.get_authorization_service")
    @patch("langflow.services.database.models.deployment.crud.get_deployment", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_attachments_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_share_aware_one_authorized_group_ignores_unauthorized_collision(
        self,
        mock_list_attachments,
        mock_get_deployment_row,
        mock_get_authz,
        mock_ensure_perm,
        mock_validate_fv,
        mock_get_pa,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_update_rows,
        mock_get_flow_version,
    ):
        """An unrelated owner with the same snapshot id must NOT block a legitimate share-holder."""
        from langflow.api.v1.deployments import update_snapshot

        user = _fake_user()
        target_flow_version_id = uuid4()
        # Alice — the actor has WRITE on her deployment via a share grant.
        alice_id = uuid4()
        alice_dep = _fake_deployment_row(user_id=alice_id)
        # Bob — also has snapshot id "tool-1", but actor has no access.
        bob_id = uuid4()
        bob_dep = _fake_deployment_row(user_id=bob_id)

        mock_list_attachments.return_value = [
            SimpleNamespace(
                flow_version_id=uuid4(),
                deployment_id=alice_dep.id,
                provider_snapshot_id="tool-1",
                user_id=alice_id,
            ),
            SimpleNamespace(
                flow_version_id=uuid4(),
                deployment_id=bob_dep.id,
                provider_snapshot_id="tool-1",
                user_id=bob_id,
            ),
        ]
        deps_by_id = {alice_dep.id: alice_dep, bob_dep.id: bob_dep}

        async def _resolve(_session, *, user_id, deployment_id):  # noqa: ARG001
            return deps_by_id.get(deployment_id)

        mock_get_deployment_row.side_effect = _resolve
        mock_get_authz.return_value = self._share_aware_authz()

        # Allow only Alice's deployment; deny Bob's.
        async def _maybe_authorize(*_args, **kwargs):
            if kwargs["deployment_user_id"] == alice_id:
                return
            raise HTTPException(status_code=403, detail="denied")

        mock_ensure_perm.side_effect = _maybe_authorize

        provider_account = _fake_provider_account(user_id=alice_id)
        provider_account.id = alice_dep.deployment_provider_account_id
        mock_get_pa.return_value = provider_account
        adapter = AsyncMock()
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.resolve_snapshot_update_artifact.return_value = {"artifact": "payload"}
        mock_get_mapper.return_value = mapper
        mock_update_rows.return_value = 1
        mock_get_flow_version.return_value = SimpleNamespace(id=target_flow_version_id, flow_id=uuid4(), data={})
        session = AsyncMock()
        session.get.return_value = SimpleNamespace(id=uuid4())

        response = await update_snapshot(
            provider_snapshot_id="tool-1",
            body=SnapshotUpdateRequest(flow_version_id=target_flow_version_id),
            session=session,
            current_user=user,
            telemetry=_fake_telemetry(),
        )
        assert response.provider_snapshot_id == "tool-1"
        # Mutation must run inside the OWNER's namespace (Alice's), not the actor's.
        mock_update_rows.assert_awaited_once_with(
            session,
            user_id=alice_id,
            provider_snapshot_id="tool-1",
            flow_version_id=target_flow_version_id,
        )
        mock_validate_fv.assert_awaited_once_with(
            flow_version_ids=[target_flow_version_id],
            user_id=alice_id,
            project_id=alice_dep.project_id,
            db=session,
        )

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.ensure_deployment_permission", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.get_authorization_service")
    @patch("langflow.services.database.models.deployment.crud.get_deployment", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_attachments_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_share_aware_multiple_authorized_groups_returns_409(
        self,
        mock_list_attachments,
        mock_get_deployment_row,
        mock_get_authz,
        mock_ensure_perm,
    ):
        """Actor has WRITE on two unrelated owners' snapshots — route must refuse with 409."""
        from langflow.api.v1.deployments import update_snapshot

        user = _fake_user()
        alice_id = uuid4()
        carol_id = uuid4()
        alice_dep = _fake_deployment_row(user_id=alice_id)
        carol_dep = _fake_deployment_row(user_id=carol_id)
        mock_list_attachments.return_value = [
            SimpleNamespace(
                flow_version_id=uuid4(),
                deployment_id=alice_dep.id,
                provider_snapshot_id="tool-1",
                user_id=alice_id,
            ),
            SimpleNamespace(
                flow_version_id=uuid4(),
                deployment_id=carol_dep.id,
                provider_snapshot_id="tool-1",
                user_id=carol_id,
            ),
        ]
        deps_by_id = {alice_dep.id: alice_dep, carol_dep.id: carol_dep}

        async def _resolve(_session, *, user_id, deployment_id):  # noqa: ARG001
            return deps_by_id.get(deployment_id)

        mock_get_deployment_row.side_effect = _resolve
        mock_get_authz.return_value = self._share_aware_authz()
        # Allow both groups.
        mock_ensure_perm.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await update_snapshot(
                provider_snapshot_id="tool-1",
                body=SnapshotUpdateRequest(flow_version_id=uuid4()),
                session=AsyncMock(),
                current_user=user,
                telemetry=_fake_telemetry(),
            )
        assert exc_info.value.status_code == 409
        assert "multiple owners" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.ensure_deployment_permission", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.get_authorization_service")
    @patch("langflow.services.database.models.deployment.crud.get_deployment", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_attachments_by_provider_snapshot_id", new_callable=AsyncMock)
    async def test_one_owner_spanning_multiple_provider_accounts_returns_409(
        self,
        mock_list_attachments,
        mock_get_deployment_row,
        mock_get_authz,
        mock_ensure_perm,
    ):
        """Single owner across two provider accounts must 409.

        The external snapshot update can only run against one adapter, but the DB
        rewrite would otherwise corrupt rows tied to the second provider account.
        """
        from langflow.api.v1.deployments import update_snapshot

        user = _fake_user()
        owner_id = user.id  # actor is the owner (OSS-path-compatible)
        provider_a = uuid4()
        provider_b = uuid4()
        dep_a = _fake_deployment_row(user_id=owner_id, deployment_provider_account_id=provider_a)
        dep_b = _fake_deployment_row(user_id=owner_id, deployment_provider_account_id=provider_b)
        mock_list_attachments.return_value = [
            SimpleNamespace(
                flow_version_id=uuid4(),
                deployment_id=dep_a.id,
                provider_snapshot_id="tool-1",
                user_id=owner_id,
            ),
            SimpleNamespace(
                flow_version_id=uuid4(),
                deployment_id=dep_b.id,
                provider_snapshot_id="tool-1",
                user_id=owner_id,
            ),
        ]
        deps_by_id = {dep_a.id: dep_a, dep_b.id: dep_b}

        async def _resolve(_session, *, user_id, deployment_id):  # noqa: ARG001
            return deps_by_id.get(deployment_id)

        mock_get_deployment_row.side_effect = _resolve
        # Either share-aware or OSS works; the multi-provider check fires
        # after the owner group is selected so the result is the same.
        mock_get_authz.return_value = self._share_aware_authz()
        mock_ensure_perm.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await update_snapshot(
                provider_snapshot_id="tool-1",
                body=SnapshotUpdateRequest(flow_version_id=uuid4()),
                session=AsyncMock(),
                current_user=user,
                telemetry=_fake_telemetry(),
            )
        assert exc_info.value.status_code == 409
        assert "provider accounts" in exc_info.value.detail.lower()


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
        mock_resolve.return_value = (deployment_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")
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
            telemetry=_fake_telemetry(),
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
                telemetry=_fake_telemetry(),
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
                telemetry=_fake_telemetry(),
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
                telemetry=_fake_telemetry(),
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Provider account is already tracked by user."

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.update_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_update_provider_account_raw_guard_exception_propagates(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_update_provider_account,
    ):
        """PATCH preserves raw guard-shaped DB exceptions without rewriting them."""
        from langflow.api.v1.deployments import update_provider_account

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account

        mapper = MagicMock()
        mapper.resolve_verify_credentials_for_update.return_value = None
        mapper.resolve_provider_account_update.return_value = {"provider_data": {"tenant_id": "tenant-renamed"}}
        mock_get_mapper.return_value = mapper
        mock_resolve_adapter.return_value = AsyncMock()
        mock_update_provider_account.side_effect = Exception(
            "DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE:"
            "Cannot modify provider key, provider tenant id, or provider URL "
            "on an existing deployment provider account. "
            "Re-create the account instead."
        )

        with pytest.raises(
            Exception,
            match="DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE",
        ):
            await update_provider_account(
                provider_id=existing_account.id,
                session=AsyncMock(),
                payload=DeploymentProviderAccountUpdateRequest(provider_data={"tenant_id": "tenant-renamed"}),
                current_user=_fake_user(),
                telemetry=_fake_telemetry(),
            )

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.update_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_update_provider_account_propagates_deployment_guard_error_instance(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_update_provider_account,
    ):
        """PATCH preserves ORM-raised DeploymentGuardError exceptions."""
        from langflow.api.v1.deployments import update_provider_account

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account

        mapper = MagicMock()
        mapper.resolve_verify_credentials_for_update.return_value = None
        mapper.resolve_provider_account_update.return_value = {"provider_data": {"tenant_id": "tenant-renamed"}}
        mock_get_mapper.return_value = mapper
        mock_resolve_adapter.return_value = AsyncMock()
        mock_update_provider_account.side_effect = DeploymentGuardError(
            code="DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE",
            technical_detail="Cannot modify provider key, provider tenant id, or provider URL.",
            detail="Cannot modify provider key, provider tenant id, or provider URL.",
        )

        with pytest.raises(
            DeploymentGuardError,
            match="Cannot modify provider key, provider tenant id, or provider URL",
        ):
            await update_provider_account(
                provider_id=existing_account.id,
                session=AsyncMock(),
                payload=DeploymentProviderAccountUpdateRequest(provider_data={"tenant_id": "tenant-renamed"}),
                current_user=_fake_user(),
                telemetry=_fake_telemetry(),
            )

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock, return_value=([], 1, {}))
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
                telemetry=_fake_telemetry(),
            )

        assert exc_info.value.status_code == 409
        mock_count_deployments.assert_awaited_once()
        mock_list_synced.assert_awaited_once()
        mock_delete_provider_account.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock, return_value=([], 0, {}))
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
            telemetry=_fake_telemetry(),
        )

        assert response.status_code == 204
        mock_count_deployments.assert_awaited_once()
        mock_list_synced.assert_awaited_once()
        mock_delete_provider_account.assert_awaited_once_with(
            session,
            provider_account=existing_account,
        )

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock, return_value=([], 0, {}))
    @patch(f"{ROUTES_MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_delete_provider_account_sets_deployment_provider_scope_for_reconciliation(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_count_deployments,  # noqa: ARG002
        mock_list_synced,
        mock_delete_provider_account,  # noqa: ARG002
    ):
        """Reconciliation must run inside ``deployment_provider_scope`` so adapters can resolve credentials.

        Regression test: without the scope, the WxO adapter raises
        ``CredentialResolutionError("Deployment account context is not available...")``
        with status 401, the reconciliation is silently dropped, and the stale local
        count blocks every provider-account delete with a 409.
        """
        from langflow.api.v1.deployments import delete_provider_account
        from langflow.services.adapters.deployment.context import DeploymentProviderIDContext

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account
        mock_get_mapper.return_value = MagicMock()
        mock_resolve_adapter.return_value = AsyncMock()

        observed_provider_ids: list[object] = []

        async def capture_scope(*_args, **_kwargs):
            current = DeploymentProviderIDContext.get_current()
            observed_provider_ids.append(None if current is None else current.provider_id)
            return ([], 0, {})

        mock_list_synced.side_effect = capture_scope

        response = await delete_provider_account(
            provider_id=existing_account.id,
            session=AsyncMock(),
            current_user=_fake_user(),
            telemetry=_fake_telemetry(),
        )

        assert response.status_code == 204
        assert observed_provider_ids == [existing_account.id], (
            "list_deployments_synced must run inside deployment_provider_scope(provider_account.id) "
            "so the adapter can resolve credentials from DeploymentProviderIDContext."
        )
        # And the scope must not leak after the handler returns.
        assert DeploymentProviderIDContext.get_current() is None

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_delete_provider_account_falls_back_to_local_count_when_reconciliation_raises(
        self,
        mock_get_provider_account,
        mock_get_mapper,
        mock_resolve_adapter,
        mock_count_deployments,
        mock_list_synced,
        mock_delete_provider_account,
    ):
        """If reconciliation fails (e.g. adapter credential error), fall back to the local count.

        The handler must surface the safe 409 (rather than crash) and must NOT delete the
        provider account row while local deployments are still tracked.
        """
        from langflow.api.v1.deployments import delete_provider_account
        from lfx.services.adapters.deployment.exceptions import CredentialResolutionError

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account
        mock_get_mapper.return_value = MagicMock()
        mock_resolve_adapter.return_value = AsyncMock()
        mock_list_synced.side_effect = CredentialResolutionError(
            message="Deployment account context is not available for adapter resolution."
        )

        with pytest.raises(HTTPException) as exc_info:
            await delete_provider_account(
                provider_id=existing_account.id,
                session=AsyncMock(),
                current_user=_fake_user(),
                telemetry=_fake_telemetry(),
            )

        assert exc_info.value.status_code == 409
        mock_count_deployments.assert_awaited_once()
        mock_list_synced.assert_awaited_once()
        mock_delete_provider_account.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.delete_provider_account_row", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.list_deployments_synced", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=0)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_delete_provider_account_skips_reconciliation_when_no_local_deployments(
        self,
        mock_get_provider_account,
        mock_get_mapper,  # noqa: ARG002
        mock_resolve_adapter,  # noqa: ARG002
        mock_count_deployments,
        mock_list_synced,
        mock_delete_provider_account,
    ):
        """When the local count is 0 we must not hit the provider; just delete the row."""
        from langflow.api.v1.deployments import delete_provider_account

        existing_account = _fake_provider_account()
        mock_get_provider_account.return_value = existing_account
        session = AsyncMock()

        response = await delete_provider_account(
            provider_id=existing_account.id,
            session=session,
            current_user=_fake_user(),
            telemetry=_fake_telemetry(),
        )

        assert response.status_code == 204
        mock_count_deployments.assert_awaited_once()
        mock_list_synced.assert_not_awaited()
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
        mapper.resolve_kwargs_for_metadata_update.return_value = {"description": None}
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()
        session.commit.side_effect = RuntimeError("DB commit failed")

        payload = MagicMock()
        payload.display_name = None
        payload.description = None

        with pytest.raises(RuntimeError, match="DB commit failed"):
            await update_deployment(
                deployment_id=dep_row.id,
                session=session,
                payload=payload,
                current_user=_fake_user(),
                telemetry=_fake_telemetry(),
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
        mapper.resolve_kwargs_for_metadata_update.return_value = {"description": None}
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.display_name = None
        payload.description = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
            telemetry=_fake_telemetry(),
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
        mapper.resolve_kwargs_for_metadata_update.return_value = {"description": None}
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")

        reused_fv_id = uuid4()
        new_fv_id = uuid4()
        mock_resolve_fvp.return_value = ([reused_fv_id, new_fv_id], [])

        mock_list_attachments.return_value = [
            SimpleNamespace(flow_version_id=reused_fv_id, provider_snapshot_id="existing-tool-1"),
        ]

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.display_name = None
        payload.description = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
            telemetry=_fake_telemetry(),
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
        mapper.resolve_kwargs_for_metadata_update.return_value = {"description": None}
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")

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
        payload.display_name = None
        payload.description = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
            telemetry=_fake_telemetry(),
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
        mapper.resolve_kwargs_for_metadata_update.return_value = {}
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")

        fv_id_1 = uuid4()
        fv_id_2 = uuid4()
        mock_resolve_fvp.return_value = ([fv_id_1, fv_id_2], [])

        mock_list_attachments.return_value = []

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.display_name = None
        payload.description = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
            telemetry=_fake_telemetry(),
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
    async def test_provider_update_metadata_is_persisted_from_adapter_result(
        self,
        mock_resolve_amm,
        mock_resolve_fvp,  # noqa: ARG002
        mock_validate_fv,  # noqa: ARG002
        mock_resolve_snap,  # noqa: ARG002
        mock_apply_patch,  # noqa: ARG002
        mock_update_db,
    ):
        """PATCH should persist provider-returned metadata, even when the DB row is stale."""
        from langflow.api.v1.deployments import update_deployment

        dep_row = _fake_deployment_row(display_name="old-name", description="old-description")
        updated_row = _fake_deployment_row(
            id=dep_row.id,
            resource_key=dep_row.resource_key,
            display_name="provider-renamed",
            description="provider-description",
            deployment_provider_account_id=dep_row.deployment_provider_account_id,
            project_id=dep_row.project_id,
        )
        adapter = AsyncMock()
        mapper = MagicMock()
        update_result = DeploymentUpdateResult(id="provider-dep-1")
        adapter.update.return_value = update_result
        mapper.resolve_deployment_update = AsyncMock(return_value=MagicMock())
        mapper.shape_deployment_update_result.return_value = MagicMock()
        mapper.resolve_kwargs_for_metadata_update.return_value = {
            "display_name": "provider-renamed",
            "description": "provider-description",
        }
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")
        mock_update_db.return_value = updated_row

        session = AsyncMock()
        session.commit.return_value = None

        payload = DeploymentUpdateRequest.model_validate(
            {
                "provider_data": {"display_name": "renamed"},
                "description": None,
            }
        )

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
            telemetry=_fake_telemetry(),
        )

        mock_update_db.assert_awaited_once()
        update_kwargs = mock_update_db.call_args.kwargs
        assert update_kwargs["display_name"] == "provider-renamed"
        assert update_kwargs["description"] == "provider-description"
        mapper.resolve_kwargs_for_metadata_update.assert_called_once_with(update_result)


# ---------------------------------------------------------------------------
# get_deployment: deployment-level sync
# ---------------------------------------------------------------------------


class TestGetDeploymentSync:
    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_stale_row_deleted_when_provider_returns_not_found(
        self,
        mock_resolve,
        mock_delete_row,
    ):
        """When the provider raises DeploymentNotFoundError, the DB row is deleted and 404 returned."""
        from langflow.api.v1.deployments import get_deployment
        from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        adapter.get.side_effect = DeploymentNotFoundError(message="gone")
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper(), "watsonx-orchestrate", "tenant-1")

        user = _fake_user()
        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=user)

        assert exc_info.value.status_code == 404
        # Stale-row delete now runs in the deployment owner's namespace so
        # a non-owner with a share grant can still prune the owner's stale
        # row. ``current_user`` is only the actor for audit.
        mock_delete_row.assert_awaited_once_with(session, user_id=dep_row.user_id, deployment_id=dep_row.id)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
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
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper(), "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 401
        mock_delete_row.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
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
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper(), "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 503
        mock_delete_row.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.count_deployment_attachments", new_callable=AsyncMock, return_value=0)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_get_deployment_does_not_inject_resource_key_into_provider_data(
        self,
        mock_resolve,
        mock_count_att,  # noqa: ARG002
        mock_delete_unbound,  # noqa: ARG002
    ):
        from langflow.api.v1.deployments import get_deployment
        from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper

        class _MapperForGet(BaseDeploymentMapper):
            def shape_deployment_get_data(self, provider_data, *, name=None):  # noqa: ARG002
                if provider_data is None:
                    return None
                sanitized_provider_data = dict(provider_data)
                sanitized_provider_data.pop("tool_ids", None)
                return sanitized_provider_data or None

            def extract_metadata_for_get(self, get_result):
                _ = get_result
                return {"display_name": dep_row.display_name, "description": dep_row.description}

            def extract_snapshot_bindings_for_get(self, get_result, *, resource_key: str):
                return [
                    ProviderSnapshotBinding(resource_key=resource_key, snapshot_id=snapshot_id)
                    for snapshot_id in get_result.model_dump()["provider_data"]["tool_ids"]
                ]

        created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        updated_at = datetime(2026, 1, 3, 4, 5, 6, tzinfo=timezone.utc)
        dep_row = _fake_deployment_row(
            resource_key="provider-rk-1",
            display_name="db-owned-name",
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
                "tool_ids": ["tool-1", "tool-2"],
            }
        }
        adapter.get.return_value = provider_deployment
        mock_resolve.return_value = (dep_row, adapter, _MapperForGet(), "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()
        session.begin_nested = MagicMock(return_value=_AsyncNoopSavepoint())
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.resource_key == "provider-rk-1"
        assert result.description == "db-owned-description"
        assert result.type == "agent"
        assert result.created_at == created_at
        assert result.updated_at == updated_at
        assert "tool_ids" not in result.provider_data
        assert result.provider_data == {"llm": "virtual-model/bedrock/openai.gpt-oss-120b-1:0"}

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.count_deployment_attachments", new_callable=AsyncMock, return_value=0)
    @patch(f"{HELPERS_MODULE}.update_deployment_metadata", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_get_sync_passes_provider_description_and_keeps_display_name_in_provider_data(
        self,
        mock_resolve,
        mock_update_metadata,
        mock_count_att,  # noqa: ARG002
        mock_delete_unbound,  # noqa: ARG002
    ):
        from langflow.api.v1.deployments import get_deployment
        from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper

        class _MapperForGet(BaseDeploymentMapper):
            def shape_deployment_get_data(self, provider_data, *, name=None):  # noqa: ARG002
                return dict(provider_data) if provider_data is not None else None

            def extract_metadata_for_get(self, get_result):
                data = get_result.model_dump()["provider_data"]
                return {
                    "display_name": data["display_name"],
                    "description": data["description"],
                }

            def extract_snapshot_bindings_for_get(self, get_result, *, resource_key: str):
                _ = (get_result, resource_key)
                return []

        dep_row = _fake_deployment_row(
            resource_key="provider-rk-1",
            display_name="old label",
            description="old description",
            deployment_type="agent",
        )
        long_description = "x" * 501
        adapter = AsyncMock()
        adapter.get.return_value = DeploymentGetResult(
            id="provider-rk-1",
            name="agent_technical_name",
            type="agent",
            provider_data={
                "display_name": "Provider Label",
                "description": long_description,
            },
        )

        def _apply_metadata(*_args, **kwargs):
            dep_row.display_name = kwargs["display_name"]
            dep_row.description = kwargs["description"]
            return dep_row

        mock_update_metadata.side_effect = _apply_metadata
        mock_resolve.return_value = (dep_row, adapter, _MapperForGet(), "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()
        session.begin_nested = MagicMock(return_value=_AsyncNoopSavepoint())
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.description == long_description
        assert result.provider_data["display_name"] == "Provider Label"
        assert not hasattr(result, "display_name")
        mock_update_metadata.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.count_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_snapshot_sync_corrects_attached_count(
        self,
        mock_resolve,
        mock_count_att,
        mock_delete_unbound,
    ):
        """Binding-aware sync corrects attached_count in the response."""
        from langflow.api.v1.deployments import get_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        provider_deployment = MagicMock()
        provider_deployment.name = "deployed-agent"
        provider_deployment.description = "desc"
        provider_deployment.type = "agent"
        provider_deployment.created_at = None
        provider_deployment.updated_at = None
        provider_deployment.model_dump.return_value = {}
        adapter.get.return_value = provider_deployment
        mapper.extract_snapshot_bindings_for_get.return_value = [
            ProviderSnapshotBinding(resource_key=dep_row.resource_key, snapshot_id="snap-1")
        ]
        mapper.extract_metadata_for_get.return_value = {
            "display_name": dep_row.display_name,
            "description": dep_row.description,
        }
        mapper.shape_deployment_get_data.return_value = None
        mock_resolve.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")
        mock_count_att.return_value = 1

        session = AsyncMock()
        session.begin_nested = MagicMock(return_value=_AsyncNoopSavepoint())
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.attached_count == 1
        mock_delete_unbound.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.count_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_unsupported_provider_get_sync_raises(
        self,
        mock_resolve,
        mock_count_att,
        mock_delete_unbound,
    ):
        """NotImplemented mapper GET sync fails because binding-aware sync is required."""
        from langflow.api.v1.deployments import get_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        provider_deployment = MagicMock()
        provider_deployment.name = "deployed-agent"
        provider_deployment.description = "desc"
        provider_deployment.type = "agent"
        provider_deployment.created_at = None
        provider_deployment.updated_at = None
        provider_deployment.model_dump.return_value = {}
        adapter.get.return_value = provider_deployment
        mapper.extract_snapshot_bindings_for_get.side_effect = NotImplementedError("not supported")
        mapper.extract_metadata_for_get.return_value = {
            "display_name": dep_row.display_name,
            "description": dep_row.description,
        }
        mapper.shape_deployment_get_data.return_value = None
        mock_resolve.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 500
        assert "does not support binding-aware GET sync" in str(exc_info.value.detail)
        session.rollback.assert_not_awaited()
        mock_count_att.assert_not_awaited()
        mock_delete_unbound.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.count_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_binding_aware_sync_error_falls_back_to_unverified_count(
        self,
        mock_resolve,
        mock_count_att,
        mock_delete_unbound,
    ):
        """When binding-aware sync raises, response uses unverified attachment count."""
        from langflow.api.v1.deployments import get_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        provider_deployment = MagicMock()
        provider_deployment.name = "deployed-agent"
        provider_deployment.description = "desc"
        provider_deployment.type = "agent"
        provider_deployment.created_at = None
        provider_deployment.updated_at = None
        provider_deployment.model_dump.return_value = {}
        adapter.get.return_value = provider_deployment
        mapper.extract_snapshot_bindings_for_get.return_value = [
            ProviderSnapshotBinding(resource_key=dep_row.resource_key, snapshot_id="snap-1")
        ]
        mapper.extract_metadata_for_get.return_value = {
            "display_name": dep_row.display_name,
            "description": dep_row.description,
        }
        mapper.shape_deployment_get_data.return_value = None
        mock_resolve.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")
        mock_count_att.return_value = 2
        mock_delete_unbound.side_effect = RuntimeError("provider down")

        session = AsyncMock()
        session.begin_nested = MagicMock(return_value=_AsyncNoopSavepoint())
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.attached_count == 2
        session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.count_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_binding_aware_sync_and_fallback_count_failure_raises(
        self,
        mock_resolve,
        mock_count_att,
        mock_delete_unbound,
    ):
        """When sync and fallback count both fail, return an explicit count error."""
        from langflow.api.v1.deployments import get_deployment

        dep_row = _fake_deployment_row()
        adapter = AsyncMock()
        mapper = MagicMock()
        provider_deployment = MagicMock()
        provider_deployment.name = "deployed-agent"
        provider_deployment.description = "desc"
        provider_deployment.type = "agent"
        provider_deployment.created_at = None
        provider_deployment.updated_at = None
        provider_deployment.model_dump.return_value = {}
        adapter.get.return_value = provider_deployment
        mapper.extract_snapshot_bindings_for_get.return_value = [
            ProviderSnapshotBinding(resource_key=dep_row.resource_key, snapshot_id="snap-1")
        ]
        mapper.extract_metadata_for_get.return_value = {
            "display_name": dep_row.display_name,
            "description": dep_row.description,
        }
        mapper.shape_deployment_get_data.return_value = None
        mock_resolve.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")
        mock_delete_unbound.side_effect = RuntimeError("sync failed")
        mock_count_att.side_effect = RuntimeError("count failed")

        session = AsyncMock()
        session.begin_nested = MagicMock(return_value=_AsyncNoopSavepoint())
        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 500
        assert str(dep_row.id) in str(exc_info.value.detail)
        assert "Failed to retrieve the number of flows attached" in str(exc_info.value.detail)
        session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{HELPERS_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{HELPERS_MODULE}.count_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_adapter_mapper_from_deployment", new_callable=AsyncMock)
    async def test_binding_aware_sync_prunes_detached_attachments(
        self,
        mock_resolve,
        mock_count_att,
        mock_delete_unbound,
    ):
        """Binding-aware sync sends authoritative bindings and returns corrected count."""
        from langflow.api.v1.deployments import get_deployment

        dep_row = _fake_deployment_row(resource_key="agent-rk-1")
        adapter = AsyncMock()
        mapper = MagicMock()
        provider_deployment = MagicMock()
        provider_deployment.model_dump.return_value = {}
        adapter.get.return_value = provider_deployment
        mapper.extract_snapshot_bindings_for_get.return_value = [
            ProviderSnapshotBinding(resource_key="agent-rk-1", snapshot_id="snap-1")
        ]
        mapper.extract_metadata_for_get.return_value = {
            "display_name": dep_row.display_name,
            "description": dep_row.description,
        }
        mapper.shape_deployment_get_data.return_value = None
        mock_resolve.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")
        mock_count_att.return_value = 1

        session = AsyncMock()
        session.begin_nested = MagicMock(return_value=_AsyncNoopSavepoint())
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.attached_count == 1
        mock_delete_unbound.assert_awaited_once_with(
            db=session,
            user_id=ANY,
            provider_account_id=dep_row.deployment_provider_account_id,
            deployment_ids=[dep_row.id],
            bindings=[ProviderSnapshotBinding(resource_key="agent-rk-1", snapshot_id="snap-1")],
        )


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
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate", "tenant-1")

        user = _fake_user()
        session = AsyncMock()

        response = await delete_deployment(
            deployment_id=dep_row.id, session=session, current_user=user, telemetry=_fake_telemetry()
        )

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
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await delete_deployment(
                deployment_id=dep_row.id, session=session, current_user=_fake_user(), telemetry=_fake_telemetry()
            )

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
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate", "tenant-1")

        user = _fake_user()
        session = AsyncMock()
        session.commit.side_effect = [RuntimeError("commit failed"), None]

        response = await delete_deployment(
            deployment_id=dep_row.id, session=session, current_user=user, telemetry=_fake_telemetry()
        )

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
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate", "tenant-1")

        session = AsyncMock()
        session.commit.side_effect = [RuntimeError("commit failed"), RuntimeError("still failing")]

        with pytest.raises(HTTPException) as exc_info:
            await delete_deployment(
                deployment_id=dep_row.id, session=session, current_user=_fake_user(), telemetry=_fake_telemetry()
            )

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
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate", "tenant-1")

        user = _fake_user()
        session = AsyncMock()

        response = await delete_deployment(
            deployment_id=dep_row.id,
            session=session,
            current_user=user,
            include_provider=True,
            telemetry=_fake_telemetry(),
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
        mock_resolve.return_value = (dep_row, adapter, "watsonx-orchestrate", "tenant-1")

        user = _fake_user()
        session = AsyncMock()

        response = await delete_deployment(
            deployment_id=dep_row.id,
            session=session,
            current_user=user,
            include_provider=False,
            telemetry=_fake_telemetry(),
        )

        assert response.status_code == 204
        adapter.delete.assert_not_awaited()
        mock_delete_row.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_deployment: duplicate name returns 409
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# create_deployment: project-scoped flow version validation
# ---------------------------------------------------------------------------


class TestCreateDeploymentProjectValidation:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_validation_called_before_adapter(
        self,
        mock_get_pa,
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
            await create_deployment(
                session=AsyncMock(), payload=payload, current_user=_fake_user(), telemetry=_fake_telemetry()
            )

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
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_empty_flow_version_ids_skips_validation(
        self,
        mock_get_pa,
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
        create_result = DeploymentCreateResult(id="prov-1", type=DeploymentType.AGENT)
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
        payload.display_name = "test"
        payload.type = "agent"
        payload.description = None

        session = AsyncMock()
        session.commit.return_value = None

        with (
            patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock, return_value=_fake_deployment_row()),
            patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock),
        ):
            mapper.shape_deployment_create_result.return_value = MagicMock()
            await create_deployment(
                session=session, payload=payload, current_user=_fake_user(), telemetry=_fake_telemetry()
            )

        mock_validate_fv.assert_awaited_once()
        assert mock_validate_fv.call_args.kwargs["flow_version_ids"] == []


class TestCreateDeploymentSchemaValidation:
    @pytest.mark.asyncio
    @patch(f"{ROUTES_MODULE}.validate_project_scoped_flow_version_ids", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_project_id_for_deployment_create", new_callable=AsyncMock)
    @patch(f"{ROUTES_MODULE}.resolve_deployment_adapter")
    @patch(f"{ROUTES_MODULE}.get_deployment_mapper")
    @patch(f"{ROUTES_MODULE}.get_owned_provider_account_or_404", new_callable=AsyncMock)
    async def test_mapper_schema_validation_error_surfaces_422(
        self,
        mock_get_pa,
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
            await create_deployment(
                session=AsyncMock(), payload=payload, current_user=_fake_user(), telemetry=_fake_telemetry()
            )

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
        mock_resolve_amm.return_value = (dep_row, adapter, mapper, "watsonx-orchestrate", "tenant-1")

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
                telemetry=_fake_telemetry(),
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
