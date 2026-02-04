"""Tests for subgraph isolation to verify if create_subgraph provides sufficient state isolation.

These tests verify whether calling create_subgraph multiple times from the same parent graph
produces isolated subgraphs that don't share state from previous executions.
"""

import pytest
from lfx.components.input_output import ChatInput, ChatOutput, TextOutputComponent
from lfx.graph import Graph


class TestSubgraphIsolation:
    """Tests to verify subgraph state isolation."""

    @pytest.mark.asyncio
    async def test_create_subgraph_provides_fresh_state(self):
        """Test that calling create_subgraph multiple times gives fresh unbuilt state each time."""
        # Create a simple graph: chat_input -> text_output -> chat_output
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="test message")
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        parent_graph = Graph(chat_input, chat_output)

        # Create first subgraph with just text_output
        subgraph_vertex_ids = {"text_output"}

        # Use async context manager for subgraph1
        async with parent_graph.create_subgraph(subgraph_vertex_ids) as subgraph1:
            subgraph1.prepare()

            # Verify subgraph1 vertex is not built initially
            vertex1 = subgraph1.get_vertex("text_output")
            assert not vertex1.built, "Subgraph1 vertex should not be built initially"

            # Run the first subgraph
            async for _ in subgraph1.async_start():
                pass

            # Verify subgraph1 vertex is now built
            assert vertex1.built, "Subgraph1 vertex should be built after execution"

        # Create second subgraph from the SAME parent graph
        async with parent_graph.create_subgraph(subgraph_vertex_ids) as subgraph2:
            subgraph2.prepare()

            # Verify subgraph2 vertex is fresh (not built)
            vertex2 = subgraph2.get_vertex("text_output")
            assert not vertex2.built, "Subgraph2 vertex should not be built (should be fresh)"

            # Verify they are different vertex objects
            assert vertex1 is not vertex2, "Subgraph vertices should be different objects"

    @pytest.mark.asyncio
    async def test_create_subgraph_isolates_context(self):
        """Test that subgraph context modifications don't affect parent or other subgraphs."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="test")
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=chat_input.message_response)

        parent_graph = Graph(chat_input, chat_output, context={"shared_key": "original_value"})

        # Create first subgraph
        async with parent_graph.create_subgraph({"chat_input", "chat_output"}) as subgraph1:
            # Modify subgraph1's context
            subgraph1.context["shared_key"] = "modified_in_subgraph1"
            subgraph1.context["new_key"] = "new_value"

            # Create second subgraph (nested to allow comparison)
            async with parent_graph.create_subgraph({"chat_input", "chat_output"}) as subgraph2:
                # Verify parent context is unchanged
                assert parent_graph.context["shared_key"] == "original_value", (
                    "Parent context should not be modified by subgraph"
                )
                assert "new_key" not in parent_graph.context, "New key should not appear in parent context"

                # Verify subgraph2 has original context (shallow copy behavior)
                # Note: This tests if the context is properly copied
                assert subgraph2.context["shared_key"] == "original_value", (
                    "Subgraph2 should have original context value"
                )

    @pytest.mark.asyncio
    async def test_create_subgraph_isolates_run_state(self):
        """Test that subgraph run state (run_manager, queues) is isolated."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="test")
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)

        parent_graph = Graph(chat_input, text_output)

        subgraph_ids = {"chat_input", "text_output"}

        # Create and run first subgraph
        async with parent_graph.create_subgraph(subgraph_ids) as subgraph1:
            subgraph1.prepare()

            # Capture initial run queue
            initial_queue = list(subgraph1._run_queue)
            assert len(initial_queue) > 0, "Subgraph1 should have items in run queue after prepare"

            # Run subgraph1 to completion
            async for _ in subgraph1.async_start():
                pass

            # Run queue should be empty after completion
            assert len(subgraph1._run_queue) == 0, "Subgraph1 run queue should be empty after completion"

        # Create second subgraph
        async with parent_graph.create_subgraph(subgraph_ids) as subgraph2:
            subgraph2.prepare()

            # Subgraph2 should have fresh run queue
            assert len(subgraph2._run_queue) > 0, "Subgraph2 should have items in run queue (fresh state)"
            assert list(subgraph2._run_queue) == initial_queue, "Subgraph2 run queue should match initial state"

    @pytest.mark.asyncio
    async def test_create_subgraph_isolates_vertex_results(self):
        """Test that vertex results from one subgraph don't leak to another."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(input_value="first_message")
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)

        parent_graph = Graph(chat_input, text_output)
        subgraph_ids = {"chat_input", "text_output"}

        # Create and run first subgraph
        async with parent_graph.create_subgraph(subgraph_ids) as subgraph1:
            subgraph1.prepare()

            async for _ in subgraph1.async_start():
                pass

            # Get vertex from subgraph1
            vertex1 = subgraph1.get_vertex("text_output")

        # Create second subgraph
        async with parent_graph.create_subgraph(subgraph_ids) as subgraph2:
            subgraph2.prepare()

            # Verify subgraph2 vertex has no results yet
            vertex2 = subgraph2.get_vertex("text_output")
            assert vertex2.results == {}, "Subgraph2 vertex should have empty results initially"

            # Verify they are different result dictionaries
            assert vertex1.results is not vertex2.results, "Result dicts should be different objects"

    @pytest.mark.asyncio
    async def test_mutable_context_objects_are_shared(self):
        """Test that mutable objects in context ARE shared between subgraphs.

        This is intentional behavior - loop iterations need to share state through context.
        The shallow copy allows subgraphs to communicate via mutable context objects.
        """
        mutable_list = ["item1"]
        mutable_dict = {"key": "value"}

        chat_input = ChatInput(_id="chat_input")
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=chat_input.message_response)

        parent_graph = Graph(
            chat_input,
            chat_output,
            context={
                "mutable_list": mutable_list,
                "mutable_dict": mutable_dict,
            },
        )

        # Create first subgraph
        async with parent_graph.create_subgraph({"chat_input", "chat_output"}) as subgraph1:
            # Modify mutable objects in subgraph1's context
            subgraph1.context["mutable_list"].append("item2")
            subgraph1.context["mutable_dict"]["new_key"] = "new_value"

            # Create second subgraph (nested to allow comparison)
            async with parent_graph.create_subgraph({"chat_input", "chat_output"}) as subgraph2:
                # Mutable objects SHOULD be shared (intentional for loop state communication)
                assert subgraph2.context["mutable_list"] is subgraph1.context["mutable_list"], (
                    "Mutable list should be shared between subgraphs"
                )
                assert subgraph2.context["mutable_dict"] is subgraph1.context["mutable_dict"], (
                    "Mutable dict should be shared between subgraphs"
                )

                # Changes from subgraph1 should be visible in subgraph2
                assert "item2" in subgraph2.context["mutable_list"], "Subgraph2 should see item2 added by subgraph1"
                assert subgraph2.context["mutable_dict"]["new_key"] == "new_value", (
                    "Subgraph2 should see new_key added by subgraph1"
                )
