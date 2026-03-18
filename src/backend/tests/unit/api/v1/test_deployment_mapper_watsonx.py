"""Tests for Watsonx deployment mapper and API payload contract."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.mappers.deployments import get_mapper
from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper
from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
    WatsonxApiDeploymentUpdatePayload,
    WatsonxApiDeploymentUpdateResultData,
)
from langflow.api.v1.schemas.deployments import DeploymentUpdateRequest
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
)
from lfx.services.adapters.deployment.schema import DeploymentType, DeploymentUpdateResult
from lfx.services.adapters.schema import AdapterType


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
    assert mapper.api_payloads.deployment_update is not None
    assert mapper.api_payloads.deployment_update_result is not None


def test_watsonx_api_payload_accepts_flow_version_bind_contract() -> None:
    flow_version_id = uuid4()
    payload = WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "bind",
                    "tool": {"flow_version_id": str(flow_version_id)},
                    "app_ids": ["app-one"],
                }
            ],
        }
    )
    assert payload.operations[0].op == "bind"


def test_watsonx_api_payload_accepts_flow_version_unbind_and_remove_contract() -> None:
    flow_version_id = uuid4()
    payload = WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "unbind",
                    "tool": {"flow_version_id": str(flow_version_id)},
                    "app_ids": ["app-one"],
                },
                {
                    "op": "remove_tool",
                    "tool": {"flow_version_id": str(flow_version_id)},
                },
            ],
        }
    )
    assert payload.operations[0].op == "unbind"
    assert payload.operations[1].op == "remove_tool"


def test_watsonx_mapper_resolves_flow_version_patch_from_provider_operations() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    add_flow_version_id = uuid4()
    remove_flow_version_id = uuid4()
    payload = DeploymentUpdateRequest(
        provider_data={
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "bind",
                    "tool": {"flow_version_id": str(add_flow_version_id)},
                    "app_ids": ["app-one"],
                },
                {
                    "op": "unbind",
                    "tool": {"flow_version_id": str(remove_flow_version_id)},
                    "app_ids": ["app-one"],
                },
            ],
        }
    )

    add_ids, remove_ids = mapper.resolve_flow_version_patch(payload)

    assert add_ids == [add_flow_version_id]
    assert remove_ids == [remove_flow_version_id]


@pytest.mark.asyncio
async def test_watsonx_mapper_resolve_update_passthrough_without_provider_data() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(spec={"name": "n"})

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=_FakeDb([]),
        payload=payload,
    )

    assert resolved.spec is not None
    assert resolved.provider_data is None


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
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "bind",
                    "tool": {"flow_version_id": str(flow_version_id)},
                    "app_ids": ["app-one"],
                }
            ],
        }
    )

    resolved = await mapper.resolve_deployment_update(
        user_id=uuid4(),
        deployment_db_id=uuid4(),
        db=_FakeDb([row]),
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["tools"]["raw_payloads"][0]["name"] == "Flow A_v1"
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "Flow A_v1"


@pytest.mark.asyncio
async def test_watsonx_mapper_rejects_top_level_config_updates() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(config={"config_id": "cfg-1"})

    with pytest.raises(
        HTTPException,
        match="Watsonx update does not support top-level 'config'",
    ):
        await mapper.resolve_deployment_update(
            user_id=uuid4(),
            deployment_db_id=uuid4(),
            db=_FakeDb([]),
            payload=payload,
        )


def test_watsonx_mapper_rejects_top_level_flow_version_patch() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentUpdateRequest(
        flow_version_ids={
            "add": [uuid4()],
        }
    )

    with pytest.raises(HTTPException, match="Top-level 'flow_version_ids' is not supported"):
        mapper.resolve_flow_version_patch(payload)


@pytest.mark.asyncio
async def test_watsonx_mapper_translates_unbind_and_remove_via_attachment_snapshot_ids() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    deployment_db_id = uuid4()
    user_id = uuid4()
    payload = DeploymentUpdateRequest(
        provider_data={
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "unbind",
                    "tool": {"flow_version_id": str(flow_version_id)},
                    "app_ids": ["app-one"],
                },
                {
                    "op": "remove_tool",
                    "tool": {"flow_version_id": str(flow_version_id)},
                },
            ],
        }
    )
    attachment_row = SimpleNamespace(
        flow_version_id=flow_version_id,
        provider_snapshot_id="tool-1",
    )
    db = _FakeDb([attachment_row])

    resolved = await mapper.resolve_deployment_update(
        user_id=user_id,
        deployment_db_id=deployment_db_id,
        db=db,
        payload=payload,
    )
    provider_data = resolved.provider_data or {}

    assert provider_data["operations"][0]["tool_id"] == "tool-1"
    assert provider_data["operations"][1]["tool_id"] == "tool-1"


def test_watsonx_update_result_data_normalizes_fields() -> None:
    data = WatsonxApiDeploymentUpdateResultData.from_provider_result(
        {
            "created_snapshot_ids": ["  snap-1  ", "", "snap-2"],
            "tool_app_bindings": [
                {"tool_id": "  tool-1  ", "app_ids": [" app-a ", "", "app-b"]},
            ],
            "ignored_key": True,
        }
    )

    assert data.created_snapshot_ids == ["snap-1", "snap-2"]
    assert data.tool_app_bindings is not None
    assert data.tool_app_bindings[0].tool_id == "tool-1"
    assert data.tool_app_bindings[0].app_ids == ["app-a", "app-b"]


def test_watsonx_mapper_shapes_update_response_from_result_schema() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=UTC)
    deployment_id = uuid4()
    deployment_row = SimpleNamespace(
        id=deployment_id,
        name="WXO Deployment",
        deployment_type=DeploymentType.AGENT.value,
        created_at=timestamp,
        updated_at=timestamp,
    )
    result = DeploymentUpdateResult(
        id="provider-id",
        provider_result={
            "created_snapshot_ids": ["snap-1", ""],
            "tool_app_bindings": [{"tool_id": "tool-1", "app_ids": ["app-a"]}],
        },
    )

    shaped = mapper.shape_deployment_update_result(result, deployment_row, description="updated")

    assert shaped.id == deployment_id
    assert shaped.provider_data == {"tool_app_bindings": [{"tool_id": "tool-1", "app_ids": ["app-a"]}]}
    assert mapper.resolve_created_snapshot_ids(result) == ["snap-1"]
