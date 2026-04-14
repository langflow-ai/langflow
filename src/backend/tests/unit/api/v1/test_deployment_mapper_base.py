"""Tests for deployment API mapper base contracts."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
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
from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentProviderAccountCreateRequest,
    DeploymentUpdateRequest,
    ExecutionCreateRequest,
)
from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
from lfx.services.adapters.deployment.schema import (
    DeploymentCreateResult,
    DeploymentListResult,
    DeploymentType,
    DeploymentUpdateResult,
    ExecutionCreateResult,
    ExecutionStatusResult,
    ItemResult,
    SnapshotItem,
    SnapshotListResult,
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
    label: str


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
    api_fields = {field.name for field in fields(DeploymentApiPayloads)}
    adapter_fields = {field.name for field in fields(DeploymentPayloadSchemas)}
    assert adapter_fields.issubset(api_fields), f"Adapter fields not in API payloads: {adapter_fields - api_fields}"


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
        name="create-deploy",
        description="",
        type="agent",
        provider_data={"some_key": "some_value"},
    )

    resolved = await mapper.resolve_deployment_create(
        user_id=uuid4(),
        project_id=uuid4(),
        db=None,  # type: ignore[arg-type]
        payload=payload,
    )

    assert resolved.snapshot is None
    assert resolved.config is None
    assert resolved.provider_data == {"some_key": "some_value"}


@pytest.mark.asyncio
async def test_base_mapper_resolve_deployment_create_validates_provider_data_when_slot_configured() -> None:
    mapper = _TypedMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="create-deploy",
        description="",
        type="agent",
        provider_data={"label": "some_value"},
    )

    resolved = await mapper.resolve_deployment_create(
        user_id=uuid4(),
        project_id=uuid4(),
        db=None,  # type: ignore[arg-type]
        payload=payload,
    )

    assert resolved.provider_data == {"label": "some_value"}


@pytest.mark.asyncio
async def test_base_mapper_resolve_deployment_create_rejects_invalid_provider_data_when_slot_configured() -> None:
    mapper = _TypedMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="create-deploy",
        description="",
        type="agent",
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
        "shape_deployment_operation_result",
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


def test_base_mapper_shapes_deployment_create_result() -> None:
    mapper = BaseDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    deployment_id = uuid4()
    provider_account_id = uuid4()
    result = DeploymentCreateResult(id="provider-id", provider_result={"ok": True})
    deployment_row = SimpleNamespace(
        id=deployment_id,
        name="Deployment 1",
        description="desc",
        deployment_type=DeploymentType.AGENT,
        resource_key="provider-id",
        created_at=timestamp,
        updated_at=timestamp,
        deployment_provider_account_id=provider_account_id,
    )

    shaped = mapper.shape_deployment_create_result(result, deployment_row=deployment_row, provider_key="test-provider")

    assert shaped.id == deployment_id
    assert shaped.provider_id == provider_account_id
    assert shaped.provider_key == "test-provider"
    assert shaped.name == "Deployment 1"
    assert shaped.type == DeploymentType.AGENT
    assert shaped.provider_data == {"ok": True}


def test_base_mapper_shapes_deployment_list_result() -> None:
    mapper = BaseDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    result = DeploymentListResult(
        deployments=[
            ItemResult(
                id="dep-1",
                name="Deployment 1",
                type=DeploymentType.AGENT,
                created_at=timestamp,
                updated_at=timestamp,
                provider_data={"ok": True},
            )
        ]
    )

    shaped = mapper.shape_deployment_list_result(result)

    assert shaped.page == 1
    assert shaped.size == 1
    assert shaped.total == 1
    assert shaped.provider_data == {
        "entries": [
            {
                "id": "dep-1",
                "name": "Deployment 1",
                "type": DeploymentType.AGENT,
                "description": None,
                "created_at": timestamp,
                "updated_at": timestamp,
                "ok": True,
            }
        ]
    }


def test_base_mapper_shapes_flow_version_list_result() -> None:
    mapper = BaseDeploymentMapper()
    attached_at = datetime.now(tz=timezone.utc)
    flow_version_id = uuid4()
    flow_id = uuid4()
    rows = [
        (
            SimpleNamespace(provider_snapshot_id=" tool-1 ", created_at=attached_at),
            SimpleNamespace(id=flow_version_id, flow_id=flow_id, version_number=4),
            "Flow A",
        )
    ]
    snapshot_result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-1",
                name="Tool 1",
                provider_data={"connections": {"cfg-1": "conn-1"}},
            )
        ]
    )

    shaped = mapper.shape_flow_version_list_result(
        rows=rows,
        snapshot_result=snapshot_result,
        page=2,
        size=5,
        total=7,
    )

    assert shaped.page == 2
    assert shaped.size == 5
    assert shaped.total == 7
    assert len(shaped.flow_versions) == 1
    assert shaped.flow_versions[0].id == flow_version_id
    assert shaped.flow_versions[0].flow_id == flow_id
    assert shaped.flow_versions[0].flow_name == "Flow A"
    assert shaped.flow_versions[0].version_number == 4
    assert shaped.flow_versions[0].attached_at == attached_at
    assert shaped.flow_versions[0].provider_snapshot_id == "tool-1"
    assert shaped.flow_versions[0].provider_data is None


def test_base_mapper_flow_version_item_data_defaults_to_none() -> None:
    mapper = BaseDeploymentMapper()
    rows = [
        (
            SimpleNamespace(provider_snapshot_id=None, created_at=None),
            SimpleNamespace(id=uuid4(), flow_id=uuid4(), version_number=1),
            None,
        )
    ]

    shaped = mapper.shape_flow_version_list_result(
        rows=rows,
        snapshot_result=None,
        page=1,
        size=20,
        total=1,
    )

    assert len(shaped.flow_versions) == 1
    assert shaped.flow_versions[0].flow_name is None
    assert shaped.flow_versions[0].provider_snapshot_id is None
    assert shaped.flow_versions[0].provider_data is None


def test_shape_deployment_list_items_without_filter() -> None:
    """Without a flow filter, flow_version_ids is omitted."""
    mapper = BaseDeploymentMapper()
    provider_account_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        resource_key="rk-1",
        deployment_type=DeploymentType.AGENT,
        name="Dep",
        description=None,
        created_at=None,
        updated_at=None,
        deployment_provider_account_id=provider_account_id,
    )
    items = mapper.shape_deployment_list_items(
        rows_with_counts=[(row, 0, [])],
        has_flow_filter=False,
        provider_key="test-provider",
    )
    assert len(items) == 1
    assert items[0].provider_id == provider_account_id
    assert items[0].provider_key == "test-provider"
    assert items[0].flow_version_ids is None


def test_shape_deployment_list_items_with_filter() -> None:
    """With a flow filter, flow_version_ids is populated from matched tuples."""
    mapper = BaseDeploymentMapper()
    fv_id = uuid4()
    provider_account_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        resource_key="rk-1",
        deployment_type=DeploymentType.AGENT,
        name="Dep",
        description=None,
        created_at=None,
        updated_at=None,
        deployment_provider_account_id=provider_account_id,
    )
    items = mapper.shape_deployment_list_items(
        rows_with_counts=[(row, 1, [(fv_id, "snap-1")])],
        has_flow_filter=True,
        provider_key="test-provider",
    )
    assert len(items) == 1
    assert items[0].provider_id == provider_account_id
    assert items[0].provider_key == "test-provider"
    assert items[0].flow_version_ids == [fv_id]


def test_shape_deployment_list_items_with_filter_empty_matches() -> None:
    """With a flow filter active but no matches, flow_version_ids is empty."""
    mapper = BaseDeploymentMapper()
    provider_account_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        resource_key="rk-1",
        deployment_type=DeploymentType.AGENT,
        name="Dep",
        description=None,
        created_at=None,
        updated_at=None,
        deployment_provider_account_id=provider_account_id,
    )
    items = mapper.shape_deployment_list_items(
        rows_with_counts=[(row, 0, [])],
        has_flow_filter=True,
        provider_key="test-provider",
    )
    assert len(items) == 1
    assert items[0].provider_id == provider_account_id
    assert items[0].provider_key == "test-provider"
    assert items[0].flow_version_ids == []


def test_base_mapper_execution_provider_data_shapers_passthrough() -> None:
    mapper = BaseDeploymentMapper()
    payload = {"ok": True}

    assert mapper.shape_execution_create_provider_data(payload) is payload
    assert mapper.shape_execution_status_provider_data(payload) is payload


def test_base_mapper_formats_conflict_detail_with_generic_fallback() -> None:
    mapper = BaseDeploymentMapper()

    detail = mapper.format_conflict_detail("provider conflict detail")

    assert (
        detail
        == "A resource conflict occurred in the deployment provider. The requested operation could not be completed."
    )


def test_base_mapper_shapes_deployment_update_result() -> None:
    mapper = BaseDeploymentMapper()
    deployment_id = uuid4()
    provider_account_id = uuid4()
    timestamp = datetime.now(tz=timezone.utc)
    result = DeploymentUpdateResult(id="provider-id", provider_result={"ok": True})
    deployment_row = SimpleNamespace(
        id=deployment_id,
        name="Deployment Name",
        description="desc",
        deployment_type=DeploymentType.AGENT,
        resource_key="provider-id",
        created_at=timestamp,
        updated_at=timestamp,
        deployment_provider_account_id=provider_account_id,
    )

    shaped = mapper.shape_deployment_update_result(
        result,
        deployment_row,
        provider_key="test-provider",
    )

    assert shaped.id == deployment_id
    assert shaped.provider_id == provider_account_id
    assert shaped.provider_key == "test-provider"
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
        provider_result={"execution_id": "exec-1", "status": "accepted"},
    )

    shaped = mapper.shape_execution_create_result(
        result,
        deployment_id=deployment_id,
    )

    assert shaped.deployment_id == deployment_id
    assert shaped.provider_data == {"execution_id": "exec-1", "status": "accepted"}


def test_base_mapper_shapes_execution_status_result_with_none_execution_id() -> None:
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
    )

    assert shaped.deployment_id == deployment_id
    assert shaped.provider_data == {"status": "running"}


def test_base_mapper_exposes_reconciliation_resolvers() -> None:
    mapper = BaseDeploymentMapper()
    payload = DeploymentUpdateRequest(
        provider_data={"operations": []},
    )
    patch = mapper.util_flow_version_patch(payload)
    assert isinstance(patch, FlowVersionPatch)
    add_ids, remove_ids = patch.add_flow_version_ids, patch.remove_flow_version_ids
    assert add_ids == []
    assert remove_ids == []

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

    exec_result = ExecutionStatusResult(
        execution_id="e-1",
        deployment_id="dep-1",
        provider_result={"agent_id": "agent-1"},
    )
    assert mapper.util_resource_key_from_execution(exec_result) == "dep-1"


def test_base_mapper_shapes_provider_account_response() -> None:
    mapper = BaseDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    account = SimpleNamespace(
        id=uuid4(),
        name="staging",
        provider_tenant_id="tenant-1",
        provider_key="watsonx-orchestrate",
        provider_url="https://provider.example",
        created_at=timestamp,
        updated_at=timestamp,
    )

    shaped = mapper.resolve_provider_account_response(account)
    assert shaped.id == account.id
    assert shaped.name == "staging"
    assert shaped.provider_data == {"url": "https://provider.example"}
    assert shaped.provider_key == "watsonx-orchestrate"


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


# ---------------------------------------------------------------------------
# resolve_verify_credentials_for_create
# ---------------------------------------------------------------------------


def test_base_mapper_resolve_verify_credentials_raises_not_implemented() -> None:
    """Base mapper does not implement create credential verification."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountCreateRequest

    mapper = BaseDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="test-account",
        provider_key="watsonx-orchestrate",
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com",
            "api_key": "secret-key",  # pragma: allowlist secret
        },
    )
    with pytest.raises(NotImplementedError):
        mapper.resolve_verify_credentials_for_create(payload=payload)


def test_base_mapper_resolve_credentials_raises_not_implemented() -> None:
    """Base mapper does not implement resolve_credentials."""
    mapper = BaseDeploymentMapper()
    with pytest.raises(NotImplementedError):
        mapper.resolve_credentials(provider_data={"api_key": "key"})  # pragma: allowlist secret


def test_base_mapper_resolve_provider_account_create_raises_not_implemented() -> None:
    mapper = BaseDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="provider-account",
        provider_key="watsonx-orchestrate",
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
            "tenant_id": "tenant-1",
            "api_key": "secret-key",  # pragma: allowlist secret
        },
    )
    with pytest.raises(NotImplementedError):
        mapper.resolve_provider_account_create(payload=payload, user_id=uuid4())


def test_base_mapper_util_existing_deployment_resource_key_for_create_raises_not_implemented() -> None:
    mapper = BaseDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="deploy",
        description="",
        type="agent",
        provider_data={},
    )
    with pytest.raises(NotImplementedError):
        mapper.util_existing_deployment_resource_key_for_create(payload)


def test_base_mapper_util_should_mutate_provider_for_existing_deployment_create_raises_not_implemented() -> None:
    mapper = BaseDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="deploy",
        description="",
        type="agent",
        provider_data={},
    )
    with pytest.raises(NotImplementedError):
        mapper.util_should_mutate_provider_for_existing_deployment_create(payload)


def test_base_mapper_util_create_result_from_existing_update_raises_not_implemented() -> None:
    mapper = BaseDeploymentMapper()
    result = DeploymentUpdateResult(id="provider-deploy-id")
    with pytest.raises(NotImplementedError):
        mapper.util_create_result_from_existing_update(
            existing_resource_key="provider-deploy-id",
            result=result,
        )


# ---------------------------------------------------------------------------
# resolve_provider_account_update
# ---------------------------------------------------------------------------


def _make_existing_account():
    """Build a minimal fake existing DeploymentProviderAccount."""
    return SimpleNamespace(
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/30000000-0000-0000-0000-000000000001",
        provider_tenant_id="30000000-0000-0000-0000-000000000001",
        provider_key="watsonx-orchestrate",
    )


def test_base_mapper_resolve_provider_account_update_name_only() -> None:
    """Only name is set; no other fields should appear."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountUpdateRequest

    mapper = BaseDeploymentMapper()
    payload = DeploymentProviderAccountUpdateRequest(name="new-name")
    result = mapper.resolve_provider_account_update(
        payload=payload,
        existing_account=_make_existing_account(),
    )
    assert result == {"name": "new-name"}


def test_base_mapper_resolve_provider_account_update_provider_data_raises() -> None:
    """Base mapper cannot resolve provider_data — raises NotImplementedError."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountUpdateRequest

    mapper = BaseDeploymentMapper()
    payload = DeploymentProviderAccountUpdateRequest(provider_data={"api_key": "key"})
    with pytest.raises(NotImplementedError):
        mapper.resolve_provider_account_update(
            payload=payload,
            existing_account=_make_existing_account(),
        )
