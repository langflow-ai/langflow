"""The xyflow-to-D2 converter (Epic D.13).

`xyflow_graph_to_d2` is the pure function that converts a legacy xyflow diagram
graph (stored in ``lothal_project.diagram_json``) into D2 sequence-diagram source
(written to ``lothal_project.diagram_d2``).  It is called by the D.13 Alembic
data migration for every pre-pivot project.

These tests cover:

- A representative graph (3 nodes, 4 edges, mixed sync/async) converts to D2 that
  is structurally correct and actually compiles with the real ``d2`` binary.
- The function accepts both a JSON string and an already-parsed dict.
- Missing optional fields (edge label, edge kind) are tolerated gracefully.
- A graph with no nodes raises ``ValueError`` (the migration must skip it).
- Dashed-arrow conditions: ``animated: true``, ``kind: "async"``, ``kind: "return"``
  all produce ``-->``;  a plain sync edge produces ``->``.
- Edges are emitted in ascending ``data.order`` order regardless of list order.
"""

import asyncio
import json
import shutil

import pytest
from langflow.lothal.xyflow_to_d2 import xyflow_graph_to_d2

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

# A representative xyflow graph: 3 nodes, 4 edges, mixed sync/async/return.
# Intentionally ordered so edges are *not* in order in the list, to exercise
# the sort-by-order logic.
SAMPLE_GRAPH: dict = {
    "nodes": [
        {"id": "user", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "User"}},
        {"id": "api", "type": "systemNode", "position": {"x": 200, "y": 0}, "data": {"label": "API Server"}},
        {"id": "db", "type": "systemNode", "position": {"x": 400, "y": 0}, "data": {"label": "Database"}},
    ],
    "edges": [
        # Deliberately listed out of order to verify sort-by-order.
        {
            "id": "e3",
            "source": "api",
            "target": "user",
            "animated": True,  # dashed: return-style arrow
            "data": {"order": 3, "label": "200 OK", "kind": "return"},
        },
        {
            "id": "e1",
            "source": "user",
            "target": "api",
            "animated": False,
            "data": {"order": 1, "label": "POST /submit"},
        },
        {
            "id": "e4",
            "source": "db",
            "target": "api",
            "animated": False,
            "data": {"order": 4, "label": "row inserted", "kind": "return"},
        },
        {
            "id": "e2",
            "source": "api",
            "target": "db",
            "animated": False,
            "data": {"order": 2, "label": "INSERT INTO items", "kind": "async"},
        },
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

d2_available = shutil.which("d2") is not None
requires_d2 = pytest.mark.skipif(not d2_available, reason="the `d2` binary is not installed")


def _compile_check(d2: str) -> bool:
    """Synchronous wrapper: compile `d2` and return True iff it compiles."""
    from langflow.lothal.d2_compile import compile_d2

    result = asyncio.run(compile_d2(d2))
    return result.ok


# ---------------------------------------------------------------------------
# Structural correctness
# ---------------------------------------------------------------------------


def test_output_starts_with_shape_sequence_diagram():
    d2 = xyflow_graph_to_d2(SAMPLE_GRAPH)
    assert d2.startswith("shape: sequence_diagram")


def test_participants_declared_once_with_correct_labels():
    d2 = xyflow_graph_to_d2(SAMPLE_GRAPH)
    lines = d2.splitlines()
    # Each node should appear as "id: Label" exactly once in the header block.
    assert "user: User" in lines
    assert "api: API Server" in lines
    assert "db: Database" in lines
    # Count occurrences — must be exactly one declaration each.
    assert lines.count("user: User") == 1
    assert lines.count("api: API Server") == 1
    assert lines.count("db: Database") == 1


def test_participants_appear_before_messages():
    d2 = xyflow_graph_to_d2(SAMPLE_GRAPH)
    lines = d2.splitlines()
    def _is_declaration(text: str) -> bool:
        return ": " in text and " -> " not in text and " --> " not in text

    last_declaration = max(i for i, line in enumerate(lines) if _is_declaration(line))
    first_message = min(i for i, line in enumerate(lines) if " -> " in line or " --> " in line)
    assert last_declaration < first_message, "All participants must be declared before the first message."


def test_participants_in_node_list_order():
    """Participants appear in the order they were listed in the original node array."""
    d2 = xyflow_graph_to_d2(SAMPLE_GRAPH)
    lines = d2.splitlines()
    user_idx = next(i for i, line in enumerate(lines) if line.startswith("user:"))
    api_idx = next(i for i, line in enumerate(lines) if line.startswith("api:"))
    db_idx = next(i for i, line in enumerate(lines) if line.startswith("db:"))
    assert user_idx < api_idx < db_idx


def test_edges_emitted_in_order_ascending():
    d2 = xyflow_graph_to_d2(SAMPLE_GRAPH)
    lines = d2.splitlines()
    message_lines = [line for line in lines if " -> " in line or " --> " in line]
    # The graph has edges with order 1,2,3,4 — e1 first, e4 last.
    assert message_lines[0].startswith("user -> api:")  # order=1
    assert message_lines[1].startswith("api --> db:")   # order=2, kind=async
    assert message_lines[2].startswith("api --> user:") # order=3, animated+return
    assert message_lines[3].startswith("db --> api:")   # order=4, kind=return


# ---------------------------------------------------------------------------
# Arrow type rules
# ---------------------------------------------------------------------------


def test_sync_edge_uses_solid_arrow():
    graph = {
        "nodes": [
            {"id": "a", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "A"}},
            {"id": "b", "type": "systemNode", "position": {"x": 100, "y": 0}, "data": {"label": "B"}},
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "animated": False, "data": {"order": 1, "label": "call"}},
        ],
    }
    d2 = xyflow_graph_to_d2(graph)
    assert "a -> b: call" in d2
    assert "a --> b" not in d2


def test_animated_true_uses_dashed_arrow():
    graph = {
        "nodes": [
            {"id": "a", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "A"}},
            {"id": "b", "type": "systemNode", "position": {"x": 100, "y": 0}, "data": {"label": "B"}},
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "animated": True, "data": {"order": 1, "label": "async msg"}},
        ],
    }
    d2 = xyflow_graph_to_d2(graph)
    assert "a --> b: async msg" in d2


def test_kind_async_uses_dashed_arrow():
    graph = {
        "nodes": [
            {"id": "a", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "A"}},
            {"id": "b", "type": "systemNode", "position": {"x": 100, "y": 0}, "data": {"label": "B"}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "a",
                "target": "b",
                "animated": False,
                "data": {"order": 1, "label": "fire and forget", "kind": "async"},
            },
        ],
    }
    d2 = xyflow_graph_to_d2(graph)
    assert "a --> b: fire and forget" in d2


def test_kind_return_uses_dashed_arrow():
    graph = {
        "nodes": [
            {"id": "a", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "A"}},
            {"id": "b", "type": "systemNode", "position": {"x": 100, "y": 0}, "data": {"label": "B"}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "b",
                "target": "a",
                "animated": False,
                "data": {"order": 1, "label": "response", "kind": "return"},
            },
        ],
    }
    d2 = xyflow_graph_to_d2(graph)
    assert "b --> a: response" in d2


# ---------------------------------------------------------------------------
# Tolerance of missing optional fields
# ---------------------------------------------------------------------------


def test_missing_edge_label_accepted():
    graph = {
        "nodes": [
            {"id": "a", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "A"}},
            {"id": "b", "type": "systemNode", "position": {"x": 100, "y": 0}, "data": {"label": "B"}},
        ],
        "edges": [
            # No "label" key in data
            {"id": "e1", "source": "a", "target": "b", "animated": False, "data": {"order": 1}},
        ],
    }
    d2 = xyflow_graph_to_d2(graph)
    # Edge should still appear; label is empty (D2 allows blank label after the colon).
    assert "a -> b:" in d2


def test_missing_edge_kind_accepted():
    graph = {
        "nodes": [
            {"id": "a", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "A"}},
            {"id": "b", "type": "systemNode", "position": {"x": 100, "y": 0}, "data": {"label": "B"}},
        ],
        "edges": [
            # No "kind" key in data — should default to sync
            {"id": "e1", "source": "a", "target": "b", "animated": False, "data": {"order": 1, "label": "ping"}},
        ],
    }
    d2 = xyflow_graph_to_d2(graph)
    assert "a -> b: ping" in d2
    assert "-->" not in d2


# ---------------------------------------------------------------------------
# Input format: JSON string and dict
# ---------------------------------------------------------------------------


def test_accepts_json_string():
    json_str = json.dumps(SAMPLE_GRAPH)
    d2 = xyflow_graph_to_d2(json_str)
    assert d2.startswith("shape: sequence_diagram")
    assert "user: User" in d2


def test_accepts_dict():
    d2 = xyflow_graph_to_d2(SAMPLE_GRAPH)
    assert d2.startswith("shape: sequence_diagram")


def test_json_string_and_dict_produce_identical_output():
    d2_from_dict = xyflow_graph_to_d2(SAMPLE_GRAPH)
    d2_from_str = xyflow_graph_to_d2(json.dumps(SAMPLE_GRAPH))
    assert d2_from_dict == d2_from_str


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_raises_on_graph_with_no_nodes():
    with pytest.raises(ValueError, match="no nodes"):
        xyflow_graph_to_d2({"nodes": [], "edges": []})


def test_raises_on_empty_dict():
    with pytest.raises(ValueError, match="no nodes"):
        xyflow_graph_to_d2({})


def test_raises_on_invalid_json_string():
    with pytest.raises(ValueError, match="not valid JSON"):
        xyflow_graph_to_d2("not json at all {{{")


# ---------------------------------------------------------------------------
# Real D2 compiler round-trip
# ---------------------------------------------------------------------------


@requires_d2
def test_representative_graph_compiles():
    """The converter's output for a real representative graph actually compiles."""
    d2 = xyflow_graph_to_d2(SAMPLE_GRAPH)
    assert _compile_check(d2), f"D2 from xyflow_graph_to_d2 did not compile:\n{d2}"


@requires_d2
def test_graph_with_no_edges_compiles():
    """A graph with nodes but no edges converts to valid D2 (just participants, no messages)."""
    graph = {
        "nodes": [
            {"id": "x", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "X"}},
            {"id": "y", "type": "systemNode", "position": {"x": 100, "y": 0}, "data": {"label": "Y"}},
        ],
        "edges": [],
    }
    d2 = xyflow_graph_to_d2(graph)
    assert _compile_check(d2), f"D2 with no edges did not compile:\n{d2}"


# ---------------------------------------------------------------------------
# D.13 hardening (review-driven): ordering sentinel, id/label safety, bad input
# ---------------------------------------------------------------------------


def _participants(d2: str) -> list[str]:
    """The participant ids declared in the D2 (lines before the blank separator)."""
    out = []
    for line in d2.splitlines()[1:]:  # skip the shape header
        if not line.strip():
            break
        out.append(line.split(":", 1)[0].strip())
    return out


def _messages(d2: str) -> list[str]:
    return [ln for ln in d2.splitlines() if " -> " in ln or " --> " in ln]


def test_missing_order_sorts_after_ordered_edges():
    """An edge without data.order sorts LAST, not first — a partial-order legacy graph keeps its sequence."""
    graph = {
        "nodes": [{"id": "a", "data": {"label": "A"}}, {"id": "b", "data": {"label": "B"}}],
        "edges": [
            {"source": "a", "target": "b", "data": {"order": 1, "label": "first"}},
            {"source": "b", "target": "a", "data": {"label": "no-order"}},  # missing order
            {"source": "a", "target": "b", "data": {"order": 2, "label": "second"}},
        ],
    }
    msgs = _messages(xyflow_graph_to_d2(graph))
    assert msgs[0].endswith(": first")
    assert msgs[1].endswith(": second")
    assert msgs[2].endswith(": no-order")  # missing-order edge is last, not tied with order 0


def test_order_zero_is_distinct_from_missing_and_sorts_first():
    graph = {
        "nodes": [{"id": "a", "data": {"label": "A"}}, {"id": "b", "data": {"label": "B"}}],
        "edges": [
            {"source": "a", "target": "b", "data": {"label": "no-order"}},  # missing
            {"source": "b", "target": "a", "data": {"order": 0, "label": "zeroth"}},  # legitimate 0
        ],
    }
    msgs = _messages(xyflow_graph_to_d2(graph))
    assert msgs[0].endswith(": zeroth")  # order 0 first
    assert msgs[1].endswith(": no-order")  # missing last


@requires_d2
def test_node_id_with_dot_becomes_one_flat_participant():
    """A legacy id like 'svc.api' must not become a nested D2 container; it is slugified."""
    graph = {
        "nodes": [{"id": "svc.api", "data": {"label": "API"}}, {"id": "db", "data": {"label": "DB"}}],
        "edges": [{"source": "svc.api", "target": "db", "data": {"order": 1, "label": "query"}}],
    }
    d2 = xyflow_graph_to_d2(graph)
    parts = _participants(d2)
    assert "db" in parts
    assert not any("." in p for p in parts), f"a dot leaked into a participant id: {parts}"
    # The edge endpoint resolves to the SAME slug as the declaration.
    msg = _messages(d2)[0]
    assert msg.split(" ", 1)[0] in parts
    assert _compile_check(d2), f"slugified D2 did not compile:\n{d2}"


@requires_d2
def test_label_with_newline_does_not_break_the_statement():
    """A newline in a legacy label is collapsed to a space so it can't split the D2 line."""
    graph = {
        "nodes": [{"id": "a", "data": {"label": "Line\none"}}, {"id": "b", "data": {"label": "B"}}],
        "edges": [{"source": "a", "target": "b", "data": {"order": 1, "label": "do\nthis"}}],
    }
    d2 = xyflow_graph_to_d2(graph)
    # The newline inside the label is collapsed to a space, so each label stays on
    # its own line (one declaration per line, one message per line — no stray tokens).
    assert "a: Line one" in d2
    assert "a -> b: do this" in d2
    assert _compile_check(d2), f"D2 with newline labels did not compile:\n{d2}"


def test_edge_missing_an_endpoint_is_dropped():
    graph = {
        "nodes": [{"id": "a", "data": {"label": "A"}}, {"id": "b", "data": {"label": "B"}}],
        "edges": [
            {"source": "a", "target": "b", "data": {"order": 1, "label": "ok"}},
            {"source": "a", "data": {"order": 2, "label": "no-target"}},  # dropped
            {"target": "b", "data": {"order": 3, "label": "no-source"}},  # dropped
        ],
    }
    msgs = _messages(xyflow_graph_to_d2(graph))
    assert len(msgs) == 1
    assert msgs[0].endswith(": ok")


@pytest.mark.parametrize("bad", ["[1, 2, 3]", "null", "42", '"a string"'])
def test_non_object_json_raises_value_error(bad):
    """A top-level non-object diagram_json raises ValueError (not AttributeError) so the migration skips it."""
    with pytest.raises(ValueError, match="must be a JSON object"):
        xyflow_graph_to_d2(bad)


def test_non_int_order_does_not_crash():
    """A non-int order (e.g. a string) must not raise a TypeError mid-sort; it sorts as unordered."""
    graph = {
        "nodes": [{"id": "a", "data": {"label": "A"}}, {"id": "b", "data": {"label": "B"}}],
        "edges": [
            {"source": "a", "target": "b", "data": {"order": "x", "label": "stringy"}},
            {"source": "b", "target": "a", "data": {"order": 1, "label": "ordered"}},
        ],
    }
    msgs = _messages(xyflow_graph_to_d2(graph))
    assert msgs[0].endswith(": ordered")  # the real order sorts first
    assert msgs[1].endswith(": stringy")  # the non-int order sorts last
