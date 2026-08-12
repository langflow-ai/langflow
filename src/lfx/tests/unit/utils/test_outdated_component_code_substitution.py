"""Tests for outdated built-in code substitution on the normal build path (issue #14455).

With ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` the code stored in a node never runs:
``resolve_trusted_code_for_build`` swaps in this server's copy before executing. The hash gate
nevertheless refused any flow whose stored built-in code had drifted across an upgrade, so a
version bump that touched one built-in broke every saved flow using it — while the unauthenticated
public path already rebuilt the same flows with the server's code by default.

These tests pin the swap-by-type rule, the setting that turns it off, and the invariant that it
never widens what can execute.
"""

import hashlib
from types import SimpleNamespace

import pytest
from lfx.services.catalog_policy import CatalogPolicySnapshot
from lfx.utils import flow_validation as fv
from lfx.utils.flow_validation import (
    CustomComponentValidationError,
    check_flow_and_raise,
    substitute_outdated_component_code_in_place,
    validate_flow_for_current_settings,
)

CURRENT_CHAT_INPUT = "# ChatInput v2 (this server)"
STORED_CHAT_INPUT = "# ChatInput v1 (saved before the upgrade)"


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:12]


def _node(node_id: str, component_type, code: str | None, *, display_name: str | None = None) -> dict:
    template = {"code": {"value": code}} if code is not None else {}
    node_block: dict = {"template": template}
    if display_name is not None:
        node_block["display_name"] = display_name
    return {"id": node_id, "data": {"id": node_id, "type": component_type, "node": node_block}}


def _code_of(node: dict) -> str | None:
    return node["data"]["node"]["template"]["code"]["value"]


def _lookups() -> tuple[dict[str, set[str]], dict[str, str]]:
    return {"ChatInput": {_hash(CURRENT_CHAT_INPUT)}}, {"ChatInput": CURRENT_CHAT_INPUT}


def _settings(*, allow_custom=False, substitute=True) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=allow_custom,
            substitute_outdated_component_code=substitute,
        )
    )


def _enable(monkeypatch, *, allow_custom=False, substitute=True, lookups=_lookups) -> None:
    """Point the substitution at a synthetic single-component registry."""
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: _settings(allow_custom=allow_custom, substitute=substitute),
    )
    type_to_hash, type_to_code = lookups()
    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: type_to_hash)
    monkeypatch.setattr(fv, "get_component_code_lookups_for_validation", lambda: type_to_code)


# --- _substitute_outdated_node_code ------------------------------------------------


def test_drifted_builtin_is_rebuilt_with_server_code():
    nodes = [_node("a", "ChatInput", STORED_CHAT_INPUT, display_name="Chat Input")]

    swapped = fv._substitute_outdated_node_code(nodes, *_lookups())

    assert swapped == ["Chat Input (a)"]
    assert _code_of(nodes[0]) == CURRENT_CHAT_INPUT


def test_up_to_date_builtin_is_left_alone():
    nodes = [_node("a", "ChatInput", CURRENT_CHAT_INPUT)]

    assert fv._substitute_outdated_node_code(nodes, *_lookups()) == []
    assert _code_of(nodes[0]) == CURRENT_CHAT_INPUT


@pytest.mark.parametrize(
    "component_type",
    ["TotallyCustom", "", None, {"not": "a string"}],
    ids=["unknown", "empty", "missing", "malformed"],
)
def test_unrecognized_type_is_never_substituted(component_type):
    """The substitution must not create a path for arbitrary or relabelled code to run.

    Leaving these untouched is what keeps ``check_flow_and_raise`` blocking them.
    """
    nodes = [_node("x", component_type, "import os; os.system('id')", display_name="Sneaky")]

    assert fv._substitute_outdated_node_code(nodes, *_lookups()) == []
    assert _code_of(nodes[0]) == "import os; os.system('id')"


def test_relabelled_custom_code_is_replaced_not_executed():
    """Arbitrary code wearing a known type gets this server's component, same as the public path."""
    nodes = [_node("a", "ChatInput", "import os; os.system('pwned')")]

    assert fv._substitute_outdated_node_code(nodes, *_lookups()) == ["ChatInput (a)"]
    assert _code_of(nodes[0]) == CURRENT_CHAT_INPUT


def test_recurses_into_inlined_subflows():
    inner = _node("inner", "ChatInput", STORED_CHAT_INPUT, display_name="Inner")
    wrapper = _node("wrap", "GroupNode", None)
    wrapper["data"]["node"]["flow"] = {"data": {"nodes": [inner]}}

    swapped = fv._substitute_outdated_node_code([wrapper], *_lookups())

    assert swapped == ["Inner (inner)"]
    assert _code_of(inner) == CURRENT_CHAT_INPUT


def test_codeless_and_malformed_nodes_are_skipped():
    nodes = ["not-a-node", {"data": "not-a-dict"}, {"data": {"node": "not-a-dict"}}, _node("n", "ChatInput", None)]

    assert fv._substitute_outdated_node_code(nodes, *_lookups()) == []


# --- substitute_outdated_component_code_in_place (settings-aware) -------------------


def test_in_place_substitution_swaps_when_enabled(monkeypatch):
    _enable(monkeypatch)
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    assert substitute_outdated_component_code_in_place(flow) == ["ChatInput (a)"]
    assert _code_of(flow["nodes"][0]) == CURRENT_CHAT_INPUT


def test_no_substitution_when_custom_components_are_allowed(monkeypatch):
    """Permissive mode runs the node's own code, so nothing may be rewritten."""
    _enable(monkeypatch, allow_custom=True)
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    assert substitute_outdated_component_code_in_place(flow) == []
    assert _code_of(flow["nodes"][0]) == STORED_CHAT_INPUT


def test_no_substitution_when_operator_opts_out(monkeypatch):
    _enable(monkeypatch, substitute=False)
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    assert substitute_outdated_component_code_in_place(flow) == []
    assert _code_of(flow["nodes"][0]) == STORED_CHAT_INPUT


def test_no_substitution_without_settings_service(monkeypatch):
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    assert substitute_outdated_component_code_in_place(flow) == []


def test_no_substitution_while_registry_is_still_loading(monkeypatch):
    """Fail closed: with no trusted code available, the strict hash check must still apply."""
    _enable(monkeypatch, lookups=lambda: (None, None))
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    assert substitute_outdated_component_code_in_place(flow) == []
    assert _code_of(flow["nodes"][0]) == STORED_CHAT_INPUT


@pytest.mark.parametrize("empty", [None, {}, {"nodes": []}, {"nodes": "not-a-list"}])
def test_in_place_substitution_noop_on_empty(monkeypatch, empty):
    _enable(monkeypatch)
    assert substitute_outdated_component_code_in_place(empty) == []


def test_substitution_is_logged(monkeypatch):
    """Swapping is safe but not neutral (see #14236), so it must never happen silently."""
    _enable(monkeypatch)
    warnings: list[str] = []
    monkeypatch.setattr(fv, "logger", SimpleNamespace(warning=warnings.append))
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT, display_name="Chat Input")], "edges": []}

    substitute_outdated_component_code_in_place(flow)

    assert len(warnings) == 1
    assert "Chat Input (a)" in warnings[0]


def test_no_log_when_nothing_drifted(monkeypatch):
    _enable(monkeypatch)
    warnings: list[str] = []
    monkeypatch.setattr(fv, "logger", SimpleNamespace(warning=warnings.append))
    flow = {"nodes": [_node("a", "ChatInput", CURRENT_CHAT_INPUT)], "edges": []}

    substitute_outdated_component_code_in_place(flow)

    assert warnings == []


# --- check_flow_and_raise / validate_flow_for_current_settings ----------------------


def test_check_flow_and_raise_exempts_substitutable_drift():
    type_to_hash, type_to_code = _lookups()
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)]}

    check_flow_and_raise(
        flow,
        allow_custom_components=False,
        type_to_current_hash=type_to_hash,
        substitutable_types=type_to_code,
    )


def test_check_flow_and_raise_still_blocks_unknown_type_when_substituting():
    type_to_hash, type_to_code = _lookups()
    flow = {"nodes": [_node("x", "TotallyCustom", "import os", display_name="Custom")]}

    with pytest.raises(CustomComponentValidationError, match="custom components are not allowed"):
        check_flow_and_raise(
            flow,
            allow_custom_components=False,
            type_to_current_hash=type_to_hash,
            substitutable_types=type_to_code,
        )


def test_check_flow_and_raise_keeps_blocking_drift_without_substitution():
    type_to_hash, _ = _lookups()
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)]}

    with pytest.raises(CustomComponentValidationError, match="outdated components must be updated"):
        check_flow_and_raise(flow, allow_custom_components=False, type_to_current_hash=type_to_hash)


def test_validator_accepts_drifted_flow_and_leaves_it_untouched(monkeypatch):
    """The pre-check stops refusing the build, but must not rewrite the stored flow.

    The substitution itself happens in ``Graph.from_payload`` on the payload that is built.
    Leaving the caller's data alone is what keeps the editor flagging the node as outdated.
    """
    _enable(monkeypatch)
    monkeypatch.setattr(
        "lfx.services.deps.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=CatalogPolicySnapshot()),
    )
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    validate_flow_for_current_settings(flow)

    assert _code_of(flow["nodes"][0]) == STORED_CHAT_INPUT


def test_from_payload_substitutes_before_validating(monkeypatch):
    """Graph.from_payload owns the payload it builds, so the real swap happens there — first."""
    from lfx.graph.graph.base import Graph

    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        fv,
        "substitute_outdated_component_code_in_place",
        lambda payload: (calls.append(("substitute", payload)), [])[1],
    )
    monkeypatch.setattr(
        fv,
        "validate_flow_for_current_settings",
        lambda payload, **_kwargs: calls.append(("validate", payload)),
    )

    payload = {"nodes": [], "edges": []}
    Graph.from_payload(payload)

    assert [name for name, _ in calls] == ["substitute", "validate"]
    assert calls[0][1] is payload


def test_validator_still_refuses_drifted_flow_when_opted_out(monkeypatch):
    _enable(monkeypatch, substitute=False)
    monkeypatch.setattr(
        "lfx.services.deps.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=CatalogPolicySnapshot()),
    )
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    with pytest.raises(CustomComponentValidationError, match="outdated components must be updated"):
        validate_flow_for_current_settings(flow)
