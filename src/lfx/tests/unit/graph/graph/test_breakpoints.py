"""Tests for graph breakpoint functionality."""

import pytest
from lfx.components.input_output import ChatInput, ChatOutput, TextOutputComponent
from lfx.graph import Graph
from lfx.graph.graph.constants import Finish


class TestGraphBreakpoints:
    """Tests for graph breakpoint functionality."""

    def test_add_breakpoint(self):
        """Test adding a breakpoint to a graph."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        # Add breakpoint on chat_output
        graph.add_breakpoint("chat_output")

        assert "chat_output" in graph.breakpoints

    def test_remove_breakpoint(self):
        """Test removing a breakpoint from a graph."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        graph.add_breakpoint("chat_output")
        graph.remove_breakpoint("chat_output")

        assert "chat_output" not in graph.breakpoints

    def test_clear_breakpoints(self):
        """Test clearing all breakpoints."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        graph.add_breakpoint("chat_input")
        graph.add_breakpoint("text_output")
        graph.add_breakpoint("chat_output")

        graph.clear_breakpoints()

        assert len(graph.breakpoints) == 0

    def test_add_breakpoint_invalid_vertex_raises(self):
        """Test that adding a breakpoint on non-existent vertex raises ValueError."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        with pytest.raises(ValueError, match="vertex 'nonexistent' not found"):
            graph.add_breakpoint("nonexistent")

    @pytest.mark.asyncio
    async def test_execution_pauses_at_breakpoint(self):
        """Test that graph execution pauses when hitting a breakpoint."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Set breakpoint on text_output (middle of the graph)
        graph.add_breakpoint("text_output")

        # Run graph - should pause at text_output
        results = []
        async for result in graph.async_start():
            results.append(result)
            if graph.is_paused:
                break

        # Should have run chat_input but paused before text_output
        assert graph.is_paused
        assert len(results) == 1  # Only chat_input completed
        assert results[0].vertex.id == "chat_input"

    @pytest.mark.asyncio
    async def test_resume_after_breakpoint(self):
        """Test that graph can resume after hitting a breakpoint."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Set breakpoint on text_output
        graph.add_breakpoint("text_output")

        # Run until breakpoint
        results = []
        async for result in graph.async_start():
            results.append(result)
            if graph.is_paused:
                break

        assert graph.is_paused

        # Resume execution
        graph.resume()

        # Continue running
        results.extend([result async for result in graph.async_start()])

        # Should have completed
        assert results[-1] == Finish()
        assert not graph.is_paused

    @pytest.mark.asyncio
    async def test_breakpoint_provides_checkpoint(self):
        """Test that breakpoint provides a checkpoint for later resumption."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)
        graph.add_breakpoint("text_output")

        # Run until breakpoint
        async for _result in graph.async_start():
            if graph.is_paused:
                break

        # Get checkpoint at breakpoint
        checkpoint = graph.get_breakpoint_checkpoint()

        assert checkpoint is not None
        assert "run_manager" in checkpoint
        assert "queue" in checkpoint
        # The paused vertex should be in the queue
        assert "text_output" in checkpoint["queue"]

    @pytest.mark.asyncio
    async def test_multiple_breakpoints(self):
        """Test execution with multiple breakpoints."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Set breakpoints on both text_output and chat_output
        graph.add_breakpoint("text_output")
        graph.add_breakpoint("chat_output")

        # Run until first breakpoint (text_output)
        pause_count = 0

        # First run - should pause at text_output
        results = [result async for result in graph.async_start()]
        assert graph.is_paused
        pause_count += 1

        # Resume and continue - should pause at chat_output
        graph.resume()
        results.extend([result async for result in graph.async_start()])
        assert graph.is_paused
        pause_count += 1

        # Resume and finish
        graph.resume()
        results.extend([result async for result in graph.async_start()])

        # Should have paused twice (at text_output and chat_output)
        assert pause_count == 2
        assert results[-1] == Finish()

    @pytest.mark.asyncio
    async def test_breakpoint_on_first_vertex(self):
        """Test breakpoint on the first vertex."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)

        # Breakpoint on first vertex
        graph.add_breakpoint("chat_input")

        # Should pause immediately
        async for _result in graph.async_start():
            if graph.is_paused:
                break

        assert graph.is_paused
        # chat_input should be in queue (not yet executed)
        checkpoint = graph.get_breakpoint_checkpoint()
        assert "chat_input" in checkpoint["queue"]

    @pytest.mark.asyncio
    async def test_no_breakpoint_runs_to_completion(self):
        """Test that graph without breakpoints runs to completion."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # No breakpoints - should run to completion
        results = [result async for result in graph.async_start()]

        assert results[-1] == Finish()
        assert not graph.is_paused

    @pytest.mark.asyncio
    async def test_breakpoint_on_last_vertex(self):
        """Test breakpoint on the last vertex."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Breakpoint on last vertex
        graph.add_breakpoint("chat_output")

        # Run until breakpoint
        results = [result async for result in graph.async_start()]

        assert graph.is_paused
        # chat_input and text_output completed, chat_output waiting
        assert len(results) == 2
        assert results[0].vertex.id == "chat_input"
        assert results[1].vertex.id == "text_output"

        # Resume to complete
        graph.resume()
        results.extend([result async for result in graph.async_start()])

        assert results[-1] == Finish()
        assert not graph.is_paused

    @pytest.mark.asyncio
    async def test_remove_breakpoint_while_paused(self):
        """Test removing a breakpoint while paused at a different one."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)

        # Set breakpoints on both
        graph.add_breakpoint("text_output")
        graph.add_breakpoint("chat_output")

        # Run until first breakpoint
        async for _ in graph.async_start():
            pass
        assert graph.is_paused

        # Remove the upcoming breakpoint while paused
        graph.remove_breakpoint("chat_output")

        # Resume - should run to completion without hitting chat_output breakpoint
        graph.resume()
        results = [result async for result in graph.async_start()]

        assert results[-1] == Finish()
        assert not graph.is_paused

    @pytest.mark.asyncio
    async def test_multiple_sequential_resumes(self):
        """Test that state is clean after multiple pause/resume cycles."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)
        graph.add_breakpoint("text_output")

        # First run - pause at text_output
        async for _ in graph.async_start():
            pass
        assert graph.is_paused

        # Resume and complete
        graph.resume()
        results = [result async for result in graph.async_start()]
        assert results[-1] == Finish()

        # Start fresh run - breakpoint should work again
        async for _ in graph.async_start():
            pass
        assert graph.is_paused

        # Resume again
        graph.resume()
        results = [result async for result in graph.async_start()]
        assert results[-1] == Finish()


class TestBreakpointErrorHandling:
    """Tests for breakpoint error handling and state cleanup."""

    @pytest.mark.asyncio
    async def test_exception_cleans_up_breakpoint_state(self):
        """Test that exceptions during execution clean up breakpoint state."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        text_output = TextOutputComponent(_id="text_output")
        text_output.set(input_value=chat_input.message_response)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=text_output.text_response)

        graph = Graph(chat_input, chat_output)
        graph.add_breakpoint("text_output")

        # Run until breakpoint
        async for _ in graph.async_start():
            pass
        assert graph.is_paused

        # Set up state that would persist after resume
        graph.resume()
        assert graph._is_resuming

        # Trigger a max_iterations error (set to 0 to trigger immediately)
        with pytest.raises(ValueError, match="Max iterations"):
            async for _ in graph.async_start(max_iterations=0):
                pass

        # Verify breakpoint state was cleaned up despite exception
        assert not graph._is_paused
        assert graph._breakpoint_checkpoint is None
        assert graph._skip_breakpoint_for is None
        assert not graph._is_resuming

    @pytest.mark.asyncio
    async def test_resume_with_empty_queue_is_safe(self):
        """Test that resume() handles empty queue gracefully."""
        chat_input = ChatInput(_id="chat_input")
        chat_input.set(should_store_message=False)
        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(sender_name=chat_input.message_response)

        graph = Graph(chat_input, chat_output)
        graph.add_breakpoint("chat_input")

        # Manually set paused state with empty queue (edge case)
        graph._is_paused = True
        graph._run_queue.clear()

        # resume() should not raise even with empty queue
        graph.resume()

        # State should be cleared
        assert not graph._is_paused
        assert graph._is_resuming
        assert graph._skip_breakpoint_for is None
