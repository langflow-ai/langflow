"""Unit tests for LFX flow validation helpers."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.utils.flow_validation import (
    CODE_EXECUTION_COMPONENT_TYPES,
    FLOW_REFERENCE_COMPONENT_TYPES,
    CustomComponentValidationError,
    PublicFlowValidationError,
    collect_component_code_lookups,
    ensure_component_hash_lookups_loaded,
    prepare_public_flow_build,
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


# --- public-flow component sanitization (H1-3754930 follow-up) --------------------


def _server_components() -> dict:
    """Fake all_types_dict with one known component ('ChatInput' / 'Chat Input') and trusted code."""
    return {
        "inputs": {
            "ChatInput": {
                "display_name": "Chat Input",
                "template": {"code": {"value": "# trusted ChatInput code"}},
            }
        }
    }


def _public_settings(*, allow_custom=True, allow_public_custom=False) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=allow_custom,
            allow_public_custom_components=allow_public_custom,
        )
    )


def _node(node_id: str, component_type: str, code: str | None, *, display_name: str | None = None) -> dict:
    template = {"code": {"value": code}} if code is not None else {}
    node_block: dict = {"template": template}
    if display_name is not None:
        node_block["display_name"] = display_name
    return {"id": node_id, "data": {"id": node_id, "type": component_type, "node": node_block}}


def test_collect_component_code_lookups_maps_type_and_aliases():
    """Each component's canonical name and display-name alias map to its trusted code."""
    lookups = collect_component_code_lookups(_server_components())
    assert lookups["ChatInput"] == "# trusted ChatInput code"
    assert lookups["Chat Input"] == "# trusted ChatInput code"


def test_substitute_trusted_node_code_replaces_known_and_blocks_unknown():
    from lfx.utils import flow_validation as fv

    nodes = [
        _node("a", "ChatInput", "malicious()"),
        _node("b", "EvilCustom", "import os", display_name="Evil"),
    ]
    blocked = fv._substitute_trusted_node_code(nodes, {"ChatInput": "# trusted"})

    assert nodes[0]["data"]["node"]["template"]["code"]["value"] == "# trusted"  # known → replaced
    assert blocked == ["Evil (b)"]  # unknown → blocked
    assert nodes[1]["data"]["node"]["template"]["code"]["value"] == "import os"  # unknown not substituted


def test_substitute_trusted_node_code_blocks_non_string_type():
    """A malformed, non-string ``type`` (e.g. a dict) must be blocked, not raise TypeError."""
    from lfx.utils import flow_validation as fv

    # An unhashable ``type`` would raise on ``in type_to_code`` without the isinstance guard.
    node = _node("a", "ChatInput", "import os", display_name="Sneaky")
    node["data"]["type"] = {"not": "a string"}
    blocked = fv._substitute_trusted_node_code([node], {"ChatInput": "# trusted"})

    assert blocked == ["Sneaky (a)"]  # treated as unknown → blocked
    assert node["data"]["node"]["template"]["code"]["value"] == "import os"  # not substituted


def test_substitute_trusted_node_code_recurses_into_inlined_subflows():
    from lfx.utils import flow_validation as fv

    nodes = [
        {
            "id": "group",
            "data": {
                "id": "group",
                "type": "GroupNode",
                "node": {"flow": {"data": {"nodes": [_node("inner", "EvilCustom", "x", display_name="Evil")]}}},
            },
        }
    ]
    assert fv._substitute_trusted_node_code(nodes, {"ChatInput": "# trusted"}) == ["Evil (inner)"]


def test_substitute_trusted_node_code_leaves_codeless_nodes_untouched():
    from lfx.utils import flow_validation as fv

    # An unknown type with no code field carries no execution vector and must not be blocked.
    assert fv._substitute_trusted_node_code([_node("note", "NoteNode", None)], {"ChatInput": "# trusted"}) == []


def test_get_invalid_components_blocks_codebearing_node_with_empty_type():
    """A code-bearing node with an empty/missing type must be blocked, not skipped.

    Regression for GHSA-mfp9-86w4-493f: _get_invalid_components used to
    `continue` on a falsy ``type``, so a crafted node bypassed the
    allow_custom_components gate while its stored code still executed at build.
    """
    from lfx.utils import flow_validation as fv

    type_to_hash = {"ChatInput": {"deadbeef"}}

    # Code present, type empty -> can never match a trusted hash -> blocked.
    sneaky = _node("x", "", "import os; os.system('id')", display_name="Sneaky")
    blocked, outdated = fv._get_invalid_components([sneaky], type_to_hash)
    assert "Sneaky (x)" in blocked
    assert outdated == []

    # Control: an empty-type node with no code carries no execution vector.
    codeless = _node("n", "", None)
    blocked2, outdated2 = fv._get_invalid_components([codeless], type_to_hash)
    assert blocked2 == []
    assert outdated2 == []


@pytest.mark.asyncio
async def test_prepare_public_flow_build_substitutes_trusted_code(monkeypatch):
    """Default mode replaces stored built-in code with the server's trusted copy (no 'outdated' break)."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(fv, "_ensure_component_code_lookups", AsyncMock(return_value={"ChatInput": "# trusted"}))

    flow = {"nodes": [_node("a", "ChatInput", "stored old code")], "edges": []}
    sanitized = await fv.prepare_public_flow_build(flow)

    assert sanitized is not None
    assert sanitized["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "# trusted"
    # the caller's original flow data is not mutated
    assert flow["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "stored old code"


@pytest.mark.asyncio
async def test_prepare_public_flow_build_blocks_unknown_custom_component(monkeypatch):
    """A public flow with an unrecognized custom component is rejected."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(fv, "_ensure_component_code_lookups", AsyncMock(return_value={"ChatInput": "# trusted"}))

    flow = {"nodes": [_node("x", "MyCustom", "import os; os.system('x')", display_name="My Custom")], "edges": []}
    with pytest.raises(CustomComponentValidationError) as exc_info:
        await fv.prepare_public_flow_build(flow)
    assert "My Custom (x)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prepare_public_flow_build_neutralizes_relabelled_code(monkeypatch):
    """Arbitrary code relabelled as a known type is overwritten with the server's trusted code."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(
        fv, "_ensure_component_code_lookups", AsyncMock(return_value={"ChatInput": "# trusted ChatInput"})
    )

    flow = {"nodes": [_node("a", "ChatInput", "import os; os.system('pwned')")], "edges": []}
    sanitized = await fv.prepare_public_flow_build(flow)
    assert sanitized["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "# trusted ChatInput"


@pytest.mark.asyncio
async def test_prepare_public_flow_build_opt_in_honors_global(monkeypatch):
    """allow_public_custom_components=True returns None (DB-loaded build) and runs standard validation."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: _public_settings(allow_custom=True, allow_public_custom=True),
    )
    seen = {}
    monkeypatch.setattr(fv, "validate_flow_for_current_settings", lambda target: seen.setdefault("target", target))

    flow = {"nodes": [_node("x", "MyCustom", "import os")], "edges": []}
    assert await fv.prepare_public_flow_build(flow) is None
    assert seen.get("target") == flow


@pytest.mark.asyncio
async def test_prepare_public_flow_build_requires_settings_service(monkeypatch):
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
    with pytest.raises(RuntimeError, match="Settings service must be initialized"):
        await prepare_public_flow_build({"nodes": []})


@pytest.mark.asyncio
async def test_prepare_public_flow_build_fails_closed_without_templates(monkeypatch):
    """If the component templates can't be loaded, unverified code must not pass."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(fv, "_ensure_component_code_lookups", AsyncMock(return_value={}))

    flow = {"nodes": [_node("a", "ChatInput", "x")], "edges": []}
    with pytest.raises(CustomComponentValidationError):
        await fv.prepare_public_flow_build(flow)


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", [None, {}, {"nodes": []}, {"nodes": "not-a-list"}])
async def test_prepare_public_flow_build_noop_on_empty(monkeypatch, empty):
    """Missing/empty/malformed node lists fall back to the default build (return None), not an error."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(fv, "_ensure_component_code_lookups", AsyncMock(return_value={"ChatInput": "# t"}))
    assert await fv.prepare_public_flow_build(empty) is None


# --- validate_public_flow_no_code_execution (report H1-3754930) -------------------


REPORTED_CODE_EXECUTION_AGENT_TYPES = (
    "CSVAgent",
    "CodeActAgentSmolagents",
    "Cuga",
    "OpenDsStarAgent",
)


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


@pytest.mark.parametrize("component_type", REPORTED_CODE_EXECUTION_AGENT_TYPES)
def test_public_flow_blocks_reported_code_execution_agents(component_type):
    """Regression for H1-3813558: shipped code agents must not build anonymously."""
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(_flow_with_component(component_type))
    assert component_type in str(exc_info.value)


def test_public_flow_blocks_structured_data_analysis_starter_template():
    """The bundled data-analysis starter contains OpenDsStarAgent and must be rejected publicly."""
    repo_root = Path(__file__).resolve().parents[5]
    starter_path = (
        repo_root / "src/backend/base/langflow/initial_setup/starter_projects/Structured Data Analysis Agent.json"
    )
    starter_flow = json.loads(starter_path.read_text())

    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(starter_flow)
    assert "OpenDsStarAgent" in str(exc_info.value)


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
