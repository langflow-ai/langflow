"""Unit tests for LFX flow validation helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.utils.flow_validation import (
    CODE_EXECUTION_COMPONENT_TYPES,
    FLOW_REFERENCE_COMPONENT_TYPES,
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


# --- transitive flow execution (report H1-3754930, transitive case) ---------------


@pytest.mark.parametrize("component_type", sorted(FLOW_REFERENCE_COMPONENT_TYPES))
def test_public_flow_blocks_flow_invoking_components(component_type):
    """Flow-invoking components (Run Flow / Sub Flow / Flow as Tool) must be rejected.

    They load and execute another saved owner flow by id/name at runtime; that
    referenced flow is never re-validated, so a public wrapper flow could use one
    to reach a private flow containing a code-execution component.
    """
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(_flow_with_component(component_type))
    assert component_type in str(exc_info.value)
    assert "execute other flows" in str(exc_info.value)


def test_public_flow_blocks_wrapper_with_runflow_and_safe_nodes():
    """The real attack shape — a wrapper of otherwise-safe nodes plus a Run Flow — is blocked."""
    wrapper = {
        "nodes": [
            {"id": "ChatInput-1", "data": {"id": "ChatInput-1", "type": "ChatInput", "node": {"template": {}}}},
            {
                "id": "RunFlow-1",
                "data": {"id": "RunFlow-1", "type": "RunFlow", "node": {"display_name": "Run Flow", "template": {}}},
            },
            {"id": "ChatOutput-1", "data": {"id": "ChatOutput-1", "type": "ChatOutput", "node": {"template": {}}}},
        ],
        "edges": [],
    }
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(wrapper)
    assert "RunFlow-1" in str(exc_info.value)


def test_public_flow_blocks_nested_flow_invoking_component():
    """A flow-invoking component hidden inside an inlined sub-flow must still be caught."""
    nested = {
        "nodes": [
            {
                "id": "group-1",
                "data": {
                    "id": "group-1",
                    "type": "GroupNode",
                    "node": {"flow": {"data": _flow_with_component("SubFlow")}},
                },
            }
        ],
        "edges": [],
    }
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(nested)


def test_code_execution_and_flow_reference_sets_are_disjoint():
    """The two blocklists describe different failure modes and must not overlap."""
    assert CODE_EXECUTION_COMPONENT_TYPES.isdisjoint(FLOW_REFERENCE_COMPONENT_TYPES)


# --- aliasing bypass: match by code-hash, not just declared type ------------------


def _flow_with_typed_code(component_type: str, code: str) -> dict:
    """Build raw graph data for a single node carrying ``code`` under ``component_type``."""
    return {
        "nodes": [
            {
                "id": "evasive-1",
                "data": {
                    "id": "evasive-1",
                    "type": component_type,
                    "node": {"display_name": component_type, "template": {"code": {"value": code}}},
                },
            }
        ],
        "edges": [],
    }


def test_public_flow_blocks_flow_invoking_component_relabelled_via_code_hash(monkeypatch):
    """A flow-invoking node that relabels its ``type`` to dodge the type block is still caught.

    In the hardened ``allow_custom_components=false`` mode the build runs the node's
    stored ``code`` regardless of its declared ``type``, so the code-hash of a
    blocked component is the authoritative signal.
    """
    from lfx.utils import flow_validation as fv

    run_flow_code = "class RunFlowComponent(Component):\n    name = 'RunFlow'\n"
    code_hash = fv._compute_code_hash(run_flow_code)
    # Pretend the server's known RunFlow template hashes to this code.
    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: {"RunFlow": {code_hash}})

    # Declared type is innocuous and in NEITHER blocklist, but the code is RunFlow's.
    evasive = _flow_with_typed_code("Totally Innocent", run_flow_code)
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(evasive)
    assert "execute other flows" in str(exc_info.value)


def test_public_flow_blocks_code_execution_component_relabelled_via_code_hash(monkeypatch):
    """The same aliasing defense applies to code-execution components."""
    from lfx.utils import flow_validation as fv

    repl_code = "class PythonREPLComponent(Component):\n    pass\n"
    code_hash = fv._compute_code_hash(repl_code)
    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: {"PythonREPLComponent": {code_hash}})

    evasive = _flow_with_typed_code("Harmless Label", repl_code)
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(evasive)
    assert "code-execution" in str(exc_info.value)


def test_public_flow_code_hash_allows_unrelated_code(monkeypatch):
    """A node whose code does not match any blocked template hash must still build."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: {"RunFlow": {"deadbeefcafe"}})
    safe = _flow_with_typed_code("ChatInput", "class ChatInput(Component):\n    pass\n")
    validate_public_flow_no_code_execution(safe)  # must not raise


def test_public_flow_type_block_works_without_hash_lookups(monkeypatch):
    """When the hash lookup is unavailable, canonical type-name matching still blocks."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: None)
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(_flow_with_component("RunFlow"))
