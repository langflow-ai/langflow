"""Tests for the deployment tweak policy.

The policy layer sits above the protected-field floor in
``lfx.utils.flow_validation``. The floor refuses in every policy. The policy
only decides whether a field the floor allows is still refused.

These tests cover the three modes, the derived per-flow opt-in, and the
``stream`` exemption. The exemption has its own test because ``process_tweaks``
injects ``stream`` on every call: without the exemption a strict policy would
refuse every request, including one that sends no tweaks at all.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from lfx.exceptions.tweaks import TweakRefusedError
from lfx.processing.process import apply_tweaks, process_tweaks
from lfx.utils.flow_validation import flow_declares_api_editable


def _node(template: dict, *, node_type: str | None = None, node_id: str = "n") -> dict:
    data: dict = {"node": {"template": template}}
    if node_type is not None:
        data["type"] = node_type
    return {"id": node_id, "data": data}


def _graph(nodes: list[dict]) -> dict:
    return {"data": {"nodes": nodes, "edges": []}}


# --- the derived per-flow opt-in ------------------------------------------


def test_flow_with_no_toggles_declares_nothing():
    nodes = [_node({"a": {"value": "x", "type": "str"}})]
    assert flow_declares_api_editable(nodes) is False


def test_flow_with_one_toggle_declares_an_allowlist():
    nodes = [
        _node({"a": {"value": "x", "type": "str"}}, node_id="n1"),
        _node({"b": {"value": "y", "type": "str", "api_editable": True}}, node_id="n2"),
    ]
    assert flow_declares_api_editable(nodes) is True


def test_declaring_is_explicit_not_truthy():
    """A falsy or absent flag is not a declaration."""
    nodes = [_node({"a": {"value": "x", "type": "str", "api_editable": False}})]
    assert flow_declares_api_editable(nodes) is False


# --- permissive -----------------------------------------------------------


def test_permissive_applies_an_ordinary_field():
    node = _node({"a": {"value": "old", "type": "str"}})
    refused = apply_tweaks(node, {"a": "new"}, policy="permissive")
    assert refused == []
    assert node["data"]["node"]["template"]["a"]["value"] == "new"


def test_permissive_still_refuses_a_protected_field():
    """The floor refuses in every mode, and the refusal is now reported."""
    node = _node({"database_url": {"value": "stored", "type": "str"}}, node_type="SQLComponent")
    refused = apply_tweaks(node, {"database_url": "postgresql://attacker/db"}, policy="permissive")
    assert refused == ["database_url"]
    assert node["data"]["node"]["template"]["database_url"]["value"] == "stored"


# --- declared -------------------------------------------------------------


def test_declared_leaves_an_unprepared_flow_alone():
    """No toggles anywhere means no allowlist, so nothing is refused.

    This is what stops a deployment-wide switch from breaking every flow whose
    author never set a toggle.
    """
    node = _node({"a": {"value": "old", "type": "str"}})
    refused = apply_tweaks(node, {"a": "new"}, policy="declared", flow_declares_allowlist=False)
    assert refused == []
    assert node["data"]["node"]["template"]["a"]["value"] == "new"


def test_declared_applies_a_declared_field():
    node = _node({"a": {"value": "old", "type": "str", "api_editable": True}})
    refused = apply_tweaks(node, {"a": "new"}, policy="declared", flow_declares_allowlist=True)
    assert refused == []
    assert node["data"]["node"]["template"]["a"]["value"] == "new"


def test_declared_refuses_an_undeclared_field_on_a_declaring_flow():
    node = _node(
        {
            "declared": {"value": "old", "type": "str", "api_editable": True},
            "undeclared": {"value": "keep", "type": "str"},
        }
    )
    refused = apply_tweaks(
        node,
        {"declared": "new", "undeclared": "attacker"},
        policy="declared",
        flow_declares_allowlist=True,
    )
    assert refused == ["undeclared"]
    assert node["data"]["node"]["template"]["declared"]["value"] == "new"
    assert node["data"]["node"]["template"]["undeclared"]["value"] == "keep"


def test_declared_cannot_expose_a_protected_field():
    """An author cannot toggle their way past the floor."""
    node = _node(
        {"database_url": {"value": "stored", "type": "str", "api_editable": True}},
        node_type="SQLComponent",
    )
    refused = apply_tweaks(
        node,
        {"database_url": "postgresql://attacker/db"},
        policy="declared",
        flow_declares_allowlist=True,
    )
    assert refused == ["database_url"]
    assert node["data"]["node"]["template"]["database_url"]["value"] == "stored"


# --- off ------------------------------------------------------------------


def test_off_refuses_even_a_declared_field():
    node = _node({"a": {"value": "old", "type": "str", "api_editable": True}})
    refused = apply_tweaks(node, {"a": "new"}, policy="off", flow_declares_allowlist=True)
    assert refused == ["a"]
    assert node["data"]["node"]["template"]["a"]["value"] == "old"


# --- process_tweaks: aggregation, raising, and the stream exemption --------


def test_process_tweaks_raises_naming_every_refused_key():
    graph = _graph(
        [
            _node({"a": {"value": "old", "type": "str"}}, node_id="n1"),
            _node({"b": {"value": "old", "type": "str"}}, node_id="n2"),
        ]
    )
    with (
        patch("lfx.processing.process._resolve_tweak_policy", return_value="off"),
        pytest.raises(TweakRefusedError) as exc,
    ):
        process_tweaks(graph, {"n1": {"a": "x"}, "n2": {"b": "y"}})
    assert exc.value.refused == ["a", "b"]


def test_process_tweaks_does_not_refuse_the_injected_stream_key():
    """``stream`` is injected by process_tweaks, not sent by the caller.

    Without the exemption every request under a strict policy would 422, including
    one that sends no tweaks at all.
    """
    graph = _graph([_node({"stream": {"value": False, "type": "bool"}})])
    with patch("lfx.processing.process._resolve_tweak_policy", return_value="off"):
        # No caller tweaks at all. Only the injected stream key is present.
        process_tweaks(graph, {})


def test_process_tweaks_refuses_a_caller_supplied_stream_key():
    """A caller who sends ``stream`` explicitly is not exempt."""
    graph = _graph([_node({"stream": {"value": False, "type": "bool"}})])
    with (
        patch("lfx.processing.process._resolve_tweak_policy", return_value="off"),
        pytest.raises(TweakRefusedError) as exc,
    ):
        process_tweaks(graph, {"stream": True})
    assert exc.value.refused == ["stream"]


def test_process_tweaks_permissive_leaves_a_normal_flow_working():
    graph = _graph([_node({"a": {"value": "old", "type": "str"}}, node_id="n1")])
    with patch("lfx.processing.process._resolve_tweak_policy", return_value="permissive"):
        result = process_tweaks(graph, {"n1": {"a": "new"}})
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["a"]["value"] == "new"
