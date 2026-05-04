# ruff: noqa: ARG001
from __future__ import annotations

from contextlib import ExitStack
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from lfx.services.settings.feature_flags import FEATURE_FLAGS

if TYPE_CHECKING:
    from httpx import AsyncClient

# We'll use a mocked adapter so we don't need real credentials.
# We need to mock the adapter resolution and the telemetry service.

pytestmark = pytest.mark.skipif(
    not FEATURE_FLAGS.wxo_deployments,
    reason="wxo_deployments feature flag is disabled; deployment routes are not mounted.",
)


@pytest.fixture
def mock_telemetry_service():
    with patch("langflow.api.v1.deployments.get_telemetry_service") as mock_get:
        mock_ts = AsyncMock()
        mock_get.return_value = mock_ts
        yield mock_ts


@pytest.fixture
def mock_adapter():
    with patch("langflow.api.v1.deployments.resolve_deployment_adapter") as mock_resolve:
        mock_ad = AsyncMock()
        mock_resolve.return_value = mock_ad
        yield mock_ad


@pytest.fixture
def mock_mapper():
    with patch("langflow.api.v1.deployments.get_deployment_mapper") as mock_get:
        mock_map = MagicMock()
        # Ensure it returns something valid for verify_credentials
        mock_map.resolve_verify_credentials_for_create.return_value = {}
        mock_map.resolve_verify_credentials_for_update.return_value = {}
        mock_map.resolve_provider_account_create.return_value = AsyncMock(
            id=uuid4(), provider_key="watsonx-orchestrate"
        )
        mock_map.resolve_provider_account_response.return_value = {
            "id": str(uuid4()),
            "provider_key": "watsonx-orchestrate",
            "name": "Test",
        }
        mock_map.util_existing_deployment_resource_key_for_create.return_value = None
        mock_map.resolve_deployment_create = AsyncMock(return_value={})
        mock_map.resolve_deployment_update = AsyncMock(return_value={})
        mock_map.util_create_flow_version_ids.return_value = []
        mock_map.shape_deployment_create_result.return_value = {
            "id": str(uuid4()),
            "provider_id": str(uuid4()),
            "provider_key": "watsonx-orchestrate",
            "name": "Test",
            "type": "agent",
            "resource_key": "res-1",
        }
        mock_map.shape_deployment_update_result.return_value = {
            "id": str(uuid4()),
            "provider_id": str(uuid4()),
            "provider_key": "watsonx-orchestrate",
            "name": "Test",
            "type": "agent",
            "resource_key": "res-1",
        }
        mock_map.resolve_execution_create = AsyncMock(return_value={})
        mock_map.shape_execution_create_result.return_value = {"id": "run-1", "deployment_id": str(uuid4())}
        mock_map.resolve_snapshot_update_artifact.return_value = {}
        mock_get.return_value = mock_map
        yield mock_map


@pytest.fixture
def mock_db_crud(mock_mapper):
    with ExitStack() as stack:
        mock_create = stack.enter_context(patch("langflow.api.v1.deployments.create_provider_account_row"))
        mock_get_owned = stack.enter_context(patch("langflow.api.v1.deployments.get_owned_provider_account_or_404"))
        _mock_del_prov = stack.enter_context(patch("langflow.api.v1.deployments.delete_provider_account_row"))
        _mock_upd_prov = stack.enter_context(patch("langflow.api.v1.deployments.update_provider_account_row"))
        mock_name_exists = stack.enter_context(patch("langflow.api.v1.deployments.deployment_name_exists"))
        mock_proj_id = stack.enter_context(
            patch("langflow.api.v1.deployments.resolve_project_id_for_deployment_create")
        )
        mock_create_dep = stack.enter_context(patch("langflow.api.v1.deployments.create_deployment_db"))
        _mock_attach = stack.enter_context(patch("langflow.api.v1.deployments.attach_flow_versions"))
        mock_res_am = stack.enter_context(patch("langflow.api.v1.deployments.resolve_adapter_mapper_from_deployment"))
        mock_res_patch = stack.enter_context(patch("langflow.api.v1.deployments.resolve_flow_version_patch_for_update"))
        _mock_val_proj = stack.enter_context(
            patch("langflow.api.v1.deployments.validate_project_scoped_flow_version_ids")
        )
        mock_list_att = stack.enter_context(
            patch("langflow.api.v1.deployments.list_deployment_attachments_for_flow_version_ids")
        )
        _mock_apply_patch = stack.enter_context(
            patch("langflow.api.v1.deployments.apply_flow_version_patch_attachments")
        )
        mock_upd_dep = stack.enter_context(patch("langflow.api.v1.deployments.update_deployment_db"))
        mock_res_ad = stack.enter_context(patch("langflow.api.v1.deployments.resolve_adapter_from_deployment"))
        _mock_del_dep = stack.enter_context(
            patch("langflow.api.v1.deployments._delete_local_deployment_row_with_commit_retry")
        )
        mock_get_att = stack.enter_context(patch("langflow.api.v1.deployments.get_attachment_by_provider_snapshot_id"))
        mock_get_dep_row = stack.enter_context(
            patch("langflow.services.database.models.deployment.crud.get_deployment")
        )
        mock_get_fv = stack.enter_context(
            patch("langflow.services.database.models.flow_version.crud.get_flow_version_entry")
        )
        mock_upd_fv = stack.enter_context(
            patch("langflow.api.v1.deployments.update_flow_version_by_provider_snapshot_id")
        )
        mock_count_deps = stack.enter_context(
            patch("langflow.api.v1.deployments._count_provider_deployments_after_reconciliation")
        )

        mock_create.return_value = AsyncMock(
            id=uuid4(), provider_key="watsonx-orchestrate", provider_tenant_id="tenant-test"
        )
        mock_get_owned.return_value = AsyncMock(
            id=uuid4(), provider_key="watsonx-orchestrate", provider_tenant_id="tenant-test"
        )
        mock_name_exists.return_value = False
        mock_proj_id.return_value = uuid4()
        mock_create_dep.return_value = AsyncMock(id=uuid4())

        mock_res_am.return_value = (
            AsyncMock(id=uuid4(), resource_key="res-1", deployment_provider_account_id=uuid4(), project_id=uuid4()),
            AsyncMock(),
            mock_mapper,
            "watsonx-orchestrate",
            "tenant-test",
        )
        mock_res_patch.return_value = ([], [])
        mock_list_att.return_value = []
        mock_upd_dep.return_value = AsyncMock()
        mock_res_ad.return_value = (
            AsyncMock(id=uuid4(), resource_key="res-1", deployment_provider_account_id=uuid4()),
            AsyncMock(),
            "watsonx-orchestrate",
            "tenant-test",
        )
        mock_get_att.return_value = AsyncMock(deployment_id=uuid4(), flow_version_id=uuid4())
        mock_get_dep_row.return_value = AsyncMock(deployment_provider_account_id=uuid4())
        mock_get_fv.return_value = AsyncMock(flow_id=uuid4(), data={})
        mock_upd_fv.return_value = 1
        mock_count_deps.return_value = 0

        yield


@pytest.mark.asyncio
async def test_create_provider_account_telemetry(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    response = await client.post(
        "api/v1/deployments/providers",
        json={"provider_key": "watsonx-orchestrate", "name": "Test", "provider_data": {"foo": "bar"}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    mock_telemetry_service.log_package_deployment_provider.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment_provider.call_args[0][0]
    assert payload.deployment_action == "provider.create"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is True
    assert payload.wxo_tenant_id == "tenant-test"


@pytest.mark.asyncio
async def test_update_provider_account_telemetry(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    response = await client.patch(
        f"api/v1/deployments/providers/{uuid4()}",
        json={"name": "Test", "provider_data": {"foo": "bar"}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    mock_telemetry_service.log_package_deployment_provider.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment_provider.call_args[0][0]
    assert payload.deployment_action == "provider.update"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is True
    assert payload.wxo_tenant_id == "tenant-test"


@pytest.mark.asyncio
async def test_delete_provider_account_telemetry(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    response = await client.delete(f"api/v1/deployments/providers/{uuid4()}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_telemetry_service.log_package_deployment_provider.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment_provider.call_args[0][0]
    assert payload.deployment_action == "provider.delete"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is True
    assert payload.wxo_tenant_id == "tenant-test"


@pytest.mark.asyncio
async def test_create_deployment_telemetry(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    response = await client.post(
        "api/v1/deployments",
        json={"provider_id": str(uuid4()), "name": "Test", "type": "agent", "provider_data": {}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.json()
    mock_telemetry_service.log_package_deployment.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment.call_args[0][0]
    assert payload.deployment_action == "deployment.create"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is True
    assert payload.wxo_tenant_id == "tenant-test"


@pytest.mark.asyncio
async def test_update_deployment_telemetry(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    response = await client.patch(f"api/v1/deployments/{uuid4()}", json={"name": "Test"}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    mock_telemetry_service.log_package_deployment.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment.call_args[0][0]
    assert payload.deployment_action == "deployment.update"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is True
    assert payload.wxo_tenant_id == "tenant-test"


@pytest.mark.asyncio
async def test_delete_deployment_telemetry(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    response = await client.delete(f"api/v1/deployments/{uuid4()}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_telemetry_service.log_package_deployment.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment.call_args[0][0]
    assert payload.deployment_action == "deployment.delete"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is True
    assert payload.wxo_tenant_id == "tenant-test"


@pytest.mark.asyncio
async def test_create_deployment_run_telemetry(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    response = await client.post(
        f"api/v1/deployments/{uuid4()}/runs", json={"provider_data": {}}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_201_CREATED, response.json()
    mock_telemetry_service.log_package_deployment_run.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment_run.call_args[0][0]
    assert payload.deployment_action == "deployment.run"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is True
    assert payload.wxo_tenant_id == "tenant-test"


@pytest.mark.asyncio
async def test_update_snapshot_telemetry(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    response = await client.patch(
        "api/v1/deployments/snapshots/snap-1", json={"flow_version_id": str(uuid4())}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK
    mock_telemetry_service.log_package_deployment.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment.call_args[0][0]
    assert payload.deployment_action == "snapshot.update"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is True
    assert payload.wxo_tenant_id == "tenant-test"


@pytest.mark.asyncio
async def test_create_provider_account_telemetry_error(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    mock_adapter.verify_credentials.side_effect = ValueError("Invalid credentials")
    response = await client.post(
        "api/v1/deployments/providers",
        json={"provider_key": "watsonx-orchestrate", "name": "Test", "provider_data": {"foo": "bar"}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    mock_telemetry_service.log_package_deployment_provider.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment_provider.call_args[0][0]
    assert payload.deployment_action == "provider.create"
    assert payload.deployment_provider == "watsonx-orchestrate"
    assert payload.deployment_success is False
    assert payload.deployment_error_message == "400: Invalid credentials"
    # verify_credentials raises before the row is created, so the tenant_id is not yet set.
    assert payload.wxo_tenant_id is None


@pytest.mark.asyncio
async def test_cross_route_smoke_exception_after_provider_set(
    client: AsyncClient, mock_telemetry_service, mock_adapter, mock_mapper, mock_db_crud, logged_in_headers
):
    # Simulate an error during adapter.create after the provider has been set in the route
    mock_adapter.create.side_effect = RuntimeError("Something went wrong")
    response = await client.post(
        "api/v1/deployments",
        json={"provider_id": str(uuid4()), "name": "Test", "type": "agent", "provider_data": {}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    mock_telemetry_service.log_package_deployment.assert_awaited_once()
    payload = mock_telemetry_service.log_package_deployment.call_args[0][0]
    assert payload.deployment_action == "deployment.create"
    assert payload.deployment_provider == "watsonx-orchestrate"  # Provider should be captured!
    assert payload.deployment_success is False
    assert payload.deployment_error_message == (
        "500: An unexpected error occurred while communicating with the deployment provider."
    )
    # tenant_id is captured before the adapter call that raises.
    assert payload.wxo_tenant_id == "tenant-test"
