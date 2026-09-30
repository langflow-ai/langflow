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
    SubstitutableComponentTypes,
    check_flow_and_raise,
    collect_component_code_lookups,
    collect_component_hash_lookups,
    substitute_outdated_component_code_in_place,
    validate_flow_for_current_settings,
)

CURRENT_CHAT_INPUT = "# ChatInput v2 (this server)"
STORED_CHAT_INPUT = "# ChatInput v1 (saved before the upgrade)"
# A components_path component the operator installed under a name a built-in already uses.
OVERRIDE_CHAT_INPUT = "# ChatInput (operator's components_path copy)"


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


def _ambiguous_lookups() -> tuple[dict[str, set[str]], dict[str, str]]:
    """A registry where two components claim the type ``ChatInput``.

    ``collect_component_hash_lookups`` keeps both hashes; ``collect_component_code_lookups`` is
    first-wins, so its single code value may belong to either component.
    """
    return (
        {"ChatInput": {_hash(CURRENT_CHAT_INPUT), _hash(OVERRIDE_CHAT_INPUT)}},
        {"ChatInput": CURRENT_CHAT_INPUT},
    )


def _mismatched_lookups() -> tuple[dict[str, set[str]], dict[str, str]]:
    """Build the exact first-alias mismatch reported on the PR review thread."""
    all_types = {
        "first": {
            "ChatInput": {
                # This first alias contributes source but no hash metadata.
                "template": {"code": {"value": OVERRIDE_CHAT_INPUT}},
            }
        },
        "second": {
            "ChatInput": {
                "metadata": {"code_hash": _hash(CURRENT_CHAT_INPUT)},
                "template": {"code": {"value": CURRENT_CHAT_INPUT}},
            }
        },
    }
    type_to_hash, _ = collect_component_hash_lookups(all_types)
    return type_to_hash, collect_component_code_lookups(all_types)


def _subst_args(lookups=_lookups) -> tuple[dict[str, str], SubstitutableComponentTypes]:
    """Build ``_substitute_outdated_node_code``'s ``(type_to_code, substitutable_types)`` pair."""
    type_to_hash, type_to_code = lookups()
    return type_to_code, SubstitutableComponentTypes(type_to_hash, type_to_code)


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

    swapped = fv._substitute_outdated_node_code(nodes, *_subst_args())

    assert swapped == ["Chat Input (a)"]
    assert _code_of(nodes[0]) == CURRENT_CHAT_INPUT


def test_up_to_date_builtin_is_left_alone():
    nodes = [_node("a", "ChatInput", CURRENT_CHAT_INPUT)]

    assert fv._substitute_outdated_node_code(nodes, *_subst_args()) == []
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

    assert fv._substitute_outdated_node_code(nodes, *_subst_args()) == []
    assert _code_of(nodes[0]) == "import os; os.system('id')"


def test_relabelled_custom_code_is_replaced_not_executed():
    """Arbitrary code wearing a known type gets this server's component, same as the public path."""
    nodes = [_node("a", "ChatInput", "import os; os.system('pwned')")]

    assert fv._substitute_outdated_node_code(nodes, *_subst_args()) == ["ChatInput (a)"]
    assert _code_of(nodes[0]) == CURRENT_CHAT_INPUT


def test_recurses_into_inlined_subflows():
    inner = _node("inner", "ChatInput", STORED_CHAT_INPUT, display_name="Inner")
    wrapper = _node("wrap", "GroupNode", None)
    wrapper["data"]["node"]["flow"] = {"data": {"nodes": [inner]}}

    swapped = fv._substitute_outdated_node_code([wrapper], *_subst_args())

    assert swapped == ["Inner (inner)"]
    assert _code_of(inner) == CURRENT_CHAT_INPUT


def test_codeless_and_malformed_nodes_are_skipped():
    nodes = ["not-a-node", {"data": "not-a-dict"}, {"data": {"node": "not-a-dict"}}, _node("n", "ChatInput", None)]

    assert fv._substitute_outdated_node_code(nodes, *_subst_args()) == []


# --- ambiguous types: two components claiming one name -----------------------------


def test_ambiguous_type_is_never_substituted():
    """Drift on a contested type must not be resolved into the *wrong* component.

    When a built-in and a ``components_path`` component share a name the hash lookup keeps both
    hashes while the code lookup keeps only whichever the registry yielded first. Stored code
    matching neither hash is then indistinguishable from "this node is the other component", so
    the node is left for ``check_flow_and_raise`` to block, as it was before this pass existed.
    """
    nodes = [_node("a", "ChatInput", STORED_CHAT_INPUT, display_name="Chat Input")]

    assert fv._substitute_outdated_node_code(nodes, *_subst_args(_ambiguous_lookups)) == []
    assert _code_of(nodes[0]) == STORED_CHAT_INPUT


@pytest.mark.parametrize("code", [CURRENT_CHAT_INPUT, OVERRIDE_CHAT_INPUT], ids=["builtin", "override"])
def test_ambiguous_type_still_builds_when_its_code_matches_either_component(code):
    """Only *drift* is refused on a contested type; both current versions still build."""
    type_to_hash, _ = _ambiguous_lookups()
    flow = {"nodes": [_node("a", "ChatInput", code)]}

    check_flow_and_raise(
        flow,
        allow_custom_components=False,
        type_to_current_hash=type_to_hash,
        substitutable_types=_subst_args(_ambiguous_lookups)[1],
    )


def test_check_flow_and_raise_still_blocks_drift_on_an_ambiguous_type():
    """The pre-check must agree with the substitution: not substituted means not exempted.

    Otherwise the node would clear validation carrying code this server cannot resolve, and
    ``resolve_trusted_code_for_build`` would fail it later with a far less actionable message.
    """
    type_to_hash, _ = _ambiguous_lookups()
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)]}

    with pytest.raises(CustomComponentValidationError, match="outdated components must be updated"):
        check_flow_and_raise(
            flow,
            allow_custom_components=False,
            type_to_current_hash=type_to_hash,
            substitutable_types=_subst_args(_ambiguous_lookups)[1],
        )


def test_in_place_substitution_skips_ambiguous_type(monkeypatch):
    _enable(monkeypatch, lookups=_ambiguous_lookups)
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    assert substitute_outdated_component_code_in_place(flow) == []
    assert _code_of(flow["nodes"][0]) == STORED_CHAT_INPUT


def test_mismatched_trusted_code_is_neither_substituted_nor_exempted():
    """A single hash is not enough when the type lookup points at different source."""
    type_to_hash, type_to_code = _mismatched_lookups()
    substitutable_types = SubstitutableComponentTypes(type_to_hash, type_to_code)
    nodes = [_node("a", "ChatInput", STORED_CHAT_INPUT, display_name="Chat Input")]

    assert "ChatInput" not in substitutable_types
    assert fv._substitute_outdated_node_code(nodes, type_to_code, substitutable_types) == []
    assert _code_of(nodes[0]) == STORED_CHAT_INPUT

    with pytest.raises(CustomComponentValidationError, match="outdated components must be updated"):
        check_flow_and_raise(
            {"nodes": nodes},
            allow_custom_components=False,
            type_to_current_hash=type_to_hash,
            substitutable_types=substitutable_types,
        )


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


def test_substitution_lookups_are_captured_under_one_cache_lock(monkeypatch):
    """A hot reload cannot pair the hash index from one registry with code from another."""
    from lfx.interface import components as component_module

    class TrackingLock:
        def __init__(self) -> None:
            self.active = False
            self.entries = 0

        def __enter__(self):
            assert not self.active
            self.active = True
            self.entries += 1

        def __exit__(self, *_args) -> None:
            self.active = False

    lock = TrackingLock()
    monkeypatch.setattr(component_module, "component_cache", SimpleNamespace(state_lock=lock))
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings())
    type_to_hash, type_to_code = _lookups()

    def get_hashes():
        assert lock.active
        return type_to_hash

    def get_code():
        assert lock.active
        return type_to_code

    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", get_hashes)
    monkeypatch.setattr(fv, "get_component_code_lookups_for_validation", get_code)

    lookups = fv.get_outdated_code_substitution_lookups()

    assert lookups is not None
    assert lock.entries == 1


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
    type_to_hash, _ = _lookups()
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)]}

    check_flow_and_raise(
        flow,
        allow_custom_components=False,
        type_to_current_hash=type_to_hash,
        substitutable_types=_subst_args()[1],
    )


def test_check_flow_and_raise_still_blocks_unknown_type_when_substituting():
    type_to_hash, _ = _lookups()
    flow = {"nodes": [_node("x", "TotallyCustom", "import os", display_name="Custom")]}

    with pytest.raises(CustomComponentValidationError, match="custom components are not allowed"):
        check_flow_and_raise(
            flow,
            allow_custom_components=False,
            type_to_current_hash=type_to_hash,
            substitutable_types=_subst_args()[1],
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


def test_validator_uses_hashes_from_the_same_snapshot_as_substitution(monkeypatch):
    """Validation must not pair an earlier hash index with a later substitution index."""
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings())
    monkeypatch.setattr(
        "lfx.services.deps.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=CatalogPolicySnapshot()),
    )
    type_to_hash, type_to_code = _lookups()
    lookups = type_to_code, SubstitutableComponentTypes(type_to_hash, type_to_code)
    monkeypatch.setattr(fv, "get_outdated_code_substitution_lookups", lambda: lookups)
    monkeypatch.setattr(
        fv,
        "get_component_hash_lookups_for_validation",
        lambda: pytest.fail("standalone hash lookup would create a mixed registry snapshot"),
    )

    validate_flow_for_current_settings({"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)]})


def test_from_payload_substitutes_before_validating(monkeypatch):
    """Graph.from_payload owns the payload it builds, so the real swap happens there — first."""
    from lfx.graph.graph.base import Graph

    calls: list[tuple[str, dict, dict]] = []
    monkeypatch.setattr(
        fv,
        "substitute_outdated_component_code_in_place",
        lambda payload, **kwargs: (calls.append(("substitute", payload, kwargs)), [])[1],
    )
    monkeypatch.setattr(
        fv,
        "validate_flow_for_current_settings",
        lambda payload, **kwargs: calls.append(("validate", payload, kwargs)),
    )

    payload = {"nodes": [], "edges": []}
    Graph.from_payload(payload)

    assert [name for name, *_ in calls] == ["substitute", "validate"]
    assert calls[0][1] is payload
    assert calls[0][2] == {"validate_public_execution": False}


def test_validator_still_refuses_drifted_flow_when_opted_out(monkeypatch):
    _enable(monkeypatch, substitute=False)
    monkeypatch.setattr(
        "lfx.services.deps.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=CatalogPolicySnapshot()),
    )
    flow = {"nodes": [_node("a", "ChatInput", STORED_CHAT_INPUT)], "edges": []}

    with pytest.raises(CustomComponentValidationError, match="outdated components must be updated"):
        validate_flow_for_current_settings(flow)
