"""Which fixes a restore accepts: only ones that address a violation the restore would hit."""

from __future__ import annotations

import json

import pytest
from langflow.services.flow_history.errors import RestoreFixNotAllowedError
from langflow.services.flow_history.restore_fixes import check_restore_fixes
from lfx.services.flow_operations import parse_flow_operations


def _node(node_id: str) -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "node": {
                "template": {"text": {"type": "str", "value": ""}},
                "outputs": [{"name": "out"}, {"name": "other"}],
            }
        },
    }


def _handle(value: dict) -> str:
    return json.dumps(value, separators=(",", ":")).replace('"', "œ")


def _edge(edge_id: str, source: str, *, output: str = "out", field: str = "text") -> dict:
    source_handle, target_handle = {"name": output}, {"fieldName": field}
    return {
        "id": edge_id,
        "source": source,
        "target": "b",
        "sourceHandle": _handle(source_handle),
        "targetHandle": _handle(target_handle),
        "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
    }


def _legacy_edge(edge_id: str) -> dict:
    """An edge in a format older editors wrote: handle strings that are not JSON, and no data."""
    return {"id": edge_id, "source": "a", "target": "b", "sourceHandle": "x|y", "targetHandle": "z|w"}


STORED = {"nodes": [_node("a"), _node("b"), _node("c")], "edges": []}


def _revision(*edges: dict) -> dict:
    return {"nodes": [_node("a"), _node("b"), _node("c")], "edges": list(edges)}


def _check(revision: dict, fixes: list[dict]) -> None:
    check_restore_fixes(revision, STORED, parse_flow_operations(fixes))


def _rewrite(edge_id: str, *paths_and_values: tuple[list, object]) -> list[dict]:
    updates = [{"id": edge_id, "op": "set_field", "path": path, "value": value} for path, value in paths_and_values]
    return [{"type": "update_edges", "updates": updates}]


def test_an_edge_with_broken_handles_may_be_deleted():
    _check(_revision(_legacy_edge("old")), [{"type": "delete_edges", "ids": ["old"]}])


def test_an_edge_with_broken_handles_may_have_them_rewritten():
    handles = {"sourceHandle": {"name": "out"}, "targetHandle": {"fieldName": "text"}}
    _check(
        _revision(_legacy_edge("old")),
        _rewrite(
            "old",
            (["sourceHandle"], _handle(handles["sourceHandle"])),
            (["targetHandle"], _handle(handles["targetHandle"])),
            (["data"], handles),
        ),
    )


def test_an_edge_naming_a_missing_output_may_be_reconnected():
    _check(
        _revision(_edge("e", "a", output="gone")),
        _rewrite(
            "e",
            (["sourceHandle"], _handle({"name": "other"})),
            (["data", "sourceHandle"], {"name": "other"}),
        ),
    )


def test_either_edge_into_an_input_taken_twice_may_be_deleted():
    revision = _revision(_edge("first", "a"), _edge("second", "c"))

    _check(revision, [{"type": "delete_edges", "ids": ["first"]}])
    _check(revision, [{"type": "delete_edges", "ids": ["second"]}])


@pytest.mark.parametrize(
    ("revision", "fixes"),
    [
        pytest.param(
            _revision(_legacy_edge("old"), _edge("good", "a")),
            [{"type": "delete_edges", "ids": ["good"]}],
            id="delete an edge that breaks no rule",
        ),
        pytest.param(
            _revision(_legacy_edge("old")),
            _rewrite("old", (["animated"], True)),
            id="write something other than a handle",
        ),
        pytest.param(
            _revision(_edge("e", "a", output="gone")),
            _rewrite("e", (["data"], {"sourceHandle": {"name": "other"}, "targetHandle": {"fieldName": "text"}})),
            id="replace data the edge already has",
        ),
        pytest.param(
            _revision(_legacy_edge("old")),
            _rewrite("old", (["data"], {"sourceHandle": {}, "targetHandle": {}, "label": "x"})),
            id="set data holding more than the handles",
        ),
        pytest.param(
            _revision(_edge("first", "a"), _edge("second", "c")),
            _rewrite("second", (["data", "targetHandle"], {"fieldName": "other"})),
            id="rewrite an edge into a taken input",
        ),
        pytest.param(
            _revision(_legacy_edge("old")),
            [{"type": "update_edges", "updates": [{"id": "old", "op": "delete_field", "path": ["sourceHandle"]}]}],
            id="delete a handle",
        ),
    ],
)
def test_a_fix_that_addresses_no_violation_is_refused(revision, fixes):
    with pytest.raises(RestoreFixNotAllowedError):
        _check(revision, fixes)


def test_an_edge_the_stored_flow_already_has_is_not_the_restores_to_fix():
    old = _legacy_edge("old")
    stored = {"nodes": STORED["nodes"], "edges": [old]}

    with pytest.raises(RestoreFixNotAllowedError):
        check_restore_fixes(_revision(old), stored, parse_flow_operations([{"type": "delete_edges", "ids": ["old"]}]))
