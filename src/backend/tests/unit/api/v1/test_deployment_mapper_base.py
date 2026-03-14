"""Tests for deployment API mapper base contracts."""

from __future__ import annotations

from dataclasses import fields

import pytest
from langflow.api.v1.mappers.deployments.base import (
    BaseDeploymentMapper,
    DeploymentApiPayloads,
    DeploymentMapperRegistry,
)
from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
from lfx.services.adapters.payload import AdapterPayloadValidationError, PayloadSlot, PayloadSlotPolicy
from pydantic import BaseModel


class _ApiSpec(BaseModel):
    region: str


class _ApiConfig(BaseModel):
    retries: int


class _ApiUpdate(BaseModel):
    patch: str


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
    ("resolve_deployment_update", {"patch": "replace"}),
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
    "deployment_operation_result",
    "deployment_list_result",
    "config_list_result",
    "snapshot_list_result",
    "execution_result",
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
        "shape_execution_result",
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


def test_mapper_registry_returns_default_when_unregistered() -> None:
    registry = DeploymentMapperRegistry()
    assert isinstance(registry.get("missing-provider"), BaseDeploymentMapper)


def test_mapper_registry_returns_registered_mapper() -> None:
    registry = DeploymentMapperRegistry()
    mapper = _TypedMapper()
    registry.register("acme", mapper)
    assert registry.get("acme") is mapper


def test_mapper_registry_re_register_same_key_replaces_mapper() -> None:
    registry = DeploymentMapperRegistry()
    mapper1 = _TypedMapper()
    mapper2 = BaseDeploymentMapper()
    registry.register("acme", mapper1)
    registry.register("acme", mapper2)
    assert registry.get("acme") is mapper2


def test_mapper_registry_rejects_non_mapper_instances() -> None:
    registry = DeploymentMapperRegistry()
    with pytest.raises(TypeError, match="BaseDeploymentMapper"):
        registry.register("bad", object())  # type: ignore[arg-type]
