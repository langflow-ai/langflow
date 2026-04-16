from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper
from lfx.services.adapters.deployment.schema import (
    DeploymentCreateResult,
    DeploymentListResult,
    DeploymentType,
    DeploymentUpdateResult,
    ExecutionCreateResult,
    ItemResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deployment_row(**overrides):
    defaults = {
        "id": uuid4(),
        "deployment_provider_account_id": uuid4(),
        "name": "db-deployment-name",
        "description": "db-description",
        "deployment_type": DeploymentType.AGENT,
        "resource_key": "provider-deployment-id",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# shape_deployment_create_result
# ---------------------------------------------------------------------------


def test_shape_deployment_create_result_maps_db_identity_and_provider_result() -> None:
    mapper = BaseDeploymentMapper()
    provider_account_id = uuid4()
    now = datetime.now(timezone.utc)
    deployment_row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=provider_account_id,
        name="db-deployment-name",
        description="db-description",
        deployment_type=DeploymentType.AGENT,
        resource_key="provider-deployment-id",
        created_at=now,
        updated_at=now,
    )
    adapter_result = DeploymentCreateResult(
        id="provider-deployment-id",
        provider_result={"snapshot_bindings": [{"source_ref": "fv-1", "snapshot_id": "tool-1"}]},
    )

    response = mapper.shape_deployment_create_result(adapter_result, deployment_row, provider_key="test-provider")

    assert response.id == deployment_row.id
    assert response.provider_id == provider_account_id
    assert response.provider_key == "test-provider"
    assert response.name == deployment_row.name
    assert response.description == "db-description"
    assert response.created_at == now
    assert response.updated_at == now
    assert response.type == DeploymentType.AGENT
    assert response.provider_data == {"snapshot_bindings": [{"source_ref": "fv-1", "snapshot_id": "tool-1"}]}


def test_shape_deployment_create_result_with_none_provider_result() -> None:
    mapper = BaseDeploymentMapper()
    row = _make_deployment_row()
    result = DeploymentCreateResult(id="dep-1", provider_result=None)

    response = mapper.shape_deployment_create_result(result, row, provider_key="test-provider")

    assert response.provider_data is None


def test_shape_deployment_create_result_with_empty_dict_provider_result() -> None:
    """Empty dict provider_result is passed through as-is."""
    mapper = BaseDeploymentMapper()
    row = _make_deployment_row()
    result = DeploymentCreateResult(id="dep-1", provider_result={})

    response = mapper.shape_deployment_create_result(result, row, provider_key="test-provider")

    assert response.provider_data == {}


# ---------------------------------------------------------------------------
# shape_deployment_update_result
# ---------------------------------------------------------------------------


def test_shape_deployment_update_result_maps_db_identity_and_provider_result() -> None:
    mapper = BaseDeploymentMapper()
    provider_account_id = uuid4()
    now = datetime.now(timezone.utc)
    row = _make_deployment_row(
        deployment_provider_account_id=provider_account_id,
        created_at=now,
        updated_at=now,
    )
    result = DeploymentUpdateResult(
        id="provider-dep-id",
        provider_result={"status": "updated", "version": 2},
    )

    response = mapper.shape_deployment_update_result(result, row, provider_key="my-provider")

    assert response.id == row.id
    assert response.provider_id == provider_account_id
    assert response.provider_key == "my-provider"
    assert response.name == row.name
    assert response.description == row.description
    assert response.type == DeploymentType.AGENT
    assert response.created_at == now
    assert response.updated_at == now
    assert response.resource_key == row.resource_key
    assert response.provider_data == {"status": "updated", "version": 2}


# ---------------------------------------------------------------------------
# shape_deployment_list_result
# ---------------------------------------------------------------------------


def test_shape_deployment_list_result_with_entries() -> None:
    mapper = BaseDeploymentMapper()
    now = datetime.now(timezone.utc)
    items = [
        ItemResult(
            id="dep-1",
            name="Deployment One",
            type=DeploymentType.AGENT,
            provider_data={"region": "us-east"},
            created_at=now,
            updated_at=now,
        ),
        ItemResult(
            id="dep-2",
            name="Deployment Two",
            type=DeploymentType.AGENT,
            provider_data=None,
            created_at=now,
            updated_at=now,
        ),
    ]
    result = DeploymentListResult(deployments=items)

    response = mapper.shape_deployment_list_result(result)

    assert response.deployments == []
    assert response.provider_data is not None
    entries = response.provider_data["entries"]
    assert len(entries) == 2
    assert entries[0]["id"] == "dep-1"
    assert entries[0]["name"] == "Deployment One"
    assert entries[0]["region"] == "us-east"
    assert entries[1]["id"] == "dep-2"
    assert response.page == 1
    assert response.size == 2
    assert response.total == 2


def test_shape_deployment_list_result_null_provider_data_on_item() -> None:
    """Items with None provider_data produce an empty dict for spread."""
    mapper = BaseDeploymentMapper()
    items = [
        ItemResult(id="dep-1", name="No PD", type=DeploymentType.AGENT, provider_data=None),
    ]
    result = DeploymentListResult(deployments=items)

    response = mapper.shape_deployment_list_result(result)

    entries = response.provider_data["entries"]
    assert len(entries) == 1
    assert entries[0]["id"] == "dep-1"
    assert entries[0]["name"] == "No PD"


def test_shape_deployment_list_result_with_extra_provider_data_fields() -> None:
    """Items with dict provider_data spread extra keys into the entry."""
    mapper = BaseDeploymentMapper()
    items = [
        ItemResult(
            id="dep-1",
            name="With PD",
            type=DeploymentType.AGENT,
            provider_data={"region": "us-east", "version": 3},
        ),
    ]
    result = DeploymentListResult(deployments=items)

    response = mapper.shape_deployment_list_result(result)

    entries = response.provider_data["entries"]
    assert len(entries) == 1
    assert entries[0]["region"] == "us-east"
    assert entries[0]["version"] == 3


# ---------------------------------------------------------------------------
# shape_execution_create_result
# ---------------------------------------------------------------------------


def test_shape_execution_create_result_with_provider_data() -> None:
    mapper = BaseDeploymentMapper()
    dep_id = uuid4()
    result = ExecutionCreateResult(
        deployment_id="provider-dep-id",
        provider_result={"execution_id": "exec-1", "status": "running"},
    )

    response = mapper.shape_execution_create_result(result, deployment_id=dep_id)

    assert response.deployment_id == dep_id
    assert response.provider_data == {"execution_id": "exec-1", "status": "running"}


# ---------------------------------------------------------------------------
# shape_deployment_list_items (DB-backed list)
# ---------------------------------------------------------------------------


def test_shape_deployment_list_items_basic() -> None:
    mapper = BaseDeploymentMapper()
    now = datetime.now(timezone.utc)
    dep_id = uuid4()
    prov_id = uuid4()
    row = SimpleNamespace(
        id=dep_id,
        deployment_provider_account_id=prov_id,
        deployment_type=DeploymentType.AGENT,
        name="My Dep",
        description="desc",
        resource_key="rk-1",
        created_at=now,
        updated_at=now,
    )

    items = mapper.shape_deployment_list_items(
        rows_with_counts=[(row, 3, [])],
        has_flow_filter=False,
        provider_key="test-provider",
    )

    assert len(items) == 1
    item = items[0]
    assert item.id == dep_id
    assert item.provider_id == prov_id
    assert item.provider_key == "test-provider"
    assert item.name == "My Dep"
    assert item.attached_count == 3
    assert item.flow_version_ids is None


def test_shape_deployment_list_items_with_flow_filter() -> None:
    mapper = BaseDeploymentMapper()
    row = _make_deployment_row()
    fv_id = uuid4()

    items = mapper.shape_deployment_list_items(
        rows_with_counts=[(row, 1, [(fv_id, "tool-1")])],
        has_flow_filter=True,
        provider_key="test-provider",
    )

    assert items[0].flow_version_ids == [fv_id]


# ---------------------------------------------------------------------------
# shape_config_list_result pagination
# ---------------------------------------------------------------------------


def test_shape_config_list_result_pagination() -> None:
    from lfx.services.adapters.deployment.schema import ConfigListItem, ConfigListResult

    mapper = BaseDeploymentMapper()
    configs = [ConfigListItem(id=f"cfg-{i}", name=f"Config {i}") for i in range(5)]
    result = ConfigListResult(configs=configs, provider_result={"extra": "meta"})

    response = mapper.shape_config_list_result(result, page=2, size=2)

    assert response.page == 2
    assert response.size == 2
    assert response.total == 5
    assert response.provider_data is not None
    # page 2 with size 2 means offset 2, so items at index 2 and 3
    assert len(response.provider_data["configs"]) == 2
    assert response.provider_data["configs"][0]["id"] == "cfg-2"
    assert response.provider_data["configs"][1]["id"] == "cfg-3"
    assert response.provider_data["extra"] == "meta"


def test_shape_config_list_result_empty() -> None:
    from lfx.services.adapters.deployment.schema import ConfigListResult

    mapper = BaseDeploymentMapper()
    result = ConfigListResult(configs=[], provider_result=None)

    response = mapper.shape_config_list_result(result, page=1, size=10)

    assert response.total == 0
    assert response.provider_data == {"configs": []}
