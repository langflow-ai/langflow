"""A Loop inside another Loop must give the same result in every process.

Each outer iteration runs a subgraph in which the inner Loop's only incoming edge is its own feedback edge,
so no vertex there is free of predecessors. The run must still start at the inner Loop, whatever the
vertex ids and the string hash seed are. Each case builds the flow with fresh vertex ids, so a start picked
from set order fails on some of them.
"""

from uuid import uuid4

import pytest
from lfx.exceptions.component import ComponentBuildError
from lfx.graph.flow_builder.builder import build_flow_from_spec
from lfx.graph.graph.base import Graph

ITEMS = ["first", "second", "third", "fourth", "fifth"]
ID_SETS = range(8)

NESTED_LOOP_SPEC = """\
name: Nested Loop
nodes:
  CL: CreateList
  OUTER: LoopComponent
  INNER: LoopComponent
  P: ParserComponent
  INNER_TC: TypeConverterComponent
  OUTER_TC: TypeConverterComponent
  POST: ParserComponent
  O: ChatOutput
edges:
  CL.list -> OUTER.data
  OUTER.item -> INNER.data
  INNER.item -> P.input_data
  P.parsed_text -> INNER_TC.input_data
  INNER_TC.data_output -> INNER.item
  INNER.done -> OUTER_TC.input_data
  OUTER_TC.data_output -> OUTER.item
  OUTER.done -> POST.input_data
  POST.parsed_text -> O.input_value
config:
  P.mode: Stringify
  INNER_TC.output_type: JSON
  OUTER_TC.output_type: JSON
  POST.mode: Stringify
"""

FAN_OUT_SPEC = """\
name: Nested Loop Fan-out
nodes:
  CL: CreateList
  OUTER: LoopComponent
  IN1: LoopComponent
  P1: ParserComponent
  TC1: TypeConverterComponent
  IN2: LoopComponent
  P2: ParserComponent
  TC2: TypeConverterComponent
  OUTER_TC: TypeConverterComponent
edges:
  CL.list -> OUTER.data
  OUTER.item -> IN1.data
  OUTER.item -> IN2.data
  IN1.item -> P1.input_data
  P1.parsed_text -> TC1.input_data
  TC1.data_output -> IN1.item
  IN2.item -> P2.input_data
  P2.parsed_text -> TC2.input_data
  TC2.data_output -> IN2.item
  IN1.done -> OUTER_TC.input_data
  OUTER_TC.data_output -> OUTER.item
config:
  P1.mode: Stringify
  P2.mode: Stringify
  TC1.output_type: JSON
  TC2.output_type: JSON
  OUTER_TC.output_type: JSON
"""


def _nested_loop_graph(spec: str = NESTED_LOOP_SPEC, *, failing: bool = False) -> tuple[Graph, dict[str, str]]:
    built = build_flow_from_spec(spec)
    templates = {node["id"]: node["data"]["node"]["template"] for node in built["flow"]["data"]["nodes"]}
    ids = built["node_id_map"]
    templates[ids["CL"]]["texts"]["value"] = ITEMS
    if failing:
        templates[ids["P"]]["mode"]["value"] = "Parser"
        templates[ids["P"]]["pattern"]["value"] = "{text!z}"
    graph = Graph.from_payload(built["flow"], flow_id=str(uuid4()), flow_name="Nested Loop", user_id=str(uuid4()))
    return graph, ids


@pytest.mark.asyncio
@pytest.mark.parametrize("_id_set", ID_SETS)
async def test_should_start_each_outer_iteration_at_the_inner_loop(_id_set):
    graph, ids = _nested_loop_graph()
    outer = graph.get_vertex(ids["OUTER"])
    outer.instantiate_component(user_id=graph.user_id)
    body = outer.custom_component.get_loop_body_vertices()

    async with graph.create_subgraph(body) as iteration_subgraph:
        iteration_subgraph.prepare()

        assert iteration_subgraph._first_layer == [ids["INNER"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("_id_set", ID_SETS)
async def test_should_start_each_outer_iteration_at_every_inner_loop_it_feeds(_id_set):
    graph, ids = _nested_loop_graph(FAN_OUT_SPEC)
    outer = graph.get_vertex(ids["OUTER"])
    outer.instantiate_component(user_id=graph.user_id)
    body = outer.custom_component.get_loop_body_vertices()

    async with graph.create_subgraph(body) as iteration_subgraph:
        iteration_subgraph.prepare()

        assert iteration_subgraph._first_layer == sorted([ids["IN1"], ids["IN2"]])


@pytest.mark.asyncio
@pytest.mark.parametrize("_id_set", ID_SETS)
async def test_should_run_the_inner_loop_body_for_every_outer_item(_id_set):
    graph, ids = _nested_loop_graph()

    async for _ in graph.async_start():
        pass

    output = str(graph.get_vertex(ids["O"]).built_result)
    assert all(item in output for item in ITEMS), output


@pytest.mark.asyncio
@pytest.mark.parametrize("_id_set", ID_SETS)
async def test_should_report_the_inner_loop_body_error(_id_set):
    graph, _ = _nested_loop_graph(failing=True)

    with pytest.raises(ComponentBuildError) as exc_info:
        async for _ in graph.async_start():
            pass

    assert "Unknown conversion specifier z" in str(exc_info.value)
