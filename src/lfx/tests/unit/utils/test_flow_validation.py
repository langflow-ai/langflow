"""Unit tests for LFX flow validation helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.utils.flow_validation import (
    CODE_EXECUTION_COMPONENT_TYPES,
    CustomComponentValidationError,
    PublicFlowValidationError,
    ensure_component_hash_lookups_loaded,
    validate_flow_for_current_settings,
    validate_public_flow_no_code_execution,
)


def _blocked_raw_graph() -> dict:
    return {
        "nodes": [
            {
                "id": "node-1",
                "data": {
                    "id": "node-1",
                    "type": "TotallyCustom",
                    "node": {
                        "display_name": "Blocked Node",
                        "template": {
                            "code": {"value": "print('blocked')"},
                        },
                    },
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.asyncio
async def test_ensure_component_hash_lookups_loaded_requires_settings_service(monkeypatch):
    """Hash warmup should fail loudly when the settings service is unavailable."""
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)

    with pytest.raises(RuntimeError, match="Settings service must be initialized"):
        await ensure_component_hash_lookups_loaded()


@pytest.mark.asyncio
async def test_ensure_component_hash_lookups_loaded_surfaces_loader_failures(monkeypatch):
    """Loader failures should not be masked as a transient initialization state."""
    from lfx.interface.components import component_cache

    settings_service = SimpleNamespace(
        settings=SimpleNamespace(allow_custom_components=False),
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(component_cache, "type_to_current_hash", None)

    with (
        patch(
            "lfx.interface.components.get_and_cache_all_types_dict",
            new=AsyncMock(side_effect=RuntimeError("component import failed")),
        ),
        pytest.raises(RuntimeError, match="component import failed"),
    ):
        await ensure_component_hash_lookups_loaded()


def test_validate_flow_for_current_settings_requires_settings_service(monkeypatch):
    """Unified validation should also require the settings service."""
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
    graph = SimpleNamespace(raw_graph_data=_blocked_raw_graph())

    with pytest.raises(RuntimeError, match="Settings service must be initialized"):
        validate_flow_for_current_settings(graph)


# --- validate_public_flow_no_code_execution (report H1-3754930) -------------------


def _flow_with_component(component_type: str) -> dict:
    """Build minimal raw graph data containing a single node of ``component_type``."""
    node_id = f"{component_type}-1"
    return {
        "nodes": [
            {
                "id": node_id,
                "data": {
                    "id": node_id,
                    "type": component_type,
                    "node": {"display_name": component_type, "template": {}},
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.parametrize("component_type", sorted(CODE_EXECUTION_COMPONENT_TYPES))
def test_public_flow_blocks_code_execution_components(component_type):
    """Every code-execution component must be rejected on the unauthenticated public path."""
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(_flow_with_component(component_type))
    assert component_type in str(exc_info.value)


def test_public_flow_allows_safe_components():
    """A flow without code-execution components must build on the public path."""
    safe = {
        "nodes": [
            {"id": "ChatInput-1", "data": {"id": "ChatInput-1", "type": "ChatInput", "node": {"template": {}}}},
        ],
        "edges": [],
    }
    validate_public_flow_no_code_execution(safe)  # must not raise


def test_public_flow_blocks_nested_code_execution_component():
    """A code-execution component hidden inside a sub-flow must still be caught."""
    nested = {
        "nodes": [
            {
                "id": "group-1",
                "data": {
                    "id": "group-1",
                    "type": "GroupNode",
                    "node": {"flow": {"data": _flow_with_component("PythonREPLComponent")}},
                },
            }
        ],
        "edges": [],
    }
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(nested)


def test_public_flow_unwraps_data_envelope():
    """The {"data": {...}} envelope must be unwrapped before validation."""
    wrapped = {"data": _flow_with_component("PythonREPLTool")}
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(wrapped)


@pytest.mark.parametrize("empty", [None, {}, {"nodes": []}, {"nodes": "not-a-list"}])
def test_public_flow_noop_on_empty(empty):
    """Missing/empty/malformed node lists are a no-op, not an error."""
    validate_public_flow_no_code_execution(empty)  # must not raise


def test_public_flow_validation_error_is_custom_component_error():
    """Subclassing keeps the existing public-build handler (CustomComponentValidationError -> 400)."""
    assert issubclass(PublicFlowValidationError, CustomComponentValidationError)
