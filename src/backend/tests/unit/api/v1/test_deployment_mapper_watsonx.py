"""Tests for Watsonx deployment mapper and API payload contract."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.mappers.deployments import get_mapper
from langflow.api.v1.mappers.deployments.base import (
    BaseDeploymentMapper,
    OuterRequestValidationError,
    OuterRequestValidationNotConfiguredError,
)
from langflow.api.v1.mappers.deployments.contracts import (
    CreatedSnapshotIds,
    CreateSnapshotBindings,
    FlowVersionPatch,
    UpdateSnapshotBindings,
)

try:
    from langflow.services.adapters.deployment.watsonx_orchestrate import (
        WatsonxOrchestrateDeploymentService,  # noqa: F401
    )
except ModuleNotFoundError:
    pytest.skip(
        "Skipping Watsonx mapper tests: optional IBM SDK dependencies not available.",
        allow_module_level=True,
    )

from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper
from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
    WatsonxApiDeploymentCreatePayload,
    WatsonxApiDeploymentListItemProviderData,
    WatsonxApiDeploymentUpdatePayload,
    WatsonxApiDeploymentUpdateResultData,
)
from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentProviderAccountUpdateRequest,
    DeploymentUpdateRequest,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxDeploymentUpdateResultData,
)
from lfx.services.adapters.deployment.schema import (
    ConfigListItem,
    ConfigListResult,
    DeploymentCreateResult,
    DeploymentGetResult,
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
from pydantic import BaseModel, ValidationError

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


@pytest.mark.asyncio
async def test_watsonx_mapper_resolve_deployment_list_adapter_params_passthrough() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    params = await mapper.resolve_deployment_list_adapter_params(
        deployment_type=DeploymentType.AGENT,
        provider_params={"env": "prod"},
    )
    assert params.deployment_types == [DeploymentType.AGENT]
    assert params.provider_params == {"env": "prod"}


@pytest.mark.asyncio
async def test_watsonx_mapper_resolve_deployment_list_passes_none_through() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    params = await mapper.resolve_deployment_list_adapter_params(
        deployment_type=None,
        provider_params=None,
    )
    assert params is None


def test_watsonx_mapper_is_registered() -> None:
    mapper = get_mapper(AdapterType.DEPLOYMENT, WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY)
    assert isinstance(mapper, WatsonxOrchestrateDeploymentMapper)
    assert mapper.api_payloads.deployment_create is not None
    assert mapper.api_payloads.deployment_update is not None
    assert mapper.api_payloads.deployment_update_result is not None
    assert mapper.api_payloads.config_list_result is not None
    assert mapper.api_payloads.config_item_data is not None
    assert mapper.api_payloads.snapshot_list_result is not None


def test_watsonx_mapper_load_from_provider_params_force_draft_filter() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    assert mapper.resolve_load_from_provider_deployment_list_params() == {"environment": "draft"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_data",
    [
        {"input": "hello"},
        {"message": {"role": "user", "content": "hello"}},
        {"input": "hello", "thread_id": "thread-1"},
    ],
)
async def test_watsonx_mapper_execution_input_accepts_supported_request_shapes(provider_data: dict) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    resolved = await mapper.resolve_execution_input(provider_data, db=_FakeDb([]))
    assert resolved == provider_data


@pytest.mark.asyncio
async def test_watsonx_mapper_execution_input_rejects_agent_id_override_field() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    with pytest.raises(HTTPException) as exc_info:
        await mapper.resolve_execution_input(
            {"input": "hello", "agent_id": "agent-1"},
            db=_FakeDb([]),
        )
    assert exc_info.value.status_code == 422
    assert "agent_id" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_watsonx_mapper_execution_input_rejects_unknown_fields() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    with pytest.raises(HTTPException) as exc_info:
        await mapper.resolve_execution_input(
            {"input": "hello", "llm_params": {"temperature": 0.2}},
            db=_FakeDb([]),
        )
    assert exc_info.value.status_code == 422
    assert "llm_params" in str(exc_info.value.detail)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_data",
    [
        {},
        {"thread_id": "thread-only"},
        {"input": "hello", "message": {"role": "user", "content": "hello"}},
    ],
)
async def test_watsonx_mapper_execution_input_requires_exactly_one_input_source(provider_data: dict) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    with pytest.raises(HTTPException) as exc_info:
        await mapper.resolve_execution_input(provider_data, db=_FakeDb([]))
    assert exc_info.value.status_code == 422
    assert "exactly one of 'input' or 'message'" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_watsonx_mapper_execution_input_rejects_none_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    with pytest.raises(HTTPException) as exc_info:
        await mapper.resolve_execution_input(None, db=_FakeDb([]))
    assert exc_info.value.status_code == 422
    assert "Missing provider_data" in str(exc_info.value.detail)


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
    assert exc_info.value.detail == "Invalid deployment list item provider_data payload: expected object."


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
        provider_data={
            "display_name": "Agent 1",
            "description": "desc",
            "tool_ids": ["tool-1", "tool-2"],
            "llm": TEST_WXO_LLM,
            "environments": ["draft", "live"],
        },
    )

    shaped = mapper._shape_provider_deployment_list_entry(item)

    assert shaped["id"] == "agent-1"
    assert shaped["name"] == "Agent 1"
    assert shaped["type"] == DeploymentType.AGENT
    assert shaped["description"] == "desc"
    assert shaped["display_name"] == "Agent 1"
    assert shaped["created_at"] == now
    assert shaped["updated_at"] == now
    assert shaped["tool_ids"] == ["tool-1", "tool-2"]
    assert shaped["llm"] == TEST_WXO_LLM
    assert shaped["environments"] == ["draft", "live"]
    assert "provider_data" not in shaped
    assert "resource_key" not in shaped


def test_watsonx_mapper_provider_list_entry_rejects_blank_tool_id() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    now = datetime.now(tz=timezone.utc)
    item = ItemResult(
        id="agent-1",
        name="Agent 1",
        type=DeploymentType.AGENT,
        created_at=now,
        updated_at=now,
        provider_data={
            "display_name": "Agent 1",
            "description": "desc",
            "tool_ids": ["tool-1", "  "],
            "llm": TEST_WXO_LLM,
            "environments": ["draft", "live"],
        },
    )

    result = DeploymentListResult(deployments=[item])
    with pytest.raises(HTTPException) as exc_info:
        mapper.shape_deployment_list_result(result)

    assert exc_info.value.status_code == 500
    assert "Unexpected result while building deployment list provider payload" in str(exc_info.value.detail)


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
                provider_data={
                    "display_name": "Agent 1",
                    "description": "desc",
                    "tool_ids": ["tool-1"],
                    "llm": TEST_WXO_LLM,
                    "environments": ["live"],
                },
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
            "description": "desc",
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "updated_at": now.isoformat().replace("+00:00", "Z"),
            "display_name": "Agent 1",
            "tool_ids": ["tool-1"],
            "llm": TEST_WXO_LLM,
            "environments": ["live"],
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
                provider_data={"description": "desc", "unexpected": "value"},
            )
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.shape_deployment_list_result(result)

    assert exc_info.value.status_code == 500
    assert "Unexpected result while building deployment list provider payload" in str(exc_info.value.detail)


def test_watsonx_mapper_extracts_list_item_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_view = SimpleNamespace(
        deployments=[
            SimpleNamespace(
                id="agent-1",
                name="agent_api_name",
                provider_data={
                    "display_name": "  Agent One  ",
                    "description": "  Provider description  ",
                    "tool_ids": ["tool-1"],
                    "llm": TEST_WXO_LLM,
                    "environments": [" draft ", "live"],
                },
            )
        ]
    )

    provider_data_by_resource_key = mapper.extract_list_item_provider_data(provider_view)

    assert provider_data_by_resource_key == {
        "agent-1": {
            "name": "agent_api_name",
            "display_name": "  Agent One  ",
            "llm": TEST_WXO_LLM,
            "environments": [" draft ", "live"],
        }
    }


def test_watsonx_api_list_item_provider_data_rejects_blank_environment() -> None:
    with pytest.raises(ValidationError):
        WatsonxApiDeploymentListItemProviderData(
            name="Agent 1",
            display_name="Agent One",
            description="Provider description",
            environments=["draft", "  "],
        )


def test_watsonx_mapper_shapes_get_provider_agent_metadata() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()

    provider_data = mapper.shape_deployment_get_data(
        {
            "llm": TEST_WXO_LLM,
            "display_name": "  Agent Display Name  ",
            "description": "  Provider description  ",
            "tool_ids": ["tool-1"],
            "environments": ["draft"],
        },
        name="agent_api_name",
    )

    assert provider_data == {
        "llm": TEST_WXO_LLM,
        "name": "agent_api_name",
        "display_name": "  Agent Display Name  ",
        "environments": ["draft"],
    }


def test_watsonx_mapper_shapes_get_provider_agent_metadata_requires_llm() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()

    with pytest.raises(HTTPException) as exc_info:
        mapper.shape_deployment_get_data(
            {
                "llm": None,
                "display_name": "Agent Display Name",
                "description": "Provider description",
                "tool_ids": ["tool-1"],
                "environments": ["draft"],
            },
            name="agent_api_name",
        )

    assert exc_info.value.status_code == 500
    assert "Invalid value for field 'llm'." in str(exc_info.value.detail)


@pytest.mark.parametrize(
    ("item", "expected_message"),
    [
        (
            SimpleNamespace(id="agent-1", provider_data="bad-payload-type"),
            "Invalid payload.",
        ),
        (
            SimpleNamespace(id="agent-1", provider_data={"tool_ids": ["tool-1"]}),
            "Missing required field 'display_name'.",
        ),
        (
            SimpleNamespace(
                id="agent-1",
                provider_data={
                    "display_name": None,
                    "description": "Provider description",
                    "tool_ids": ["tool-1"],
                    "llm": TEST_WXO_LLM,
                    "environments": ["draft"],
                },
            ),
            "Invalid value for field 'display_name'.",
        ),
    ],
)
def test_watsonx_mapper_extract_list_item_provider_data_contract_breaks_raise_http_error(
    item: SimpleNamespace,
    expected_message: str,
) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()

    with pytest.raises(HTTPException) as exc_info:
        mapper.extract_list_item_provider_data(SimpleNamespace(deployments=[item]))
    assert exc_info.value.status_code == 500
    assert expected_message in str(exc_info.value.detail)


def test_watsonx_mapper_shapes_synced_list_items_with_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=uuid4(),
        deployment_type=DeploymentType.AGENT,
        display_name="Agent 1",
        description="desc",
        resource_key="agent-1",
        created_at=None,
        updated_at=None,
    )
    fv_id = uuid4()

    items = mapper.shape_deployment_list_items(
        rows_with_counts=[(row, 2, [(fv_id, "tool-1")])],
        has_flow_filter=True,
        provider_key=WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
        provider_data_by_resource_key={
            "agent-1": {
                "name": "Agent 1",
                "display_name": "Agent One",
                "description": "Provider description",
                "llm": TEST_WXO_LLM,
                "environments": ["draft"],
            }
        },
    )

    assert len(items) == 1
    assert items[0].resource_key == "agent-1"
    assert items[0].flow_version_ids == [fv_id]
    assert items[0].provider_data == {
        "name": "Agent 1",
        "display_name": "Agent One",
        "description": "Provider description",
        "llm": TEST_WXO_LLM,
        "environments": ["draft"],
    }


def test_watsonx_mapper_shape_synced_list_items_requires_provider_data_map() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()

    with pytest.raises(ValueError, match="provider_data_by_resource_key is required"):
        mapper.shape_deployment_list_items(
            rows_with_counts=[],
            provider_key=WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
        )


def test_watsonx_mapper_shape_synced_list_items_rejects_missing_provider_data_key() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=uuid4(),
        deployment_type=DeploymentType.AGENT,
        display_name="Agent 1",
        description=None,
        resource_key="agent-1",
        created_at=None,
        updated_at=None,
    )

    with pytest.raises(ValueError, match="Missing provider_data for wxO deployment resource_key='agent-1'"):
        mapper.shape_deployment_list_items(
            rows_with_counts=[(row, 0, [])],
            provider_key=WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
            provider_data_by_resource_key={},
        )


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
                name="tool_technical_1",
                provider_data={
                    "name": "tool_technical_1",
                    "display_name": "Tool 1",
                    "connections": {"cfg-1": "conn-1", "cfg-2": "conn-2"},
                },
            )
        ]
    )
    shaped_by_snapshot_id = mapper._resolve_flow_version_item_data_by_snapshot_id(snapshot_result=snapshot_result)

    assert shaped_by_snapshot_id == {
        "tool-1": {
            "app_ids": ["cfg-1", "cfg-2"],
            "tool_name": "tool_technical_1",
            "tool_display_name": "Tool 1",
        }
    }


def test_wxo_mapper_flow_version_item_data_rejects_empty_tool_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    snapshot_result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-1",
                name="",
                provider_data={"name": "", "display_name": "Tool 1", "connections": {}},
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
                name="tool_technical_1",
                provider_data={
                    "name": "tool_technical_1",
                    "display_name": "Tool 1",
                    "connections": {"cfg-1": "conn-1"},
                },
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
    assert shaped.flow_versions[0].provider_data == {
        "app_ids": ["cfg-1"],
        "tool_name": "tool_technical_1",
        "tool_display_name": "Tool 1",
    }


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
                name="tool_technical_1",
                provider_data={"name": "tool_technical_1", "display_name": "Tool 1", "connections": {}},
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
    assert shaped.flow_versions[0].provider_data == {
        "app_ids": [],
        "tool_name": "tool_technical_1",
        "tool_display_name": "Tool 1",
    }


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
                name="tool_technical_2",
                provider_data={
                    "name": "tool_technical_2",
                    "display_name": "Tool 2",
                    "connections": {"cfg-2": "conn-2"},
                },
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
                name="tool_technical_1",
                provider_data={
                    "name": "tool_technical_1",
                    "display_name": "Tool 1",
                    "connections": {"cfg-1": "conn-1"},
                },
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
            "name": "tool_technical_1",
            "display_name": "Tool 1",
            "connections": {"cfg-1": "conn-1"},
        }
    ]
    assert "provider_data" not in shaped.provider_data["tools"][0]


def test_watsonx_mapper_snapshot_list_result_ignores_extra_provider_result_fields() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = SnapshotListResult(
        snapshots=[
            SnapshotItem(
                id="tool-1",
                name="tool_technical_1",
                provider_data={
                    "name": "tool_technical_1",
                    "display_name": "Tool 1",
                    "connections": {"cfg-1": "conn-1"},
                },
            )
        ],
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
            "display_name": "Create Agent",
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


def test_watsonx_api_payload_rejects_metadata_only_create_contract() -> None:
    with pytest.raises(ValidationError, match="add_flows or upsert_tools"):
        WatsonxApiDeploymentCreatePayload.model_validate(
            {
                "display_name": "Create Agent",
                "llm": TEST_WXO_LLM,
            }
        )


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
                "display_name": "Create Agent",
                "connections": [],
                "add_flows": [
                    {
                        "flow_version_id": str(flow_version_id),
                        "app_ids": ["app-one"],
                    }
                ],
            }
        )


def test_watsonx_api_payload_rejects_create_without_display_name() -> None:
    flow_version_id = uuid4()
    with pytest.raises(ValidationError, match="display_name"):
        WatsonxApiDeploymentCreatePayload.model_validate(
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


def test_watsonx_api_payload_accepts_existing_agent_id_only() -> None:
    payload = WatsonxApiDeploymentCreatePayload.model_validate(
        {"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46"}
    )

    assert payload.existing_agent_id == "21b2b5a4-ef72-4697-8731-132163669a46"


def test_watsonx_api_payload_rejects_existing_agent_id_with_outer_description() -> None:
    payload = WatsonxApiDeploymentCreatePayload.model_validate(
        {"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46"}
    )
    outer_payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="local description",
        type="agent",
        provider_data={"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46"},
    )

    with pytest.raises(ValueError, match="description already set for the agent in wxO"):
        payload.validate_with_outer_fields(outer_payload)


def test_base_mapper_wraps_outer_request_value_error() -> None:
    class _OuterAwarePayload(BaseModel):
        def validate_with_outer_fields(self, outer_payload) -> None:
            _ = outer_payload
            msg = "outer validation failed"
            raise ValueError(msg)

    with pytest.raises(OuterRequestValidationError, match="Invalid content for request payload") as exc_info:
        BaseDeploymentMapper.validate_with_outer_request(
            _OuterAwarePayload(),
            DeploymentCreateRequest(provider_id=uuid4(), type="agent"),
        )

    assert exc_info.value.model_name == "_OuterAwarePayload"
    assert exc_info.value.detail == "outer validation failed"


def test_base_mapper_rejects_outer_request_validation_without_hook() -> None:
    class _PayloadWithoutOuterHook(BaseModel):
        value: str = "ok"

    with pytest.raises(OuterRequestValidationNotConfiguredError, match="does not support outer request validation"):
        BaseDeploymentMapper.validate_with_outer_request(
            _PayloadWithoutOuterHook(),
            DeploymentCreateRequest(provider_id=uuid4(), type="agent"),
        )


def test_base_mapper_provider_label_must_be_defined() -> None:
    with pytest.raises(NotImplementedError, match="must override PROVIDER_LABEL"):
        BaseDeploymentMapper().get_provider_label()


def test_base_mapper_parse_api_request_slot_requires_configured_slot() -> None:
    class _TestMapper(BaseDeploymentMapper):
        PROVIDER_LABEL = "test provider"

    with pytest.raises(HTTPException) as exc_info:
        _TestMapper().parse_api_request_slot(slot=None, slot_name="test_slot", raw={})

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "The test provider integration is not configured for this operation."


def test_base_mapper_parse_api_request_slot_rejects_missing_provider_data() -> None:
    class _TestMapper(BaseDeploymentMapper):
        PROVIDER_LABEL = "test provider"

    class _Payload(BaseModel):
        value: str

    with pytest.raises(HTTPException) as exc_info:
        _TestMapper().parse_api_request_slot(slot=PayloadSlot(_Payload), slot_name="test_slot", raw=None)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Missing provider_data for test provider."


def test_base_mapper_parse_api_request_slot_sanitizes_validation_errors() -> None:
    class _TestMapper(BaseDeploymentMapper):
        PROVIDER_LABEL = "test provider"

    class _Payload(BaseModel):
        value: str

    with pytest.raises(HTTPException) as exc_info:
        _TestMapper().parse_api_request_slot(slot=PayloadSlot(_Payload), slot_name="test_slot", raw={})

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Invalid provider_data for test provider: Missing required field 'value'."


def test_base_mapper_parse_api_request_slot_maps_missing_outer_validation_hook() -> None:
    class _TestMapper(BaseDeploymentMapper):
        PROVIDER_LABEL = "test provider"

    class _Payload(BaseModel):
        value: str

    with pytest.raises(HTTPException) as exc_info:
        _TestMapper().parse_api_request_slot(
            slot=PayloadSlot(_Payload),
            slot_name="test_slot",
            raw={"value": "ok"},
            outer_payload=DeploymentCreateRequest(provider_id=uuid4(), type="agent"),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "The test provider integration is not configured for this operation."


def test_base_mapper_parse_adapter_slot_requires_configured_slot() -> None:
    class _TestMapper(BaseDeploymentMapper):
        PROVIDER_LABEL = "test provider"

    with pytest.raises(HTTPException) as exc_info:
        _TestMapper().parse_adapter_slot(
            slot=None,
            slot_name="test_slot",
            raw={},
            operation="testing adapter output",
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "The test provider integration is not configured for testing adapter output."


def test_base_mapper_parse_adapter_slot_rejects_missing_adapter_result() -> None:
    class _TestMapper(BaseDeploymentMapper):
        PROVIDER_LABEL = "test provider"

    class _Payload(BaseModel):
        value: str

    with pytest.raises(HTTPException) as exc_info:
        _TestMapper().parse_adapter_slot(
            slot=PayloadSlot(_Payload),
            slot_name="test_slot",
            raw=None,
            operation="testing adapter output",
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Empty result while testing adapter output (test provider)."


def test_base_mapper_parse_adapter_slot_sanitizes_validation_errors() -> None:
    class _TestMapper(BaseDeploymentMapper):
        PROVIDER_LABEL = "test provider"

    class _Payload(BaseModel):
        value: str

    with pytest.raises(HTTPException) as exc_info:
        _TestMapper().parse_adapter_slot(
            slot=PayloadSlot(_Payload),
            slot_name="test_slot",
            raw={},
            operation="testing adapter output",
        )

    assert exc_info.value.status_code == 500
    assert (
        exc_info.value.detail
        == "Unexpected result while testing adapter output (test provider): Missing required field 'value'."
    )


def test_watsonx_api_payload_rejects_null_existing_agent_id() -> None:
    with pytest.raises(ValidationError, match="existing_agent_id cannot be set to null"):
        WatsonxApiDeploymentCreatePayload.model_validate({"existing_agent_id": None})


@pytest.mark.parametrize(
    "extra_provider_data",
    [
        {"display_name": "Renamed"},
        {"llm": TEST_WXO_LLM},
        {"connections": []},
        {"add_flows": []},
        {"upsert_tools": []},
    ],
)
def test_watsonx_api_payload_rejects_existing_agent_id_with_any_extra_field(extra_provider_data: dict) -> None:
    provider_data = {
        "existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46",
        **extra_provider_data,
    }

    with pytest.raises(ValidationError, match="tracking existing wxO agents"):
        WatsonxApiDeploymentCreatePayload.model_validate(provider_data)


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


@pytest.mark.parametrize("field_name", ["display_name", "llm"])
def test_watsonx_api_payload_rejects_null_update_scalars(field_name: str) -> None:
    with pytest.raises(ValidationError, match=f"{field_name} cannot be set to null"):
        WatsonxApiDeploymentUpdatePayload.model_validate({field_name: None})


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


def test_watsonx_mapper_create_result_from_existing_resource_includes_empty_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    create_result = mapper.util_create_result_from_existing_resource(
        existing_resource=DeploymentGetResult(
            id="existing-agent-1",
            name="agent_technical_name",
            type="agent",
            provider_data={
                "display_name": "Provider Label",
                "description": "Provider description",
                "tool_ids": [],
                "llm": TEST_WXO_LLM,
                "environments": ["draft"],
            },
        )
    )

    assert create_result.id == "existing-agent-1"
    assert create_result.type == DeploymentType.AGENT
    assert create_result.name == "agent_technical_name"
    assert create_result.description == "Provider description"
    assert isinstance(create_result.provider_result, dict)
    assert "deployment_name" not in create_result.provider_result
    assert create_result.provider_result.get("display_name") == "Provider Label"
    assert "description" not in create_result.provider_result
    assert create_result.provider_result.get("app_ids") == []
    assert create_result.provider_result.get("tools_with_refs") == []


def test_watsonx_mapper_existing_resource_result_preserves_description_before_db_write() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    long_description = "x" * 501

    create_result = mapper.util_create_result_from_existing_resource(
        existing_resource=DeploymentGetResult(
            id="existing-agent-1",
            name="agent_technical_name",
            type="agent",
            provider_data={
                "display_name": "Provider Label",
                "description": long_description,
                "tool_ids": [],
                "llm": TEST_WXO_LLM,
                "environments": ["draft"],
            },
        )
    )

    assert create_result.description == long_description


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


def test_watsonx_mapper_create_utilities_default_when_provider_data_missing() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="",
        type="agent",
    )

    assert mapper.util_create_flow_version_ids(payload) == []
    assert mapper.util_existing_deployment_resource_key_for_create(payload) is None


def test_watsonx_mapper_create_utilities_reject_explicit_null_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="",
        type="agent",
        provider_data=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.util_create_flow_version_ids(payload)
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Missing provider_data for watsonx Orchestrate."

    with pytest.raises(HTTPException) as exc_info:
        mapper.util_existing_deployment_resource_key_for_create(payload)
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Missing provider_data for watsonx Orchestrate."


def test_watsonx_mapper_existing_agent_onboarding_allows_db_only_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        type="agent",
        provider_data={"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46"},
    )

    assert mapper.util_create_flow_version_ids(payload) == []
    assert mapper.util_existing_deployment_resource_key_for_create(payload) == "21b2b5a4-ef72-4697-8731-132163669a46"


@pytest.mark.parametrize(
    "provider_data",
    [
        {"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46", "display_name": "Renamed"},
        {"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46", "llm": TEST_WXO_LLM},
        {
            "existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46",
            "add_flows": [{"flow_version_id": "21b2b5a4-ef72-4697-8731-132163669a46"}],
        },
    ],
)
def test_watsonx_mapper_existing_agent_onboarding_rejects_provider_mutations(provider_data: dict) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        type="agent",
        provider_data=provider_data,
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.util_existing_deployment_resource_key_for_create(payload)
    assert exc_info.value.status_code == 422


def test_watsonx_mapper_existing_agent_onboarding_rejects_description_mutation() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="",
        type="agent",
        provider_data={"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46"},
    )

    with pytest.raises(HTTPException) as exc_info:
        mapper.util_create_flow_version_ids(payload)
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        mapper.util_existing_deployment_resource_key_for_create(payload)
    assert exc_info.value.status_code == 422


def test_watsonx_mapper_existing_agent_create_model_uses_provider_metadata() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    user_id = uuid4()
    project_id = uuid4()
    provider_account_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=provider_account_id,
        type="agent",
        provider_data={"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46"},
    )
    existing_provider_resource = DeploymentGetResult(
        id="21b2b5a4-ef72-4697-8731-132163669a46",
        name="agent_technical_name",
        type="agent",
        provider_data={
            "display_name": "Provider Label",
            "description": "Provider description",
            "tool_ids": [],
            "llm": TEST_WXO_LLM,
            "environments": ["draft"],
        },
    )

    deployment = mapper.resolve_deployment_model_from_existing_resource_for_create(
        payload=payload,
        user_id=user_id,
        project_id=project_id,
        deployment_provider_account_id=provider_account_id,
        existing_provider_resource=existing_provider_resource,
    )

    assert deployment.display_name == "Provider Label"
    assert deployment.description == "Provider description"


def test_watsonx_mapper_existing_agent_create_model_passes_description_for_db_write() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_account_id = uuid4()
    long_description = "x" * 501
    payload = DeploymentCreateRequest(
        provider_id=provider_account_id,
        type="agent",
        provider_data={"existing_agent_id": "21b2b5a4-ef72-4697-8731-132163669a46"},
    )
    existing_provider_resource = DeploymentGetResult(
        id="21b2b5a4-ef72-4697-8731-132163669a46",
        name="agent_technical_name",
        type="agent",
        provider_data={
            "display_name": "Provider Label",
            "description": long_description,
            "tool_ids": [],
            "llm": TEST_WXO_LLM,
            "environments": ["draft"],
        },
    )

    deployment = mapper.resolve_deployment_model_from_existing_resource_for_create(
        payload=payload,
        user_id=uuid4(),
        project_id=uuid4(),
        deployment_provider_account_id=provider_account_id,
        existing_provider_resource=existing_provider_resource,
    )

    assert deployment.description == long_description


def test_watsonx_mapper_metadata_sync_kwargs_include_display_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_result = DeploymentListResult(
        deployments=[
            ItemResult(
                id="provider-agent-1",
                name="agent_technical_name",
                type="agent",
                provider_data={
                    "display_name": "Provider Label",
                    "description": "Provider description",
                    "tool_ids": [],
                    "llm": TEST_WXO_LLM,
                    "environments": [],
                },
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )
        ]
    )

    assert mapper.extract_metadata_for_list(provider_result) == {
        "provider-agent-1": {
            "display_name": "Provider Label",
            "description": "Provider description",
        }
    }


def test_watsonx_mapper_metadata_sync_passes_list_description() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_result = DeploymentListResult(
        deployments=[
            ItemResult(
                id="provider-agent-1",
                name="agent_technical_name",
                type="agent",
                provider_data={
                    "display_name": "Provider Label",
                    "description": "short",
                    "tool_ids": [],
                    "llm": TEST_WXO_LLM,
                    "environments": [],
                },
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            ),
            ItemResult(
                id="provider-agent-2",
                name="agent_technical_name_2",
                type="agent",
                provider_data={
                    "display_name": "Provider Label 2",
                    "description": "x" * 501,
                    "tool_ids": [],
                    "llm": TEST_WXO_LLM,
                    "environments": [],
                },
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            ),
        ]
    )

    metadata = mapper.extract_metadata_for_list(provider_result)

    assert metadata["provider-agent-2"]["description"] == "x" * 501


def test_watsonx_mapper_get_metadata_sync_kwargs_include_display_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_result = DeploymentGetResult(
        id="provider-agent-1",
        name="agent_technical_name",
        type="agent",
        provider_data={
            "display_name": "Provider Label",
            "description": "Provider description",
            "tool_ids": [],
            "llm": TEST_WXO_LLM,
            "environments": [],
        },
    )

    assert mapper.extract_metadata_for_get(provider_result) == {
        "display_name": "Provider Label",
        "description": "Provider description",
    }


def test_watsonx_mapper_create_model_uses_adapter_result_description() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    user_id = uuid4()
    project_id = uuid4()
    provider_account_id = uuid4()
    result = DeploymentCreateResult(
        id="provider-id",
        type=DeploymentType.AGENT,
        name="langflow_OK_AGENT_6_cea1e533",
        description="Langflow deployment OK AGENT 6",
        provider_result={
            "display_name": "OK AGENT 6",
            "app_ids": [],
            "tools_with_refs": [],
        },
    )

    deployment = mapper.resolve_deployment_model_for_create(
        result=result,
        user_id=user_id,
        project_id=project_id,
        deployment_provider_account_id=provider_account_id,
    )

    assert deployment.resource_key == "provider-id"
    assert deployment.display_name == "OK AGENT 6"
    assert deployment.deployment_type == DeploymentType.AGENT
    assert deployment.description == "Langflow deployment OK AGENT 6"


def test_watsonx_mapper_create_model_passes_adapter_result_description() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    result = DeploymentCreateResult(
        id="provider-id",
        type=DeploymentType.AGENT,
        name="langflow_OK_AGENT_6_cea1e533",
        description="x" * 501,
        provider_result={
            "display_name": "OK AGENT 6",
            "app_ids": [],
            "tools_with_refs": [],
        },
    )

    deployment = mapper.resolve_deployment_model_for_create(
        result=result,
        user_id=uuid4(),
        project_id=uuid4(),
        deployment_provider_account_id=uuid4(),
    )

    assert deployment.description == result.description


@pytest.mark.asyncio
async def test_watsonx_mapper_resolve_update_passthrough_without_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(description="new description")

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=_FakeDb([]),
        payload=payload,
    )

    assert resolved.spec is not None
    assert resolved.spec.description == "new description"
    assert resolved.provider_data is None
    assert mapper.util_flow_version_patch(payload) == FlowVersionPatch()


@pytest.mark.asyncio
async def test_watsonx_mapper_resolve_update_preserves_explicit_null_description() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(description=None)

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=_FakeDb([]),
        payload=payload,
    )

    assert resolved.spec is not None
    assert resolved.spec.description is None
    assert "description" in resolved.spec.model_fields_set
    assert resolved.provider_data is None


@pytest.mark.asyncio
async def test_watsonx_mapper_resolve_update_null_description_does_not_set_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(description=None, provider_data={"llm": TEST_WXO_LLM})

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=_FakeDb([]),
        payload=payload,
    )

    assert resolved.spec is not None
    assert resolved.spec.description is None
    assert "description" in resolved.spec.model_fields_set
    assert "name" not in resolved.spec.model_fields_set
    provider_data = resolved.provider_data or {}
    assert provider_data["llm"] == TEST_WXO_LLM
    assert provider_data["operations"] == []
    assert provider_data["tools"]["raw_payloads"] is None
    assert provider_data["connections"] == {"raw_payloads": None}


def test_watsonx_mapper_flow_version_patch_without_provider_data_is_empty() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(description="new description")

    patch = mapper.util_flow_version_patch(payload)

    assert patch.add_flow_version_ids == []
    assert patch.remove_flow_version_ids == []


@pytest.mark.asyncio
async def test_watsonx_mapper_resolve_update_rejects_explicit_null_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(description="new description", provider_data=None)

    with pytest.raises(HTTPException) as exc_info:
        await mapper.resolve_deployment_update(
            user_id=uuid4(),
            deployment_db_id=uuid4(),
            db=_FakeDb([]),
            payload=payload,
        )

    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        mapper.util_flow_version_patch(payload)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_create_bind_into_raw_tool_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="",
        type="agent",
        provider_data={
            "display_name": "create-deploy",
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

    assert resolved.spec.name is None
    assert provider_data["display_name"] == "create-deploy"
    assert provider_data["llm"] == TEST_WXO_LLM
    raw_tool_name = provider_data["tools"]["raw_payloads"][0]["name"]
    raw_provider_data = provider_data["tools"]["raw_payloads"][0]["provider_data"]
    assert raw_provider_data["project_id"] == str(project_id)
    assert raw_provider_data["source_ref"] == str(flow_version_id)
    assert raw_provider_data["tool_display_name"] == "Flow A"
    assert raw_provider_data["tool_name"].startswith("langflow_Flow_A_")
    assert raw_tool_name == "Flow A"
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == raw_provider_data["tool_name"]


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_create_bind_with_tool_display_name_override() -> None:
    """Create bind should generate a technical name from the tool_display_name override."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="",
        type="agent",
        provider_data={
            "display_name": "create-deploy",
            "llm": TEST_WXO_LLM,
            "connections": [],
            "add_flows": [
                {
                    "flow_version_id": str(flow_version_id),
                    "tool_display_name": "My Create Tool",
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

    assert resolved.spec.name is None
    assert provider_data["display_name"] == "create-deploy"
    raw_tool_name = provider_data["tools"]["raw_payloads"][0]["name"]
    raw_provider_data = provider_data["tools"]["raw_payloads"][0]["provider_data"]
    assert raw_provider_data["tool_display_name"] == "My Create Tool"
    assert raw_provider_data["tool_name"].startswith("langflow_My_Create_Tool_")
    assert raw_tool_name == "Flow A"
    assert provider_data["operations"][0]["op"] == "bind"
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == raw_provider_data["tool_name"]
    assert all(op["op"] != "rename_tool" for op in provider_data["operations"])


@pytest.mark.asyncio
async def test_watsonx_mapper_maps_create_adapter_payload_validation_errors_to_500(monkeypatch) -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="",
        type="agent",
        provider_data={
            "display_name": "create-deploy",
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

    original_parse = PayloadSlot.parse

    def _parse_with_deployment_create_failure(_self, _raw):
        if _self.adapter_model.__name__ == "WatsonxDeploymentCreatePayload":
            raise AdapterPayloadValidationError(
                model_name="WatsonxDeploymentCreatePayload",
                error=fake_validation_error,  # type: ignore[arg-type]
            )
        return original_parse(_self, _raw)

    monkeypatch.setattr(PayloadSlot, "parse", _parse_with_deployment_create_failure)

    with pytest.raises(HTTPException) as exc_info:
        await mapper.resolve_deployment_create(
            user_id=uuid4(),
            project_id=uuid4(),
            db=_FakeDb([row]),
            payload=payload,
        )
    assert exc_info.value.status_code == 500
    assert (
        exc_info.value.detail
        == "Unexpected result while building the deployment_create provider payload (watsonx Orchestrate): "
        "Invalid payload."
    )


async def test_watsonx_mapper_create_reports_missing_llm_field_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="",
        type="agent",
        provider_data={
            "display_name": "create-deploy",
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
    assert (
        exc.value.detail
        == "Invalid provider_data for watsonx Orchestrate: provider_data.llm is required for new agent creation."
    )


@pytest.mark.asyncio
async def test_watsonx_mapper_create_reports_unknown_field_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        description="",
        type="agent",
        provider_data={
            "display_name": "create-deploy",
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
        description="",
        type="agent",
        provider_data={
            "display_name": "create-deploy",
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
    raw_tool_name = provider_data["tools"]["raw_payloads"][0]["name"]
    raw_provider_data = provider_data["tools"]["raw_payloads"][0]["provider_data"]
    assert raw_provider_data["project_id"] == str(project_id)
    assert raw_provider_data["source_ref"] == str(flow_version_id)
    assert raw_provider_data["tool_display_name"] == "Flow A"
    assert raw_provider_data["tool_name"].startswith("langflow_Flow_A_")
    assert raw_tool_name == "Flow A"


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
    raw_tool_name = provider_data["tools"]["raw_payloads"][0]["name"]
    raw_provider_data = provider_data["tools"]["raw_payloads"][0]["provider_data"]
    assert raw_provider_data["project_id"] == str(project_id)
    assert raw_provider_data["source_ref"] == str(flow_version_id)
    assert raw_provider_data["tool_display_name"] == "Flow A"
    assert raw_provider_data["tool_name"].startswith("langflow_Flow_A_")
    assert raw_tool_name == "Flow A"
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == raw_provider_data["tool_name"]


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
    raw_payload_by_source_ref = {
        item["provider_data"]["source_ref"]: item for item in provider_data["tools"]["raw_payloads"]
    }
    assert set(raw_payload_by_source_ref) == {str(flow_version_id_bound), str(flow_version_id_unbound)}
    assert len(provider_data["operations"]) == 1
    assert (
        provider_data["operations"][0]["tool"]["name_of_raw"]
        == raw_payload_by_source_ref[str(flow_version_id_bound)]["provider_data"]["tool_name"]
    )
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
    assert "display_name" not in provider_data
    assert provider_data["operations"] == []
    assert provider_data["tools"].get("raw_payloads") is None
    assert provider_data["connections"].get("raw_payloads") is None


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


def test_watsonx_update_result_data_preserves_provider_owned_strings() -> None:
    flow_version_id = uuid4()
    data = WatsonxApiDeploymentUpdateResultData.from_provider_result(
        {
            "name": "agent_technical_name",
            "display_name": "Agent Display Name",
            "created_app_ids": ["  app-one  ", "app-two"],
            "created_tools": [
                {"flow_version_id": str(flow_version_id), "tool_id": "tool-1"},
            ],
            "ignored_key": True,
        }
    )

    assert data.name == "agent_technical_name"
    assert data.display_name == "Agent Display Name"
    assert data.created_app_ids == ["  app-one  ", "app-two"]
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
        display_name="WXO Deployment",
        description="updated",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    new_flow_version_id = uuid4()
    result = DeploymentUpdateResult(
        id="provider-id",
        provider_result={
            "name": "agent_technical_name",
            "display_name": "Provider Label",
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
        "name": "agent_technical_name",
        "display_name": "Provider Label",
        "created_app_ids": ["created-app-1"],
        "created_tools": [
            {"flow_version_id": str(new_flow_version_id), "tool_id": "new-tool-1"},
        ],
    }


def test_watsonx_mapper_shapes_update_response_with_provider_display_name() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    deployment_row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=uuid4(),
        resource_key="agent-123",
        display_name="Stale DB Label",
        description="updated",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = DeploymentUpdateResult(
        id="provider-id",
        provider_result={
            "name": "agent_technical_name",
            "display_name": "Provider Label",
            "description": "Provider description",
            "created_app_ids": [],
            "created_snapshot_bindings": [],
        },
    )

    shaped = mapper.shape_deployment_update_result(result, deployment_row, provider_key="watsonx-orchestrate")

    assert shaped.provider_data["display_name"] == "Provider Label"


def test_watsonx_mapper_resolves_kwargs_for_metadata_update_from_adapter_result() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    description = "x" * 501
    result = DeploymentUpdateResult(
        id="provider-id",
        provider_result={
            "name": "agent_technical_name",
            "display_name": "Provider Label",
            "description": description,
        },
    )

    metadata = mapper.resolve_kwargs_for_metadata_update(result)

    assert metadata == {
        "display_name": "Provider Label",
        "description": description,
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
        display_name="WXO Deployment",
        description="updated",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = DeploymentUpdateResult(
        id="provider-id",
        provider_result={
            "name": "agent_technical_name",
            "display_name": "Provider Label",
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


def test_watsonx_mapper_shapes_create_response_with_provider_names() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    provider_account_id = uuid4()
    flow_version_id = uuid4()
    deployment_row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=provider_account_id,
        resource_key="agent-123",
        display_name="WXO Deployment",
        description="created",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = DeploymentCreateResult(
        id="provider-id",
        type=DeploymentType.AGENT,
        name="agent_technical_name",
        description="created",
        provider_result={
            "display_name": "WXO Deployment",
            "app_ids": ["created-app-1"],
            "tools_with_refs": [
                {"source_ref": str(flow_version_id), "tool_id": "new-tool-1"},
            ],
        },
    )

    shaped = mapper.shape_deployment_create_result(result, deployment_row, provider_key="watsonx-orchestrate")

    assert shaped.provider_data == {
        "name": "agent_technical_name",
        "display_name": "WXO Deployment",
        "created_app_ids": ["created-app-1"],
        "created_tools": [
            {"flow_version_id": str(flow_version_id), "tool_id": "new-tool-1"},
        ],
    }


def test_watsonx_mapper_create_response_rejects_non_uuid_source_ref_in_created_tools() -> None:
    """Create result must reject non-UUID source_ref in created tools."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=timezone.utc)
    provider_account_id = uuid4()
    deployment_row = SimpleNamespace(
        id=uuid4(),
        deployment_provider_account_id=provider_account_id,
        resource_key="agent-123",
        display_name="WXO Deployment",
        description="updated",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = DeploymentCreateResult(
        id="provider-id",
        type=DeploymentType.AGENT,
        name="agent_technical_name",
        description="updated",
        provider_result={
            "display_name": "WXO Deployment",
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
            type=DeploymentType.AGENT,
            name="agent_technical_name",
            description="created",
            provider_result={
                "display_name": "Agent Display Name",
                "tools_with_refs": [{"source_ref": "fv-1", "tool_id": "snap-1"}],
            },
        ),
    )
    assert isinstance(create_bindings, CreateSnapshotBindings)
    assert create_bindings.to_source_ref_map() == {"fv-1": "snap-1"}

    created_ids = mapper.util_created_snapshot_ids(
        result=DeploymentUpdateResult(
            id="provider-id",
            provider_result={
                "name": "agent_technical_name",
                "display_name": "Provider Label",
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
                "name": "agent_technical_name",
                "display_name": "Provider Label",
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
    assert result.base_url == "https://api.us-south.wxo.cloud.ibm.com/"
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
    assert result.base_url == "https://api.us-south.wxo.cloud.ibm.com/"


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
        description="",
        type="agent",
        provider_data={
            "display_name": "deploy-with-vars",
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

    raw_payload = provider_data["tools"]["raw_payloads"][0]
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == raw_payload["provider_data"]["tool_name"]
    assert raw_payload["provider_data"]["source_ref"] == str(flow_version_id)


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
async def test_watsonx_mapper_upsert_flow_with_tool_display_name_emits_rename_for_existing_attachment() -> None:
    """tool_display_name on upsert_flows should become rename_tool for existing attachments."""
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
                    "tool_display_name": "My Better Tool",
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
    assert provider_data["operations"][1]["tool_display_name"] == "My Better Tool"


@pytest.mark.asyncio
async def test_watsonx_mapper_upsert_flow_with_add_remove_and_tool_display_name_emits_bind_unbind_rename() -> None:
    """upsert_flows with add/remove + tool_display_name should emit bind, unbind, and rename."""
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
                    "tool_display_name": "My Mixed Tool",
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
    assert provider_data["operations"][2]["tool_display_name"] == "My Mixed Tool"


@pytest.mark.asyncio
async def test_watsonx_mapper_tool_display_name_rename_compatible_with_all_update_operation_families() -> None:
    """tool_display_name rename should coexist with flow removals, tool upserts/removals, and spec updates."""
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
        description="updated-description",
        provider_data={
            "display_name": "updated-name",
            "llm": TEST_WXO_LLM,
            "connections": [],
            "upsert_flows": [
                {
                    "flow_version_id": str(flow_version_id_upsert),
                    "add_app_ids": ["app-add"],
                    "remove_app_ids": ["app-remove"],
                    "tool_display_name": "My Combined Tool",
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
    assert "name" not in resolved.spec.model_fields_set
    assert resolved.spec.description == "updated-description"
    assert provider_data["display_name"] == "updated-name"
    assert provider_data["llm"] == TEST_WXO_LLM
    assert provider_data["tools"]["raw_payloads"] is None

    ops = provider_data["operations"]
    assert [op["op"] for op in ops] == ["bind", "unbind", "rename_tool", "remove_tool", "bind", "remove_tool"]

    assert ops[0]["tool"]["tool_id_with_ref"]["tool_id"] == "existing-tool-upsert"
    assert ops[0]["app_ids"] == ["app-add"]

    assert ops[1]["tool"]["tool_id"] == "existing-tool-upsert"
    assert ops[1]["app_ids"] == ["app-remove"]

    assert ops[2]["tool"]["tool_id"] == "existing-tool-upsert"
    assert ops[2]["tool_display_name"] == "My Combined Tool"

    assert ops[3]["tool"]["tool_id"] == "existing-tool-remove"

    assert ops[4]["tool"]["tool_id_with_ref"]["tool_id"] == "external-tool-upsert"
    assert ops[4]["app_ids"] == ["external-app-add"]

    assert ops[5]["tool"]["tool_id"] == "external-tool-remove"


@pytest.mark.asyncio
async def test_watsonx_mapper_tool_display_name_override_generates_valid_technical_name() -> None:
    """tool_display_name should not be treated as a caller-owned technical name."""
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
                    "tool_display_name": "valid name",
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
    raw_tool_name = provider_data["operations"][0]["tool"]["name_of_raw"]
    raw_payload = provider_data["tools"]["raw_payloads"][0]
    assert raw_tool_name == raw_payload["provider_data"]["tool_name"]
    assert raw_payload["provider_data"]["source_ref"] == str(flow_version_id)
    assert raw_payload["provider_data"]["tool_name"].startswith("langflow_valid_name_")


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
        display_name="WXO Deployment",
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
                name="agent_technical_name",
                display_name="Provider Label",
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
        display_name="WXO Deployment",
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
                name="agent_technical_name",
                display_name="Provider Label",
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
                name="agent_technical_name",
                display_name="Provider Label",
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
            "display_name": "Create Agent",
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
            "display_name": "Create Agent",
            "llm": TEST_WXO_LLM,
            "upsert_tools": [
                {"tool_id": "existing-tool", "add_app_ids": []},
            ],
        }
    )
