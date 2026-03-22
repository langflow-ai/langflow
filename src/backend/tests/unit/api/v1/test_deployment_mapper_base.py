"""Tests for deployment API mapper base contracts."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.v1.mappers.deployments import get_mapper_registry
from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper, DeploymentApiPayloads
from langflow.api.v1.mappers.deployments.contracts import (
    CreatedSnapshotIds,
    CreateSnapshotBindings,
    FlowVersionPatch,
    UpdateSnapshotBindings,
)
from langflow.api.v1.mappers.deployments.registry import DeploymentMapperRegistry
from langflow.api.v1.schemas.deployments import DeploymentCreateRequest, DeploymentUpdateRequest, ExecutionCreateRequest
from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
from lfx.services.adapters.deployment.schema import (
    DeploymentCreateResult,
    DeploymentType,
    DeploymentUpdateResult,
    ExecutionCreateResult,
    ExecutionStatusResult,
)
from lfx.services.adapters.payload import AdapterPayloadValidationError, PayloadSlot, PayloadSlotPolicy
from lfx.services.adapters.schema import AdapterType
from pydantic import BaseModel


class _ApiSpec(BaseModel):
    region: str


class _ApiConfig(BaseModel):
    retries: int


class _ApiUpdate(BaseModel):
    patch: str


class _ApiCreate(BaseModel):
    resource_name_prefix: str


class _ApiExecutionInput(BaseModel):
    invocation_id: str


class _ApiDeploymentListParams(BaseModel):
    env: str


class _ApiConfigListParams(BaseModel):
    config_tag: str


class _ApiSnapshotListParams(BaseModel):
    snapshot_tag: str


class _TypedMapper(BaseDeploymentMapper):
    api_payloads = DeploymentApiPayloads(
        deployment_create=PayloadSlot(_ApiCreate, policy=PayloadSlotPolicy.VALIDATE_ONLY),
        deployment_spec=PayloadSlot(_ApiSpec, policy=PayloadSlotPolicy.VALIDATE_ONLY),
        deployment_config=PayloadSlot(_ApiConfig, policy=PayloadSlotPolicy.VALIDATE_ONLY),
        deployment_update=PayloadSlot(_ApiUpdate, policy=PayloadSlotPolicy.VALIDATE_ONLY),
        execution_input=PayloadSlot(_ApiExecutionInput, policy=PayloadSlotPolicy.VALIDATE_ONLY),
        deployment_list_params=PayloadSlot(_ApiDeploymentListParams, policy=PayloadSlotPolicy.VALIDATE_ONLY),
        config_list_params=PayloadSlot(_ApiConfigListParams, policy=PayloadSlotPolicy.VALIDATE_ONLY),
        snapshot_list_params=PayloadSlot(_ApiSnapshotListParams, policy=PayloadSlotPolicy.VALIDATE_ONLY),
    )


class _NormalizingMapper(BaseDeploymentMapper):
    api_payloads = DeploymentApiPayloads(
        deployment_config=PayloadSlot(_ApiConfig, policy=PayloadSlotPolicy.VALIDATE_AND_DUMP),
    )


INBOUND_METHOD_CASES = [
    ("resolve_deployment_spec", {"region": "us-east-1"}),
    ("resolve_deployment_config", {"retries": 3}),
    ("resolve_execution_input", {"invocation_id": "inv-1"}),
    ("resolve_deployment_list_params", {"env": "prod"}),
    ("resolve_config_list_params", {"config_tag": "release"}),
    ("resolve_snapshot_list_params", {"snapshot_tag": "nightly"}),
]

INBOUND_SLOT_NAMES = [
    "deployment_spec",
    "deployment_config",
    "deployment_update",
    "execution_input",
    "deployment_list_params",
    "config_list_params",
    "snapshot_list_params",
]

OUTBOUND_SLOT_NAMES = [
    "deployment_create_result",
    "deployment_update_result",
    "deployment_operation_result",
    "deployment_list_result",
    "config_list_result",
    "snapshot_list_result",
    "deployment_item_data",
    "deployment_status_data",
]


def test_api_payload_field_names_match_adapter_registry() -> None:
    api_fields = [field.name for field in fields(DeploymentApiPayloads)]
    adapter_fields = [field.name for field in fields(DeploymentPayloadSchemas)]
    assert api_fields == adapter_fields


@pytest.mark.asyncio
@pytest.mark.parametrize(("method_name", "payload"), INBOUND_METHOD_CASES)
async def test_base_mapper_resolvers_passthrough_when_slot_not_configured(
    method_name: str, payload: dict[str, str | int]
) -> None:
    mapper = BaseDeploymentMapper()
    resolver = getattr(mapper, method_name)
    resolved = await resolver(payload, db=None)  # type: ignore[arg-type]
    assert resolved == payload


@pytest.mark.asyncio
@pytest.mark.parametrize(("method_name", "payload"), INBOUND_METHOD_CASES)
async def test_base_mapper_resolvers_validate_configured_slots_without_re_serializing(
    method_name: str, payload: dict[str, str | int]
) -> None:
    mapper = _TypedMapper()
    resolver = getattr(mapper, method_name)
    resolved = await resolver(payload, db=None)  # type: ignore[arg-type]
    assert resolved == payload
    assert resolved is payload


@pytest.mark.asyncio
async def test_base_mapper_resolvers_apply_normalize_policy_when_slot_configured() -> None:
    mapper = _NormalizingMapper()
    payload: dict[str, str | int] = {"retries": "3"}

    resolved = await mapper.resolve_deployment_config(payload, db=None)  # type: ignore[arg-type]

    assert resolved == {"retries": 3}
    assert resolved is not payload


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name", [name for name, _ in INBOUND_METHOD_CASES])
async def test_base_mapper_resolvers_reject_invalid_payload_for_configured_slots(method_name: str) -> None:
    mapper = _TypedMapper()
    resolver = getattr(mapper, method_name)
    with pytest.raises(AdapterPayloadValidationError, match="Invalid payload"):
        await resolver({"unknown": "field"}, db=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name", [name for name, _ in INBOUND_METHOD_CASES])
async def test_base_mapper_resolvers_passthrough_none_payload_when_slot_configured(method_name: str) -> None:
    mapper = _TypedMapper()
    resolver = getattr(mapper, method_name)
    resolved = await resolver(None, db=None)  # type: ignore[arg-type]
    assert resolved is None


@pytest.mark.asyncio
async def test_base_mapper_resolve_deployment_create_passthrough_without_flow_versions() -> None:
    mapper = BaseDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        spec={"name": "create-deploy", "description": "", "type": "agent"},
        provider_data={"resource_name_prefix": "lf_test_"},
    )

    resolved = await mapper.resolve_deployment_create(
        user_id=uuid4(),
        project_id=uuid4(),
        db=None,  # type: ignore[arg-type]
        payload=payload,
    )

    assert resolved.snapshot is None
    assert resolved.config is None
    assert resolved.provider_data == {"resource_name_prefix": "lf_test_"}


@pytest.mark.asyncio
async def test_base_mapper_resolve_deployment_create_validates_provider_data_when_slot_configured() -> None:
    mapper = _TypedMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        spec={"name": "create-deploy", "description": "", "type": "agent"},
        provider_data={"resource_name_prefix": "lf_test_"},
    )

    resolved = await mapper.resolve_deployment_create(
        user_id=uuid4(),
        project_id=uuid4(),
        db=None,  # type: ignore[arg-type]
        payload=payload,
    )

    assert resolved.provider_data == {"resource_name_prefix": "lf_test_"}


@pytest.mark.asyncio
async def test_base_mapper_resolve_deployment_create_rejects_invalid_provider_data_when_slot_configured() -> None:
    mapper = _TypedMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        spec={"name": "create-deploy", "description": "", "type": "agent"},
        provider_data={"invalid": "value"},
    )

    with pytest.raises(AdapterPayloadValidationError, match="Invalid payload"):
        await mapper.resolve_deployment_create(
            user_id=uuid4(),
            project_id=uuid4(),
            db=None,  # type: ignore[arg-type]
            payload=payload,
        )


@pytest.mark.asyncio
async def test_base_mapper_resolve_deployment_update_passthrough_when_slot_not_configured() -> None:
    mapper = BaseDeploymentMapper()
    payload = DeploymentUpdateRequest(provider_data={"patch": "replace"})

    resolved = await mapper.resolve_deployment_update(  # type: ignore[arg-type]
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=None,
        payload=payload,
    )

    assert resolved.spec is None
    assert resolved.config is None
    assert resolved.provider_data == {"patch": "replace"}


@pytest.mark.asyncio
async def test_base_mapper_resolve_deployment_update_validates_provider_data_when_slot_configured() -> None:
    mapper = _TypedMapper()
    payload = DeploymentUpdateRequest(provider_data={"patch": "replace"})

    resolved = await mapper.resolve_deployment_update(  # type: ignore[arg-type]
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=None,
        payload=payload,
    )

    assert resolved.provider_data == {"patch": "replace"}


@pytest.mark.asyncio
async def test_base_mapper_resolve_deployment_update_rejects_invalid_provider_data_when_slot_configured() -> None:
    mapper = _TypedMapper()
    payload = DeploymentUpdateRequest(provider_data={"invalid": "value"})

    with pytest.raises(AdapterPayloadValidationError, match="Invalid payload"):
        await mapper.resolve_deployment_update(  # type: ignore[arg-type]
            user_id=uuid4(),
            deployment_db_id=uuid4(),
            db=None,
            payload=payload,
        )


@pytest.mark.asyncio
async def test_base_mapper_resolve_execution_create_passthrough_when_slot_not_configured() -> None:
    mapper = BaseDeploymentMapper()
    payload = ExecutionCreateRequest(
        provider_id=uuid4(),
        deployment_id=uuid4(),
        provider_data={"invocation_id": "inv-1"},
    )

    resolved = await mapper.resolve_execution_create(
        deployment_resource_key="provider-deployment-id",
        db=None,  # type: ignore[arg-type]
        payload=payload,
    )

    assert resolved.deployment_id == "provider-deployment-id"
    assert resolved.provider_data == {"invocation_id": "inv-1"}


@pytest.mark.asyncio
async def test_base_mapper_resolve_execution_create_validates_provider_data_when_slot_configured() -> None:
    mapper = _TypedMapper()
    payload = ExecutionCreateRequest(
        provider_id=uuid4(),
        deployment_id=uuid4(),
        provider_data={"invocation_id": "inv-1"},
    )

    resolved = await mapper.resolve_execution_create(
        deployment_resource_key="provider-deployment-id",
        db=None,  # type: ignore[arg-type]
        payload=payload,
    )

    assert resolved.deployment_id == "provider-deployment-id"
    assert resolved.provider_data == {"invocation_id": "inv-1"}


@pytest.mark.asyncio
async def test_base_mapper_resolve_execution_create_rejects_invalid_provider_data_when_slot_configured() -> None:
    mapper = _TypedMapper()
    payload = ExecutionCreateRequest(
        provider_id=uuid4(),
        deployment_id=uuid4(),
        provider_data={"invalid": "value"},
    )

    with pytest.raises(AdapterPayloadValidationError, match="Invalid payload"):
        await mapper.resolve_execution_create(
            deployment_resource_key="provider-deployment-id",
            db=None,  # type: ignore[arg-type]
            payload=payload,
        )


def test_mapper_has_resolve_method_for_all_inbound_slots() -> None:
    for slot_name in INBOUND_SLOT_NAMES:
        assert hasattr(BaseDeploymentMapper, f"resolve_{slot_name}")


def test_mapper_has_shape_method_for_all_outbound_slots() -> None:
    for slot_name in OUTBOUND_SLOT_NAMES:
        assert hasattr(BaseDeploymentMapper, f"shape_{slot_name}")


@pytest.mark.parametrize(
    "method_name",
    [
        "shape_deployment_create_result",
        "shape_deployment_operation_result",
        "shape_deployment_list_result",
        "shape_config_list_result",
        "shape_snapshot_list_result",
        "shape_deployment_item_data",
        "shape_deployment_status_data",
    ],
)
def test_base_mapper_shapers_passthrough_provider_payload(method_name: str) -> None:
    mapper = BaseDeploymentMapper()
    payload = {"ok": True}
    shaper = getattr(mapper, method_name)
    shaped = shaper(payload)
    assert shaped is payload


def test_base_mapper_execution_provider_data_shapers_passthrough() -> None:
    mapper = BaseDeploymentMapper()
    payload = {"ok": True}

    assert mapper.shape_execution_create_provider_data(payload) is payload
    assert mapper.shape_execution_status_provider_data(payload) is payload


def test_base_mapper_shapes_deployment_update_result() -> None:
    mapper = BaseDeploymentMapper()
    deployment_id = uuid4()
    timestamp = datetime.now(tz=UTC)
    result = DeploymentUpdateResult(id="provider-id", provider_result={"ok": True})
    deployment_row = SimpleNamespace(
        id=deployment_id,
        name="Deployment Name",
        description="desc",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )

    shaped = mapper.shape_deployment_update_result(
        result,
        deployment_row,
    )

    assert shaped.id == deployment_id
    assert shaped.name == "Deployment Name"
    assert shaped.description == "desc"
    assert shaped.type == DeploymentType.AGENT
    assert shaped.provider_data == {"ok": True}


def test_base_mapper_shapes_execution_create_result() -> None:
    mapper = BaseDeploymentMapper()
    deployment_id = uuid4()
    result = ExecutionCreateResult(
        execution_id="exec-1",
        deployment_id="provider-dep-1",
        provider_result={"status": "accepted"},
    )

    shaped = mapper.shape_execution_create_result(
        result,
        deployment_id=deployment_id,
    )

    assert shaped.execution_id == "exec-1"
    assert shaped.deployment_id == deployment_id
    assert shaped.provider_data == {"status": "accepted"}


def test_base_mapper_shapes_execution_status_result_with_fallback() -> None:
    mapper = BaseDeploymentMapper()
    deployment_id = uuid4()
    result = ExecutionStatusResult(
        execution_id=None,
        deployment_id="provider-dep-1",
        provider_result={"status": "running"},
    )

    shaped = mapper.shape_execution_status_result(
        result,
        deployment_id=deployment_id,
        fallback_execution_id="exec-fallback",
    )

    assert shaped.execution_id == "exec-fallback"
    assert shaped.deployment_id == deployment_id
    assert shaped.provider_data == {"status": "running"}


def test_base_mapper_exposes_reconciliation_resolvers() -> None:
    mapper = BaseDeploymentMapper()
    add_id = uuid4()
    remove_id = uuid4()
    payload = DeploymentUpdateRequest(
        add_flow_version_ids=[add_id],
        remove_flow_version_ids=[remove_id],
    )
    patch = mapper.util_flow_version_patch(payload)
    assert isinstance(patch, FlowVersionPatch)
    add_ids, remove_ids = patch.add_flow_version_ids, patch.remove_flow_version_ids
    assert add_ids == [add_id]
    assert remove_ids == [remove_id]

    create_result = DeploymentCreateResult(
        id="provider-id",
        provider_result={"snapshot_bindings": [{"source_ref": "fv-1", "snapshot_id": "snap-1"}]},
    )
    bindings = mapper.util_create_snapshot_bindings(
        result=create_result,
    )
    assert isinstance(bindings, CreateSnapshotBindings)
    assert bindings.snapshot_bindings == []

    update_result = DeploymentUpdateResult(id="provider-id")
    created_ids = mapper.util_created_snapshot_ids(
        result=update_result,
    )
    assert isinstance(created_ids, CreatedSnapshotIds)
    assert created_ids.ids == []
    update_bindings = mapper.util_update_snapshot_bindings(
        result=update_result,
    )
    assert isinstance(update_bindings, UpdateSnapshotBindings)
    assert update_bindings.snapshot_bindings == []

    assert mapper.util_execution_id(execution_id="exec-1", provider_result={"run_id": "run-1"}) == "exec-1"
    assert (
        mapper.util_execution_deployment_resource_key(deployment_id="dep-1", provider_result={"agent_id": "agent-1"})
        == "dep-1"
    )


def test_base_mapper_resolve_provider_tenant_id_passthrough() -> None:
    mapper = BaseDeploymentMapper()
    assert (
        mapper.resolve_provider_tenant_id(
            provider_url="https://example.com/instances/abc",
            provider_tenant_id="tenant-1",
        )
        == "tenant-1"
    )
    assert (
        mapper.resolve_provider_tenant_id(
            provider_url="https://example.com/instances/abc",
            provider_tenant_id=None,
        )
        is None
    )


def test_base_mapper_shapes_provider_account_response() -> None:
    mapper = BaseDeploymentMapper()
    timestamp = datetime.now(tz=UTC)
    account = SimpleNamespace(
        id=uuid4(),
        provider_tenant_id="tenant-1",
        provider_key="provider-1",
        provider_url="https://provider.example",
        created_at=timestamp,
        updated_at=timestamp,
    )

    shaped = mapper.shape_provider_account_response(account)
    assert shaped.id == account.id
    assert shaped.provider_tenant_id == "tenant-1"
    assert shaped.provider_key == "provider-1"
    assert shaped.provider_url == "https://provider.example"


def test_mapper_registry_returns_default_when_unregistered() -> None:
    registry = DeploymentMapperRegistry()
    assert isinstance(registry.get("missing-provider"), BaseDeploymentMapper)


def test_mapper_registry_returns_registered_mapper() -> None:
    registry = DeploymentMapperRegistry()
    registry.register("acme", _TypedMapper)
    resolved = registry.get("acme")
    assert isinstance(resolved, _TypedMapper)


def test_mapper_registry_re_register_same_key_replaces_mapper() -> None:
    registry = DeploymentMapperRegistry()
    registry.register("acme", _TypedMapper)
    registry.register("acme", BaseDeploymentMapper)
    resolved = registry.get("acme")
    assert isinstance(resolved, BaseDeploymentMapper)
    assert not isinstance(resolved, _TypedMapper)


def test_mapper_registry_rejects_non_mapper_classes() -> None:
    registry = DeploymentMapperRegistry()
    with pytest.raises(TypeError, match="BaseDeploymentMapper"):
        registry.register("bad", object)  # type: ignore[arg-type]


def test_mapper_registry_accessor_returns_singleton() -> None:
    registry1 = get_mapper_registry(AdapterType.DEPLOYMENT)
    registry2 = get_mapper_registry(AdapterType.DEPLOYMENT)
    assert registry1 is registry2


def test_mapper_registry_get_returns_cached_instance_for_key() -> None:
    registry = DeploymentMapperRegistry()
    registry.register("acme", _TypedMapper)
    first = registry.get("acme")
    second = registry.get("acme")
    assert first is second
