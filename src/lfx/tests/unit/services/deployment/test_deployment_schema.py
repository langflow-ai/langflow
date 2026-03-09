"""Tests for deployment schema validation and shared model shapes."""

import json
from uuid import UUID, uuid4

import pytest
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentDataUpdate,
    BaseFlowArtifact,
    ConfigDeploymentBindingUpdate,
    ConfigItem,
    DeploymentConfig,
    DeploymentCreate,
    DeploymentCreateResult,
    DeploymentDeleteResult,
    DeploymentListParams,
    DeploymentType,
    DeploymentUpdate,
    DeploymentUpdateResult,
    EnvVarSource,
    EnvVarValueSpec,
    ExecutionCreate,
    ExecutionCreateResult,
    ExecutionStatusResult,
    RedeployResult,
    SnapshotDeploymentBindingUpdate,
    SnapshotItems,
    get_deployment_create_schema,
    get_str_id,
    get_uuid,
)
from pydantic import ValidationError


def test_snapshot_items_requires_raw_payloads() -> None:
    with pytest.raises(ValidationError, match="Field required"):
        SnapshotItems()

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SnapshotItems(
            raw_payloads=[
                {
                    "id": uuid4(),
                    "name": "Flow",
                    "description": "test",
                    "data": {},
                    "tags": [],
                }
            ],
            reference_ids=["snap_1"],
        )


def test_config_item_requires_exactly_one_source() -> None:
    with pytest.raises(ValidationError, match="Exactly one of 'reference_id' or 'raw_payload'"):
        ConfigItem()

    with pytest.raises(ValidationError, match="Exactly one of 'reference_id' or 'raw_payload'"):
        ConfigItem(reference_id="cfg_1", raw_payload={"name": "cfg"})


def test_config_item_accepts_reference_id_only() -> None:
    item = ConfigItem(reference_id="cfg_1")
    assert item.reference_id == "cfg_1"
    assert item.raw_payload is None


def test_config_item_accepts_raw_payload_only() -> None:
    item = ConfigItem(raw_payload={"name": "cfg"})
    assert item.raw_payload is not None
    assert item.reference_id is None


def test_deployment_list_params_normalizes_and_dedupes_id_filters() -> None:
    dep_uuid = uuid4()
    cfg_uuid = uuid4()

    params = DeploymentListParams(
        deployment_ids=[dep_uuid, "  dep-id  ", "dep-id"],
        snapshot_ids=["  snap-id  ", "snap-id"],
        config_ids=[cfg_uuid, str(cfg_uuid)],
    )

    assert params.deployment_ids == [str(dep_uuid), "dep-id"]
    assert params.snapshot_ids == ["snap-id"]
    assert params.config_ids == [str(cfg_uuid)]


def test_deployment_list_params_defaults_to_none() -> None:
    params = DeploymentListParams()
    assert params.deployment_ids is None
    assert params.snapshot_ids is None
    assert params.config_ids is None
    assert params.deployment_types is None
    assert params.provider_params is None


def test_deployment_list_params_dedupes_types_preserving_order() -> None:
    params = DeploymentListParams(
        deployment_types=[
            DeploymentType.AGENT,
            DeploymentType.AGENT,
        ]
    )
    assert params.deployment_types == [DeploymentType.AGENT]


def test_deployment_list_params_rejects_blank_filter_ids() -> None:
    with pytest.raises(ValidationError):
        DeploymentListParams(deployment_ids=["   "])


def test_snapshot_binding_update_accepts_idlike_and_dedupes() -> None:
    snapshot_uuid = uuid4()

    payload = SnapshotDeploymentBindingUpdate(
        add=[snapshot_uuid, f"  {snapshot_uuid}  ", "snap_1", "snap_1"],
        remove=["  snap_2  ", "snap_2"],
    )

    assert payload.add == [str(snapshot_uuid), "snap_1"]
    assert payload.remove == ["snap_2"]


def test_snapshot_binding_update_add_only() -> None:
    payload = SnapshotDeploymentBindingUpdate(add=["snap_1"])
    assert payload.add == ["snap_1"]
    assert payload.remove is None


def test_snapshot_binding_update_remove_only() -> None:
    payload = SnapshotDeploymentBindingUpdate(remove=["snap_1"])
    assert payload.remove == ["snap_1"]
    assert payload.add is None


def test_snapshot_binding_update_rejects_overlap_after_normalization() -> None:
    snapshot_uuid = uuid4()
    with pytest.raises(ValidationError, match="cannot be present in both 'add' and 'remove'"):
        SnapshotDeploymentBindingUpdate(
            add=[snapshot_uuid, " snap_1 "],
            remove=[str(snapshot_uuid), "snap_1"],
        )


def test_snapshot_binding_update_rejects_blank_ids() -> None:
    with pytest.raises(ValidationError):
        SnapshotDeploymentBindingUpdate(add=["   "])


def test_snapshot_binding_update_preserves_order_while_deduping() -> None:
    payload = SnapshotDeploymentBindingUpdate(add=["b", "a", "b", "c", "a"])
    assert payload.add == ["b", "a", "c"]


def test_snapshot_binding_update_rejects_noop_payload() -> None:
    with pytest.raises(ValidationError, match="At least one of 'add' or 'remove'"):
        SnapshotDeploymentBindingUpdate()


def test_config_item_reference_id_rejects_blank() -> None:
    with pytest.raises(ValidationError):
        ConfigItem(reference_id="   ")


def test_config_deployment_binding_update_normalizes_and_accepts_uuid() -> None:
    cfg_uuid = uuid4()

    normalized = ConfigDeploymentBindingUpdate(config_id="  cfg_1  ")
    assert normalized.config_id == "cfg_1"

    passthrough = ConfigDeploymentBindingUpdate(config_id=cfg_uuid)
    assert passthrough.config_id == cfg_uuid


def test_config_deployment_binding_update_rejects_blank() -> None:
    with pytest.raises(ValidationError):
        ConfigDeploymentBindingUpdate(config_id="   ")


def test_deployment_create_rejects_invalid_deployment_type() -> None:
    with pytest.raises(ValidationError, match="type"):
        DeploymentCreate(spec={"name": "my deployment", "type": "invalid-type"})


def test_snapshot_items_rejects_empty_raw_payload_list() -> None:
    with pytest.raises(ValidationError):
        SnapshotItems(raw_payloads=[])


def test_base_flow_artifact_allows_extra_fields() -> None:
    flow = BaseFlowArtifact(
        id=uuid4(),
        name="Flow",
        description="desc",
        data={"nodes": [], "edges": []},
        tags=["tag"],
        viewport={"x": 10, "y": 20},
    )
    assert flow.model_extra is not None
    assert flow.model_extra["viewport"] == {"x": 10, "y": 20}


def test_base_flow_artifact_requires_nodes_and_edges() -> None:
    with pytest.raises(ValidationError, match="Flow must have nodes"):
        BaseFlowArtifact(
            id=uuid4(),
            name="Flow",
            data={"edges": []},
        )

    with pytest.raises(ValidationError, match="Flow must have edges"):
        BaseFlowArtifact(
            id=uuid4(),
            name="Flow",
            data={"nodes": []},
        )


def test_base_flow_artifact_validates_nodes_and_edges_are_lists() -> None:
    with pytest.raises(ValidationError, match="Flow 'nodes' must be a list"):
        BaseFlowArtifact(
            id=uuid4(),
            name="Flow",
            data={"nodes": "not a list", "edges": []},
        )

    with pytest.raises(ValidationError, match="Flow 'edges' must be a list"):
        BaseFlowArtifact(
            id=uuid4(),
            name="Flow",
            data={"nodes": [], "edges": 42},
        )


def test_base_flow_artifact_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        BaseFlowArtifact(
            id=uuid4(),
            name="",
            data={"nodes": [], "edges": []},
        )


def test_snapshot_items_accepts_starter_project_data_shape() -> None:
    payload = SnapshotItems(
        raw_payloads=[
            {
                "id": uuid4(),
                "name": "Starter Project Flow",
                "description": "starter project payload shape",
                "data": {"nodes": [], "edges": []},
            }
        ]
    )
    assert payload.raw_payloads is not None
    assert payload.raw_payloads[0].data == {"nodes": [], "edges": []}


def test_snapshot_items_rejects_wrapped_data_shape() -> None:
    with pytest.raises(ValidationError, match="Flow must have nodes"):
        SnapshotItems(
            raw_payloads=[
                {
                    "id": uuid4(),
                    "name": "Wrapped Flow",
                    # Invalid for BaseFlowArtifact.data: this is one level too high.
                    "data": {"data": {"nodes": [], "edges": []}},
                }
            ]
        )


def test_execution_create_normalizes_string_deployment_id() -> None:
    payload = ExecutionCreate(deployment_id="  dep_1  ")
    assert payload.deployment_id == "dep_1"


def test_execution_create_accepts_uuid_deployment_id() -> None:
    dep_uuid = uuid4()
    payload = ExecutionCreate(deployment_id=dep_uuid)
    assert payload.deployment_id == dep_uuid


def test_execution_create_rejects_blank_deployment_id() -> None:
    with pytest.raises(ValidationError):
        ExecutionCreate(deployment_id="   ")


def test_get_id_helpers_round_trip() -> None:
    value = uuid4()
    value_str = get_str_id(value)
    assert isinstance(value_str, str)
    assert get_uuid(value_str) == value

    passthrough = "dep_1"
    assert get_str_id(passthrough) == passthrough
    assert get_uuid(str(value)) == UUID(str(value))


def test_get_uuid_rejects_non_uuid_strings() -> None:
    with pytest.raises(ValueError, match="Use get_str_id\\(\\) for opaque IDs"):
        get_uuid("dep_1")


def test_execution_create_and_status_results_have_same_shape() -> None:
    payload = {
        "execution_id": "exec_1",
        "deployment_id": "dep_1",
        "provider_result": {"status": "running"},
    }

    create_result = ExecutionCreateResult(**payload)
    status_result = ExecutionStatusResult(**payload)

    assert create_result.model_dump() == status_result.model_dump()


def test_operation_results_share_provider_result_contract() -> None:
    provider_result = {"accepted": True}

    deleted = DeploymentDeleteResult(id="dep_1", provider_result=provider_result)
    updated = DeploymentUpdateResult(id="dep_1", provider_result=provider_result)
    redeployed = RedeployResult(id="dep_1", provider_result=provider_result)

    assert deleted.provider_result == provider_result
    assert updated.provider_result == provider_result
    assert redeployed.provider_result == provider_result


def test_base_deployment_data_update_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError, match="At least one of 'name' or 'description'"):
        BaseDeploymentDataUpdate()


def test_deployment_update_requires_at_least_one_section() -> None:
    with pytest.raises(ValidationError, match="At least one of 'spec', 'snapshot', or 'config'"):
        DeploymentUpdate()


def test_deployment_update_accepts_spec_only() -> None:
    update = DeploymentUpdate(spec={"name": "new name"})
    assert update.spec is not None
    assert update.snapshot is None
    assert update.config is None


def test_deployment_update_accepts_config_only() -> None:
    update = DeploymentUpdate(config={"config_id": "cfg_1"})
    assert update.config is not None
    assert update.spec is None
    assert update.snapshot is None


def test_deployment_update_accepts_snapshot_only() -> None:
    update = DeploymentUpdate(snapshot={"add": ["snap_1"]})
    assert update.snapshot is not None
    assert update.spec is None
    assert update.config is None


def test_env_var_config_accepts_raw_and_variable_sources() -> None:
    config = DeploymentConfig(
        name="cfg",
        environment_variables={
            "RAW_TOKEN": EnvVarValueSpec(value="literal", source=EnvVarSource.RAW),
            "VAR_TOKEN": EnvVarValueSpec(value="OPENAI_API_KEY", source=EnvVarSource.VARIABLE),
        },
    )
    assert config.environment_variables is not None
    assert config.environment_variables["RAW_TOKEN"].source == EnvVarSource.RAW
    assert config.environment_variables["VAR_TOKEN"].source == EnvVarSource.VARIABLE


def test_env_var_value_spec_rejects_blank_value() -> None:
    with pytest.raises(ValidationError):
        EnvVarValueSpec(value="  ")


def test_deployment_create_happy_path_with_snapshot_and_config() -> None:
    payload = DeploymentCreate(
        spec={"name": "my deployment", "description": "desc", "type": DeploymentType.AGENT},
        snapshot={
            "raw_payloads": [
                {
                    "id": uuid4(),
                    "name": "Flow",
                    "description": "flow description",
                    "data": {"nodes": [], "edges": []},
                }
            ]
        },
        config={"raw_payload": {"name": "cfg", "description": "cfg desc"}},
    )
    assert payload.spec.type == DeploymentType.AGENT
    assert payload.snapshot is not None
    assert payload.config is not None


def test_deployment_create_result_defaults() -> None:
    result = DeploymentCreateResult(
        id="dep_1",
        name="deployment",
        description="",
        type=DeploymentType.AGENT,
    )
    assert result.snapshot_ids == []
    assert result.config_id is None


def test_get_deployment_create_schema_returns_valid_json() -> None:
    schema_str = get_deployment_create_schema()
    schema = json.loads(schema_str)
    assert "properties" in schema
    assert "spec" in schema["properties"]


def test_get_deployment_create_schema_is_cached() -> None:
    first = get_deployment_create_schema()
    second = get_deployment_create_schema()
    assert first is second
