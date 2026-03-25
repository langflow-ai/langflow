"""Tests for Watsonx deployment mapper and API payload contract."""

from __future__ import annotations

from datetime import UTC, datetime
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
from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper
from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
    WatsonxApiDeploymentCreatePayload,
    WatsonxApiDeploymentUpdatePayload,
    WatsonxApiDeploymentUpdateResultData,
)
from langflow.api.v1.schemas.deployments import DeploymentCreateRequest, DeploymentUpdateRequest
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
)
from lfx.services.adapters.deployment.schema import DeploymentCreateResult, DeploymentType, DeploymentUpdateResult
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
    assert mapper.api_payloads.deployment_create is not None
    assert mapper.api_payloads.deployment_update is not None
    assert mapper.api_payloads.deployment_update_result is not None


def test_watsonx_api_payload_accepts_flow_version_create_bind_contract() -> None:
    flow_version_id = uuid4()
    payload = WatsonxApiDeploymentCreatePayload.model_validate(
        {
            "resource_name_prefix": "lf_abc_",
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "bind",
                    "flow_version_id": str(flow_version_id),
                    "app_ids": ["app-one"],
                }
            ],
        }
    )
    assert payload.operations[0].op == "bind"


def test_watsonx_api_payload_accepts_flow_version_bind_contract() -> None:
    flow_version_id = uuid4()
    payload = WatsonxApiDeploymentUpdatePayload.model_validate(
        {
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "bind",
                    "flow_version_id": str(flow_version_id),
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
                    "flow_version_id": str(flow_version_id),
                    "app_ids": ["app-one"],
                },
                {
                    "op": "remove_tool",
                    "flow_version_id": str(flow_version_id),
                },
            ],
        }
    )
    assert payload.operations[0].op == "unbind"
    assert payload.operations[1].op == "remove_tool"


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
async def test_watsonx_mapper_translates_create_bind_into_raw_tool_payload() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    flow_version_id = uuid4()
    flow_id = uuid4()
    project_id = uuid4()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        spec={"name": "create-deploy", "description": "", "type": "agent"},
        provider_data={
            "resource_name_prefix": "lf_test_",
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "bind",
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

    assert provider_data["resource_name_prefix"] == "lf_test_"
    assert provider_data["tools"]["raw_payloads"][0]["name"] == "Flow A"
    assert provider_data["tools"]["raw_payloads"][0]["provider_data"] == {
        "project_id": str(project_id),
        "source_ref": str(flow_version_id),
    }
    assert provider_data["operations"][0]["tool"]["name_of_raw"] == "Flow A"


@pytest.mark.asyncio
async def test_watsonx_mapper_rejects_top_level_flow_version_and_config_on_create() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentCreateRequest(
        provider_id=uuid4(),
        spec={"name": "create-deploy", "description": "", "type": "agent"},
        flow_version_ids=[uuid4()],
        provider_data={
            "resource_name_prefix": "lf_test_",
            "connections": {"existing_app_ids": ["app-one"]},
            "operations": [
                {
                    "op": "bind",
                    "flow_version_id": str(uuid4()),
                    "app_ids": ["app-one"],
                }
            ],
        },
    )

    with pytest.raises(
        HTTPException,
        match="Watsonx create does not support top-level 'config' or 'flow_version_ids'",
    ):
        await mapper.resolve_deployment_create(
            user_id=uuid4(),
            project_id=uuid4(),
            db=_FakeDb([]),
            payload=payload,
        )


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
                    "flow_version_id": str(flow_version_id),
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
    assert provider_data["tools"]["raw_payloads"][0]["provider_data"] == {
        "project_id": str(project_id),
        "source_ref": str(flow_version_id),
    }
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
                    "flow_version_id": str(flow_version_id),
                    "app_ids": ["app-one"],
                },
                {
                    "op": "remove_tool",
                    "flow_version_id": str(flow_version_id),
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

    assert provider_data["operations"][0]["tool"]["tool_id"] == "tool-1"
    assert provider_data["operations"][0]["tool"]["source_ref"] == str(flow_version_id)
    assert provider_data["operations"][1]["tool"]["tool_id"] == "tool-1"
    assert provider_data["operations"][1]["tool"]["source_ref"] == str(flow_version_id)


def test_watsonx_update_result_data_normalizes_fields() -> None:
    flow_version_id = uuid4()
    data = WatsonxApiDeploymentUpdateResultData.from_provider_result(
        {
            "created_app_ids": ["  app-one  ", "", "app-two"],
            "tool_app_bindings": [
                {"flow_version_id": str(flow_version_id), "app_ids": [" app-a ", "", "app-b"]},
            ],
            "ignored_key": True,
        }
    )

    assert data.created_app_ids == ["app-one", "app-two"]
    assert data.tool_app_bindings is not None
    assert data.tool_app_bindings[0].flow_version_id == flow_version_id
    assert data.tool_app_bindings[0].app_ids == ["app-a", "app-b"]


def test_watsonx_mapper_shapes_update_response_from_result_schema() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=UTC)
    deployment_id = uuid4()
    deployment_row = SimpleNamespace(
        id=deployment_id,
        name="WXO Deployment",
        description="updated",
        deployment_type=DeploymentType.AGENT,
        created_at=timestamp,
        updated_at=timestamp,
    )
    new_flow_version_id = uuid4()
    existing_flow_version_id = uuid4()
    result = DeploymentUpdateResult(
        id="provider-id",
        provider_result={
            "created_app_ids": ["created-app-1"],
            "added_snapshot_bindings": [
                {"source_ref": str(new_flow_version_id), "tool_id": "new-tool-1", "created": True},
                {"source_ref": str(existing_flow_version_id), "tool_id": "existing-tool-1", "created": False},
            ],
            "tool_app_bindings": [
                {"tool_id": "new-tool-1", "app_ids": ["app-a"]},
                {"tool_id": "existing-tool-1", "app_ids": ["app-b"]},
            ],
        },
    )

    shaped = mapper.shape_deployment_update_result(result, deployment_row)

    assert shaped.id == deployment_id
    assert shaped.provider_data == {
        "created_app_ids": ["created-app-1"],
        "tool_app_bindings": [
            {"flow_version_id": str(new_flow_version_id), "app_ids": ["app-a"]},
            {"flow_version_id": str(existing_flow_version_id), "app_ids": ["app-b"]},
        ],
    }


def test_watsonx_mapper_update_response_raises_on_invalid_source_ref() -> None:
    """Non-UUID source_ref in snapshot bindings raises HTTP 500."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=UTC)
    deployment_row = SimpleNamespace(
        id=uuid4(),
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
            "added_snapshot_bindings": [
                {"source_ref": "not-a-uuid", "tool_id": "tool-1", "created": False},
            ],
            "tool_app_bindings": [
                {"tool_id": "tool-1", "app_ids": ["app-a"]},
            ],
        },
    )

    with pytest.raises(HTTPException) as exc:
        mapper.shape_deployment_update_result(result, deployment_row)
    assert exc.value.status_code == 500
    assert "not a valid UUID" in exc.value.detail


def test_watsonx_mapper_update_response_raises_on_unmapped_tool_binding() -> None:
    """tool_app_binding whose tool_id has no matching snapshot ref raises HTTP 500."""
    mapper = WatsonxOrchestrateDeploymentMapper()
    timestamp = datetime.now(tz=UTC)
    mapped_fv_id = uuid4()
    deployment_row = SimpleNamespace(
        id=uuid4(),
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
            "added_snapshot_bindings": [
                {"source_ref": str(mapped_fv_id), "tool_id": "mapped-tool", "created": True},
            ],
            "tool_app_bindings": [
                {"tool_id": "mapped-tool", "app_ids": ["app-a"]},
                {"tool_id": "orphan-tool", "app_ids": ["app-b"]},
            ],
        },
    )

    with pytest.raises(HTTPException) as exc:
        mapper.shape_deployment_update_result(result, deployment_row)
    assert exc.value.status_code == 500
    assert "orphan-tool" in exc.value.detail
    assert "no matching snapshot binding" in exc.value.detail


def test_watsonx_mapper_exposes_reconciliation_resolvers() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    add_id = uuid4()
    remove_id = uuid4()
    patch = mapper.util_flow_version_patch(
        DeploymentUpdateRequest(
            provider_data={
                "connections": {"existing_app_ids": ["app-one"]},
                "operations": [
                    {"op": "bind", "flow_version_id": str(add_id), "app_ids": ["app-one"]},
                    {"op": "unbind", "flow_version_id": str(remove_id), "app_ids": ["app-one"]},
                ],
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


def test_watsonx_mapper_resolve_provider_tenant_id_from_url() -> None:
    mapper = WatsonxOrchestrateDeploymentMapper()
    assert (
        mapper.resolve_provider_tenant_id(
            provider_url="https://api.example.com/orchestrate/instances/account-123/agents",
            provider_tenant_id=None,
        )
        == "account-123"
    )
    assert (
        mapper.resolve_provider_tenant_id(
            provider_url="https://api.example.com/orchestrate/instances/account-123/agents",
            provider_tenant_id="tenant-explicit",
        )
        == "tenant-explicit"
    )


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
# resolve_verify_credentials
# ---------------------------------------------------------------------------


def test_wxo_mapper_resolve_verify_credentials_packs_api_key() -> None:
    """WXO mapper packs api_key into provider_data via the adapter slot."""
    from langflow.api.v1.schemas.deployments import DeploymentProviderAccountCreateRequest
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    mapper = WatsonxOrchestrateDeploymentMapper()
    payload = DeploymentProviderAccountCreateRequest(
        name="test-account",
        provider_key="watsonx-orchestrate",
        provider_url="https://api.us-south.wxo.cloud.ibm.com",
        api_key="my-secret-key",  # pragma: allowlist secret
    )
    result = mapper.resolve_verify_credentials(payload=payload)
    assert isinstance(result, VerifyCredentials)
    assert "cloud.ibm.com" in result.base_url
    assert result.provider_data is not None
    assert result.provider_data["api_key"] == "my-secret-key"  # pragma: allowlist secret


def test_wxo_mapper_resolve_verify_credentials_rejects_extra_fields() -> None:
    """WXO slot uses extra='forbid' so unexpected credential fields are rejected."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import PAYLOAD_SCHEMAS
    from lfx.services.adapters.payload import AdapterPayloadValidationError

    slot = PAYLOAD_SCHEMAS.verify_credentials
    assert slot is not None
    with pytest.raises(AdapterPayloadValidationError):
        slot.parse({"api_key": "ok", "unexpected": "field"})  # pragma: allowlist secret
