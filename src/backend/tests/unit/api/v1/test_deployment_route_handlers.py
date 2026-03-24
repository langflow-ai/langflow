"""Route-handler-level tests for deployment endpoints.

Covers the integration behaviour of the FastAPI route handlers:
- Rollback on commit failure (create / update)
- GET single-deployment synchronization (deployment-level and snapshot-level)
- Project-scoped flow-version validation (create / update)
- Stubbed 501 routes (redeploy / duplicate)
- resolve_deployment_adapter edge cases
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from lfx.services.adapters.deployment.exceptions import (
    AuthenticationError,
    DeploymentNotFoundError,
    ServiceUnavailableError,
)
from lfx.services.adapters.deployment.schema import DeploymentCreateResult, DeploymentUpdateResult

ROUTES_MODULE = "langflow.api.v1.deployments"
HELPERS_MODULE = "langflow.api.v1.mappers.deployments.helpers"


# ---------------------------------------------------------------------------
# Shared factories
# ---------------------------------------------------------------------------


def _fake_provider_account(*, provider_key: str = "watsonx_orchestrate") -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), provider_key=provider_key)


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
        create_result = DeploymentCreateResult(id="provider-dep-1")
        adapter.create.return_value = create_result
        mock_resolve_adapter.return_value = adapter
        mapper = MagicMock()
        mapper.util_create_flow_version_ids.return_value = []
        mapper.resolve_deployment_create = AsyncMock(return_value=MagicMock())
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        mock_create_db.return_value = _fake_deployment_row()

        session = AsyncMock()
        session.commit.side_effect = RuntimeError("DB commit failed")

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.spec.name = "test"
        payload.spec.type = "agent"
        payload.spec.description = None

        with pytest.raises(RuntimeError, match="DB commit failed"):
            await create_deployment(session=session, payload=payload, current_user=_fake_user())

        mock_rollback.assert_awaited_once()
        assert mock_rollback.call_args.kwargs["resource_id"] == create_result.id

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
        mapper.resolve_deployment_create = AsyncMock(return_value=MagicMock())
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()
        dep_row = _fake_deployment_row()
        mock_create_db.return_value = dep_row

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.spec.name = "test"
        payload.spec.type = "agent"
        payload.spec.description = None

        with patch(f"{ROUTES_MODULE}.to_deployment_create_response") as mock_response:
            mock_response.return_value = MagicMock()
            await create_deployment(session=session, payload=payload, current_user=_fake_user())

        mock_rollback.assert_not_awaited()


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
        mock_resolve_amm.return_value = (dep_row, adapter, mapper)

        session = AsyncMock()
        session.commit.side_effect = RuntimeError("DB commit failed")

        payload = MagicMock()
        payload.spec = None

        with pytest.raises(RuntimeError, match="DB commit failed"):
            await update_deployment(
                deployment_id=dep_row.id,
                session=session,
                payload=payload,
                current_user=_fake_user(),
            )

        mock_rollback.assert_awaited_once()
        assert mock_rollback.call_args.kwargs["deployment_row"] is dep_row

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
        mock_resolve_amm.return_value = (dep_row, adapter, mapper)

        session = AsyncMock()
        session.commit.return_value = None

        payload = MagicMock()
        payload.spec = None

        await update_deployment(
            deployment_id=dep_row.id,
            session=session,
            payload=payload,
            current_user=_fake_user(),
        )

        mock_rollback.assert_not_awaited()


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
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper())

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
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper())

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
        mock_resolve.return_value = (dep_row, adapter, BaseDeploymentMapper())

        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert exc_info.value.status_code == 503
        mock_delete_row.assert_not_awaited()

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
        from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper

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
        mock_resolve.return_value = (dep_row, adapter, WatsonxOrchestrateDeploymentMapper())

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
        from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper

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
        mock_resolve.return_value = (dep_row, adapter, WatsonxOrchestrateDeploymentMapper())
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
        from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper

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
        mock_resolve.return_value = (dep_row, adapter, WatsonxOrchestrateDeploymentMapper())

        att1 = _fake_attachment(provider_snapshot_id="snap-1")
        att2 = _fake_attachment(provider_snapshot_id="snap-2")
        mock_list_att.return_value = [att1, att2]
        mock_fetch_snap.side_effect = RuntimeError("provider down")

        session = AsyncMock()
        result = await get_deployment(deployment_id=dep_row.id, session=session, current_user=_fake_user())

        assert result.attached_count == 2
        mock_sync_snap.assert_not_awaited()


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
        payload.spec.name = "duplicate-name"

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
        payload.spec.name = "taken"

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
        mapper.resolve_deployment_create = AsyncMock(return_value=MagicMock())
        mock_get_mapper.return_value = mapper
        mock_resolve_project.return_value = uuid4()

        payload = MagicMock()
        payload.provider_id = pa.id
        payload.spec.name = "test"
        payload.spec.type = "agent"
        payload.spec.description = None

        session = AsyncMock()
        session.commit.return_value = None

        with (
            patch(f"{ROUTES_MODULE}.create_deployment_db", new_callable=AsyncMock, return_value=_fake_deployment_row()),
            patch(f"{ROUTES_MODULE}.attach_flow_versions", new_callable=AsyncMock),
            patch(f"{ROUTES_MODULE}.to_deployment_create_response", return_value=MagicMock()),
        ):
            await create_deployment(session=session, payload=payload, current_user=_fake_user())

        mock_validate_fv.assert_awaited_once()
        assert mock_validate_fv.call_args.kwargs["flow_version_ids"] == []


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
        mock_resolve_amm.return_value = (dep_row, adapter, mapper)

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
# Stubbed 501 routes
# ---------------------------------------------------------------------------


class TestStubbedRoutes:
    @pytest.mark.asyncio
    async def test_redeploy_returns_501(self):
        from langflow.api.v1.deployments import redeploy_deployment

        with pytest.raises(HTTPException) as exc_info:
            await redeploy_deployment(
                deployment_id=uuid4(),
                session=AsyncMock(),
                current_user=_fake_user(),
            )

        assert exc_info.value.status_code == 501

    @pytest.mark.asyncio
    async def test_duplicate_returns_501(self):
        from langflow.api.v1.deployments import duplicate_deployment

        with pytest.raises(HTTPException) as exc_info:
            await duplicate_deployment(
                deployment_id=uuid4(),
                session=AsyncMock(),
                current_user=_fake_user(),
            )

        assert exc_info.value.status_code == 501


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
