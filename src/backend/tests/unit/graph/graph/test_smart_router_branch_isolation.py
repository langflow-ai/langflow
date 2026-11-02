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
from lfx.components.flow_controls.conditional_router import ConditionalRouterComponent
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
from lfx.custom.custom_component.component import Component
from lfx.graph.graph.base import Graph
from lfx.io import HandleInput, MessageTextInput, Output
from lfx.schema.message import Message


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


class _ElseSmartRouter(_StubbedSmartRouter):
    """Two routes plus an Else output, to exercise the ``default_result`` deactivation path.

    Mirrors what ``update_outputs`` produces when ``enable_else_output=True``: the two
    ``category_{i}_result`` outputs plus a ``default_result`` output bound to
    ``default_response``.
    """

    outputs = [
        Output(display_name="Positive", name="category_1_result", method="process_case", group_outputs=True),
        Output(display_name="Negative", name="category_2_result", method="process_case", group_outputs=True),
        Output(display_name="Else", name="default_result", method="default_response", group_outputs=True),
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
        self.received = getattr(self.input_value, "text", self.input_value)
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
        self.received: dict[str, object] = {}

    def run_merge(self) -> Message:
        self.did_run = True
        self.received = {
            "in1": getattr(self, "in1", None),
            "in2": getattr(self, "in2", None),
            "in3": getattr(self, "in3", None),
        }
        return Message(text="merged")


class ListMergeSink(Component):
    """Merge node with a single ``is_list=True`` input fed by several branches.

    Records exactly what landed in the list so a stray contribution from an excluded
    predecessor (the input's template default) is observable.
    """

    display_name = "List Merge Sink"
    name = "ListMergeSink"

    inputs = [HandleInput(name="items", display_name="Items", input_types=["Message"], is_list=True, required=False)]
    outputs = [Output(display_name="Out", name="out", method="run_merge")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.did_run = False
        self.received_items: list = []

    def run_merge(self) -> Message:
        self.did_run = True
        self.received_items = list(self.items or [])
        return Message(text="merged")


def _make_router(router_cls, routes, **extra):
    router = router_cls(_id="router")
    router.set(input_text="I love this product!", routes=routes, **extra)
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


async def test_unselected_branch_does_not_run_when_outputs_share_node_directly():
    """Regression for the exact shape in LE-1427 / Alice's report.

    Both router outputs connect *directly* to the same downstream node (no intermediate
    branch nodes): ``router.category_1_result -> shared.in1`` and
    ``router.category_2_result -> shared.in2``. The matched output feeds the shared node;
    the unselected output is excluded but must not stop the shared node from running once.

    This complements ``test_unselected_branch_does_not_run_when_branches_reconverge`` (which
    routes through intermediate nodes): here the router is the immediate predecessor of the
    merge, so the shared node is reachable from a sibling output of the *router itself*.
    """
    router = _make_router(_StubbedSmartRouter, _TWO_ROUTES)
    shared = MergeSink(_id="shared")

    graph = Graph()
    graph.add_component(router, "router")
    graph.add_component(shared, "shared")
    graph.add_component_edge("router", ("category_1_result", "in1"), "shared")
    graph.add_component_edge("router", ("category_2_result", "in2"), "shared")

    yielded = await _run(graph)

    assert shared.did_run is True, "Shared node should run once from the matched output"
    assert getattr(shared.received["in1"], "text", shared.received["in1"]) == "I love this product!"
    assert getattr(shared.received["in2"], "text", shared.received["in2"]) == ""
    assert "shared" in yielded


async def test_list_input_merge_excludes_unselected_branch_contribution():
    """A shared ``is_list=True`` input must not collect the excluded branch's template default.

    When both the selected and the unselected branch feed the same list input, the excluded
    predecessor is never built. Pulling a value for it would return the input's template
    default (an empty ``Message``/``""``) and inject a stray element next to the real one.
    Only the selected branch should contribute.
    """
    router = _make_router(_StubbedSmartRouter, _TWO_ROUTES)
    selected, unselected = RecordingSink(_id="selected"), RecordingSink(_id="unselected")
    merge = ListMergeSink(_id="merge")

    graph = Graph()
    graph.add_component(router, "router")
    graph.add_component(selected, "selected")
    graph.add_component(unselected, "unselected")
    graph.add_component(merge, "merge")
    graph.add_component_edge("router", ("category_1_result", "input_value"), "selected")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "unselected")
    graph.add_component_edge("selected", ("out", "items"), "merge")
    graph.add_component_edge("unselected", ("out", "items"), "merge")

    await _run(graph)

    assert selected.did_run is True
    assert unselected.did_run is False
    assert merge.did_run is True
    # Only the selected branch contributes: exactly one element, no stray template-default ''.
    texts = [getattr(item, "text", item) for item in merge.received_items]
    assert texts == ["ran:selected"], f"merge collected a stray element: {merge.received_items!r}"


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


async def test_else_branch_does_not_run_when_a_route_matches():
    """With ``enable_else_output=True`` and a matched route, the Else branch must not run.

    The ``default_result`` (Else) output feeds its own leaf. On a match the router excludes
    that branch: ``process_case`` appends ``default_result`` to its deactivation list and
    ``default_response`` also calls ``_deactivate_branches(["default_result"])``. Both paths
    run, so this guards the *aggregate* Else-exclusion behavior (the two paths are redundant,
    so it does not isolate either one). The Else leaf must stay unrun while the matched leaf
    and the merge node fed by the selected branch still run.
    """
    router = _make_router(_ElseSmartRouter, _TWO_ROUTES, enable_else_output=True)
    router.forced_category = "Positive"  # matches route 1 -> Else must be excluded

    selected, unselected = RecordingSink(_id="selected"), RecordingSink(_id="unselected")
    else_leaf = RecordingSink(_id="else_leaf")
    merge = MergeSink(_id="merge")

    graph = Graph()
    for comp, cid in (
        (router, "router"),
        (selected, "selected"),
        (unselected, "unselected"),
        (else_leaf, "else_leaf"),
        (merge, "merge"),
    ):
        graph.add_component(comp, cid)
    graph.add_component_edge("router", ("category_1_result", "input_value"), "selected")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "unselected")
    # The Else output feeds its own (dead-end) leaf.
    graph.add_component_edge("router", ("default_result", "input_value"), "else_leaf")
    # The selected branch reconverges with the (excluded) unselected branch on the merge node.
    graph.add_component_edge("selected", ("out", "in1"), "merge")
    graph.add_component_edge("unselected", ("out", "in2"), "merge")

    yielded = await _run(graph)

    assert selected.did_run is True
    assert unselected.did_run is False, "Unselected route branch executed despite the match"
    assert else_leaf.did_run is False, "Else branch executed despite a matched route"
    assert merge.did_run is True, "Merge node should execute from the selected branch"
    assert "else_leaf" not in yielded
    assert "merge" in yielded


async def test_else_branch_runs_when_no_route_matches():
    """With ``enable_else_output=True`` and no matched route, only the Else branch runs.

    Complements the match case: ``default_response`` takes its no-match path (returns the
    input as default) so the Else leaf runs, while every ``category_{i}_result`` branch is
    deactivated by ``process_case`` and stays unrun.
    """
    router = _make_router(_ElseSmartRouter, _TWO_ROUTES, enable_else_output=True)
    router.forced_category = "NONE"  # no route matches -> Else is the only live branch

    selected, unselected = RecordingSink(_id="selected"), RecordingSink(_id="unselected")
    else_leaf = RecordingSink(_id="else_leaf")

    graph = Graph()
    for comp, cid in (
        (router, "router"),
        (selected, "selected"),
        (unselected, "unselected"),
        (else_leaf, "else_leaf"),
    ):
        graph.add_component(comp, cid)
    graph.add_component_edge("router", ("category_1_result", "input_value"), "selected")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "unselected")
    graph.add_component_edge("router", ("default_result", "input_value"), "else_leaf")

    yielded = await _run(graph)

    assert else_leaf.did_run is True, "Else branch should run when no route matches"
    assert selected.did_run is False, "Route branch 1 should not run when no route matches"
    assert unselected.did_run is False, "Route branch 2 should not run when no route matches"
    assert "else_leaf" in yielded


def test_update_outputs_names_match_routing_contract():
    """Guard the output-name contract the routing logic relies on (category_{i}_result)."""
    component = SmartRouterComponent()
    frontend_node = component.update_outputs({"outputs": []}, "routes", _TWO_ROUTES)
    names = [o.name for o in frontend_node["outputs"]]
    assert names == ["category_1_result", "category_2_result"]


class _DecisionSmartRouter(SmartRouterComponent):
    outputs = _ElseSmartRouter.outputs


def _decision_graph(*, connected_else=True, **settings):
    router = _make_router(
        _DecisionSmartRouter,
        _TWO_ROUTES,
        routing_mode="Decision Model",
        decision_model=[{"name": "test-model", "provider": "Test"}],
        minimum_probability=0.7,
        enable_else_output=True,
    )
    router.set(**settings)
    graph = Graph()
    sinks = {name: RecordingSink(_id=name) for name in ("positive", "negative", "else")}
    graph.add_component(router, "router")
    for name, sink in sinks.items():
        graph.add_component(sink, name)
    graph.add_component_edge("router", ("category_1_result", "input_value"), "positive")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "negative")
    if connected_else:
        graph.add_component_edge("router", ("default_result", "input_value"), "else")
    return graph, router, sinks


def _decision_result(positive=0.8, negative=0.2):
    from lfx.base.models.decisions.schema import DecisionResult

    return DecisionResult(
        kind="choice",
        provider="Test",
        model="test-model",
        probabilities={"category_1_result": positive, "category_2_result": negative},
        selected_option="category_1_result" if positive > negative else "category_2_result",
    )


async def test_decision_router_evaluates_once_and_preserves_reconvergence(monkeypatch):
    calls = []

    def evaluate(request, **_kwargs):
        calls.append(request)
        return _decision_result()

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    graph, router, sinks = _decision_graph()
    merge = MergeSink(_id="merge")
    graph.add_component(merge, "merge")
    graph.add_component_edge("positive", ("out", "in1"), "merge")
    graph.add_component_edge("negative", ("out", "in2"), "merge")

    await _run(graph)

    assert len(calls) == 1
    assert sinks["positive"].did_run
    assert not sinks["negative"].did_run
    assert not sinks["else"].did_run
    assert merge.did_run
    assert router._decision_evidence["reason"] == "accepted"
    assert router._decision_evidence["activated_branch"] == "category_1_result"
    artifacts = router._artifacts
    assert any(artifact["raw"]["decision"]["result"]["model"] == "test-model" for artifact in artifacts.values())


async def test_decision_router_tie_and_below_threshold_use_else(monkeypatch):
    for probability, reason in ((0.5, "tied_top_probability"), (0.6, "below_minimum_probability")):
        monkeypatch.setattr(
            "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
            lambda *_args, p=probability, **_kwargs: _decision_result(p, 1 - p),
        )
        graph, router, sinks = _decision_graph()
        await _run(graph)
        assert sinks["else"].did_run
        assert not sinks["positive"].did_run
        assert not sinks["negative"].did_run
        assert router._decision_evidence["reason"] == reason


async def test_decision_router_applies_inclusive_top_route_override_only(monkeypatch):
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *_args, **_kwargs: _decision_result(0.7, 0.3),
    )
    for top_threshold, expected in ((0.7, "positive"), (0.8, "else")):
        routes = [
            {**_TWO_ROUTES[0], "minimum_probability": top_threshold},
            {**_TWO_ROUTES[1], "minimum_probability": 0.1},
        ]
        graph, router, sinks = _decision_graph(routes=routes)
        await _run(graph)
        assert sinks[expected].did_run
        assert not sinks["negative"].did_run
        assert router._decision_evidence["applied_threshold"] == top_threshold


async def test_decision_router_checks_real_else_before_inference(monkeypatch):
    import pytest

    calls = []
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *args, **_kwargs: calls.append(args),
    )
    for settings in ({"connected_else": False}, {"enable_else_output": False}):
        graph, _, _ = _decision_graph(**settings)
        with pytest.raises(Exception, match="Include Else Output on and its Else output connected"):
            await _run(graph)
    assert calls == []


async def test_decision_router_error_else_keeps_diagnostics(monkeypatch):
    from lfx.base.models.decisions.schema import DecisionEvaluationError

    def evaluate(*_args, **_kwargs):
        msg = "Provider timed out"
        raise DecisionEvaluationError(msg)

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    graph, router, sinks = _decision_graph(evaluation_error_action="Route to Else")
    await _run(graph)
    assert sinks["else"].did_run
    assert not sinks["positive"].did_run
    assert router._decision_evidence["reason"] == "evaluation_error"
    assert router._decision_evidence["error"]["message"] == "Provider timed out"


async def test_decision_router_permission_and_configuration_always_stop(monkeypatch):
    import pytest
    from lfx.base.models.decisions.schema import DecisionConfigurationError

    for error in (PermissionError("Denied by policy"), DecisionConfigurationError("Invalid model configuration")):

        def evaluate(*_args, error=error, **_kwargs):
            raise error

        monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
        graph, _, sinks = _decision_graph(evaluation_error_action="Route to Else")
        with pytest.raises(Exception, match=str(error)):
            await _run(graph)
        assert not any(sink.did_run for sink in sinks.values())


async def test_decision_router_reentry_resets_evaluation_and_evidence(monkeypatch):
    calls = []

    def evaluate(*args, **_kwargs):
        calls.append(args)
        return _decision_result(0.8, 0.2) if len(calls) == 1 else _decision_result(0.2, 0.8)

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    graph, router, sinks = _decision_graph()
    await _run(graph)
    assert sinks["positive"].did_run
    for sink in sinks.values():
        sink.did_run = False
    await _run(graph)
    assert len(calls) == 2
    assert sinks["negative"].did_run
    assert not sinks["positive"].did_run
    assert not sinks["else"].did_run
    assert router._decision_evidence["activated_branch"] == "category_2_result"


async def test_decision_router_refusal_uses_explicit_error_policy(monkeypatch):
    import pytest
    from lfx.base.models.decisions.schema import DecisionResult

    result = DecisionResult(
        kind="choice", provider="Test", model="test-model", status="refusal", refusal="Cannot evaluate this input"
    )
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision", lambda *_args, **_kwargs: result
    )
    graph, router, sinks = _decision_graph()
    with pytest.raises(Exception, match="declined to answer"):
        await _run(graph)
    assert not any(sink.did_run for sink in sinks.values())
    assert router._decision_evidence["activated_branch"] is None

    graph, router, sinks = _decision_graph(evaluation_error_action="Route to Else")
    await _run(graph)
    assert sinks["else"].did_run
    assert router._decision_evidence["reason"] == "refusal"
    assert router._decision_evidence["result"]["refusal"] == "Cannot evaluate this input"


async def test_decision_router_keeps_message_precedence(monkeypatch):
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *_args, **_kwargs: _decision_result(),
    )
    for override, route_value, expected in (("", "route text", "route text"), ("override", "route text", "override")):
        graph, router, _ = _decision_graph(
            routes=[{**_TWO_ROUTES[0], "output_value": route_value}, _TWO_ROUTES[1]], message=override
        )
        await _run(graph)
        assert router._results["category_1_result"].text == expected


async def test_decision_router_checks_else_in_imported_graph(monkeypatch):
    import pytest

    calls = []
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *args, **_kwargs: calls.append(args),
    )
    import inspect

    from lfx.components.llm_operations import llm_conditional_router

    for settings, error in (
        ({"connected_else": False}, "Include Else Output on and its Else output connected"),
        ({"minimum_probability": None}, "Enter a Minimum Probability"),
    ):
        graph, _, _ = _decision_graph(**settings)
        graph.prepare()
        payload = graph.dump()
        router_node = next(node for node in payload["data"]["nodes"] if node["id"] == "router")
        # Export the real built-in source, not the test-only subclass's containing module.
        template = router_node["data"]["node"]["template"]
        template["code"]["value"] = inspect.getsource(llm_conditional_router)
        for field in ("decision_model", "decision_question", "minimum_probability", "evaluation_error_action"):
            template[field].update(show=True, required=True)
        template["model"].update(value=None, show=False, required=False)
        imported = Graph.from_payload(payload)
        with pytest.raises(Exception, match=error):
            await _run(imported)
    assert not calls


async def test_valid_imported_decision_graph_requires_no_language_model(monkeypatch):
    import inspect

    from lfx.components.llm_operations import llm_conditional_router

    calls = []

    def evaluate(request, **_kwargs):
        calls.append(request)
        return _decision_result()

    # Imported built-in source binds its evaluator at execution time.
    monkeypatch.setattr("lfx.base.models.decisions.runtime.evaluate_decision", evaluate)
    graph, _, _ = _decision_graph()
    graph.prepare()
    payload = graph.dump()
    for node in payload["data"]["nodes"]:
        template = node["data"]["node"]["template"]
        if node["id"] == "router":
            template["code"]["value"] = inspect.getsource(llm_conditional_router)
            for field in ("decision_model", "decision_question", "minimum_probability", "evaluation_error_action"):
                template[field].update(show=True, required=True)
            template["model"].update(value=None, show=False, required=False)
        else:
            template["code"]["value"] = (
                "from lfx.custom import Component\n"
                "from lfx.io import MessageTextInput, Output\n"
                "from lfx.schema.message import Message\n\n" + inspect.getsource(RecordingSink)
            )
    imported = Graph.from_payload(payload)
    yielded = await _run(imported)
    assert len(calls) == 1
    assert "positive" in yielded
    assert "negative" not in yielded
    assert "else" not in yielded


async def test_decision_router_never_forwards_language_model_api_key(monkeypatch):
    seen = []

    def evaluate(_request, **kwargs):
        seen.append(kwargs)
        return _decision_result()

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    graph, _, _ = _decision_graph(api_key="language-model-key")  # pragma: allowlist secret
    await _run(graph)
    assert seen
    assert all(kwargs.get("api_key") is None for kwargs in seen)


async def test_decision_router_hard_failure_never_records_or_caches_else(monkeypatch):
    from types import SimpleNamespace

    import pytest

    def evaluate(*_args, **_kwargs):
        msg = "Denied by policy"
        raise PermissionError(msg)

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    _, router, _ = _decision_graph(evaluation_error_action="Route to Else")
    router._vertex = SimpleNamespace(
        outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
    )
    with pytest.raises(PermissionError):
        router._get_categorization()
    assert router._categorization_result is None
    assert router._decision_evidence["activated_branch"] is None
    assert router._decision_evidence["reason"] == "permission_denied"


def _connected_router(**settings):
    from types import SimpleNamespace

    _, router, _ = _decision_graph(**settings)
    router._vertex = SimpleNamespace(
        outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
    )
    return router


async def test_decision_router_accepts_a_route_with_no_description(monkeypatch):
    seen = []

    def evaluate(request, **_kwargs):
        seen.append(request)
        return _decision_result()

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    routes = [
        {"route_category": "Positive", "route_description": None, "output_value": ""},
        {"route_category": "Negative", "route_description": "bad", "output_value": ""},
    ]
    router = _connected_router(routes=routes)
    assert router._get_categorization() == "Positive"
    assert seen[0].options[0].description == ""


async def test_decision_router_requires_named_routes_before_inference(monkeypatch):
    import pytest
    from lfx.base.models.decisions.schema import DecisionConfigurationError

    calls = []
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *args, **_kwargs: calls.append(args),
    )
    routes = [{"route_category": "", "route_description": "x"}, {"route_category": "Negative"}]
    router = _connected_router(routes=routes)
    with pytest.raises(DecisionConfigurationError, match="Every route needs a Route Name"):
        router._get_categorization()
    assert not calls


async def test_decision_router_evidence_keeps_the_error_category(monkeypatch):
    from lfx.base.models.decisions.schema import DecisionEvaluationError

    def evaluate(*_args, **_kwargs):
        msg = "TypeSafe decision request timed out."
        raise DecisionEvaluationError(msg, category="timeout")

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    router = _connected_router(evaluation_error_action="Route to Else")
    assert router._get_categorization() == ""
    assert router._decision_evidence["error"] == {
        "category": "timeout",
        "message": "TypeSafe decision request timed out.",
    }
    assert router._decision_evidence["activated_branch"] == "default_result"


async def test_decision_router_needs_two_routes(monkeypatch):
    import pytest
    from lfx.base.models.decisions.schema import DecisionConfigurationError

    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *_args, **_kwargs: pytest.fail("inference must not run"),
    )
    router = _connected_router(routes=[{"route_category": "Positive", "route_description": "good"}])
    with pytest.raises(DecisionConfigurationError, match="Add at least two routes"):
        router._get_categorization()


_GAP_ROUTES = [
    {**_TWO_ROUTES[0], "route_id": "category_1_result"},
    {**_TWO_ROUTES[1], "route_id": "category_3_result"},
]


class _GapSmartRouter(_StubbedSmartRouter):
    """Outputs after the middle of three routes was deleted: the survivors keep their IDs."""

    outputs = [
        Output(display_name="Positive", name="category_1_result", method="process_case", group_outputs=True),
        Output(display_name="Negative", name="category_3_result", method="process_case", group_outputs=True),
        Output(display_name="Else", name="default_result", method="default_response", group_outputs=True),
    ]


def _gap_graph(router):
    graph = Graph()
    sinks = {name: RecordingSink(_id=name) for name in ("positive", "negative", "else")}
    graph.add_component(router, "router")
    for name, sink in sinks.items():
        graph.add_component(sink, name)
    graph.add_component_edge("router", ("category_1_result", "input_value"), "positive")
    graph.add_component_edge("router", ("category_3_result", "input_value"), "negative")
    graph.add_component_edge("router", ("default_result", "input_value"), "else")
    return graph, sinks


async def test_language_model_routing_follows_route_ids_not_positions():
    router = _make_router(_GapSmartRouter, _GAP_ROUTES, last_route_number=3, enable_else_output=True)
    router.forced_category = "Negative"
    graph, sinks = _gap_graph(router)

    await _run(graph)

    assert sinks["negative"].received == "I love this product!"
    assert not sinks["positive"].did_run
    assert not sinks["else"].did_run


async def test_routes_without_ids_keep_their_positional_outputs():
    """Rows sent without IDs, such as an API tweak written before route IDs, still route by position."""
    router = _make_router(_StubbedSmartRouter, _TWO_ROUTES, last_route_number=2)
    router.forced_category = "Negative"
    positive, negative = RecordingSink(_id="positive"), RecordingSink(_id="negative")
    graph = Graph()
    graph.add_component(router, "router")
    graph.add_component(positive, "positive")
    graph.add_component(negative, "negative")
    graph.add_component_edge("router", ("category_1_result", "input_value"), "positive")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "negative")

    await _run(graph)

    assert negative.received == "I love this product!"
    assert not positive.did_run


class _GapDecisionSmartRouter(SmartRouterComponent):
    outputs = _GapSmartRouter.outputs


async def test_decision_routing_follows_route_ids_not_positions(monkeypatch):
    from lfx.base.models.decisions.schema import DecisionResult

    asked = []

    def evaluate(request, **_kwargs):
        asked.append([option.id for option in request.options])
        return DecisionResult(
            kind="choice",
            provider="Test",
            model="test-model",
            probabilities={"category_1_result": 0.1, "category_3_result": 0.9},
            selected_option="category_3_result",
        )

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    router = _make_router(
        _GapDecisionSmartRouter,
        _GAP_ROUTES,
        last_route_number=3,
        routing_mode="Decision Model",
        decision_model=[{"name": "test-model", "provider": "Test"}],
        minimum_probability=0.7,
        enable_else_output=True,
    )
    graph, sinks = _gap_graph(router)

    await _run(graph)

    assert asked == [["category_1_result", "category_3_result"]]
    assert sinks["negative"].did_run
    assert not sinks["positive"].did_run
    assert not sinks["else"].did_run
    assert router._decision_evidence["activated_branch"] == "category_3_result"


class _BooleanSmartRouter(SmartRouterComponent):
    """Mirrors what ``update_outputs`` produces for a Boolean router: Yes, No and Else."""

    outputs = [
        Output(display_name="Yes", name="yes_result", method="process_case", group_outputs=True),
        Output(display_name="No", name="no_result", method="process_case", group_outputs=True),
        Output(display_name="Else", name="default_result", method="default_response", group_outputs=True),
    ]


@pytest.mark.parametrize(
    ("probability_true", "ran", "received"),
    [
        (0.9, "yes", "Refund team, here we come."),
        (0.1, "no", "I love this product!"),  # No has no message, so the input passes through
        (0.6, "else", "I love this product!"),
    ],
)
async def test_boolean_router_runs_only_the_answer_it_reaches(monkeypatch, probability_true, ran, received):
    from lfx.base.models.decisions.schema import DecisionResult

    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *_args, **_kwargs: DecisionResult(
            kind="boolean", provider="Test", model="test-model", probability_true=probability_true
        ),
    )
    router = _make_router(
        _BooleanSmartRouter,
        _TWO_ROUTES,  # left over from Choice, and ignored
        routing_mode="Decision Model",
        decision_model=[{"name": "test-model", "provider": "Test"}],
        decision_kind="Boolean",
        decision_question="Is the customer asking for a refund?",
        yes_message="Refund team, here we come.",
        minimum_probability=0.7,
        enable_else_output=True,
    )
    graph = Graph()
    sinks = {name: RecordingSink(_id=name) for name in ("yes", "no", "else")}
    graph.add_component(router, "router")
    for name, sink in sinks.items():
        graph.add_component(sink, name)
    graph.add_component_edge("router", ("yes_result", "input_value"), "yes")
    graph.add_component_edge("router", ("no_result", "input_value"), "no")
    graph.add_component_edge("router", ("default_result", "input_value"), "else")

    await _run(graph)

    assert [name for name, sink in sinks.items() if sink.did_run] == [ran]
    assert sinks[ran].received == received


class _ScoreSmartRouter(SmartRouterComponent):
    """Mirrors what ``update_outputs`` produces for a Score router with three levels, and Else."""

    outputs = [
        Output(display_name=name, name=f"level_{i}_result", method="process_case", group_outputs=True)
        for i, name in enumerate(("Low", "Medium", "High"), start=1)
    ] + [Output(display_name="Else", name="default_result", method="default_response", group_outputs=True)]


@pytest.mark.parametrize(("probabilities", "ran"), [((0.1, 0.4, 0.5), "medium"), ((0.0, 0.1, 0.9), "high")])
async def test_score_router_runs_only_the_level_its_score_rounds_to(monkeypatch, probabilities, ran):
    from lfx.base.models.decisions.schema import DecisionResult

    ids = [f"level_{i}_result" for i in (1, 2, 3)]
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *_args, **_kwargs: DecisionResult(
            kind="score",
            provider="Test",
            model="test-model",
            probabilities=dict(zip(ids, probabilities, strict=True)),
            score=sum(i * p for i, p in enumerate(probabilities)),
        ),
    )
    router = _make_router(
        _ScoreSmartRouter,
        _TWO_ROUTES,  # Choice's routes, which Score leaves alone
        routing_mode="Decision Model",
        decision_model=[{"name": "test-model", "provider": "Test"}],
        decision_kind="Score",
        decision_question="How urgent is this message?",
        score_levels=[
            {"route_category": name, "route_description": "", "output_value": ""} for name in ("Low", "Medium", "High")
        ],
        enable_else_output=True,
    )
    graph = Graph()
    sinks = {name: RecordingSink(_id=name) for name in ("low", "medium", "high", "else")}
    graph.add_component(router, "router")
    for name, sink in sinks.items():
        graph.add_component(sink, name)
    for level, name in zip(ids, ("low", "medium", "high"), strict=True):
        graph.add_component_edge("router", (level, "input_value"), name)
    graph.add_component_edge("router", ("default_result", "input_value"), "else")

    await _run(graph)

    assert [name for name, sink in sinks.items() if sink.did_run] == [ran]


async def test_a_boolean_tweak_on_a_routes_flow_stops_before_inference(monkeypatch):
    """Boolean's Yes and No outputs must be the saved ones, or every route branch would run."""
    import pytest

    calls = []
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *args, **_kwargs: calls.append(args),
    )
    graph, _, sinks = _decision_graph(decision_kind="Boolean", decision_question="Is this a refund?")
    with pytest.raises(Exception, match="outputs don't match its Decision Type"):
        await _run(graph)
    assert not calls
    assert not any(sink.did_run for sink in sinks.values())
