import pytest
from lfx.components.flow_controls.conditional_router import ConditionalRouterComponent
from lfx.components.input_output import TextOutputComponent
from lfx.components.input_output.text import TextInputComponent
from lfx.graph.graph.base import Graph


async def _run_router_graph(
    *,
    input_value: str,
    match_text: str,
    default_route: str,
    true_case_message: str = "",
    false_case_message: str = "",
) -> dict[str, str]:
    text_input = TextInputComponent(_id="text_input").set(input_value=input_value)
    router = ConditionalRouterComponent(_id="router").set(
        input_text=text_input.text_response,
        match_text=match_text,
        operator="equals",
        true_case_message=true_case_message,
        false_case_message=false_case_message,
        max_iterations=1,
        default_route=default_route,
    )
    true_output = TextOutputComponent(_id="true_output").set(input_value=router.true_response)
    false_output = TextOutputComponent(_id="false_output").set(input_value=router.false_response)
    graph = Graph(text_input, true_output)
    graph.add_component(false_output)
    graph.add_component_edge("router", ("false_result", "input_value"), "false_output")

    built: dict[str, str] = {}
    async for result in graph.async_start(config={"output": {"cache": False}}):
        vertex = getattr(result, "vertex", None)
        if vertex is not None and vertex.id in {"true_output", "false_output"}:
            built[vertex.id] = vertex.built_object["text"].data["text"]
    return built


@pytest.mark.parametrize(
    ("default_route", "input_value", "kwargs", "expected_vertex", "expected_text"),
    [
        ("true_result", "no", {"true_case_message": "fallback true"}, "true_output", "fallback true"),
        ("false_result", "yes", {"false_case_message": "fallback false"}, "false_output", "fallback false"),
        ("true_result", "no", {}, "true_output", "no"),
        ("false_result", "yes", {}, "false_output", "yes"),
    ],
)
async def test_should_route_case_message_to_default_route_when_max_iterations_is_reached(
    default_route, input_value, kwargs, expected_vertex, expected_text
):
    built = await _run_router_graph(input_value=input_value, match_text="yes", default_route=default_route, **kwargs)

    assert built == {expected_vertex: expected_text}


@pytest.mark.parametrize(
    ("input_value", "expected_vertex", "expected_text"),
    [
        ("yes", "true_output", "fallback true"),
        ("no", "false_output", "fallback false"),
    ],
)
async def test_should_follow_condition_when_it_already_matches_the_default_route(
    input_value, expected_vertex, expected_text
):
    default_route = "true_result" if expected_vertex == "true_output" else "false_result"

    built = await _run_router_graph(
        input_value=input_value,
        match_text="yes",
        default_route=default_route,
        true_case_message="fallback true",
        false_case_message="fallback false",
    )

    assert built == {expected_vertex: expected_text}


async def test_should_deliver_true_case_message_when_a_cycle_hits_max_iterations():
    text_input = TextInputComponent(_id="text_input")
    router = ConditionalRouterComponent(_id="router").set(
        input_text=text_input.text_response,
        match_text="never",
        operator="equals",
        true_case_message="loop finished",
        max_iterations=3,
        default_route="true_result",
    )
    text_input.set(input_value=router.false_response)
    true_output = TextOutputComponent(_id="true_output").set(input_value=router.true_response)
    graph = Graph(text_input, true_output)

    texts = [
        result.vertex.built_object["text"].data["text"]
        async for result in graph.async_start(max_iterations=20, config={"output": {"cache": False}})
        if getattr(result, "vertex", None) is not None and result.vertex.id == "true_output"
    ]

    assert graph.context.get("router_iteration") == 3
    assert texts == ["loop finished"]
