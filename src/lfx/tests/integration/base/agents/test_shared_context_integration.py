# ruff: noqa: PT018
"""Integration tests for multi-agent SharedContext collaboration.

These tests require:
- OPENAI_API_KEY environment variable
- langchain-openai package (install with: uv sync --group integration)
"""

import os
from unittest.mock import MagicMock

import pytest
from lfx.components.agent_blocks.agent_step import AgentStepComponent
from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
from lfx.components.agent_blocks.shared_context import SharedContextComponent
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.graph import Graph
from lfx.schema.message import Message

pytestmark = [pytest.mark.integration]


def build_agent_components(component_id_prefix: str):
    """Build and return agent components (while_loop, agent_step, execute_tool)."""
    while_loop = WhileLoopComponent(_id=f"{component_id_prefix}_while_loop")
    agent_step = AgentStepComponent(_id=f"{component_id_prefix}_agent_step")
    execute_tool = ExecuteToolComponent(_id=f"{component_id_prefix}_execute_tool")
    return while_loop, agent_step, execute_tool


def configure_agent(
    while_loop,
    agent_step,
    execute_tool,
    *,
    api_key: str,
    system_message: str,
    input_value: str,
    tools: list,
    max_iterations: int = 5,
):
    """Configure agent components with the given parameters."""
    while_loop.set(
        max_iterations=max_iterations,
        loop=execute_tool.execute_tools,
        input_value=input_value,
    )

    agent_step.set(
        model="gpt-4.1-nano",
        api_key=api_key,
        system_message=system_message,
        temperature=0.1,
        tools=tools,
        messages=while_loop.loop_output,
    )

    execute_tool.set(ai_message=agent_step.get_tool_calls, tools=tools)


async def run_agent_graph(while_loop, agent_step, *, context: dict | None = None, max_iterations: int = 5) -> Message:
    """Build and run an agent graph, returning the final message.

    Args:
        while_loop: The WhileLoop component
        agent_step: The AgentStep component
        context: Shared context dict that persists across agent runs
        max_iterations: Max iterations for the agent loop
    """
    # Build graph with shared context
    graph = Graph(start=while_loop, end=agent_step, context=context)

    async for _ in graph.async_start(
        max_iterations=max_iterations * 3,
        config={"output": {"cache": False}},
    ):
        pass

    output = agent_step.get_output_by_method(agent_step.get_ai_message)
    assert output is not None and hasattr(output, "value") and output.value is not None
    return output.value


def create_shared_context_with_context(component_id: str, shared_ctx: dict) -> SharedContextComponent:
    """Create a SharedContext component that uses a pre-existing context dict.

    Args:
        component_id: The component ID
        shared_ctx: The shared context dict to use

    Returns:
        A SharedContextComponent configured to use the shared context
    """
    shared_context = SharedContextComponent(_id=component_id)
    # Create a mock vertex that points to the shared context
    mock_vertex = MagicMock()
    mock_vertex.graph = MagicMock()
    mock_vertex.graph.context = shared_ctx
    shared_context._vertex = mock_vertex
    return shared_context


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestSharedContextMultiAgent:
    """Integration tests for multi-agent SharedContext collaboration."""

    @pytest.mark.asyncio
    async def test_two_agents_share_information(self):
        """Test that Agent 1 stores info and Agent 2 retrieves it.

        Scenario:
        - Agent 1 stores an arbitrary value using shared_context_write
        - Agent 2 reads it using shared_context_read and reports it

        Uses arbitrary made-up data that the model couldn't know on its own.
        """
        api_key = os.environ.get("OPENAI_API_KEY")

        # Create a shared context dict that persists across agent runs
        shared_ctx: dict = {}

        # Use arbitrary data that no LLM could know
        test_value = "XK7-PLUM-9382"  # pragma: allowlist secret

        # Create shared context component with access to shared context
        shared_context = create_shared_context_with_context("shared_ctx", shared_ctx)
        shared_context_tools = await shared_context.to_toolkit()

        # === Agent 1: Stores arbitrary code ===
        w1, a1, e1 = build_agent_components("agent1_writer")
        configure_agent(
            w1,
            a1,
            e1,
            api_key=api_key,
            system_message=(
                "You are a data entry agent. Use the shared_context_write tool to store "
                f"the following value with key 'test_data': '{test_value}'. "
                "Then say DONE."
            ),
            input_value="Store the test data.",
            tools=shared_context_tools,
        )

        result1 = await run_agent_graph(w1, a1, context=shared_ctx)
        assert isinstance(result1, Message)
        assert "done" in result1.text.lower() or "stored" in result1.text.lower()

        # Verify data was stored
        assert "shared_ctx:test_data" in shared_ctx, f"Expected key in context, got: {list(shared_ctx.keys())}"

        # === Agent 2: Reads and reports ===
        w2, a2, e2 = build_agent_components("agent2_reader")

        # Create new tools that point to same context
        shared_context2 = create_shared_context_with_context("shared_ctx2", shared_ctx)
        shared_context_tools2 = await shared_context2.to_toolkit()

        configure_agent(
            w2,
            a2,
            e2,
            api_key=api_key,
            system_message=(
                "You are a reporter. Use shared_context_read to get the value stored "
                "at key 'test_data'. Report the exact value you found."
            ),
            input_value="What is the test data value?",
            tools=shared_context_tools2,
        )

        result2 = await run_agent_graph(w2, a2, context=shared_ctx)
        assert isinstance(result2, Message)
        # Agent 2 must report the exact arbitrary value - proves it read from context
        assert test_value.lower() in result2.text.lower(), f"Expected '{test_value}' in response, got: {result2.text}"

        # Verify events were recorded - proves agents actually contacted shared context
        events = SharedContextComponent.get_events(shared_ctx)
        assert len(events) >= 2, f"Expected at least 2 events, got {len(events)}: {events}"

        # Check we have both write and read operations
        operations = [e["operation"] for e in events]
        assert "set" in operations, f"Expected 'set' operation in events: {operations}"
        assert "get" in operations, f"Expected 'get' operation in events: {operations}"

    @pytest.mark.asyncio
    async def test_three_agents_pr_review_workflow(self):
        """Test a PR review workflow with three agents.

        Scenario:
        - Agent 1 (PR Fetcher) stores PR data
        - Agent 2 (Code Reviewer) reads PR data, adds review to collection
        - Agent 3 (Aggregator) reads all reviews and summarizes
        """
        api_key = os.environ.get("OPENAI_API_KEY")

        # Create a shared context dict that persists across all agents
        shared_ctx: dict = {}

        # Create shared context with namespace for isolation
        shared_context = create_shared_context_with_context("pr_shared_ctx", shared_ctx)
        shared_context.set(namespace="pr_review")
        shared_context_tools = await shared_context.to_toolkit()

        # === Agent 1: PR Fetcher ===
        # Stores mock PR data
        w1, a1, e1 = build_agent_components("pr_fetcher")
        configure_agent(
            w1,
            a1,
            e1,
            api_key=api_key,
            system_message=(
                "You are a PR data fetcher. Use shared_context_write to store PR info "
                "with key 'pr_data'. Store this JSON as a string: "
                '\'{"title": "Add login feature", "files": ["auth.py", "login.html"]}\'. '
                "Then say DONE."
            ),
            input_value="Fetch and store the PR data.",
            tools=shared_context_tools,
        )

        result1 = await run_agent_graph(w1, a1, context=shared_ctx)
        assert isinstance(result1, Message)

        # === Agent 2: Code Reviewer ===
        # Reads PR data and adds a review
        shared_context2 = create_shared_context_with_context("pr_shared_ctx2", shared_ctx)
        shared_context2.set(namespace="pr_review")
        shared_context_tools2 = await shared_context2.to_toolkit()

        w2, a2, e2 = build_agent_components("code_reviewer")
        configure_agent(
            w2,
            a2,
            e2,
            api_key=api_key,
            system_message=(
                "You are a code reviewer. First use shared_context_read to get 'pr_data'. "
                "Then use shared_context_append to add your review to key 'reviews'. "
                "Your review should mention the files you saw. Then say DONE."
            ),
            input_value="Review the PR.",
            tools=shared_context_tools2,
        )

        result2 = await run_agent_graph(w2, a2, context=shared_ctx)
        assert isinstance(result2, Message)

        # === Agent 3: Aggregator ===
        # Reads all reviews and summarizes
        shared_context3 = create_shared_context_with_context("pr_shared_ctx3", shared_ctx)
        shared_context3.set(namespace="pr_review")
        shared_context_tools3 = await shared_context3.to_toolkit()

        w3, a3, e3 = build_agent_components("aggregator")
        configure_agent(
            w3,
            a3,
            e3,
            api_key=api_key,
            system_message=(
                "You are a review aggregator. Use shared_context_list to see what keys are available. "
                "Then use shared_context_read to get the 'reviews' collection. "
                "Summarize what the reviewers found in your response."
            ),
            input_value="Summarize all reviews.",
            tools=shared_context_tools3,
        )

        result3 = await run_agent_graph(w3, a3, context=shared_ctx)
        assert isinstance(result3, Message)
        # The aggregator should mention something from the reviews
        # At minimum, it should have found some reviews
        response_lower = result3.text.lower()
        assert "review" in response_lower or "auth" in response_lower or "login" in response_lower

    @pytest.mark.asyncio
    async def test_agent_discovers_available_data(self):
        """Test that an agent can discover what data is available.

        Scenario:
        - Seed some data manually
        - Agent uses shared_context_list to discover keys
        - Agent reports what it found
        """
        api_key = os.environ.get("OPENAI_API_KEY")

        # Create a shared context dict and seed it
        shared_ctx: dict = {}

        # Create and seed shared context
        shared_context = create_shared_context_with_context("discovery_ctx", shared_ctx)

        # Seed some data
        shared_context.set(key="task_instructions", operation="set", value="Process the data")
        await shared_context.execute()

        shared_context.set(key="input_data", operation="set", value="Sample input for processing")
        await shared_context.execute()

        shared_context.set(key="config", operation="set", value="debug=true")
        await shared_context.execute()

        # Get tools for agent
        shared_context_tools = await shared_context.to_toolkit()

        # === Agent: Data Explorer ===
        w1, a1, e1 = build_agent_components("data_explorer")
        configure_agent(
            w1,
            a1,
            e1,
            api_key=api_key,
            system_message=(
                "You are a data explorer. Use shared_context_list to discover what keys "
                "are available. Then read each key using shared_context_read and report "
                "a summary of all the data you found."
            ),
            input_value="What data is available in the shared context?",
            tools=shared_context_tools,
        )

        result = await run_agent_graph(w1, a1, context=shared_ctx)
        assert isinstance(result, Message)

        # Agent should mention some of the keys or their values
        response_lower = result.text.lower()
        found_keys = (
            "task" in response_lower
            or "input" in response_lower
            or "config" in response_lower
            or "debug" in response_lower
        )
        assert found_keys, f"Agent should have found seeded data, got: {result.text}"
