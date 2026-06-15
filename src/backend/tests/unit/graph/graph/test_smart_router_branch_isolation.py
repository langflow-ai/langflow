"""Graph-level regression tests for Smart Router branch isolation.

Reproduces https://github.com/langflow-ai/langflow/issues/13440: the branch that the
LLM does *not* select must not continue into its downstream nodes. The bug only surfaced
once a branch reconverged on a shared downstream node, because ``stop()`` alone marks a
branch INACTIVE for a single scheduling pass and that state is reset between passes -- a
re-activated branch was then picked up again through the shared node. Smart Router now also
records a *persistent* conditional exclusion (like the If-Else router).

These tests drive the real graph engine and the real ``process_case`` / ``default_response``
routing logic; only the LLM categorization is stubbed so the assertions are deterministic.

The persistent-exclusion mechanism lives in ``Graph.exclude_branch_conditionally`` and is
shared with the If-Else router (``ConditionalRouterComponent``). The final test guards that
shared path with the same reconvergence scenario: it would have failed before this fix
because the merge node was excluded along with the unselected branch and never ran.
"""

import pytest

try:
    from lfx.components.flow_controls.conditional_router import ConditionalRouterComponent
    from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
    from lfx.custom.custom_component.component import Component
    from lfx.graph.graph.base import Graph
    from lfx.io import MessageTextInput, Output
    from lfx.schema.message import Message
except ImportError as e:
    pytest.skip(f"Failed to import components in tests. Exception: {e}", allow_module_level=True)


class _StubbedSmartRouter(SmartRouterComponent):
    """Smart Router with deterministic categorization (no real LLM call).

    The static ``outputs`` mirror exactly what ``update_outputs`` produces for the routes
    used in these tests (``category_{i}_result`` + optional ``default_result``), so the real
    routing code under test is exercised unchanged.
    """

    forced_category = "Positive"

    outputs = [
        Output(display_name="Positive", name="category_1_result", method="process_case", group_outputs=True),
        Output(display_name="Negative", name="category_2_result", method="process_case", group_outputs=True),
    ]

    def _get_categorization(self) -> str:
        self._categorization_result = self.forced_category
        return self.forced_category


class _ThreeRouteSmartRouter(_StubbedSmartRouter):
    """Three-route variant to exercise excluding more than one unselected branch."""

    outputs = [
        Output(display_name="Positive", name="category_1_result", method="process_case", group_outputs=True),
        Output(display_name="Neutral", name="category_2_result", method="process_case", group_outputs=True),
        Output(display_name="Negative", name="category_3_result", method="process_case", group_outputs=True),
    ]


class RecordingSink(Component):
    display_name = "Recording Sink"
    name = "RecordingSink"

    inputs = [MessageTextInput(name="input_value", display_name="Input", required=False)]
    outputs = [Output(display_name="Out", name="out", method="run_sink")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.did_run = False

    def run_sink(self) -> Message:
        self.did_run = True
        return Message(text=f"ran:{self._id}")


class MergeSink(Component):
    display_name = "Merge Sink"
    name = "MergeSink"

    inputs = [
        MessageTextInput(name="in1", display_name="In1", required=False),
        MessageTextInput(name="in2", display_name="In2", required=False),
        MessageTextInput(name="in3", display_name="In3", required=False),
    ]
    outputs = [Output(display_name="Out", name="out", method="run_merge")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.did_run = False

    def run_merge(self) -> Message:
        self.did_run = True
        return Message(text="merged")


def _make_router(router_cls, routes):
    router = router_cls(_id="router")
    router.set(input_text="I love this product!", routes=routes)
    return router


async def _run(graph: Graph) -> list[str]:
    graph.prepare()
    return [result.vertex.id async for result in graph.async_start() if hasattr(result, "vertex")]


_TWO_ROUTES = [
    {"route_category": "Positive", "route_description": "good", "output_value": ""},
    {"route_category": "Negative", "route_description": "bad", "output_value": ""},
]


async def test_unselected_branch_does_not_run_separate_leaves():
    """Each route feeds its own leaf: only the matched route's leaf runs."""
    router = _make_router(_StubbedSmartRouter, _TWO_ROUTES)
    selected, unselected = RecordingSink(_id="selected"), RecordingSink(_id="unselected")

    graph = Graph()
    graph.add_component(router, "router")
    graph.add_component(selected, "selected")
    graph.add_component(unselected, "unselected")
    graph.add_component_edge("router", ("category_1_result", "input_value"), "selected")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "unselected")

    yielded = await _run(graph)

    assert selected.did_run is True
    assert unselected.did_run is False
    assert "unselected" not in yielded


async def test_unselected_branch_does_not_run_when_branches_reconverge():
    """Regression for #13440.

    Branches reconverging on a shared downstream node must not re-run the unselected branch.
    """
    router = _make_router(_StubbedSmartRouter, _TWO_ROUTES)
    selected, unselected = RecordingSink(_id="selected"), RecordingSink(_id="unselected")
    merge = MergeSink(_id="merge")

    graph = Graph()
    graph.add_component(router, "router")
    graph.add_component(selected, "selected")
    graph.add_component(unselected, "unselected")
    graph.add_component(merge, "merge")
    graph.add_component_edge("router", ("category_1_result", "input_value"), "selected")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "unselected")
    graph.add_component_edge("selected", ("out", "in1"), "merge")
    graph.add_component_edge("unselected", ("out", "in2"), "merge")

    yielded = await _run(graph)

    assert selected.did_run is True
    assert unselected.did_run is False, "Unselected branch executed despite not being routed to"
    assert merge.did_run is True, "Merge node should execute from selected branch"
    assert "unselected" not in yielded
    assert "merge" in yielded


def _make_if_else_router():
    """If-Else router whose condition evaluates True, so it routes to ``true_result``."""
    router = ConditionalRouterComponent(_id="router")
    router.set(input_text="go", match_text="go", operator="equals")
    return router


async def test_if_else_unselected_branch_does_not_run_when_branches_reconverge():
    """Reconvergence regression for the shared If-Else routing path.

    ``ConditionalRouterComponent`` (If-Else) drives the same persistent
    ``Graph.exclude_branch_conditionally`` mechanism as Smart Router. When its branches
    reconverge on a shared downstream node, the unselected branch must stay excluded while
    the shared node still runs from the selected branch. Before the exclusion logic learned
    to keep a sibling output's shared descendants, the merge node was excluded too and never
    ran -- so this guards a real (and previously latent) If-Else behavior, not only the new
    Smart Router code.
    """
    router = _make_if_else_router()  # condition True -> routes to ``true_result``
    selected, unselected = RecordingSink(_id="selected"), RecordingSink(_id="unselected")
    merge = MergeSink(_id="merge")

    graph = Graph()
    graph.add_component(router, "router")
    graph.add_component(selected, "selected")
    graph.add_component(unselected, "unselected")
    graph.add_component(merge, "merge")
    graph.add_component_edge("router", ("true_result", "input_value"), "selected")
    graph.add_component_edge("router", ("false_result", "input_value"), "unselected")
    graph.add_component_edge("selected", ("out", "in1"), "merge")
    graph.add_component_edge("unselected", ("out", "in2"), "merge")

    yielded = await _run(graph)

    assert selected.did_run is True
    assert unselected.did_run is False, "Unselected If-Else branch executed despite the condition routing elsewhere"
    assert merge.did_run is True, "Merge node should execute from the selected branch"
    assert "unselected" not in yielded
    assert "merge" in yielded


async def test_only_matched_branch_runs_with_three_routes():
    """With three routes, both unselected branches must be excluded (not just the last one)."""
    three_routes = [
        {"route_category": "Positive", "route_description": "good", "output_value": ""},
        {"route_category": "Neutral", "route_description": "meh", "output_value": ""},
        {"route_category": "Negative", "route_description": "bad", "output_value": ""},
    ]
    router = _make_router(_ThreeRouteSmartRouter, three_routes)
    router.forced_category = "Neutral"  # select the middle route

    sink1, sink2, sink3 = (RecordingSink(_id="sink1"), RecordingSink(_id="sink2"), RecordingSink(_id="sink3"))
    merge = MergeSink(_id="merge")

    graph = Graph()
    for comp, cid in ((router, "router"), (sink1, "sink1"), (sink2, "sink2"), (sink3, "sink3"), (merge, "merge")):
        graph.add_component(comp, cid)
    graph.add_component_edge("router", ("category_1_result", "input_value"), "sink1")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "sink2")
    graph.add_component_edge("router", ("category_3_result", "input_value"), "sink3")
    graph.add_component_edge("sink1", ("out", "in1"), "merge")
    graph.add_component_edge("sink2", ("out", "in2"), "merge")
    graph.add_component_edge("sink3", ("out", "in3"), "merge")

    await _run(graph)

    assert sink2.did_run is True, "Matched (middle) branch should run"
    assert sink1.did_run is False, "Unselected branch 1 should not run"
    assert sink3.did_run is False, "Unselected branch 3 should not run"


def test_update_outputs_names_match_routing_contract():
    """Guard the output-name contract the routing logic relies on (category_{i}_result)."""
    component = SmartRouterComponent()
    frontend_node = component.update_outputs({"outputs": []}, "routes", _TWO_ROUTES)
    names = [o.name for o in frontend_node["outputs"]]
    assert names == ["category_1_result", "category_2_result"]
