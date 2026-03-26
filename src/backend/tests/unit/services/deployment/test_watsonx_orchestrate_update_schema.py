"""Unit tests for Watsonx deployment update provider schema."""

from __future__ import annotations

from uuid import UUID

import pytest

try:
    import langflow.services.adapters.deployment.watsonx_orchestrate  # noqa: F401
except ModuleNotFoundError:
    pytest.skip(
        "Skipping Watsonx deployment tests: optional IBM SDK dependencies not available.",
        allow_module_level=True,
    )

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxAgentExecutionResultData,
    WatsonxDeploymentCreatePayload,
    WatsonxDeploymentCreateResultData,
    WatsonxDeploymentUpdatePayload,
    WatsonxDeploymentUpdateResultData,
    WatsonxFlowArtifactProviderData,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.service import WatsonxOrchestrateDeploymentService
from lfx.services.adapters.payload import AdapterPayloadValidationError


def _raw_tool(name: str, suffix: int) -> dict:
    return {
        "id": str(UUID(int=suffix)),
        "name": name,
        "description": "desc",
        "data": {"nodes": [], "edges": []},
        "tags": [],
        "provider_data": {"project_id": "project-1", "source_ref": f"fv-{suffix}"},
    }


def _raw_connection(app_id: str) -> dict:
    return {
        "app_id": app_id,
        "environment_variables": {
            "API_KEY": {"source": "raw", "value": "secret"},
        },
    }


def test_payload_schema_slot_registered_for_deployment_update() -> None:
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_create is not None
    assert slot.deployment_create.adapter_model is WatsonxDeploymentCreatePayload
    assert slot.flow_artifact is not None
    assert slot.flow_artifact.adapter_model is WatsonxFlowArtifactProviderData
    assert slot.deployment_create_result is not None
    assert slot.deployment_create_result.adapter_model is WatsonxDeploymentCreateResultData
    assert slot.deployment_update is not None
    assert slot.deployment_update.adapter_model is WatsonxDeploymentUpdatePayload
    assert slot.deployment_update_result is not None
    assert slot.deployment_update_result.adapter_model is WatsonxDeploymentUpdateResultData
    assert slot.execution_create_result is not None
    assert slot.execution_create_result.adapter_model is WatsonxAgentExecutionResultData
    assert slot.execution_status_result is not None
    assert slot.execution_status_result.adapter_model is WatsonxAgentExecutionResultData


def test_create_schema_accepts_raw_tool_pool_and_shared_connection_refs() -> None:
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_create is not None

    payload = {
        "resource_name_prefix": "lf_pref_",
        "tools": {
            "raw_payloads": [_raw_tool("tool-new-1", 11)],
        },
        "connections": {
            "existing_app_ids": ["app-existing-1"],
            "raw_payloads": [_raw_connection("app-new-1")],
        },
        "operations": [
            {
                "op": "bind",
                "tool": {"name_of_raw": "tool-new-1"},
                "app_ids": ["app-new-1"],
            },
            {
                "op": "bind",
                "tool": {"tool_id_with_ref": {"source_ref": "fv-existing-1", "tool_id": "tool-existing-1"}},
                "app_ids": ["app-existing-1"],
            },
        ],
    }

    applied = slot.deployment_create.apply(payload)
    assert applied["resource_name_prefix"] == "lf_pref_"
    assert applied["operations"][0]["tool"]["name_of_raw"] == "tool-new-1"


def test_create_schema_dedupes_duplicate_raw_tool_names() -> None:
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_create is not None

    payload = {
        "resource_name_prefix": "lf_pref_",
        "tools": {
            "raw_payloads": [
                _raw_tool("tool-dup", 101),
                _raw_tool("tool-dup", 102),
            ],
        },
        "connections": {"existing_app_ids": ["app-existing-1"]},
        "operations": [
            {
                "op": "bind",
                "tool": {"name_of_raw": "tool-dup"},
                "app_ids": ["app-existing-1"],
            }
        ],
    }

    applied = slot.deployment_create.apply(payload)
    raw_payloads = applied["tools"]["raw_payloads"]
    assert len(raw_payloads) == 1
    assert raw_payloads[0]["name"] == "tool-dup"
    # First payload wins after dedupe.
    assert raw_payloads[0]["provider_data"]["source_ref"] == "fv-101"


def test_create_schema_rejects_blank_resource_name_prefix() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_create.apply(  # type: ignore[union-attr]
            {
                "resource_name_prefix": "   ",
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-existing-1"}},
                        "app_ids": ["app-existing-1"],
                    }
                ],
                "connections": {"existing_app_ids": ["app-existing-1"]},
            }
        )
    assert "String should have at least 1 character" in str(exc.value.error)


def test_create_schema_rejects_too_long_resource_name_prefix() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_create.apply(  # type: ignore[union-attr]
            {
                "resource_name_prefix": "a" * (WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH - len("lf_") + 1),
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-existing-1"}},
                        "app_ids": ["app-existing-1"],
                    }
                ],
                "connections": {"existing_app_ids": ["app-existing-1"]},
            }
        )
    assert "cannot exceed" in str(exc.value.error)


def test_update_schema_accepts_raw_tool_pool_and_shared_connection_refs() -> None:
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_update is not None

    payload = {
        "resource_name_prefix": "lf_pref_",
        "tools": {
            "raw_payloads": [_raw_tool("tool-new-1", 1)],
        },
        "connections": {
            "existing_app_ids": ["app-existing-1"],
            "raw_payloads": [_raw_connection("app-new-1")],
        },
        "operations": [
            {
                "op": "bind",
                "tool": {"name_of_raw": "tool-new-1"},
                "app_ids": ["app-new-1"],
            },
            {
                "op": "bind",
                "tool": {"tool_id_with_ref": {"source_ref": "fv-existing-1", "tool_id": "tool-existing-1"}},
                "app_ids": ["app-existing-1"],
            },
        ],
    }

    applied = slot.deployment_update.apply(payload)
    assert applied["operations"][0]["tool"]["name_of_raw"] == "tool-new-1"
    assert applied["operations"][1]["tool"]["tool_id_with_ref"]["tool_id"] == "tool-existing-1"


def test_update_schema_rejects_too_long_resource_name_prefix() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "resource_name_prefix": "a" * (WXO_RESOURCE_NAME_PREFIX_MAX_LENGTH - len("lf_") + 1),
                "connections": {"existing_app_ids": ["app-existing-1"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-existing-1"}},
                        "app_ids": ["app-existing-1"],
                    }
                ],
            }
        )
    assert "cannot exceed" in str(exc.value.error)


def test_update_schema_rejects_prefixed_app_id_collisions() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "resource_name_prefix": "lf_",
                "connections": {
                    "existing_app_ids": ["dup"],
                    "raw_payloads": [_raw_connection("dup")],
                },
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-existing-1"}},
                        "app_ids": ["dup"],
                    }
                ],
            }
        )
    assert "collides with raw app ids" in str(exc.value.error)


def test_update_schema_rejects_missing_raw_tool_reference() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "connections": {
                    "existing_app_ids": ["app-existing-1"],
                },
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"name_of_raw": "missing-tool"},
                        "app_ids": ["app-existing-1"],
                    }
                ],
            }
        )
    assert "name_of_raw not found" in str(exc.value.error)


def test_update_schema_rejects_tool_reference_with_both_selectors() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "tools": {"raw_payloads": [_raw_tool("tool-new-1", 1)]},
                "connections": {"existing_app_ids": ["app-existing-1"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {
                            "tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-existing-1"},
                            "name_of_raw": "tool-new-1",
                        },
                        "app_ids": ["app-existing-1"],
                    }
                ],
            }
        )
    assert "Exactly one of 'tool.tool_id_with_ref' or 'tool.name_of_raw' must be provided" in str(exc.value.error)


def test_update_schema_rejects_conflicting_source_ref_for_same_tool_id() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "connections": {"existing_app_ids": ["app-1", "app-2"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": {"source_ref": "fv-aaa", "tool_id": "tool-1"}},
                        "app_ids": ["app-1"],
                    },
                    {
                        "op": "unbind",
                        "tool": {"source_ref": "fv-bbb", "tool_id": "tool-1"},
                        "app_ids": ["app-2"],
                    },
                ],
            }
        )
    assert "Conflicting source_ref for tool_id='tool-1'" in str(exc.value.error)


def test_update_schema_rejects_bind_app_id_not_in_declared_pools() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "tools": {
                    "raw_payloads": [_raw_tool("tool-new-1", 2)],
                },
                "connections": {
                    "existing_app_ids": ["app-existing-1"],
                },
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"name_of_raw": "tool-new-1"},
                        "app_ids": ["app-not-declared"],
                    }
                ],
            }
        )
    assert "operation app_ids must be declared in" in str(exc.value.error)


def test_update_schema_rejects_unused_existing_app_ids() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "connections": {"existing_app_ids": ["app-existing-1", "app-unused"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-existing-1"}},
                        "app_ids": ["app-existing-1"],
                    }
                ],
            }
        )
    assert "existing_app_ids contains ids not referenced by operations" in str(exc.value.error)


def test_update_schema_rejects_unused_raw_connection_app_ids() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "resource_name_prefix": "lf_pref_",
                "tools": {"raw_payloads": [_raw_tool("tool-new-1", 3)]},
                "connections": {"raw_payloads": [_raw_connection("app-new-1"), _raw_connection("app-unused")]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"name_of_raw": "tool-new-1"},
                        "app_ids": ["app-new-1"],
                    }
                ],
            }
        )
    assert "raw_payloads contains app_id values not referenced by operations" in str(exc.value.error)


def test_update_schema_dedupes_bind_app_ids() -> None:
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_update is not None

    payload = {
        "connections": {"existing_app_ids": ["app-existing-1", "app-existing-2"]},
        "operations": [
            {
                "op": "bind",
                "tool": {"tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-existing-1"}},
                "app_ids": ["app-existing-1", "app-existing-1", "app-existing-2"],
            }
        ],
    }

    applied = slot.deployment_update.apply(payload)
    assert applied["operations"][0]["app_ids"] == ["app-existing-1", "app-existing-2"]


def test_update_schema_requires_unbind_app_ids() -> None:
    with pytest.raises(AdapterPayloadValidationError):
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "operations": [
                    {
                        "op": "unbind",
                        "tool": {"source_ref": "fv-1", "tool_id": "tool-1"},
                    }
                ]
            }
        )


def test_update_schema_rejects_unbind_raw_app_ids() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "connections": {"raw_payloads": [_raw_connection("app-new-1")]},
                "operations": [
                    {
                        "op": "unbind",
                        "tool": {"source_ref": "fv-1", "tool_id": "tool-1"},
                        "app_ids": ["app-new-1"],
                    }
                ],
            }
        )
    assert "must reference connections.existing_app_ids only" in str(exc.value.error)


# ---------------------------------------------------------------------------
# validate_has_work / put_tools
# ---------------------------------------------------------------------------


def test_update_schema_rejects_empty_operations_without_put_tools() -> None:
    """Neither operations nor put_tools → must reject."""
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {}
        )
    assert "At least one of 'operations' or 'put_tools' must be provided" in str(exc.value.error)


def test_update_schema_accepts_put_tools_alone() -> None:
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_update is not None

    applied = slot.deployment_update.apply({"put_tools": ["tool-id-1", "tool-id-2"]})
    assert applied["put_tools"] == ["tool-id-1", "tool-id-2"]
    assert applied["operations"] == []


def test_update_schema_put_tools_deduplicates() -> None:
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_update is not None

    applied = slot.deployment_update.apply({"put_tools": ["t1", "t2", "t1", "t3", "t2"]})
    assert applied["put_tools"] == ["t1", "t2", "t3"]


def test_update_schema_rejects_put_tools_with_operations() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "put_tools": ["tool-id-1"],
                "connections": {"existing_app_ids": ["app-1"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-1"}},
                        "app_ids": ["app-1"],
                    }
                ],
            }
        )
    assert "standalone full replacement and cannot be combined" in str(exc.value.error)


def test_update_schema_rejects_put_tools_with_resource_name_prefix() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "put_tools": ["tool-id-1"],
                "resource_name_prefix": "lf_",
            }
        )
    assert "standalone full replacement and cannot be combined" in str(exc.value.error)


def test_update_schema_rejects_put_tools_with_raw_tool_payloads() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "put_tools": ["tool-id-1"],
                "tools": {"raw_payloads": [_raw_tool("tool-new", 1)]},
            }
        )
    assert "standalone full replacement and cannot be combined" in str(exc.value.error)


def test_update_schema_rejects_put_tools_with_connection_existing_app_ids() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "put_tools": ["tool-id-1"],
                "connections": {"existing_app_ids": ["app-1"]},
            }
        )
    assert "standalone full replacement and cannot be combined" in str(exc.value.error)


def test_update_schema_accepts_operations_without_put_tools() -> None:
    """Existing happy-path: operations alone is valid (pre-existing behavior)."""
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_update is not None

    applied = slot.deployment_update.apply(
        {
            "connections": {"existing_app_ids": ["app-1"]},
            "operations": [
                {
                    "op": "bind",
                    "tool": {"tool_id_with_ref": {"source_ref": "fv-1", "tool_id": "tool-1"}},
                    "app_ids": ["app-1"],
                }
            ],
        }
    )
    assert len(applied["operations"]) == 1
    assert applied["put_tools"] is None
