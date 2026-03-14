"""Tests for deployment payload slot formalization."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

import pytest
from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    ConfigListParams,
    ConfigListResult,
    DeploymentCreateResult,
    DeploymentListParams,
    DeploymentListResult,
    DeploymentOperationResult,
    DeploymentStatusResult,
    DeploymentType,
    ExecutionResultBase,
    ItemResult,
    SnapshotListParams,
    SnapshotListResult,
)
from lfx.services.adapters.payload import AdapterPayloadValidationError, PayloadSlot, PayloadSlotPolicy
from pydantic import BaseModel


class _SpecModel(BaseModel):
    region: str


class _StatusModel(BaseModel):
    healthy: bool


class _FilterModel(BaseModel):
    env: str


class _ResultModel(BaseModel):
    external_url: str


class _ExecutionResultModel(BaseModel):
    status: str


class _ConfigFilterModel(BaseModel):
    namespace: str


class _SnapshotFilterModel(BaseModel):
    label: str


class _ApiLikeConfigModel(BaseModel):
    retries: int


class _Color(str, Enum):
    BLUE = "blue"


class _NestedPayload(BaseModel):
    tag: str


class _RichPayload(BaseModel):
    uid: UUID
    created_at: datetime
    color: _Color
    nested: _NestedPayload


def test_payload_slot_parse_and_dump_round_trip() -> None:
    slot = PayloadSlot(_SpecModel)

    parsed = slot.parse({"region": "us-east-1"})

    assert isinstance(parsed, _SpecModel)
    assert slot.dump(parsed) == {"region": "us-east-1"}


def test_payload_slot_raises_typed_validation_error() -> None:
    slot = PayloadSlot(_SpecModel)

    with pytest.raises(AdapterPayloadValidationError, match="Invalid payload") as exc:
        slot.parse({"missing": "region"})
    assert exc.value.model_name == "_SpecModel"
    assert exc.value.error is not None


def test_payload_slot_dump_json_serializes_uuid_datetime_enum_and_nested_model() -> None:
    slot = PayloadSlot(_RichPayload)
    parsed = slot.parse(
        {
            "uid": "d779b2b7-302e-4f7b-af66-3fe4fd51b9fe",
            "created_at": "2026-01-02T03:04:05Z",
            "color": "blue",
            "nested": {"tag": "x"},
        }
    )

    dumped = slot.dump(parsed)

    assert dumped == {
        "uid": "d779b2b7-302e-4f7b-af66-3fe4fd51b9fe",
        "created_at": "2026-01-02T03:04:05Z",
        "color": "blue",
        "nested": {"tag": "x"},
    }


def test_payload_slot_apply_validate_only_policy_returns_original_payload() -> None:
    slot = PayloadSlot(_SpecModel, policy=PayloadSlotPolicy.VALIDATE_ONLY)
    raw = {"region": "us-east-1"}

    applied = slot.apply(raw)

    assert applied == raw
    assert applied is raw


def test_payload_slot_apply_validate_and_dump_policy_normalizes_payload() -> None:
    slot = PayloadSlot(_ApiLikeConfigModel, policy=PayloadSlotPolicy.VALIDATE_AND_DUMP)
    raw = {"retries": "3"}

    applied = slot.apply(raw)

    assert applied == {"retries": 3}
    assert applied is not raw


def test_deployment_payload_schemas_exposes_slots_and_active_slots() -> None:
    schemas = DeploymentPayloadSchemas(
        deployment_spec=PayloadSlot(_SpecModel),
        deployment_status_data=PayloadSlot(_StatusModel),
    )

    all_slots = schemas.slots()
    active_slots = schemas.active_slots()

    assert set(all_slots) == {field.name for field in fields(DeploymentPayloadSchemas)}
    assert set(active_slots) == {"deployment_spec", "deployment_status_data"}
    assert all_slots["deployment_config"] is None


def test_deployment_payload_schemas_defaults_to_no_active_slots() -> None:
    assert DeploymentPayloadSchemas().active_slots() == {}


def test_generic_parametrization_applies_to_provider_fields() -> None:
    typed_spec = BaseDeploymentData[_SpecModel](
        name="dep",
        description="",
        type=DeploymentType.AGENT,
        provider_spec={"region": "us-east-1"},
    )
    typed_status = DeploymentStatusResult[_StatusModel](
        id="dep_1",
        provider_data={"healthy": True},
    )
    typed_params = DeploymentListParams[_FilterModel](provider_params={"env": "prod"})

    assert isinstance(typed_spec.provider_spec, _SpecModel)
    assert isinstance(typed_status.provider_data, _StatusModel)
    assert isinstance(typed_params.provider_params, _FilterModel)


def test_generic_parametrization_applies_to_result_and_list_models() -> None:
    typed_create = DeploymentCreateResult[_ResultModel](
        id="dep_1",
        provider_result={"external_url": "https://dep.example"},
    )
    typed_operation = DeploymentOperationResult[_ResultModel](
        id="dep_1",
        provider_result={"external_url": "https://dep.example"},
    )
    typed_execution = ExecutionResultBase[_ExecutionResultModel](
        execution_id="exec_1",
        deployment_id="dep_1",
        provider_result={"status": "running"},
    )
    typed_item = ItemResult[_StatusModel](
        id="dep_1",
        name="dep",
        type=DeploymentType.AGENT,
        provider_data={"healthy": True},
    )
    typed_deployment_list = DeploymentListResult[_ResultModel](
        deployments=[],
        provider_result={"external_url": "https://dep.example"},
    )
    typed_config_list = ConfigListResult[_ResultModel](
        configs=[],
        provider_result={"external_url": "https://dep.example"},
    )
    typed_snapshot_list = SnapshotListResult[_ResultModel](
        snapshots=[],
        provider_result={"external_url": "https://dep.example"},
    )
    typed_config_params = ConfigListParams[_ConfigFilterModel](provider_params={"namespace": "prod"})
    typed_snapshot_params = SnapshotListParams[_SnapshotFilterModel](provider_params={"label": "nightly"})

    assert isinstance(typed_create.provider_result, _ResultModel)
    assert isinstance(typed_operation.provider_result, _ResultModel)
    assert isinstance(typed_execution.provider_result, _ExecutionResultModel)
    assert isinstance(typed_item.provider_data, _StatusModel)
    assert isinstance(typed_deployment_list.provider_result, _ResultModel)
    assert isinstance(typed_config_list.provider_result, _ResultModel)
    assert isinstance(typed_snapshot_list.provider_result, _ResultModel)
    assert isinstance(typed_config_params.provider_params, _ConfigFilterModel)
    assert isinstance(typed_snapshot_params.provider_params, _SnapshotFilterModel)


def test_unparametrized_models_keep_dict_passthrough_behavior() -> None:
    payload = {"region": "us-east-1"}
    data = BaseDeploymentData(
        name="dep",
        description="",
        type=DeploymentType.AGENT,
        provider_spec=payload,
    )
    assert data.provider_spec == payload

    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    rich_slot = PayloadSlot(_RichPayload)
    dumped = rich_slot.dump(
        _RichPayload(
            uid=UUID("d779b2b7-302e-4f7b-af66-3fe4fd51b9fe"),
            created_at=now,
            color=_Color.BLUE,
            nested=_NestedPayload(tag="x"),
        )
    )
    assert dumped["uid"] == "d779b2b7-302e-4f7b-af66-3fe4fd51b9fe"
