"""Python objects as arguments and results: what the fixtures, which are JSON text, cannot show.

A Python value is read with the limits of the JSON parser, and refused with the
same engine error as text that does not parse. Results are Python values, with
numbers as ``json.loads`` reads their text.
"""

from __future__ import annotations

import json
import math
import threading
import time
from typing import TYPE_CHECKING

import pytest
from lfx_native import ops

if TYPE_CHECKING:
    from collections.abc import Callable


def nested(depth: int, leaf: object, *, as_dict: bool = False) -> object:
    for _ in range(depth):
        leaf = {"x": leaf} if as_dict else [leaf]
    return leaf


def refused_as_text(value: object) -> bool:
    try:
        ops.canonical_json(json.dumps(value).encode())
    except ops.EngineError:
        return True
    return False


@pytest.mark.parametrize("as_dict", [False, True], ids=["lists", "dicts"])
def test_nesting_has_the_parser_limit(as_dict):
    deepest = nested(127, 1, as_dict=as_dict)
    too_deep = nested(128, 1, as_dict=as_dict)
    ops.canonical_json(deepest)
    with pytest.raises(ops.EngineError) as refused:
        ops.canonical_json(too_deep)
    assert (refused.value.kind, refused.value.code) == ("FlowDataValidationError", "FLOW_GRAPH_INVALID")
    # The same limit as the text of the same values.
    assert not refused_as_text(deepest)
    assert refused_as_text(too_deep)


def test_a_flow_nested_too_deep_is_refused():
    flow = {"nodes": [{"id": "a", "data": {"node": {"template": {"t": {"value": nested(122, 1)}}}}}], "edges": []}
    with pytest.raises(ops.EngineError) as refused:
        ops.graph_hash(flow)
    assert refused.value.code == "FLOW_GRAPH_INVALID"
    assert refused_as_text(flow)


@pytest.mark.parametrize(
    "value",
    [{"name": "\ud800"}, ["\udc00"], {"\ud800": 1}],
    ids=["value", "list item", "key"],
)
def test_a_lone_surrogate_is_refused(value):
    with pytest.raises(ops.EngineError) as refused:
        ops.canonical_json(value)
    assert (refused.value.kind, refused.value.code) == ("FlowDataValidationError", "FLOW_GRAPH_INVALID")


@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf], ids=["nan", "inf", "-inf"])
def test_a_number_that_is_not_finite_is_refused(number):
    with pytest.raises(ops.EngineError) as refused:
        ops.canonical_json({"n": number})
    assert refused.value.code == "FLOW_GRAPH_INVALID"


@pytest.mark.parametrize("value", [{1: "a"}, {"a": {1, 2}}, {"a": object()}], ids=["int key", "set", "object"])
def test_a_value_that_is_not_json_is_a_type_error(value):
    with pytest.raises(TypeError):
        ops.canonical_json(value)


def test_json_values_read_as_json_reads_them():
    assert ops.canonical_json((1, "a", None)) == '[1,"a",null]'
    assert ops.canonical_json([True, False, 1]) == "[true,false,1]"
    # A str is a JSON string, never text to parse.
    assert ops.canonical_json('{"a": 1}') == '"{\\"a\\": 1}"'
    assert [violation["code"] for violation in ops.validate("{}")] == ["FLOW_DATA_NOT_OBJECT"]


FLOW = {
    "nodes": [{"id": "a", "data": {"node": {"template": {"t": {"value": "x", "type": "str"}}}}}],
    "edges": [],
    "viewport": {"x": 0, "y": 0, "zoom": 1},
}


def set_value(value: object) -> list[dict]:
    return [
        {
            "type": "update_nodes",
            "updates": [
                {"id": "a", "op": "set_field", "path": ["data", "node", "template", "t", "value"], "value": value}
            ],
        }
    ]


@pytest.mark.parametrize("value", [1, 1.0, -0.0, 12345678901234567890123, 0.1, "é", None, True], ids=repr)
def test_values_come_back_as_given(value):
    state = ops.GraphState(FLOW)
    state.apply(set_value(value))
    result = state.to_dict()["nodes"][0]["data"]["node"]["template"]["t"]["value"]
    assert type(result) is type(value)
    assert result == value or (isinstance(value, float) and math.isnan(value))
    if isinstance(value, float):
        assert math.copysign(1, result) == math.copysign(1, value)


def test_numbers_come_back_as_json_loads_reads_their_text():
    flow = b'{"nodes": [], "edges": [], "a": 1e2, "b": 1, "c": 1.0, "d": 123456789012345678901234567890}'
    assert ops.GraphState(flow).to_dict() == json.loads(flow)
    assert [type(value) for value in ops.GraphState(flow).to_dict().values()][2:] == [float, int, float, int]


def test_text_and_objects_give_the_same_results():
    text = json.dumps(FLOW).encode()
    assert ops.graph_hash(text) == ops.graph_hash(FLOW)
    assert ops.ops_diff(text, json.dumps(FLOW).encode()) == ops.ops_diff(FLOW, FLOW) == []
    state = ops.GraphState(text)
    assert state.to_dict() == json.loads(state.to_json()) == FLOW


def test_error_details_are_a_dict():
    with pytest.raises(ops.EngineError) as refused:
        ops.GraphState(FLOW).apply([*set_value(1), {"type": "delete_nodes", "ids": "a"}])
    details = refused.value.details
    assert isinstance(details, dict)
    assert details["code"] == refused.value.code


def test_a_result_shares_each_key_as_json_loads_does():
    flow = {
        "nodes": [{"id": node, "data": {"node": {"template": {}}}} for node in ("a", "b")],
        "edges": [],
    }

    def data_key(node: dict) -> str:
        return next(key for key in node if key == "data")

    first, second = ops.GraphState(flow).to_dict()["nodes"]
    assert data_key(first) is data_key(second)
    parsed = json.loads(json.dumps(flow))["nodes"]
    assert data_key(parsed[0]) is data_key(parsed[1])


def test_threads_share_one_state():
    """A batch and the reads of the graph wait for each other: none fails, and none sees half a batch."""
    template = {"t": {"value": "", "type": "str"}, "u": {"value": "", "type": "str"}}
    flow = {"nodes": [{"id": "a", "data": {"node": {"template": template}}}], "edges": []}
    state = ops.GraphState(flow)

    def both(marker: str) -> list[dict]:
        updates = [
            {"id": "a", "op": "set_field", "path": ["data", "node", "template", field, "value"], "value": marker}
            for field in ("t", "u")
        ]
        return [{"type": "update_nodes", "updates": updates}]

    def fields(graph: dict) -> tuple[str, str]:
        template = graph["nodes"][0]["data"]["node"]["template"]
        return template["t"]["value"], template["u"]["value"]

    done = threading.Event()
    problems: list[str] = []

    def write() -> None:
        try:
            for index in range(300):
                state.apply(both(f"v{index}"))
        finally:
            done.set()

    def read(graph: Callable[[], dict]) -> None:
        while not done.is_set():
            try:
                first, second = fields(graph())
            except Exception as error:  # noqa: BLE001 -- the test records any failure
                problems.append(f"{type(error).__name__}: {error}")
                return
            if first != second:
                problems.append(f"half a batch: {first} and {second}")
                return

    threads = [
        threading.Thread(target=write),
        threading.Thread(target=read, args=(state.to_dict,)),
        threading.Thread(target=read, args=(lambda: json.loads(state.to_json()),)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert problems == []
    assert fields(state.to_dict()) == ("v299", "v299")


def test_batches_wait_for_a_large_read_without_the_gil():
    """A read of a large graph runs without the GIL and holds the lock.

    A batch then waits for the lock without the GIL, and no thread deadlocks or sees half a batch.
    """
    template = {"t": {"value": "", "type": "str"}, "u": {"value": "", "type": "str"}}
    nodes = [{"id": f"n{index}", "data": {"node": {"template": template}}} for index in range(400)]
    state = ops.GraphState({"nodes": nodes, "edges": []})
    done = threading.Event()
    problems: list[str] = []

    def write() -> None:
        try:
            for index in range(200):
                path = ["data", "node", "template"]
                updates = [
                    {"id": "n0", "op": "set_field", "path": [*path, field, "value"], "value": f"v{index}"}
                    for field in ("t", "u")
                ]
                state.apply([{"type": "update_nodes", "updates": updates}])
        finally:
            done.set()

    def read() -> None:
        while not done.is_set():
            template = json.loads(state.to_json())["nodes"][0]["data"]["node"]["template"]
            first, second = template["t"]["value"], template["u"]["value"]
            if first != second:
                problems.append(f"half a batch: {first} and {second}")
                return

    threads = [threading.Thread(target=write), threading.Thread(target=read), threading.Thread(target=read)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert problems == []


SMALL_CALLS_SECONDS = 0.25


def test_a_small_call_keeps_the_gil():
    """A small batch keeps the GIL.

    So a busy Python thread does not make each call wait a switch interval (5 ms by default) for the GIL.
    """
    state = ops.GraphState(FLOW)
    stop = threading.Event()

    def spin() -> None:
        while not stop.is_set():
            pass

    spinner = threading.Thread(target=spin)
    spinner.start()
    try:
        start = time.perf_counter()
        for index in range(100):
            state.apply(set_value(f"v{index}"))
        elapsed = time.perf_counter() - start
    finally:
        stop.set()
        spinner.join()
    # A wait for the GIL after each call takes 100 switch intervals: 0.5 s.
    assert elapsed < SMALL_CALLS_SECONDS


def value_of(graph: dict) -> object:
    return graph["nodes"][0]["data"]["node"]["template"]["t"]["value"]


def test_a_staged_batch_is_read_only_after_keep():
    state = ops.GraphState(FLOW)
    staged = state.stage(set_value("y"), forward=True, backward=True)
    assert staged == ops.GraphState(FLOW).apply(set_value("y"), forward=True, backward=True)
    assert state.staged
    # Readers see the committed graph while the batch waits.
    assert state.to_dict() == FLOW
    assert json.loads(state.to_json()) == FLOW
    state.keep()
    assert not state.staged
    assert value_of(state.to_dict()) == "y"
    assert value_of(json.loads(state.to_json())) == "y"


def test_the_staged_graph_is_the_graph_keep_makes():
    state = ops.GraphState(FLOW)
    with pytest.raises(RuntimeError, match="no batch is staged"):
        state.to_json(staged=True)
    state.stage(set_value("y"))
    staged = state.to_json(staged=True)
    assert value_of(json.loads(staged)) == "y"
    assert value_of(json.loads(state.to_json())) == "x"
    state.keep()
    assert state.to_json() == staged
    state.stage(set_value("z"))
    state.drop()
    with pytest.raises(RuntimeError, match="no batch is staged"):
        state.to_json(staged=True)


@pytest.mark.parametrize("call", ["apply", "stage"])
def test_forward_json_gives_each_forward_operation_as_ascii_text(call):
    value = 'x"\\\n\u00e9\u2028\U0001f600'
    with_objects = getattr(ops.GraphState(FLOW), call)(set_value(value), forward=True, forward_json=True)
    texts = with_objects["forward_operations_json"]
    assert all(isinstance(text, bytes) and text.isascii() for text in texts)
    operations = with_objects["forward_operations"]
    assert [json.loads(text) for text in texts] == operations
    # The text ``to_json`` writes for the same value: compact, every character above U+007F escaped.
    assert texts == [json.dumps(operation, separators=(",", ":")).encode() for operation in operations]
    only_text = getattr(ops.GraphState(FLOW), call)(set_value(value), forward_json=True)
    assert only_text == {"forward_operations_json": texts}


def test_a_dropped_batch_leaves_the_graph_as_it_was():
    state = ops.GraphState(FLOW)
    state.stage(set_value("y"))
    assert state.drop() is True
    assert not state.staged
    assert state.to_dict() == FLOW
    assert state.drop() is False
    state.apply(set_value("z"))
    assert value_of(state.to_dict()) == "z"


def test_a_staged_batch_refuses_the_next_batch():
    state = ops.GraphState(FLOW)
    state.stage(set_value("y"))
    for call in (
        lambda: state.apply(set_value("z")),
        lambda: state.replay(set_value("z")),
        lambda: state.stage(set_value("z")),
    ):
        with pytest.raises(RuntimeError, match="a batch is staged"):
            call()
    state.keep()
    assert value_of(state.to_dict()) == "y"


def test_a_refused_batch_is_not_staged():
    state = ops.GraphState(FLOW)
    with pytest.raises(ops.EngineError):
        state.stage([*set_value("y"), {"type": "delete_nodes", "ids": ["missing"]}])
    assert not state.staged
    with pytest.raises(RuntimeError, match="no batch is staged"):
        state.keep()
    assert state.to_dict() == FLOW


def changed(value: object) -> dict:
    flow = json.loads(json.dumps(FLOW))
    flow["nodes"][0]["data"]["node"]["template"]["t"]["value"] = value
    return flow


def test_a_plain_graph_answers_as_the_functions_do():
    target = changed("y")
    base, plain_target = ops.GraphPlain(FLOW), ops.GraphPlain(json.dumps(target).encode())
    assert base.validate() == ops.validate(FLOW) == []
    assert plain_target.validate(base) == ops.validate(target, FLOW)
    assert base.ops_diff(plain_target) == ops.ops_diff(FLOW, target)
    assert base.graph_hash() == ops.graph_hash(FLOW)
    assert not base.equals(plain_target)
    assert base.equals(ops.GraphPlain(FLOW))
    assert base.to_dict() == json.loads(base.to_json()) == FLOW


def test_a_plain_graph_repairs_as_repair_does():
    broken = {"nodes": [{"data": {"node": {"template": {}}}}], "edges": "none"}
    repaired, fixes = ops.GraphPlain(broken).repair()
    expected = ops.repair(broken)
    assert isinstance(repaired, ops.GraphPlain)
    assert fixes == expected["fixes"]
    # Generated node ids are derived from the node, so both repairs agree.
    assert repaired.to_dict() == expected["flow_data"]
    assert repaired.validate() == []


def test_a_plain_graph_refuses_what_the_functions_refuse():
    broken = ops.GraphPlain({"nodes": [{"data": {}}], "edges": []})
    assert [violation["code"] for violation in broken.validate()] == [
        violation["code"] for violation in ops.validate({"nodes": [{"data": {}}], "edges": []})
    ]
    with pytest.raises(ops.EngineError) as refused:
        ops.GraphPlain(changed(math.inf))
    assert refused.value.code == "FLOW_GRAPH_INVALID"
    with pytest.raises(TypeError):
        ops.GraphPlain(FLOW).equals(FLOW)


def test_threads_share_one_plain_graph():
    plain = ops.GraphPlain(FLOW)
    target = ops.GraphPlain(changed("y"))
    expected = ops.ops_diff(FLOW, changed("y"))
    results: list[object] = []

    def diff() -> None:
        results.extend(plain.ops_diff(target) for _ in range(200))

    threads = [threading.Thread(target=diff) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [expected] * 800


def test_large_graphs_dropped_from_many_threads_leave_the_engine_working():
    """A large graph is dropped on the engine's drop thread, or where it is when that thread is busy."""
    template = {f"f{index}": {"value": "x" * 100, "type": "str"} for index in range(20)}
    nodes = [{"id": f"n{index}", "data": {"node": {"template": template}}} for index in range(500)]
    text = json.dumps({"nodes": nodes, "edges": []}).encode()
    expected = ops.GraphPlain(text).graph_hash()

    hashes: list[str] = []

    def churn() -> None:
        for _ in range(10):
            state = ops.GraphState(text)
            plain = ops.GraphPlain(text)
            hashes.extend([state.graph_hash(), plain.graph_hash()])
            del state, plain

    threads = [threading.Thread(target=churn) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert hashes == [expected] * 80
    assert ops.GraphState(text).graph_hash() == expected


def test_a_state_hashes_as_its_text_does():
    state = ops.GraphState(FLOW)
    assert state.graph_hash() == ops.GraphPlain(state.to_json().encode()).graph_hash()
    with pytest.raises(RuntimeError, match="no batch is staged"):
        state.graph_hash(staged=True)
    state.stage(set_value("y"))
    staged = state.graph_hash(staged=True)
    assert staged == ops.GraphPlain(state.to_json(staged=True).encode()).graph_hash()
    assert staged != state.graph_hash()
    state.keep()
    assert state.graph_hash() == staged


def test_a_snapshot_keeps_the_graph_as_it_was():
    state = ops.GraphState(FLOW)
    text, hashed = state.to_json(), state.graph_hash()
    snapshot = state.snapshot()
    state.apply(set_value("y"))
    state.stage(set_value("z"))
    assert (snapshot.to_json(), snapshot.graph_hash()) == (text, hashed)
    later = state.snapshot()
    assert (later.to_json(), later.graph_hash()) == (state.to_json(), state.graph_hash())
    assert value_of(json.loads(later.to_json())) == "y"


def test_a_snapshot_is_read_on_another_thread_while_batches_go_on():
    """A server writes and hashes a snapshot on a worker thread while its event loop applies batches."""
    template = {f"f{index}": {"value": "x" * 100, "type": "str"} for index in range(20)}
    nodes = [{"id": f"n{index}", "data": {"node": {"template": template}}} for index in range(500)]
    state = ops.GraphState({"nodes": nodes, "edges": []})

    def write_field(node_id: str, field: str, value: str) -> None:
        path = ["data", "node", "template", field, "value"]
        update = {"id": node_id, "op": "set_field", "path": path, "value": value}
        state.apply([{"type": "update_nodes", "updates": [update]}])

    expected = []
    snapshots = []
    for index in range(5):
        expected.append((state.to_json(), state.graph_hash()))
        snapshots.append(state.snapshot())
        write_field("n0", "f0", f"v{index}")
    seen: list[tuple[str, str]] = []

    def read() -> None:
        seen.extend((snapshot.to_json(), snapshot.graph_hash()) for snapshot in snapshots)

    def write() -> None:
        for index in range(200):
            write_field(f"n{index}", "f1", "w")

    threads = [threading.Thread(target=read), threading.Thread(target=write)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert seen == expected
