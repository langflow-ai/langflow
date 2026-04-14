"""Tests for Watsonx deployment mapper and API payload contract."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.mappers.deployments import get_mapper
from langflow.api.v1.mappers.deployments.contracts import (
    CreatedSnapshotIds,
    CreateSnapshotBindings,
    FlowVersionPatch,
    UpdateSnapshotBindings,
)
from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentProviderAccountUpdateRequest,
    DeploymentUpdateRequest,
)
from lfx.services.adapters.deployment.schema import (
    ConfigListItem,
    ConfigListResult,
    DeploymentCreateResult,
    DeploymentListLlmsResult,
    DeploymentListResult,
    DeploymentType,
    DeploymentUpdateResult,
    ItemResult,
    SnapshotItem,
    SnapshotListResult,
)
from lfx.services.adapters.payload import AdapterPayloadValidationError, PayloadSlot
from lfx.services.adapters.schema import AdapterType
from pydantic import ValidationError

try:
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
        WatsonxApiDeploymentCreatePayload,
        WatsonxApiDeploymentUpdatePayload,
        WatsonxApiDeploymentUpdateResultData,
    )
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
        WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
    )
    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
        WatsonxDeploymentUpdateResultData,
    )
except ModuleNotFoundError:
    pytest.skip(
        "Skipping Watsonx mapper tests: optional IBM SDK dependencies not available.",
        allow_module_level=True,
    )


TEST_WXO_LLM = "ibm/granite-3.3-8b"


class _FakeExecResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    async def exec(self, _statement):
        return _FakeExecResult(self._rows)


def test_watsonx_mapper_is_registered() -> None:
    mapper = get_mapper(AdapterType.DEPLOYMENT, WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY)
    assert isinstance(mapper, WatsonxOrchestrateDeploymentMapper)
    assert mapper.api_payloads.deployment_create is not None
    assert mapper.api_payloads.deployment_update is not None
    assert mapper.api_payloads.deployment_update_result is not None
    assert mapper.api_payloads.config_list_result is not None
    assert mapper.api_payloads.config_item_data is not None
    assert mapper.api_payloads.snapshot_list_result is not None


def test_watsonx_mapper_provider_list_entry_rejects_non_dict_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    item = SimpleNamespace(
        id="agent-1",
        name="Agent 1",
        type=DeploymentType.AGENT,
        description=None,
        created_at=None,
        updated_at=None,
        provider_data="bad-payload-type",
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper._shape_provider_deployment_list_entry(item)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Invalid deployment list item provider_data payload: expected object or null."


def test_watsonx_mapper_provider_list_entry_flattens_provider_data_and_uses_id() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    now = datetime.now(tz=timezone.utc)
    item = SimpleNamespace(
        id="agent-1",
        name="Agent 1",
        type=DeploymentType.AGENT,
        description="desc",
        created_at=now,
        updated_at=now,
        provider_data={"tool_ids": ["tool-1", "  ", "tool-2"], "environment": "draft"},
    )

    shaped = mapper._shape_provider_deployment_list_entry(item)

    assert shaped["id"] == "agent-1"
    assert shaped["name"] == "Agent 1"
    assert shaped["type"] == DeploymentType.AGENT.value
    assert shaped["description"] == "desc"
    assert shaped["created_at"] == now.isoformat().replace("+00:00", "Z")
    assert shaped["updated_at"] == now.isoformat().replace("+00:00", "Z")
    assert shaped["tool_ids"] == ["tool-1", "tool-2"]
    assert shaped["environment"] == "draft"
    assert "provider_data" not in shaped
    assert "resource_key" not in shaped


def test_watsonx_mapper_shapes_deployment_list_result_with_flattened_entries() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    now = datetime.now(tz=timezone.utc)
    result = DeploymentListResult(
        deployments=[
            ItemResult(
                id="agent-1",
                name="Agent 1",
                type=DeploymentType.AGENT,
                description="desc",
                created_at=now,
                updated_at=now,
                provider_data={"tool_ids": ["tool-1"], "environment": "live"},
            )
        ]
    )

    shaped = mapper.shape_deployment_list_result(result)

    assert shaped.deployments is None
    assert shaped.page is None
    assert shaped.size is None
    assert shaped.total is None
    assert shaped.provider_data is not None
    assert shaped.provider_data["deployments"] == [
        {
            "id": "agent-1",
            "name": "Agent 1",
            "type": DeploymentType.AGENT.value,
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "updated_at": now.isoformat().replace("+00:00", "Z"),
            "tool_ids": ["tool-1"],
            "environment": "live",
        }
    ]


def test_watsonx_mapper_deployment_list_result_rejects_unknown_flattened_entry_fields() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    now = datetime.now(tz=timezone.utc)
    result = DeploymentListResult(
        deployments=[
            ItemResult(
                id="agent-1",
                name="Agent 1",
                type=DeploymentType.AGENT,
                created_at=now,
                updated_at=now,
                provider_data={"unexpected": "value"},
            )
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.shape_deployment_list_result(result)

    assert exc_info.value.status_code == 500
    assert "Invalid deployment list item provider_data payload:" in str(exc_info.value.detail)


@pytest.mark.parametrize(
    ("raw_message", "expected"),
    [
        (
            "app_id is required",
            "A resource conflict occurred in the deployment provider. The requested operation could not be completed.",
        ),
        (
            "unexpected conflict",
            "A resource conflict occurred in the deployment provider. The requested operation could not be completed.",
        ),
    ],
)
def test_watsonx_mapper_formats_conflict_detail_fallback_without_structured_entity(
    raw_message: str, expected: str
) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()

    detail = mapper.format_conflict_detail(raw_message)

    assert detail == expected


@pytest.mark.parametrize(
    ("resource", "expected"),
    [
        ("tool", "A tool with this name already exists in the provider. Please choose a different name."),
        (
            "connection",
            "A connection referenced in this request already exists in the provider. Please choose a different name.",
        ),
        (
            "agent",
            "An agent with this name already exists in the provider. Please choose a different name.",
        ),
    ],
)
def test_watsonx_mapper_formats_conflict_detail_from_structured_resource(resource: str, expected: str) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    assert mapper.format_conflict_detail("provider conflict payload", resource=resource) == expected


@pytest.mark.parametrize(
    ("resource", "resource_name", "expected"),
    [
        (
            "tool",
            "Simple_Agent",
            "A tool with name 'Simple_Agent' already exists in the provider. Please choose a different name.",
        ),
        (
            "connection",
            "cfg",
            "A connection with app_id 'cfg' already exists in the provider. Please choose a different name.",
        ),
        (
            "agent",
            "My_Agent",
            "An agent with name 'My_Agent' already exists in the provider. Please choose a different name.",
        ),
    ],
)
def test_watsonx_mapper_formats_conflict_detail_from_structured_resource_and_name(
    resource: str, resource_name: str, expected: str
) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    detail = mapper.format_conflict_detail(
        "provider conflict payload",
        resource=resource,
        resource_name=resource_name,
    )
    assert detail == expected


def test_watsonx_mapper_flow_version_item_data_from_snapshot_connections() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    snapshot_result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-1",
                name="Tool 1",
                provider_data={"connections": {"cfg-1": "conn-1", "cfg-2": "conn-2"}},
            )
        ]
    )
    shaped_by_snapshot_id = mapper._resolve_flow_version_item_data_by_snapshot_id(snapshot_result=snapshot_result)

    assert shaped_by_snapshot_id == {"tool-1": {"app_ids": ["cfg-1", "cfg-2"], "tool_name": "Tool 1"}}


def test_wxo_mapper_flow_version_item_data_rejects_empty_tool_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    snapshot_result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-1",
                name="",
                provider_data={"connections": {}},
            )
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper._resolve_flow_version_item_data_by_snapshot_id(snapshot_result=snapshot_result)
    assert exc_info.value.status_code == 500
    assert "Invalid flow-version provider_data payload:" in str(exc_info.value.detail)


def test_wxo_mapper_flow_version_item_data_rejects_empty_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    snapshot_result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-1",
                name="Tool 1",
                provider_data={},
            )
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper._resolve_flow_version_item_data_by_snapshot_id(snapshot_result=snapshot_result)
    assert exc_info.value.status_code == 500
    assert "snapshot provider_data must be a non-empty object" in str(exc_info.value.detail)


def test_watsonx_mapper_shapes_flow_version_list_result_with_enrichment() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    attached_at = datetime.now(tz=timezone.utc)
    flow_version_id = uuid4()
    flow_id = uuid4()

    rows = [
        (
            SimpleNamespace(provider_snapshot_id="tool-1", created_at=attached_at),
            SimpleNamespace(id=flow_version_id, flow_id=flow_id, version_number=3),
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
        page=1,
        size=20,
        total=1,
    )

    assert shaped.total == 1
    assert len(shaped.flow_versions) == 1
    assert shaped.flow_versions[0].id == flow_version_id
    assert shaped.flow_versions[0].flow_id == flow_id
    assert shaped.flow_versions[0].flow_name == "Flow A"
    assert shaped.flow_versions[0].version_number == 3
    assert shaped.flow_versions[0].attached_at == attached_at
    assert shaped.flow_versions[0].provider_snapshot_id == "tool-1"
    assert shaped.flow_versions[0].provider_data == {"app_ids": ["cfg-1"], "tool_name": "Tool 1"}


def test_watsonx_mapper_flow_version_list_result_returns_empty_app_ids_when_snapshot_has_no_connections() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    rows = [
        (
            SimpleNamespace(provider_snapshot_id="tool-1", created_at=datetime.now(tz=timezone.utc)),
            SimpleNamespace(id=uuid4(), flow_id=uuid4(), version_number=1),
            "Flow A",
        )
    ]
    snapshot_result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-1",
                name="Tool 1",
                provider_data={"connections": {}},
            )
        ]
    )

    shaped = mapper.shape_flow_version_list_result(
        rows=rows,
        snapshot_result=snapshot_result,
        page=1,
        size=20,
        total=1,
    )

    assert shaped.total == 1
    assert len(shaped.flow_versions) == 1
    assert shaped.flow_versions[0].provider_snapshot_id == "tool-1"
    assert shaped.flow_versions[0].provider_data == {"app_ids": [], "tool_name": "Tool 1"}


def test_watsonx_mapper_flow_version_list_result_degrades_when_snapshot_result_missing() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    rows = [
        (
            SimpleNamespace(provider_snapshot_id="tool-1", created_at=datetime.now(tz=timezone.utc)),
            SimpleNamespace(id=uuid4(), flow_id=uuid4(), version_number=1),
            "Flow A",
        )
    ]

    shaped = mapper.shape_flow_version_list_result(
        rows=rows,
        snapshot_result=None,
        page=1,
        size=20,
        total=1,
    )

    assert shaped.total == 1
    assert len(shaped.flow_versions) == 1
    assert shaped.flow_versions[0].provider_snapshot_id == "tool-1"
    assert shaped.flow_versions[0].provider_data is None


def test_watsonx_mapper_flow_version_list_result_degrades_when_required_snapshot_missing() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    rows = [
        (
            SimpleNamespace(provider_snapshot_id="tool-1", created_at=datetime.now(tz=timezone.utc)),
            SimpleNamespace(id=uuid4(), flow_id=uuid4(), version_number=1),
            "Flow A",
        )
    ]
    snapshot_result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-2",
                name="Tool 2",
                provider_data={"connections": {"cfg-2": "conn-2"}},
            )
        ]
    )

    shaped = mapper.shape_flow_version_list_result(
        rows=rows,
        snapshot_result=snapshot_result,
        page=1,
        size=20,
        total=1,
    )

    assert shaped.total == 1
    assert len(shaped.flow_versions) == 1
    assert shaped.flow_versions[0].provider_snapshot_id == "tool-1"
    assert shaped.flow_versions[0].provider_data is None


def test_watsonx_mapper_shapes_config_list_result_with_full_slot_validation() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    now = datetime.now(tz=timezone.utc)
    result = ConfigListResult(
        configs=[
            ConfigListItem(
                id="conn-1",
                name="cfg-1",
                created_at=now,
                updated_at=now,
                provider_data={"type": "key_value_creds", "environment": "draft"},
            ),
            ConfigListItem(id="conn-2", name="cfg-2", provider_data={"type": "key_value_creds", "environment": "live"}),
        ],
        provider_result={"deployment_id": " dep-1 ", "tool_ids": ["tool-1", "  "]},
    )

    shaped = mapper.shape_config_list_result(result, page=1, size=1)

    assert shaped.total is None
    assert shaped.page is None
    assert shaped.size is None
    assert shaped.provider_data is not None
    assert "deployment_id" not in shaped.provider_data
    assert "tool_ids" not in shaped.provider_data
    assert shaped.provider_data["page"] == 1
    assert shaped.provider_data["size"] == 1
    assert shaped.provider_data["total"] == 2
    assert len(shaped.provider_data["connections"]) == 1
    assert shaped.provider_data["connections"][0]["app_id"] == "cfg-1"
    assert shaped.provider_data["connections"][0]["connection_id"] == "conn-1"
    assert shaped.provider_data["connections"][0]["type"] == "key_value_creds"
    assert shaped.provider_data["connections"][0]["environment"] == "draft"
    assert set(shaped.provider_data["connections"][0].keys()) == {
        "app_id",
        "connection_id",
        "type",
        "environment",
    }


def test_watsonx_mapper_shapes_config_list_result_with_environment_metadata() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = ConfigListResult(
        configs=[
            ConfigListItem(
                id="conn-1",
                name="cfg-1",
                provider_data={"type": "key_value_creds", "environment": "live"},
            ),
        ],
        provider_result={},
    )

    shaped = mapper.shape_config_list_result(result, page=1, size=10)
    assert shaped.provider_data is not None
    assert shaped.provider_data["connections"] == [
        {"connection_id": "conn-1", "app_id": "cfg-1", "type": "key_value_creds", "environment": "live"}
    ]


def test_watsonx_mapper_config_list_fails_fast_when_type_missing() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = ConfigListResult(
        configs=[
            ConfigListItem(
                id="conn-bad",
                name="cfg-bad",
                provider_data={},
            ),
        ],
        provider_result={},
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.shape_config_list_result(result, page=1, size=10)
    assert exc_info.value.status_code == 500
    detail = str(exc_info.value.detail)
    assert "Unexpected result while reading the configuration" in detail
    assert "'type'" in detail


def test_watsonx_mapper_config_list_exposes_connection_id_app_id_and_type() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = ConfigListResult(
        configs=[
            ConfigListItem(
                id="conn-dep",
                name="cfg-dep",
                provider_data={"type": "key_value_creds", "environment": "draft"},
            ),
        ],
        provider_result={},
    )

    shaped = mapper.shape_config_list_result(result, page=1, size=10)

    assert shaped.provider_data is not None
    assert "tool_ids" not in shaped.provider_data
    assert len(shaped.provider_data["connections"]) == 1
    assert shaped.provider_data["connections"][0] == {
        "connection_id": "conn-dep",
        "app_id": "cfg-dep",
        "type": "key_value_creds",
        "environment": "draft",
    }


def test_watsonx_mapper_config_list_fails_fast_when_environment_missing() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = ConfigListResult(
        configs=[
            ConfigListItem(
                id="conn-no-env",
                name="cfg-no-env",
                provider_data={"type": "key_value_creds"},
            ),
        ],
        provider_result={},
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.shape_config_list_result(result, page=1, size=10)
    assert exc_info.value.status_code == 500
    detail = str(exc_info.value.detail)
    assert "Unexpected result while reading the configuration" in detail
    assert "'environment'" in detail


def test_watsonx_mapper_config_list_rejects_missing_type_even_with_other_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = ConfigListResult(
        configs=[
            ConfigListItem(
                id="conn-1",
                name="cfg-1",
                provider_data={"security_scheme": "key_value_creds"},
            )
        ],
        provider_result={},
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.shape_config_list_result(result, page=1, size=10)
    assert exc_info.value.status_code == 500
    detail = str(exc_info.value.detail)
    assert "Unexpected result while reading the configuration" in detail
    assert "'type'" in detail


def test_watsonx_mapper_shapes_snapshot_list_result_without_nested_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-1",
                name="Tool 1",
                provider_data={"connections": {"cfg-1": "conn-1"}},
            )
        ],
        provider_result={"deployment_id": "dep-1"},
    )

    shaped = mapper.shape_snapshot_list_result(result, page=1, size=20)

    assert shaped.total is None
    assert shaped.page is None
    assert shaped.size is None
    assert shaped.provider_data is not None
    assert "deployment_id" not in shaped.provider_data
    assert shaped.provider_data["page"] == 1
    assert shaped.provider_data["size"] == 20
    assert shaped.provider_data["total"] == 1
    assert shaped.provider_data["tools"] == [
        {
            "id": "tool-1",
            "name": "Tool 1",
            "connections": {"cfg-1": "conn-1"},
        }
    ]
    assert "provider_data" not in shaped.provider_data["tools"][0]


def test_watsonx_mapper_snapshot_list_result_ignores_extra_provider_result_fields() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = SnapshotListResult(
        snapshots=[SnapshotItem(id="tool-1", name="Tool 1", provider_data={"connections": {"cfg-1": "conn-1"}})],
        provider_result={"deployment_id": "dep-1", "unexpected": True},
    )

    shaped = mapper.shape_snapshot_list_result(result, page=1, size=20)

    assert shaped.provider_data is not None
    assert "unexpected" not in shaped.provider_data
    assert "deployment_id" not in shaped.provider_data


@pytest.mark.parametrize("provider_snapshot_id", [None, "   "])
def test_watsonx_mapper_flow_version_list_result_fails_fast_on_invalid_attachment_snapshot_id(
    provider_snapshot_id: str | None,
) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    rows = [
        (
            SimpleNamespace(provider_snapshot_id=provider_snapshot_id, created_at=datetime.now(tz=timezone.utc)),
            SimpleNamespace(id=uuid4(), flow_id=uuid4(), version_number=1),
            "Flow A",
        )
    ]

    with pytest.raises(HTTPException) as exc_info:
        mapper.shape_flow_version_list_result(
            rows=rows,
            snapshot_result=SnapshotListResult(snapshots=[]),
            page=1,
            size=20,
            total=1,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Flow version attachment has an invalid provider_snapshot_id."


def test_watsonx_api_payload_accepts_flow_version_create_bind_contract() -> None:
    flow_version_id = uuid4()
    payload = WatsonxApiDeploymentCreatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "connections": [],
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "app_ids": ["app-one"],
                }
            ],
        }
    )
    assert payload.add_flows[0].flow_version_id == flow_version_id


def test_watsonx_api_payload_accepts_flow_version_bind_contract() -> None:
    flow_version_id = uuid4()
    payload = WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": ["app-one"],
                    "remove_app_ids": [],
                }
            ],
        }
    )
    assert payload.upsert_flows[0].add_app_ids == ["app-one"]


def test_watsonx_api_payload_accepts_bind_with_empty_app_ids() -> None:
    flow_version_id = uuid4()
    payload = WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": [],
                    "remove_app_ids": [],
                }
            ],
        }
    )
    assert payload.upsert_flows[0].add_app_ids == []


def test_watsonx_api_payload_rejects_create_without_llm() -> None:
    flow_version_id = uuid4()
    with pytest.raises(ValidationError, match="llm"):
        WatsonxApiDeploymentCreatePayload.model_validate(
            {
                "connections": [],
                "add_flows": [
                    {
                        "flow_version_id": str(flow_version_id),
                        "app_ids": ["app-one"],
                    }
                ],
            }
        )


def test_watsonx_api_payload_accepts_llm_only_update_contract() -> None:
    payload = WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
        }
    )
    assert payload.llm == TEST_WXO_LLM
    assert payload.upsert_flows == []
    assert payload.upsert_tools == []
    assert payload.remove_flows == []
    assert payload.remove_tools == []


def test_watsonx_api_payload_accepts_update_without_llm() -> None:
    flow_version_id = uuid4()
    payload = WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": ["app-one"],
                    "remove_app_ids": [],
                }
            ],
        }
    )
    assert payload.llm is None


def test_watsonx_api_payload_accepts_flow_version_unbind_and_remove_contract() -> None:
    flow_version_id = uuid4()
    remove_flow_version_id = uuid4()
    payload = WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": [],
                    "remove_app_ids": ["app-one"],
                },
            ],
            "remove_flows": [str(remove_flow_version_id)],
        }
    )
    assert payload.upsert_flows[0].remove_app_ids == ["app-one"]
    assert payload.remove_flows == [remove_flow_version_id]


def test_watsonx_mapper_create_result_from_existing_update_normalizes_slot_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    provider_result = WatsonxDeploymentUpdateResultData.model_validate(
        {
            "created_app_ids": ["app-one"],
            "created_snapshot_ids": ["tool-1"],
            "created_snapshot_bindings": [
                {
                    "source_ref": str(flow_version_id),
                    "tool_id": "tool-1",
                    "created": True,
                }
            ],
        }
    )
    update_result = SimpleNamespace(provider_result=provider_result)

    create_result = mapper.util_create_result_from_existing_update(
        existing_resource_key="existing-agent-1",
        result=update_result,
    )

    assert create_result.id == "existing-agent-1"
    assert create_result.provider_result == {
        "app_ids": ["app-one"],
        "tools_with_refs": [{"source_ref": str(flow_version_id), "tool_id": "tool-1"}],
        "tool_app_bindings": [],
    }


def test_watsonx_mapper_resolve_verify_credentials_for_update_returns_none_without_provider_data() -> None:
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount

    mapper = WatsonxOrchestrateDeploymentMapper()
    existing_account = DeploymentProviderAccount(
        id=uuid4(),
        user_id=uuid4(),
        name="prod",
        provider_tenant_id="tenant-1",
        provider_key="watsonx-orchestrate",
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
        api_key="encrypted-api-key",  # pragma: allowlist secret
    )
    payload = DeploymentProviderAccountUpdateRequest(name="renamed")

    verify_input = mapper.resolve_verify_credentials_for_update(payload=payload, existing_account=existing_account)
    assert verify_input is None


def test_watsonx_mapper_resolve_verify_credentials_for_update_prefers_new_provider_data() -> None:
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount

    mapper = WatsonxOrchestrateDeploymentMapper()
    existing_account = DeploymentProviderAccount(
        id=uuid4(),
        user_id=uuid4(),
        name="prod",
        provider_tenant_id="tenant-1",
        provider_key="watsonx-orchestrate",
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
        api_key="encrypted-api-key",  # pragma: allowlist secret
    )
    payload = DeploymentProviderAccountUpdateRequest(provider_data={"api_key": "new-api-key"})

    verify_input = mapper.resolve_verify_credentials_for_update(
        payload=payload,
        existing_account=existing_account,
    )

    assert verify_input is not None
    assert verify_input.base_url == existing_account.provider_url
    assert verify_input.provider_data == {"api_key": "new-api-key"}  # pragma: allowlist secret


def test_watsonx_mapper_resolve_verify_credentials_for_update_rejects_url_update() -> None:
    """WatsonxApiProviderAccountUpdate (extra='forbid') rejects url in provider_data."""
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount

    mapper = WatsonxOrchestrateDeploymentMapper()
    existing_account = DeploymentProviderAccount(
        id=uuid4(),
        user_id=uuid4(),
        name="prod",
        provider_tenant_id="tenant-1",
        provider_key="watsonx-orchestrate",
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
        api_key="encrypted-api-key",  # pragma: allowlist secret
    )
    payload = DeploymentProviderAccountUpdateRequest(
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com/instances/tenant-2",
            "api_key": "new-api-key",  # pragma: allowlist secret
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.resolve_verify_credentials_for_update(payload=payload, existing_account=existing_account)
    assert exc_info.value.status_code == 422
    assert "url" in str(exc_info.value.detail).lower()


def test_watsonx_mapper_resolve_verify_credentials_for_update_rejects_tenant_id_update() -> None:
    """WatsonxApiProviderAccountUpdate (extra='forbid') rejects tenant_id in provider_data."""
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount

    mapper = WatsonxOrchestrateDeploymentMapper()
    existing_account = DeploymentProviderAccount(
        id=uuid4(),
        user_id=uuid4(),
        name="prod",
        provider_tenant_id="tenant-1",
        provider_key="watsonx-orchestrate",
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
        api_key="encrypted-api-key",  # pragma: allowlist secret
    )
    payload = DeploymentProviderAccountUpdateRequest(
        provider_data={
            "tenant_id": "tenant-2",
            "api_key": "new-api-key",  # pragma: allowlist secret
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.resolve_verify_credentials_for_update(payload=payload, existing_account=existing_account)
    assert exc_info.value.status_code == 422
    assert "tenant_id" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_watsonx_mapper_resolve_update_passthrough_without_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(name="n")

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=_FakeDb([]),
        payload=payload,
    )

    assert resolved.spec is not None
    assert resolved.provider_data is None


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_create_bind_into_raw_tool_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="create-deploy",
        description="",
        type="agent",
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "app_ids": ["app-one"],
                }
            ],
        },
    )
    row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow A",
        flow_description="desc",
        flow_tags=["tag"],
    )

    resolved = await mapper.resolve_deployment_create(
        user_id=uuid4(),
        project_id=project_id,
        db=_FakeDb([row]),
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["llm"] == TEST_WXO_LLM
    assert provider_data["tools"]["raw_payloads"][0]["name"] == "Flow_A"
    assert provider_data["tools"]["raw_payloads"][0]["provider_data"] == {
        "project_id": str(project_id),
        "source_ref": str(flow_version_id),
    }
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "Flow_A"


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_create_bind_with_tool_name_override() -> None:
    """Create bind should use tool_name override directly in raw tool and bind selector."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="create-deploy",
        description="",
        type="agent",
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "tool_name": "My Create Tool",
                    "app_ids": ["app-one"],
                }
            ],
        },
    )
    row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow A",
        flow_description="desc",
        flow_tags=["tag"],
    )

    resolved = await mapper.resolve_deployment_create(
        user_id=uuid4(),
        project_id=project_id,
        db=_FakeDb([row]),
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["tools"]["raw_payloads"][0]["name"] == "My_Create_Tool"
    assert provider_data["operations"][0]["op"] == "bind"
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "My_Create_Tool"
    assert all(op["op"] != "rename_tool" for op in provider_data["operations"])


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_existing_create_bind_into_update_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="existing-create",
        description="desc",
        type="agent",
        provider_data={
            "llm": TEST_WXO_LLM,
            "existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46",
            "connections": [],
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "app_ids": ["app-one"],
                }
            ],
        },
    )
    row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow A",
        flow_description="desc",
        flow_tags=["tag"],
    )

    resolved = await mapper.resolve_deployment_update_for_existing_create(
        user_id=uuid4(),
        project_id=project_id,
        db=_FakeDb([row]),
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert resolved.spec is not None
    assert resolved.spec.name == "existing-create"
    assert provider_data["tools"]["raw_payloads"][0]["name"] == "Flow_A"
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "Flow_A"


@pytest.mark.asyncio
async def test_watsonx_mapper_existing_create_bind_with_tool_name_override() -> None:
    """Existing-create update path should keep bind behavior with tool_name override and no rename op."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="existing-create",
        description="desc",
        type="agent",
        provider_data={
            "llm": TEST_WXO_LLM,
            "existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46",
            "connections": [],
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "tool_name": "Existing Create Tool",
                    "app_ids": ["app-one"],
                }
            ],
        },
    )
    row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow A",
        flow_description="desc",
        flow_tags=["tag"],
    )

    resolved = await mapper.resolve_deployment_update_for_existing_create(
        user_id=uuid4(),
        project_id=project_id,
        db=_FakeDb([row]),
        payload=payload,
    )
    provider_data = resolved.provider_data or {}
    ops = provider_data["operations"]

    assert provider_data["tools"]["raw_payloads"][0]["name"] == "Existing_Create_Tool"
    assert [op["op"] for op in ops] == ["bind"]
    assert ops[0]["tool"]["name_of_raw"] == "Existing_Create_Tool"
    assert all(op["op"] != "rename_tool" for op in ops)


@pytest.mark.asyncio
async def test_watsonx_mapper_maps_create_adapter_payload_validation_errors_to_422(monkeypatch) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="create-deploy",
        description="",
        type="agent",
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "app_ids": ["app-one"],
                }
            ],
        },
    )
    row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow A",
        flow_description="desc",
        flow_tags=["tag"],
    )

    fake_validation_error = SimpleNamespace(errors=lambda: [{"msg": "simulated adapter validation failure"}])

    def _raise_adapter_payload_validation_error(_self, _raw):
        raise AdapterPayloadValidationError(
            model_name="WatsonxDeploymentCreatePayload",
            error=fake_validation_error,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(PayloadSlot, "apply", _raise_adapter_payload_validation_error)

    with pytest.raises(HTTPException) as exc_info:
        await mapper.resolve_deployment_create(
            user_id=uuid4(),
            project_id=uuid4(),
            db=_FakeDb([row]),
            payload=payload,
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Invalid provider_data payload: simulated adapter validation failure"


async def test_watsonx_mapper_create_reports_missing_llm_field_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="create-deploy",
        description="",
        type="agent",
        provider_data={
            "connections": [],
            "add_flows": [
                {
                    "flow_version_id": str(uuid4()),
                    "app_ids": ["app-one"],
                }
            ],
        },
    )

    with pytest.raises(HTTPException) as exc:
        await mapper.resolve_deployment_create(
            user_id=uuid4(),
            project_id=uuid4(),
            db=_FakeDb([]),
            payload=payload,
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "Invalid provider_data for watsonx Orchestrate: Missing required field 'llm'."


@pytest.mark.asyncio
async def test_watsonx_mapper_create_reports_unknown_field_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="create-deploy",
        description="",
        type="agent",
        provider_data={
            "llm": TEST_WXO_LLM,
            "resource_name_prefix": "lf_test_",
            "upsert_tools": [
                {
                    "tool_id": "existing-tool",
                    "add_app_ids": [],
                }
            ],
        },
    )

    with pytest.raises(HTTPException) as exc:
        await mapper.resolve_deployment_create(
            user_id=uuid4(),
            project_id=uuid4(),
            db=_FakeDb([]),
            payload=payload,
        )

    assert exc.value.status_code == 422
    assert (
        exc.value.detail
        == "Invalid provider_data for watsonx Orchestrate: Invalid field 'resource_name_prefix'. Please remove it."
    )


@pytest.mark.asyncio
async def test_watsonx_mapper_create_skips_empty_bind_operations_but_keeps_raw_tools() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow A",
        flow_description="desc",
        flow_tags=["tag"],
    )
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="create-deploy",
        description="",
        type="agent",
        provider_data={
            "llm": TEST_WXO_LLM,
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "app_ids": [],
                }
            ],
        },
    )

    resolved = await mapper.resolve_deployment_create(
        user_id=uuid4(),
        project_id=project_id,
        db=_FakeDb([row]),
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["llm"] == TEST_WXO_LLM
    assert provider_data["operations"] == []
    assert len(provider_data["tools"]["raw_payloads"]) == 1
    assert provider_data["tools"]["raw_payloads"][0]["name"] == "Flow_A"
    assert provider_data["tools"]["raw_payloads"][0]["provider_data"] == {
        "project_id": str(project_id),
        "source_ref": str(flow_version_id),
    }


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_flow_version_bind_into_raw_tool_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow A",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )
    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": ["app-one"],
                    "remove_app_ids": [],
                }
            ],
        }
    )

    db = _MultiQueryFakeDb(flow_rows=[row], attachment_rows=[])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["llm"] == TEST_WXO_LLM
    assert provider_data["tools"]["raw_payloads"][0]["name"] == "Flow_A"
    assert provider_data["tools"]["raw_payloads"][0]["provider_data"] == {
        "project_id": str(project_id),
        "source_ref": str(flow_version_id),
    }
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "Flow_A"


@pytest.mark.asyncio
async def test_watsonx_mapper_skips_empty_bind_operations_but_keeps_raw_tools() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id_unbound = uuid4()
    flow_version_id_bound = uuid4()
    project_id = uuid4()
    row_unbound = SimpleNamespace(
        flow_version_id=flow_version_id_unbound,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=uuid4(),
        flow_name="Flow Unbound",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )
    row_bound = SimpleNamespace(
        flow_version_id=flow_version_id_bound,
        flow_version_number=2,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=uuid4(),
        flow_name="Flow Bound",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )
    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id_unbound),
                    "add_app_ids": [],
                    "remove_app_ids": [],
                },
                {
                    "flow_version_id": str(flow_version_id_bound),
                    "add_app_ids": ["app-one"],
                    "remove_app_ids": [],
                },
            ],
        }
    )
    db = _MultiQueryFakeDb(flow_rows=[row_unbound, row_bound], attachment_rows=[])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert len(provider_data["tools"]["raw_payloads"]) == 2
    assert sorted(item["name"] for item in provider_data["tools"]["raw_payloads"]) == ["Flow_Bound", "Flow_Unbound"]
    assert len(provider_data["operations"]) == 1
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "Flow_Bound"
    assert provider_data["operations"][0]["app_ids"] == ["app-one"]


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_llm_only_update_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(provider_data={"llm": TEST_WXO_LLM})

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=_FakeDb([]),
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["llm"] == TEST_WXO_LLM
    assert provider_data["operations"] == []
    assert provider_data["tools"]["raw_payloads"] is None
    assert provider_data["connections"] == {"raw_payloads": None}


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_unbind_and_remove_via_attachment_snapshot_ids() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id_unbind = uuid4()
    flow_version_id_remove = uuid4()
    deployment_db_id = uuid4()
    user_id = uuid4()
    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id_unbind),
                    "add_app_ids": [],
                    "remove_app_ids": ["app-one"],
                },
            ],
            "remove_flows": [str(flow_version_id_remove)],
        }
    )
    db = _FakeDb(
        [
            SimpleNamespace(
                flow_version_id=flow_version_id_unbind,
                provider_snapshot_id="tool-1",
            ),
            SimpleNamespace(
                flow_version_id=flow_version_id_remove,
                provider_snapshot_id="tool-2",
            ),
        ]
    )

    resolved = await mapper.resolve_deployment_update(
        user_id=user_id,
        deployment_db_id=deployment_db_id,
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["tool"]["tool_id"] == "tool-1"
    assert provider_data["operations"][0]["tool"]["source_ref"] == str(flow_version_id_unbind)
    assert provider_data["operations"][1]["tool"]["tool_id"] == "tool-2"
    assert provider_data["operations"][1]["tool"]["source_ref"] == str(flow_version_id_remove)


def test_watsonx_update_result_data_normalizes_fields() -> None:
    flow_version_id = uuid4()
    data = WatsonxApiDeploymentUpdateResultData.from_provider_result(
        {
            "created_app_ids": ["  app-one  ", "", "app-two"],
            "created_tools": [
                {"flow_version_id": str(flow_version_id), "tool_id": "tool-1"},
            ],
            "ignored_key": True,
        }
    )

    assert data.created_app_ids == ["app-one", "app-two"]
    assert data.created_tools is not None
    assert data.created_tools[0].flow_version_id == flow_version_id
    assert data.created_tools[0].tool_id == "tool-1"


def test_watsonx_mapper_shapes_update_response_from_result_schema() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    deployment_id = uuid4()
    provider_account_id = uuid4()
    deployment_row = SimpleNamespace(
        id=deployment_id,
        deployment_provider_account_id=provider_account_id,
        resource_key="agent-123",
        name="WXO Deployment",
        description="updated",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    new_flow_version_id = uuid4()
    result = DeploymentUpdateResult(
        id="provider-id",
        provider_result={
            "created_app_ids": ["created-app-1"],
            "created_snapshot_bindings": [
                {"source_ref": str(new_flow_version_id), "tool_id": "new-tool-1", "created": True}
            ],
        },
    )

    shaped = mapper.shape_deployment_update_result(result, deployment_row, provider_key="watsonx-orchestrate")

    assert shaped.id == deployment_id
    assert shaped.provider_id == provider_account_id
    assert shaped.provider_key == "watsonx-orchestrate"
    assert shaped.resource_key == "agent-123"
    assert shaped.provider_data == {
        "created_app_ids": ["created-app-1"],
        "created_tools": [
            {"flow_version_id": str(new_flow_version_id), "tool_id": "new-tool-1"},
        ],
    }


def test_watsonx_mapper_update_response_rejects_non_uuid_source_ref() -> None:
    """Non-UUID source_ref in created_snapshot_bindings raises HTTP 500."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    provider_account_id = uuid4()
    deployment_row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=provider_account_id,
        resource_key="agent-123",
        name="WXO Deployment",
        description="updated",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = DeploymentUpdateResult(
        id="provider-id",
        provider_result={
            "created_app_ids": [],
            "created_snapshot_bindings": [
                {"source_ref": "not-a-uuid", "tool_id": "tool-1", "created": True},
            ],
        },
    )

    with pytest.raises(HTTPException) as exc:
        mapper.shape_deployment_update_result(result, deployment_row, provider_key="watsonx-orchestrate")
    assert exc.value.status_code == 500
    assert "non-UUID source_ref" in exc.value.detail


def test_watsonx_mapper_create_response_rejects_non_uuid_source_ref_in_created_tools() -> None:
    """Create result must reject non-UUID source_ref in created tools."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    provider_account_id = uuid4()
    deployment_row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=provider_account_id,
        resource_key="agent-123",
        name="WXO Deployment",
        description="updated",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = DeploymentCreateResult(
        id="provider-id",
        provider_result={
            "app_ids": [],
            "tools_with_refs": [
                {"source_ref": "not-a-uuid", "tool_id": "orphan-tool"},
            ],
        },
    )

    with pytest.raises(HTTPException) as exc:
        mapper.shape_deployment_create_result(result, deployment_row, provider_key="watsonx-orchestrate")
    assert exc.value.status_code == 500
    assert "orphan-tool" in exc.value.detail
    assert "non-UUID source_ref" in exc.value.detail


def test_watsonx_mapper_shapes_llm_list_result() -> None:
    """Duplicates are intentionally passed through; deduplication is a client concern."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = DeploymentListLlmsResult(
        provider_result={
            "models": [
                {"model_name": "granite-3.1-8b"},
                {"model_name": "granite-3.3-8b"},
                {"model_name": "granite-3.1-8b"},
            ]
        },
    )

    shaped = mapper.shape_llm_list_result(result)
    assert shaped.provider_data == {
        "models": [
            {"model_name": "granite-3.1-8b"},
            {"model_name": "granite-3.3-8b"},
            {"model_name": "granite-3.1-8b"},
        ]
    }


def test_watsonx_mapper_llm_list_result_raises_for_missing_provider_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = DeploymentListLlmsResult(provider_result=None)

    with pytest.raises(HTTPException) as exc:
        mapper.shape_llm_list_result(result)
    assert exc.value.status_code == 500
    assert "Empty result while listing available models" in exc.value.detail


def test_watsonx_mapper_exposes_reconciliation_resolvers() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    add_id = uuid4()
    unbind_only_id = uuid4()
    remove_id = uuid4()
    patch = mapper.util_flow_version_patch(
        DeploymentUpdateRequest(
            provider_data={
                "llm": TEST_WXO_LLM,
                "connections": [],
                "upsert_flows": [
                    {
                        "flow_version_id": str(add_id),
                        "add_app_ids": ["app-one"],
                        "remove_app_ids": [],
                    },
                    {
                        "flow_version_id": str(unbind_only_id),
                        "add_app_ids": [],
                        "remove_app_ids": ["app-one"],
                    },
                ],
                "remove_flows": [str(remove_id)],
            }
        )
    )
    assert isinstance(patch, FlowVersionPatch)
    add_ids, remove_ids = patch.add_flow_version_ids, patch.remove_flow_version_ids
    assert add_ids == [add_id]
    assert remove_ids == [remove_id]

    create_bindings = mapper.util_create_snapshot_bindings(
        result=DeploymentCreateResult(
            id="provider-id",
            provider_result={"tools_with_refs": [{"source_ref": "fv-1", "tool_id": "snap-1"}]},
        ),
    )
    assert isinstance(create_bindings, CreateSnapshotBindings)
    assert create_bindings.to_source_ref_map() == {"fv-1": "snap-1"}

    created_ids = mapper.util_created_snapshot_ids(
        result=DeploymentUpdateResult(
            id="provider-id",
            provider_result={
                "created_snapshot_ids": ["snap-1"],
                "added_snapshot_bindings": [{"source_ref": str(add_id), "tool_id": "snap-1", "created": True}],
            },
        ),
    )
    assert isinstance(created_ids, CreatedSnapshotIds)
    assert created_ids.ids == ["snap-1"]
    update_bindings = mapper.util_update_snapshot_bindings(
        result=DeploymentUpdateResult(
            id="provider-id",
            provider_result={
                "added_snapshot_bindings": [{"source_ref": str(add_id), "tool_id": "snap-1", "created": True}],
            },
        ),
    )
    assert isinstance(update_bindings, UpdateSnapshotBindings)
    assert update_bindings.to_source_ref_map() == {str(add_id): "snap-1"}


def test_wxo_mapper_provider_account_response_includes_tenant_id() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
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
    assert shaped.provider_key == "watsonx-orchestrate"
    assert shaped.provider_data == {
        "url": "https://provider.example",
        "tenant_id": "tenant-1",
    }


def test_watsonx_mapper_trusts_top_level_deployment_id() -> None:
    """WXO mapper inherits base behavior: trust result.deployment_id directly."""
    from lfx.services.adapters.deployment.schema import ExecutionStatusResult

    mapper = WatsonxOrchestrateDeploymentMapper()
    result = ExecutionStatusResult(
        execution_id="e-1",
        deployment_id="agent-1",
        provider_result={"agent_id": "agent-1", "status": "accepted"},
    )
    assert mapper.util_resource_key_from_execution(result) == "agent-1"


# ---------------------------------------------------------------------------
# resolve_verify_credentials_for_create
# ---------------------------------------------------------------------------


def test_wxo_mapper_verify_credentials_create_filters_non_credential_fields() -> None:
    """WXO mapper forwards only credential fields to adapter verification."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountCreateRequest
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="test-account",
        provider_key="watsonx-orchestrate",
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com",
            "tenant_id": "tenant-123",
            "api_key": "my-secret-key",  # pragma: allowlist secret
        },
    )
    result = mapper.resolve_verify_credentials_for_create(payload=payload)
    assert isinstance(result, VerifyCredentials)
    assert "cloud.ibm.com" in result.base_url
    assert result.provider_data is not None
    assert result.provider_data["api_key"] == "my-secret-key"  # pragma: allowlist secret
    assert "tenant_id" not in result.provider_data


def test_wxo_mapper_verify_credentials_create_accepts_missing_tenant() -> None:
    """Verify-credentials path only parses; tenant validation is deferred to resolve_provider_account_create."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountCreateRequest
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="test-account",
        provider_key="watsonx-orchestrate",
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com",
            "api_key": "my-secret-key",  # pragma: allowlist secret
        },
    )

    result = mapper.resolve_verify_credentials_for_create(payload=payload)
    assert isinstance(result, VerifyCredentials)
    assert "cloud.ibm.com" in result.base_url


def test_wxo_mapper_provider_account_create_requires_tenant() -> None:
    """Create path rejects payloads with no explicit or URL-derived tenant."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountCreateRequest

    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="test-account",
        provider_key="watsonx-orchestrate",
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com",
            "api_key": "my-secret-key",  # pragma: allowlist secret
        },
    )

    with pytest.raises(ValueError, match=r"provider_data\.tenant_id is required"):
        mapper.resolve_provider_account_create(payload=payload, user_id="user-1")


def test_wxo_mapper_resolve_credentials_returns_api_key() -> None:
    """WXO mapper extracts api_key from provider_data for DB storage."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = mapper.resolve_credentials(provider_data={"api_key": "my-key"})  # pragma: allowlist secret
    assert result == {"api_key": "my-key"}  # pragma: allowlist secret


def test_wxo_mapper_resolve_credentials_rejects_tenant_metadata() -> None:
    """Update-path credential extraction rejects non-credential fields."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    with pytest.raises(HTTPException) as exc_info:
        mapper.resolve_credentials(
            provider_data={
                "tenant_id": "tenant-123",
                "api_key": "my-key",  # pragma: allowlist secret
            }
        )
    assert exc_info.value.status_code == 422
    assert "tenant_id" in exc_info.value.detail


def test_wxo_mapper_verify_credentials_create_rejects_unknown_fields() -> None:
    """Mapper rejects unexpected provider_data keys."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountCreateRequest

    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="test-account",
        provider_key="watsonx-orchestrate",
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com",
            "tenant_id": "tenant-123",
            "api_key": "my-secret-key",  # pragma: allowlist secret
            "unexpected": "field",
        },
    )
    with pytest.raises(HTTPException) as exc_info:
        mapper.resolve_verify_credentials_for_create(payload=payload)
    assert exc_info.value.status_code == 422
    assert "Invalid field 'unexpected'" in exc_info.value.detail


def test_wxo_mapper_resolve_credentials_strips_whitespace() -> None:
    """WXO mapper strips whitespace from api_key."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = mapper.resolve_credentials(provider_data={"api_key": "  my-key  "})  # pragma: allowlist secret
    assert result == {"api_key": "my-key"}  # pragma: allowlist secret


def test_wxo_mapper_resolve_credentials_rejects_empty() -> None:
    """WXO mapper rejects empty api_key in provider_data."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    with pytest.raises(HTTPException) as exc_info:
        mapper.resolve_credentials(provider_data={"api_key": ""})
    assert exc_info.value.status_code == 422
    assert "api_key" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        mapper.resolve_credentials(provider_data={"api_key": "   "})
    assert exc_info.value.status_code == 422
    assert "api_key" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        mapper.resolve_credentials(provider_data={})
    assert exc_info.value.status_code == 422
    assert "api_key" in exc_info.value.detail


def test_wxo_mapper_provider_account_create_assembles_model() -> None:
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountCreateRequest

    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="test-account",
        provider_key="watsonx-orchestrate",
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com/instances/tenant-123",
            "tenant_id": "tenant-123",
            "api_key": "my-secret-key",  # pragma: allowlist secret
        },
    )
    result = mapper.resolve_provider_account_create(payload=payload, user_id=uuid4())
    assert result.name == "test-account"
    assert result.provider_url == "https://api.us-south.wxo.cloud.ibm.com/instances/tenant-123"
    assert result.provider_tenant_id == "tenant-123"
    assert result.api_key == "my-secret-key"  # pragma: allowlist secret


def test_wxo_mapper_provider_account_create_uses_url_tenant_fallback() -> None:
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountCreateRequest

    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="test-account",
        provider_key="watsonx-orchestrate",
        provider_data={
            "url": "https://api.us-south.wxo.cloud.ibm.com/instances/tenant-123",
            "api_key": "my-secret-key",  # pragma: allowlist secret
        },
    )

    result = mapper.resolve_provider_account_create(payload=payload, user_id=uuid4())
    assert result.provider_tenant_id == "tenant-123"


# ---------------------------------------------------------------------------
# resolve_provider_account_update (WXO override)
# ---------------------------------------------------------------------------


def _make_wxo_existing_account():
    """Build a minimal fake existing WXO DeploymentProviderAccount."""
    return SimpleNamespace(
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/30000000-0000-0000-0000-000000000001",
        provider_tenant_id="30000000-0000-0000-0000-000000000001",
        provider_key="watsonx-orchestrate",
    )


def test_wxo_mapper_update_allows_name_changes_only_for_non_credential_fields() -> None:
    """Provider-account update keeps URL/tenant immutable."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountUpdateRequest

    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentProviderAccountUpdateRequest(name="renamed")
    result = mapper.resolve_provider_account_update(
        payload=payload,
        existing_account=_make_wxo_existing_account(),
    )
    assert "provider_tenant_id" not in result
    assert "provider_url" not in result
    assert result["name"] == "renamed"


def test_wxo_mapper_resolve_verify_credentials_rejects_extra_fields() -> None:
    """WXO slot uses extra='forbid' so unexpected credential fields are rejected."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import PAYLOAD_SCHEMAS
    from lfx.services.adapters.payload import AdapterPayloadValidationError

    slot = PAYLOAD_SCHEMAS.verify_credentials
    assert slot is not None
    with pytest.raises(AdapterPayloadValidationError):
        slot.parse({"api_key": "ok", "unexpected": "field"})  # pragma: allowlist secret


@pytest.mark.asyncio
async def test_watsonx_mapper_create_preserves_env_var_source_in_connection_payloads() -> None:
    """Connections with credentials should preserve source.

    Preserve raw-vs-variable semantics all the way to the adapter payload.
    """
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        name="deploy-with-vars",
        description="",
        type="agent",
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [
                {
                    "app_id": "app-new",
                    "credentials": [
                        {
                            "key": "RAW_TOKEN",
                            "value": "literal-secret",
                            "source": "raw",
                        },  # pragma: allowlist secret
                        {"key": "VAR_REF", "value": "MY_GLOBAL_VAR", "source": "variable"},
                    ],
                }
            ],
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "app_ids": ["app-new"],
                }
            ],
        },
    )
    row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow B",
        flow_description="desc",
        flow_tags=[],
    )

    resolved = await mapper.resolve_deployment_create(
        user_id=uuid4(),
        project_id=project_id,
        db=_FakeDb([row]),
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    conn_raw_payloads = provider_data["connections"]["raw_payloads"]
    assert conn_raw_payloads is not None
    assert len(conn_raw_payloads) == 1

    env_vars = conn_raw_payloads[0]["environment_variables"]
    assert env_vars["RAW_TOKEN"]["value"] == "literal-secret"  # pragma: allowlist secret
    assert env_vars["RAW_TOKEN"]["source"] == "raw"
    assert env_vars["VAR_REF"]["value"] == "MY_GLOBAL_VAR"
    assert env_vars["VAR_REF"]["source"] == "variable"


# ---------------------------------------------------------------------------
# Smart bind: reuse existing tool when attachment exists
# ---------------------------------------------------------------------------


class _MultiQueryFakeDb:
    """Fake DB that dispatches rows based on the queried table.

    Routes ``flow_version_deployment_attachment`` queries to
    ``attachment_rows`` and everything else (flow artifact queries)
    to ``flow_rows``.  This avoids fragile call-order coupling.
    """

    def __init__(self, flow_rows, attachment_rows=None):
        self._flow_rows = flow_rows
        self._attachment_rows = attachment_rows if attachment_rows is not None else []

    async def exec(self, statement):
        if "flow_version_deployment_attachment" in str(statement):
            return _FakeExecResult(self._attachment_rows)
        return _FakeExecResult(self._flow_rows)


@pytest.mark.asyncio
async def test_watsonx_mapper_bind_reuses_existing_tool_when_attachment_exists() -> None:
    """Bind reuses existing tool when flow_version already has an attachment."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()

    flow_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=flow_id,
        flow_name="Flow A",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )
    attachment_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        provider_snapshot_id="existing-tool-id",
    )

    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": ["app-one"],
                    "remove_app_ids": [],
                }
            ],
        }
    )

    db = _MultiQueryFakeDb(flow_rows=[flow_row], attachment_rows=[attachment_row])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["op"] == "bind"
    assert provider_data["operations"][0]["tool"]["tool_id_with_ref"]["tool_id"] == "existing-tool-id"
    assert provider_data["operations"][0]["tool"]["tool_id_with_ref"]["source_ref"] == str(flow_version_id)
    assert provider_data["tools"]["raw_payloads"] is None


@pytest.mark.asyncio
async def test_watsonx_mapper_bind_creates_new_tool_when_no_attachment() -> None:
    """When no attachment exists for a flow_version, bind should use name_of_raw."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    project_id = uuid4()

    flow_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=uuid4(),
        flow_name="Flow B",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )

    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": ["app-one"],
                    "remove_app_ids": [],
                }
            ],
        }
    )

    db = _MultiQueryFakeDb(flow_rows=[flow_row], attachment_rows=[])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "Flow_B"


@pytest.mark.asyncio
async def test_watsonx_mapper_bind_reuse_with_empty_app_ids_emits_attach_tool() -> None:
    """Bind with empty app_ids for an existing tool should emit attach_tool."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    project_id = uuid4()

    flow_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=uuid4(),
        flow_name="Flow C",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )
    attachment_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        provider_snapshot_id="existing-tool-id",
    )

    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": [],
                    "remove_app_ids": [],
                }
            ],
        }
    )

    db = _MultiQueryFakeDb(flow_rows=[flow_row], attachment_rows=[attachment_row])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["op"] == "attach_tool"
    assert provider_data["operations"][0]["tool"]["tool_id"] == "existing-tool-id"


@pytest.mark.asyncio
async def test_watsonx_mapper_upsert_flow_with_tool_name_emits_rename_for_existing_attachment() -> None:
    """tool_name on upsert_flows should become rename_tool for existing attachments."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    project_id = uuid4()

    flow_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=uuid4(),
        flow_name="Flow C",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )
    attachment_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        provider_snapshot_id="existing-tool-id",
    )

    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": [],
                    "remove_app_ids": [],
                    "tool_name": "My Better Tool",
                }
            ],
        }
    )

    db = _MultiQueryFakeDb(flow_rows=[flow_row], attachment_rows=[attachment_row])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["op"] == "attach_tool"
    assert provider_data["operations"][1]["op"] == "rename_tool"
    assert provider_data["operations"][1]["tool"]["tool_id"] == "existing-tool-id"
    assert provider_data["operations"][1]["new_name"] == "My_Better_Tool"


@pytest.mark.asyncio
async def test_watsonx_mapper_upsert_flow_with_add_remove_and_tool_name_emits_bind_unbind_rename() -> None:
    """upsert_flows with add/remove + tool_name should emit bind, unbind, and rename for existing attachments."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    project_id = uuid4()

    flow_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=uuid4(),
        flow_name="Flow D",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )
    attachment_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        provider_snapshot_id="existing-tool-id",
    )

    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": ["app-add-1", "app-add-2"],
                    "remove_app_ids": ["app-remove-1"],
                    "tool_name": "My Mixed Tool",
                }
            ],
        }
    )

    db = _MultiQueryFakeDb(flow_rows=[flow_row], attachment_rows=[attachment_row])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["op"] == "bind"
    assert provider_data["operations"][0]["tool"]["tool_id_with_ref"]["tool_id"] == "existing-tool-id"
    assert provider_data["operations"][0]["app_ids"] == ["app-add-1", "app-add-2"]

    assert provider_data["operations"][1]["op"] == "unbind"
    assert provider_data["operations"][1]["tool"]["tool_id"] == "existing-tool-id"
    assert provider_data["operations"][1]["app_ids"] == ["app-remove-1"]

    assert provider_data["operations"][2]["op"] == "rename_tool"
    assert provider_data["operations"][2]["tool"]["tool_id"] == "existing-tool-id"
    assert provider_data["operations"][2]["new_name"] == "My_Mixed_Tool"


@pytest.mark.asyncio
async def test_watsonx_mapper_tool_name_rename_compatible_with_all_update_operation_families() -> None:
    """tool_name/rename should coexist with flow removals, tool upserts/removals, and spec updates."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id_upsert = uuid4()
    flow_version_id_remove = uuid4()
    project_id = uuid4()

    flow_row = SimpleNamespace(
        flow_version_id=flow_version_id_upsert,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=uuid4(),
        flow_name="Flow E",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )
    attachment_rows = [
        SimpleNamespace(
            flow_version_id=flow_version_id_upsert,
            provider_snapshot_id="existing-tool-upsert",
        ),
        SimpleNamespace(
            flow_version_id=flow_version_id_remove,
            provider_snapshot_id="existing-tool-remove",
        ),
    ]

    payload = DeploymentUpdateRequest(
        name="updated-name",
        description="updated-description",
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id_upsert),
                    "add_app_ids": ["app-add"],
                    "remove_app_ids": ["app-remove"],
                    "tool_name": "My Combined Tool",
                }
            ],
            "remove_flows": [str(flow_version_id_remove)],
            "upsert_tools": [
                {
                    "tool_id": "external-tool-upsert",
                    "add_app_ids": ["external-app-add"],
                    "remove_app_ids": [],
                }
            ],
            "remove_tools": ["external-tool-remove"],
        },
    )

    db = _MultiQueryFakeDb(flow_rows=[flow_row], attachment_rows=attachment_rows)

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert resolved.spec is not None
    assert resolved.spec.name == "updated-name"
    assert resolved.spec.description == "updated-description"
    assert provider_data["llm"] == TEST_WXO_LLM
    assert provider_data["tools"]["raw_payloads"] is None

    ops = provider_data["operations"]
    assert [op["op"] for op in ops] == ["bind", "unbind", "rename_tool", "remove_tool", "bind", "remove_tool"]

    assert ops[0]["tool"]["tool_id_with_ref"]["tool_id"] == "existing-tool-upsert"
    assert ops[0]["app_ids"] == ["app-add"]

    assert ops[1]["tool"]["tool_id"] == "existing-tool-upsert"
    assert ops[1]["app_ids"] == ["app-remove"]

    assert ops[2]["tool"]["tool_id"] == "existing-tool-upsert"
    assert ops[2]["new_name"] == "My_Combined_Tool"

    assert ops[3]["tool"]["tool_id"] == "existing-tool-remove"

    assert ops[4]["tool"]["tool_id_with_ref"]["tool_id"] == "external-tool-upsert"
    assert ops[4]["app_ids"] == ["external-app-add"]

    assert ops[5]["tool"]["tool_id"] == "external-tool-remove"


@pytest.mark.asyncio
async def test_watsonx_mapper_tool_name_override_defers_invalid_flow_name_validation() -> None:
    """A valid tool_name override should win over an invalid underlying flow name."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    project_id = uuid4()

    flow_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        flow_version_number=1,
        flow_version_data={"nodes": [], "edges": []},
        flow_id=uuid4(),
        flow_name="123 bad flow",
        flow_description="desc",
        flow_tags=["tag"],
        project_id=project_id,
    )

    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "add_app_ids": ["app-one"],
                    "remove_app_ids": [],
                    "tool_name": "valid_name",
                }
            ],
        }
    )

    db = _MultiQueryFakeDb(flow_rows=[flow_row], attachment_rows=[])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["op"] == "bind"
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "valid_name"


# ---------------------------------------------------------------------------
# Tool-id-based operations
# ---------------------------------------------------------------------------


def test_watsonx_api_payload_accepts_bind_tool_operation() -> None:
    """bind_tool operation with app_ids is accepted."""
    WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_tools": [
                {
                    "tool_id": "some-tool-id",
                    "add_app_ids": ["app-one"],
                    "remove_app_ids": [],
                }
            ],
        }
    )


def test_watsonx_api_payload_accepts_bind_tool_with_empty_app_ids() -> None:
    """bind_tool with empty app_ids (attach-only) is accepted."""
    WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "upsert_tools": [
                {
                    "tool_id": "some-tool-id",
                    "add_app_ids": [],
                    "remove_app_ids": [],
                }
            ],
        }
    )


def test_watsonx_api_payload_accepts_unbind_tool_operation() -> None:
    """unbind_tool operation is accepted."""
    WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_tools": [
                {
                    "tool_id": "some-tool-id",
                    "add_app_ids": [],
                    "remove_app_ids": ["app-one"],
                }
            ],
        }
    )


def test_watsonx_api_payload_accepts_remove_tool_by_id_operation() -> None:
    """remove_tool_by_id operation is accepted."""
    WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "remove_tools": ["some-tool-id"],
        }
    )


def test_watsonx_api_payload_rejects_conflicting_tool_id_operations() -> None:
    """remove_tool_by_id + bind_tool for same tool_id is rejected."""
    with pytest.raises(ValidationError, match="remove_tools cannot be combined"):
        WatsonxApiDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "connections": [],
                "upsert_tools": [
                    {
                        "tool_id": "tid",
                        "add_app_ids": ["app-one"],
                        "remove_app_ids": [],
                    },
                ],
                "remove_tools": ["tid"],
            }
        )


def test_watsonx_api_payload_unbind_tool_rejects_connection_app_ids() -> None:
    """unbind_tool referencing raw connections app_ids should be rejected."""
    with pytest.raises(ValidationError, match=r"must not reference connections app_ids"):
        WatsonxApiDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "connections": [{"app_id": "app-new"}],
                "upsert_tools": [
                    {
                        "tool_id": "tid",
                        "add_app_ids": [],
                        "remove_app_ids": ["app-new"],
                    },
                ],
            }
        )


def test_watsonx_api_payload_rejects_duplicate_credential_keys() -> None:
    with pytest.raises(ValidationError, match="duplicate key values"):
        WatsonxApiDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "connections": [
                    {
                        "app_id": "app-new",
                        "credentials": [
                            {"key": "TOKEN", "value": "secret-a", "source": "raw"},  # pragma: allowlist secret
                            {"key": "TOKEN", "value": "secret-b", "source": "raw"},  # pragma: allowlist secret
                        ],
                    }
                ],
                "upsert_tools": [
                    {
                        "tool_id": "tid",
                        "add_app_ids": ["app-new"],
                        "remove_app_ids": [],
                    },
                ],
            }
        )


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_bind_tool_into_provider_operations() -> None:
    """bind_tool should produce tool_id_with_ref bind operation."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_tools": [
                {"tool_id": "external-tool", "add_app_ids": ["app-one"], "remove_app_ids": []},
            ],
        }
    )
    db = _FakeDb([])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["op"] == "bind"
    assert provider_data["operations"][0]["tool"]["tool_id_with_ref"]["tool_id"] == "external-tool"
    assert provider_data["operations"][0]["tool"]["tool_id_with_ref"]["source_ref"] == "external-tool"


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_unbind_tool_into_provider_operations() -> None:
    """unbind_tool should produce unbind operation with tool_id as source_ref."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_tools": [
                {"tool_id": "external-tool", "add_app_ids": [], "remove_app_ids": ["app-one"]},
            ],
        }
    )
    db = _FakeDb([])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["op"] == "unbind"
    assert provider_data["operations"][0]["tool"]["tool_id"] == "external-tool"
    assert provider_data["operations"][0]["tool"]["source_ref"] == "external-tool"


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_remove_tool_by_id_into_provider_operations() -> None:
    """remove_tool_by_id should produce remove_tool operation."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(
        provider_data={
            "llm": TEST_WXO_LLM,
            "remove_tools": ["external-tool"],
        }
    )
    db = _FakeDb([])

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["op"] == "remove_tool"
    assert provider_data["operations"][0]["tool"]["tool_id"] == "external-tool"
    assert provider_data["operations"][0]["tool"]["source_ref"] == "external-tool"


# ---------------------------------------------------------------------------
# tool_id in WatsonxApiCreatedTool response
# ---------------------------------------------------------------------------


def test_watsonx_created_tool_includes_tool_id() -> None:
    """WatsonxApiCreatedTool requires tool_id and non-null flow_version_id."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import WatsonxApiCreatedTool

    binding = WatsonxApiCreatedTool(
        flow_version_id=uuid4(),
        tool_id="tool-123",
    )
    assert binding.tool_id == "tool-123"
    assert binding.flow_version_id is not None

    with pytest.raises(ValidationError):
        WatsonxApiCreatedTool(tool_id="tool-456")


def test_watsonx_mapper_shapes_update_response_with_tool_id() -> None:
    """shape_deployment_update_result should include tool_id in created_tools."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    deployment_id = uuid4()
    provider_account_id = uuid4()
    flow_version_id = uuid4()
    deployment_row = SimpleNamespace(
        id=deployment_id,
        deployment_provider_account_id=provider_account_id,
        resource_key="agent-123",
        name="WXO Deployment",
        description="test",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
        PAYLOAD_SCHEMAS as WXO_SCHEMAS,
    )

    result = DeploymentUpdateResult(
        id="agent-1",
        provider_result=WXO_SCHEMAS.deployment_update_result.apply(
            WatsonxDeploymentUpdateResultData(
                created_app_ids=[],
                created_snapshot_bindings=[
                    {"source_ref": str(flow_version_id), "tool_id": "tool-1", "created": True},
                ],
            )
        ),
    )

    response = mapper.shape_deployment_update_result(result, deployment_row, provider_key="watsonx-orchestrate")
    assert response.provider_id == provider_account_id
    assert response.provider_key == "watsonx-orchestrate"
    assert response.resource_key == "agent-123"
    bindings = response.provider_data["created_tools"]
    assert len(bindings) == 1
    assert bindings[0]["tool_id"] == "tool-1"
    assert bindings[0]["flow_version_id"] == str(flow_version_id)


def test_watsonx_mapper_shapes_update_response_with_non_uuid_source_ref() -> None:
    """Non-UUID source_ref in created_snapshot_bindings should fail."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    provider_account_id = uuid4()
    deployment_row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=provider_account_id,
        resource_key="agent-123",
        name="WXO Deployment",
        description="test",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
        PAYLOAD_SCHEMAS as WXO_SCHEMAS,
    )

    result = DeploymentUpdateResult(
        id="agent-1",
        provider_result=WXO_SCHEMAS.deployment_update_result.apply(
            WatsonxDeploymentUpdateResultData(
                created_app_ids=[],
                created_snapshot_bindings=[
                    {"source_ref": "external-tool-id", "tool_id": "external-tool-id", "created": True},
                ],
            )
        ),
    )

    with pytest.raises(HTTPException) as exc:
        mapper.shape_deployment_update_result(result, deployment_row, provider_key="watsonx-orchestrate")
    assert exc.value.status_code == 500
    assert "non-UUID source_ref" in exc.value.detail


# ---------------------------------------------------------------------------
# util_update_snapshot_bindings filters non-UUID source_refs
# ---------------------------------------------------------------------------


def test_watsonx_mapper_update_snapshot_bindings_filters_non_uuid_source_refs() -> None:
    """Non-UUID source_ref bindings are excluded from attachment reconciliation."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()

    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
        PAYLOAD_SCHEMAS as WXO_SCHEMAS,
    )

    result = DeploymentUpdateResult(
        id="agent-1",
        provider_result=WXO_SCHEMAS.deployment_update_result.apply(
            WatsonxDeploymentUpdateResultData(
                created_app_ids=[],
                added_snapshot_bindings=[
                    {"source_ref": str(flow_version_id), "tool_id": "tool-fv-based", "created": True},
                    {"source_ref": "external-tool-id", "tool_id": "external-tool-id", "created": False},
                ],
            )
        ),
    )

    bindings = mapper.util_update_snapshot_bindings(result=result)
    assert len(bindings.snapshot_bindings) == 1
    assert bindings.snapshot_bindings[0].source_ref == str(flow_version_id)
    assert bindings.snapshot_bindings[0].snapshot_id == "tool-fv-based"


# ---------------------------------------------------------------------------
# Create payload: upsert_tools
# ---------------------------------------------------------------------------


def test_watsonx_create_payload_accepts_bind_tool_operation() -> None:
    """Create payload should accept upsert_tools items."""
    WatsonxApiDeploymentCreatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "upsert_tools": [
                {"tool_id": "existing-tool", "add_app_ids": []},
            ],
        }
    )


def test_watsonx_create_payload_bind_tool_without_prefix() -> None:
    """upsert_tools on create accepts minimal payload."""
    _payload = WatsonxApiDeploymentCreatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "upsert_tools": [
                {"tool_id": "existing-tool", "add_app_ids": []},
            ],
        }
    )
