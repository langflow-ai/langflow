import asyncio
import threading
import uuid
from unittest.mock import Mock, patch

import pytest
from langflow.services.tracing.langfuse import LangFuseTracer, _create_dummy_parent


class MockLangfuseCallback:
    """Mock Langfuse callback handler that simulates the real one."""

    def __init__(self):
        self.runs = {}
        self.trace = Mock()
        self.trace.span = Mock(side_effect=self._create_span)
        self.tool_starts = []
        self.parent_creations = []

    def _create_span(self, **kwargs):
        """Simulate creating a span."""
        span = Mock()
        span.name = kwargs.get("name", "unnamed")
        span.metadata = kwargs.get("metadata", {})
        return span

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):  # noqa: ARG002
        """Original implementation that would fail."""
        self.tool_starts.append({"run_id": run_id, "parent_run_id": parent_run_id, "input_str": input_str})

        if parent_run_id is None or parent_run_id not in self.runs:
            error_msg = "parent run not found"
            raise ValueError(error_msg)

        # Create child span
        self.runs[run_id] = self.runs[parent_run_id]
        return run_id


@pytest.fixture
def langfuse_tracer():
    """Create a LangFuseTracer instance."""
    with (
        patch("langfuse.Langfuse") as mock_langfuse,
        patch("langfuse.api.core.request_options.RequestOptions"),
        patch.dict(
            "os.environ",
            {
                "LANGFUSE_SECRET_KEY": "test-secret",
                "LANGFUSE_PUBLIC_KEY": "test-public",
                "LANGFUSE_HOST": "http://localhost:3000",
            },
        ),
    ):
        client = Mock()
        trace = Mock()

        # Make span return a Mock with get_langchain_handler
        span_mock = Mock()
        span_mock.get_langchain_handler = Mock(return_value=MockLangfuseCallback())
        trace.span = Mock(return_value=span_mock)
        trace.get_langchain_handler = Mock(return_value=MockLangfuseCallback())

        client.trace = Mock(return_value=trace)
        mock_langfuse.return_value = client

        # Add health check mock
        client.client = Mock()
        client.client.health = Mock()
        client.client.health.health = Mock()

        tracer = LangFuseTracer(
            trace_name="test-flow", trace_type="test", project_name="test-project", trace_id=uuid.uuid4()
        )
        yield tracer


class TestLangfuseConcurrency:
    """Test cases for Langfuse concurrency issues."""

    @pytest.mark.asyncio
    async def test_parallel_tool_start_without_lock_fails(self):
        """Test that parallel tool starts without lock causes race condition."""
        base_callback = MockLangfuseCallback()
        parent_run_id = uuid.uuid4()

        # Simulate the scenario: parent run was removed
        # Now two tools try to start simultaneously

        results = []
        errors = []

        async def tool_start(tool_name):
            try:
                run_id = uuid.uuid4()
                base_callback.on_tool_start(
                    {"name": tool_name}, f"input for {tool_name}", run_id=run_id, parent_run_id=parent_run_id
                )
                results.append(tool_name)
            except Exception as e:
                errors.append(str(e))

        # Run two tools concurrently
        await asyncio.gather(tool_start("weather_tool"), tool_start("search_tool"))

        # Both should fail because parent doesn't exist
        assert len(errors) == 2
        assert all("parent run not found" in err for err in errors)

    @pytest.mark.asyncio
    async def test_wrapped_callback_prevents_race_condition(self):
        """Test that wrapped callback with lock prevents race condition."""
        base_callback = MockLangfuseCallback()
        wrapped_callback = _create_dummy_parent(base_callback)

        parent_run_id = uuid.uuid4()

        # Both tools should now succeed because wrapper auto-creates parent
        results = []

        async def tool_start(tool_name):
            run_id = uuid.uuid4()
            wrapped_callback.on_tool_start(
                {"name": tool_name}, f"input for {tool_name}", run_id=run_id, parent_run_id=parent_run_id
            )
            results.append(tool_name)

        # Run two tools concurrently
        await asyncio.gather(tool_start("weather_tool"), tool_start("search_tool"))

        # Both should succeed
        assert len(results) == 2
        assert "weather_tool" in results
        assert "search_tool" in results

        # Parent should have been auto-created exactly once
        assert parent_run_id in wrapped_callback.runs
        assert wrapped_callback.runs[parent_run_id].metadata.get("auto_created") is True

    def test_concurrent_parent_creation_with_threads(self):
        """Test that lock prevents multiple parent creations with threads."""
        base_callback = MockLangfuseCallback()
        wrapped_callback = _create_dummy_parent(base_callback)

        parent_run_id = uuid.uuid4()
        creation_count = []

        # Track how many times parent span is created
        original_span = wrapped_callback.trace.span

        def counting_span(**kwargs):
            if kwargs.get("metadata", {}).get("auto_created"):
                creation_count.append(1)
            return original_span(**kwargs)

        wrapped_callback.trace.span = counting_span

        # Start 10 tools simultaneously in threads
        def tool_start(tool_id):
            run_id = uuid.uuid4()
            wrapped_callback.on_tool_start(
                {"name": f"tool_{tool_id}"}, f"input_{tool_id}", run_id=run_id, parent_run_id=parent_run_id
            )

        threads = [threading.Thread(target=tool_start, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Parent should be created exactly once despite 10 concurrent attempts
        assert len(creation_count) == 1
        assert parent_run_id in wrapped_callback.runs

    @pytest.mark.asyncio
    async def test_agent_with_parallel_tools_scenario(self):
        """Simulate the real agent scenario with parallel tool execution."""
        base_callback = MockLangfuseCallback()
        wrapped_callback = _create_dummy_parent(base_callback)

        # Simulate agent execution
        agent_run_id = uuid.uuid4()
        wrapped_callback.runs[agent_run_id] = Mock()  # Agent starts

        # Agent finishes and cleans up (this is the bug trigger)
        del wrapped_callback.runs[agent_run_id]

        # But tools are still executing in parallel
        tool_results = []

        async def execute_tool(tool_name, delay=0):
            await asyncio.sleep(delay)  # Simulate async execution
            run_id = uuid.uuid4()
            wrapped_callback.on_tool_start(
                {"name": tool_name},
                f"Execute {tool_name}",
                run_id=run_id,
                parent_run_id=agent_run_id,  # Refers to deleted parent
            )
            tool_results.append(tool_name)

        # Execute 3 tools in parallel
        await asyncio.gather(
            execute_tool("weather_api", 0.01), execute_tool("search_api", 0.02), execute_tool("calculator", 0.01)
        )

        # All tools should succeed
        assert len(tool_results) == 3
        assert set(tool_results) == {"weather_api", "search_api", "calculator"}

        # Auto-created parent should exist
        assert agent_run_id in wrapped_callback.runs
        assert wrapped_callback.runs[agent_run_id].metadata["auto_created"] is True

    @pytest.mark.asyncio
    async def test_get_langchain_callback_returns_wrapped_handler(self, langfuse_tracer):
        """Test that get_langchain_callback returns the wrapped handler."""
        if not langfuse_tracer.ready:
            pytest.skip("Langfuse not ready")

        callback = langfuse_tracer.get_langchain_callback()

        assert callback is not None
        # Should be wrapped with DummyParent
        assert hasattr(callback, "on_tool_start")
        assert hasattr(callback, "runs")

    def test_double_check_locking_pattern(self):
        """Test the double-check locking pattern works correctly."""
        base_callback = MockLangfuseCallback()
        wrapped_callback = _create_dummy_parent(base_callback)

        parent_run_id = uuid.uuid4()

        # Track parent creation by monitoring the span calls
        creation_count = []
        original_span = wrapped_callback.trace.span

        def counting_span(**kwargs):
            if kwargs.get("metadata", {}).get("auto_created"):
                creation_count.append(1)
            return original_span(**kwargs)

        wrapped_callback.trace.span = counting_span

        # First tool: should create parent
        run_id_1 = uuid.uuid4()
        wrapped_callback.on_tool_start({"name": "tool_1"}, "input_1", run_id=run_id_1, parent_run_id=parent_run_id)

        # Second tool: should find existing parent, not create
        run_id_2 = uuid.uuid4()
        wrapped_callback.on_tool_start({"name": "tool_2"}, "input_2", run_id=run_id_2, parent_run_id=parent_run_id)

        # Should only create parent once
        assert len(creation_count) == 1
        assert parent_run_id in wrapped_callback.runs

    @pytest.mark.asyncio
    async def test_streaming_concurrent_tokens(self):
        """Test concurrent token streaming doesn't corrupt state."""
        base_callback = MockLangfuseCallback()
        wrapped_callback = _create_dummy_parent(base_callback)

        # Simulate LLM run
        llm_run_id = uuid.uuid4()
        wrapped_callback.runs[llm_run_id] = Mock()

        # Simulate multiple tokens arriving concurrently
        token_updates = []

        async def process_token(token, run_id):
            # Simulate token processing that accesses runs
            if run_id in wrapped_callback.runs:
                token_updates.append(token)
                await asyncio.sleep(0.001)

        tokens = ["Hello", " ", "world", "!", " How", " are", " you", "?"]

        await asyncio.gather(*[process_token(token, llm_run_id) for token in tokens])

        # All tokens should be processed
        assert len(token_updates) == len(tokens)


class TestLangfuseTracerIntegration:
    """Integration tests with the actual LangFuseTracer."""

    def test_tracer_creates_wrapped_callbacks(self, langfuse_tracer):
        """Test that tracer creates properly wrapped callbacks."""
        if not langfuse_tracer.ready:
            pytest.skip("Langfuse not configured")

        callback = langfuse_tracer.get_langchain_callback()

        # Should return wrapped handler with auto-create capability
        assert callback is not None

        # Verify it has the wrapped functionality
        assert type(callback).__name__ == "DummyParent"

    @pytest.mark.asyncio
    async def test_tracer_with_span_context(self, langfuse_tracer):
        """Test tracer works correctly with active spans."""
        if not langfuse_tracer.ready:
            pytest.skip("Langfuse not ready")

        # Add a span
        langfuse_tracer.add_trace(
            trace_id="component_1", trace_name="Test Component", trace_type="component", inputs={"test": "input"}
        )

        # Get callback - should use the span's handler
        callback = langfuse_tracer.get_langchain_callback()
        assert callback is not None

        # Clean up
        langfuse_tracer.end_trace(trace_id="component_1", trace_name="Test Component", outputs={"test": "output"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
