"""Tests for merge/combine nodes downstream of conditional branches.

Reproduces the fix for the flow-control bottleneck where merge nodes
block when a ConditionalRouter excludes one branch (issue #12994).
"""

import pytest
from lfx.components.flow_controls.conditional_router import (
    ConditionalRouterComponent,
)
from lfx.components.input_output import (
    ChatInput,
    ChatOutput,
    TextInputComponent,
    TextOutputComponent,
)
from lfx.components.processing.combine_text import CombineTextComponent
from lfx.graph import Graph


def test_conditional_router_excludes_branch_and_merge_node_proceeds():
    """E2E: ConditionalRouter evaluates True, excludes False branch.

    The merge (Combine Text) node receives input from the active True
    branch and a default for the excluded False branch. It must produce
    output instead of blocking.
    """
    text_input = TextInputComponent(_id="text_input")
    text_input.set(input_value="hello")

    router = ConditionalRouterComponent(_id="router", default_route="false_result")
    router.set(
        input_text=text_input.text_response,
        match_text="hello",
        operator="equals",
        true_case_message="HELLO_TRUE",
        false_case_message="SHOULD_NOT_APPEAR",
    )

    combine = CombineTextComponent(_id="combine")
    combine.set(
        text1=router.true_response,
        text2=router.false_response,
        delimiter="|",
    )

    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=combine.combine_texts)

    graph = Graph(text_input, text_output)

    results = list(graph.start(max_iterations=20, config={"output": {"cache": False}}))

    result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
    assert "text_output" in result_ids, f"Merge node blocked; results: {result_ids}"

    # The combine output should contain the true-branch message joined
    # with the default for the excluded false branch, separated by "|".
    text_output_vertex = graph.get_vertex("text_output")
    combined = text_output_vertex.built_result
    assert combined is not None, "Text output vertex has no built result"
    assert "HELLO_TRUE" in str(combined), f"Expected true-branch message in output, got: {combined!r}"


def test_conditional_router_excludes_branch_with_chat_io():
    """E2E: Same scenario using ChatInput/ChatOutput."""
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)

    router = ConditionalRouterComponent(_id="router", default_route="false_result")
    router.set(
        input_text=chat_input.message_response,
        match_text="hello",
        operator="equals",
        true_case_message="HELLO_TRUE",
        false_case_message="SHOULD_NOT_APPEAR",
    )

    combine = CombineTextComponent(_id="combine")
    combine.set(
        text1=router.true_response,
        text2=router.false_response,
    )

    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=combine.combine_texts)

    graph = Graph(chat_input, chat_output)

    results = list(graph.start(max_iterations=20, config={"output": {"cache": False}}))

    result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
    assert "chat_output" in result_ids, f"Merge node blocked; results: {result_ids}"


@pytest.mark.asyncio
async def test_component_vertex_get_result_returns_none_for_excluded_vertex():
    """Unit test: ComponentVertex._get_result returns None for excluded vertex.

    When a vertex is in conditionally_excluded_vertices, _get_result should
    return None rather than raising ValueError.
    """
    text_input = TextInputComponent(_id="text_input")
    text_input.set(input_value="test")

    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=text_input.text_response)

    graph = Graph(text_input, text_output)

    # Get the text_input vertex and mark it as conditionally excluded
    text_input_vertex = graph.get_vertex("text_input")
    graph.conditionally_excluded_vertices.add("text_input")

    # _get_result from a requester vertex should return None
    # instead of raising ValueError for an excluded vertex
    requester = graph.get_vertex("text_output")
    result = await text_input_vertex._get_result(requester=requester, target_handle_name="input_value")

    assert result is None, f"Expected None for conditionally excluded vertex, got {result!r}"
