"""Unit tests for the BaseExecutor shared functionality."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from langflow_stepflow.worker.base_executor import BaseExecutor


class ConcreteTestExecutor(BaseExecutor):
    """Concrete implementation of BaseExecutor for testing."""

    async def _instantiate_component(
        self,
        component_info: dict[str, Any],
    ) -> tuple[Any, str]:
        """Test implementation that just returns the info as-is."""
        return component_info.get("instance"), component_info.get("name", "test")


@pytest.fixture
def executor():
    """Create a ConcreteTestExecutor instance for testing base functionality."""
    return ConcreteTestExecutor()


class TestBaseExecutorDetermineExecutionMethod:
    """Tests for _determine_execution_method in BaseExecutor."""

    def test_with_selected_output_match(self, executor):
        """Test finding method for matching selected_output."""
        outputs = [
            {"name": "text", "method": "text_response"},
            {"name": "message", "method": "build_message"},
        ]
        result = executor._determine_execution_method(outputs, "message")
        assert result == "build_message"

    def test_fallback_to_first(self, executor):
        """Test fallback to first output's method."""
        outputs = [
            {"name": "default", "method": "default_method"},
            {"name": "other", "method": "other_method"},
        ]
        result = executor._determine_execution_method(outputs, None)
        assert result == "default_method"

    def test_empty_outputs(self, executor):
        """Test with empty outputs list."""
        result = executor._determine_execution_method([], None)
        assert result is None

    def test_selected_not_found_fallback(self, executor):
        """Test fallback when selected_output doesn't match."""
        outputs = [{"name": "text", "method": "text_method"}]
        result = executor._determine_execution_method(outputs, "nonexistent")
        assert result == "text_method"


class TestBaseExecutorApplyInputDefaults:
    """Tests for _apply_component_input_defaults in BaseExecutor."""

    def test_no_inputs_attribute(self, executor):
        """Test with component that has no inputs attribute."""
        component = MagicMock(spec=[])  # No inputs attribute
        params = {"key": "value"}
        result = executor._apply_component_input_defaults(component, params)
        assert result == {"key": "value"}

    def test_adds_missing_defaults(self, executor):
        """Test that defaults are added for missing parameters."""
        input_def = MagicMock()
        input_def.name = "temperature"
        input_def.value = 0.7

        component = MagicMock()
        component.inputs = [input_def]

        params = {"model": "gpt-4"}
        result = executor._apply_component_input_defaults(component, params)
        assert result == {"model": "gpt-4", "temperature": 0.7}

    def test_preserves_existing_values(self, executor):
        """Test that existing params are not overwritten."""
        input_def = MagicMock()
        input_def.name = "temperature"
        input_def.value = 0.7

        component = MagicMock()
        component.inputs = [input_def]

        params = {"temperature": 0.9}  # Already set
        result = executor._apply_component_input_defaults(component, params)
        assert result == {"temperature": 0.9}  # Original preserved


class TestBaseExecutorApplyOutputHandlers:
    """Tests for _apply_output_handlers in BaseExecutor."""

    @pytest.mark.asyncio
    async def test_serializes_lfx_dataframe(self, executor):
        """Test that lfx DataFrames are serialized by the handler chain."""
        from lfx.schema.dataframe import DataFrame

        df = DataFrame(data=[{"text": "row1", "url": "http://example.com"}])
        handlers = executor._get_output_handlers()
        result = await executor._apply_output_handlers(df, handlers)

        assert isinstance(result, dict)
        assert result["__langflow_type__"] == "DataFrame"
        assert "json_data" in result

    @pytest.mark.asyncio
    async def test_serializes_plain_pandas_dataframe(self, executor):
        """Plain pandas DataFrames must also serialize (issue #673).

        Components compiled from flow JSON blobs may produce plain pandas
        DataFrames instead of lfx DataFrames.
        """
        import pandas as pd

        pdf = pd.DataFrame([{"text": "row1", "url": "http://example.com"}])
        handlers = executor._get_output_handlers()
        result = await executor._apply_output_handlers(pdf, handlers)

        assert isinstance(result, dict)
        assert result["__langflow_type__"] == "DataFrame"
        assert "json_data" in result

    @pytest.mark.asyncio
    async def test_serializes_message(self, executor):
        """Test that Messages are serialized correctly."""
        from lfx.schema.message import Message

        msg = Message(text="hello")
        handlers = executor._get_output_handlers()
        result = await executor._apply_output_handlers(msg, handlers)

        assert isinstance(result, dict)
        assert result["__langflow_type__"] == "Message"
        assert result["text"] == "hello"

    @pytest.mark.asyncio
    async def test_passes_through_primitives(self, executor):
        """Test that primitive values pass through unchanged."""
        handlers = executor._get_output_handlers()
        assert await executor._apply_output_handlers("hello", handlers) == "hello"
        assert await executor._apply_output_handlers(42, handlers) == 42
        assert await executor._apply_output_handlers(None, handlers) is None

    @pytest.mark.asyncio
    async def test_recurses_into_dicts(self, executor):
        """Test that dicts are recursed into."""
        handlers = executor._get_output_handlers()
        result = await executor._apply_output_handlers(
            {"key": "value", "count": 42}, handlers
        )
        assert result == {"key": "value", "count": 42}

    @pytest.mark.asyncio
    async def test_raises_on_unknown_type(self, executor):
        """Test that unknown types raise ValueError."""
        handlers = executor._get_output_handlers()
        with pytest.raises(ValueError, match="Cannot serialize object of type"):
            await executor._apply_output_handlers(object(), handlers)


class TestBaseExecutorSetupGraphContext:
    """Tests for _setup_graph_context in BaseExecutor."""

    def test_sets_graph_context(self, executor):
        """Test that graph context is set correctly."""
        component = MagicMock()
        component.__dict__ = {}

        executor._setup_graph_context(component, "test-session-id")

        assert "graph" in component.__dict__
        assert component.__dict__["graph"].session_id == "test-session-id"
        assert component.__dict__["graph"].vertices == []
        assert component.__dict__["graph"].flow_id is None
