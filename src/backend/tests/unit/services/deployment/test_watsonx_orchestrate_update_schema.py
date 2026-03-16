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

from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import WatsonxDeploymentUpdatePayload
from langflow.services.adapters.deployment.watsonx_orchestrate.service import WatsonxOrchestrateDeploymentService
from lfx.services.adapters.payload import AdapterPayloadValidationError


def _raw_tool(name: str, suffix: int) -> dict:
    return {
        "id": str(UUID(int=suffix)),
        "name": name,
        "description": "desc",
        "data": {"nodes": [], "edges": []},
        "tags": [],
        "provider_data": {"project_id": "project-1"},
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
    assert slot.deployment_update is not None
    assert slot.deployment_update.adapter_model is WatsonxDeploymentUpdatePayload


def test_update_schema_accepts_raw_tool_pool_and_shared_connection_refs() -> None:
    slot = WatsonxOrchestrateDeploymentService.payload_schemas
    assert slot is not None
    assert slot.deployment_update is not None

    payload = {
        "resource_name_prefix": "lf_pref_",
        "tools": {
            "existing_ids": ["tool-existing-1"],
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
                "tool": {"reference_id": "tool-existing-1"},
                "app_ids": ["app-existing-1"],
            },
        ],
    }

    applied = slot.deployment_update.apply(payload)
    assert applied["operations"][0]["tool"]["name_of_raw"] == "tool-new-1"
    assert applied["operations"][1]["tool"]["reference_id"] == "tool-existing-1"


def test_update_schema_rejects_prefixed_app_id_collisions() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "resource_name_prefix": "lf_",
                "tools": {"existing_ids": ["tool-existing-1"]},
                "connections": {
                    "existing_app_ids": ["dup"],
                    "raw_payloads": [_raw_connection("dup")],
                },
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": "tool-existing-1"},
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


def test_update_schema_rejects_reference_id_when_existing_ids_not_declared() -> None:
    with pytest.raises(AdapterPayloadValidationError) as exc:
        WatsonxOrchestrateDeploymentService.payload_schemas.deployment_update.apply(  # type: ignore[union-attr]
            {
                "connections": {"existing_app_ids": ["app-existing-1"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": "tool-existing-1"},
                        "app_ids": ["app-existing-1"],
                    }
                ],
            }
        )
    assert "reference_id not found in tools.existing_ids" in str(exc.value.error)


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
                "tools": {"existing_ids": ["tool-existing-1"]},
                "connections": {"existing_app_ids": ["app-existing-1", "app-unused"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": "tool-existing-1"},
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
        "tools": {"existing_ids": ["tool-existing-1"]},
        "connections": {"existing_app_ids": ["app-existing-1", "app-existing-2"]},
        "operations": [
            {
                "op": "bind",
                "tool": {"reference_id": "tool-existing-1"},
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
                        "tool_id": "tool-1",
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
                        "tool_id": "tool-1",
                        "app_ids": ["app-new-1"],
                    }
                ],
            }
        )
    assert "must reference connections.existing_app_ids only" in str(exc.value.error)
