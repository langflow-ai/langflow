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


def test_process_tweaks_does_not_mutate_the_caller_dict():
    """Injecting ``stream`` must not write into the dict the caller owns.

    A caller that reuses one tweaks dict across two runs would otherwise send
    ``stream`` on the second run without knowing it. The exemption only covers
    the injected key, so a strict policy would refuse ``stream`` and 422 a
    request naming a key the caller never supplied.
    """
    graph = _graph(
        [
            _node(
                {
                    "stream": {"value": False, "type": "bool"},
                    "a": {"value": "old", "type": "str", "api_editable": True},
                },
                node_id="n1",
            )
        ]
    )
    caller_tweaks = {"n1": {"a": "new"}}

    with patch("lfx.processing.process._resolve_tweak_policy", return_value="declared"):
        process_tweaks(graph, caller_tweaks)
        assert caller_tweaks == {"n1": {"a": "new"}}, "process_tweaks wrote into the caller's dict"
        # The reused dict must still run clean.
        process_tweaks(_graph(graph["data"]["nodes"]), caller_tweaks)


def test_process_tweaks_permissive_leaves_a_normal_flow_working():
    graph = _graph([_node({"a": {"value": "old", "type": "str"}}, node_id="n1")])
    with patch("lfx.processing.process._resolve_tweak_policy", return_value="permissive"):
        result = process_tweaks(graph, {"n1": {"a": "new"}})
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["a"]["value"] == "new"


# --- runtime-generated tweaks are not caller overrides ---------------------
# ``tweaks`` is also the internal mechanism for passing values into a sub-flow.
# The Run Flow component pushes its own declared inputs through the graph path,
# and the flow runner turns resolved load_from_db values into tweaks. Judging
# those against the deployment policy would make ``off`` disable flow-as-tool
# orchestration rather than close an API surface, which is not what an operator
# flipping a tweaks policy is asking for.


def test_off_does_not_refuse_runtime_generated_tweaks():
    """``off`` closes the API surface, it does not disable the runtime."""
    node = _node({"a": {"value": "old", "type": "str"}}, node_id="n1")
    graph = _graph([node])
    with patch("lfx.processing.process._resolve_tweak_policy", return_value="off"):
        process_tweaks(graph, {"n1": {"a": "from-the-runtime"}}, caller_supplied=False)
    assert graph["data"]["nodes"][0]["data"]["node"]["template"]["a"]["value"] == "from-the-runtime"


def test_declared_does_not_refuse_runtime_generated_tweaks():
    """A sub-flow allowlist constrains callers, not the component feeding it."""
    node = _node(
        {
            "declared": {"value": "old", "type": "str", "api_editable": True},
            "undeclared": {"value": "old", "type": "str"},
        },
        node_id="n1",
    )
    graph = _graph([node])
    with patch("lfx.processing.process._resolve_tweak_policy", return_value="declared"):
        process_tweaks(graph, {"n1": {"undeclared": "from-the-runtime"}}, caller_supplied=False)
    assert graph["data"]["nodes"][0]["data"]["node"]["template"]["undeclared"]["value"] == "from-the-runtime"


def test_runtime_generated_tweaks_still_hit_the_floor():
    """The exemption covers the policy layer only. The floor never yields."""
    graph = _graph(
        [_node({"database_url": {"value": "stored", "type": "str"}}, node_type="SQLComponent", node_id="n1")]
    )
    with (
        patch("lfx.processing.process._resolve_tweak_policy", return_value="permissive"),
        pytest.raises(TweakRefusedError) as exc,
    ):
        process_tweaks(graph, {"n1": {"database_url": "postgresql://attacker/db"}}, caller_supplied=False)
    assert exc.value.refused == ["database_url"]


def test_off_still_refuses_a_caller_supplied_tweak():
    """The exemption must not leak into the default caller path."""
    graph = _graph([_node({"a": {"value": "old", "type": "str"}}, node_id="n1")])
    with (
        patch("lfx.processing.process._resolve_tweak_policy", return_value="off"),
        pytest.raises(TweakRefusedError),
    ):
        process_tweaks(graph, {"n1": {"a": "from-a-caller"}})


def test_graph_path_exempts_runtime_generated_tweaks():
    """The Run Flow component reaches a sub-flow through this path."""
    from unittest.mock import MagicMock

    from lfx.graph.vertex.base import Vertex
    from lfx.processing.process import process_tweaks_on_graph

    vertex = MagicMock(spec=Vertex)
    vertex.id = "v1"
    vertex.data = {"node": {"template": {"a": {"value": "old", "type": "str"}}}}
    vertex.params = {}
    vertex.load_from_db_fields = []

    class _G:
        vertices = [vertex]

    with patch("lfx.processing.process._resolve_tweak_policy", return_value="off"):
        process_tweaks_on_graph(_G(), {"v1": {"a": "from-the-runtime"}}, caller_supplied=False)

    vertex.update_raw_params.assert_called_once_with({"a": "from-the-runtime"}, overwrite=True)


# --- the graph-level path (streaming and background run modes) -------------
# These modes build the graph first, so they land in process_tweaks_on_graph
# rather than process_tweaks. Before the policy existed this path filtered only
# the literal key "code", so it accepted tweaks the sync mode refused.


class _FakeVertex:
    """Minimal stand-in for a built Vertex.

    A real Graph is not needed to prove which tweaks the graph-level path
    refuses, and constructing one drags in component loading.
    """

    def __init__(self, vertex_id: str, template: dict, node_type: str | None = None) -> None:
        self.id = vertex_id
        self.data = {"node": {"template": template}}
        if node_type is not None:
            self.data["type"] = node_type
        self.params: dict = {}
        self.load_from_db_fields: list[str] = []
        self.raw_params: dict = {}

    def update_raw_params(self, params: dict, *, overwrite: bool = False) -> None:
        if overwrite:
            self.raw_params.update(params)


def test_graph_path_refuses_a_sandbox_field_the_old_filter_allowed():
    """`global_imports` is sandbox-widening and was previously applied here.

    The old code removed only the key "code", so every other entry in
    CODE_EXECUTION_FIELD_NAMES reached the built component.
    """
    from lfx.processing.process import apply_tweaks_on_vertex

    vertex = _FakeVertex(
        "v1",
        {"global_imports": {"value": "math", "type": "str"}},
        node_type="PythonREPLComponent",
    )
    refused = apply_tweaks_on_vertex(vertex, {"global_imports": "os,subprocess,socket"}, policy="permissive")
    assert refused == ["global_imports"]
    assert vertex.raw_params == {}


def test_graph_path_honors_the_policy():
    from lfx.processing.process import apply_tweaks_on_vertex

    vertex = _FakeVertex("v1", {"a": {"value": "old", "type": "str"}})
    refused = apply_tweaks_on_vertex(vertex, {"a": "new"}, policy="off")
    assert refused == ["a"]
    assert vertex.raw_params == {}


def test_graph_path_applies_and_persists_an_allowed_tweak():
    """The accepted value must reach raw_params, not only vertex.params.

    Setting params alone does not reach the built component at runtime, which is
    the bug the two former private copies of this function worked around.
    """
    from lfx.processing.process import apply_tweaks_on_vertex

    vertex = _FakeVertex("v1", {"a": {"value": "old", "type": "str"}})
    vertex.params = {"a": "old"}
    refused = apply_tweaks_on_vertex(vertex, {"a": "new"}, policy="permissive")
    assert refused == []
    assert vertex.raw_params == {"a": "new"}
    assert vertex.params["a"] == "new"


# --- atomicity ------------------------------------------------------------
# A refusal must leave the payload untouched. Applying as we go and raising at
# the end left the accepted half written, and the graph the run paths hand us is
# cached and reused, so that half survived into later runs sending no tweaks.


def test_a_refusal_applies_nothing_on_the_graph_path():
    from unittest.mock import MagicMock

    from lfx.graph.vertex.base import Vertex
    from lfx.processing.process import process_tweaks_on_graph

    def real_shaped(vid, template, node_type=None):
        # spec=Vertex so isinstance passes; process_tweaks_on_graph filters on it.
        v = MagicMock(spec=Vertex)
        v.id = vid
        v.data = {"node": {"template": template}}
        if node_type:
            v.data["type"] = node_type
        v.params = {}
        v.load_from_db_fields = []
        return v

    ok = real_shaped("a", {"text": {"value": "original", "type": "str"}})
    protected = real_shaped("b", {"database_url": {"value": "stored", "type": "str"}}, "SQLComponent")

    class _G:
        vertices = [ok, protected]

    with pytest.raises(TweakRefusedError) as exc:
        process_tweaks_on_graph(_G(), {"a": {"text": "attacker"}, "b": {"database_url": "evil"}})

    assert exc.value.refused == ["database_url"]
    # The accepted sibling must NOT have been written.
    ok.update_raw_params.assert_not_called()
    assert ok.params == {}


def test_a_refusal_applies_nothing_on_the_dict_path():
    graph = _graph(
        [
            _node({"a": {"value": "original", "type": "str"}}, node_id="n1"),
            _node({"database_url": {"value": "stored", "type": "str"}}, node_type="SQLComponent", node_id="n2"),
        ]
    )
    with pytest.raises(TweakRefusedError):
        process_tweaks(graph, {"n1": {"a": "attacker"}, "n2": {"database_url": "evil"}})

    nodes = graph["data"]["nodes"]
    assert nodes[0]["data"]["node"]["template"]["a"]["value"] == "original"
    assert nodes[1]["data"]["node"]["template"]["database_url"]["value"] == "stored"
