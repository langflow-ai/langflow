"""Tests for flow execution module.

Tests FlowExecutionResult, extract_response_text, _run_graph_with_events,
execute_flow_file, execute_flow_file_streaming, and module constants.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from langflow.agentic.services.flow_executor import (
    _run_graph_with_events,
    execute_flow_file,
    execute_flow_file_streaming,
    extract_response_text,
)
from langflow.agentic.services.flow_types import (
    FLOWS_BASE_PATH,
    STREAMING_EVENT_TIMEOUT_SECONDS,
    STREAMING_QUEUE_MAX_SIZE,
    FlowExecutionResult,
)
from langflow.agentic.services.helpers.event_consumer import parse_event_data

MODULE = "langflow.agentic.services.flow_executor"


class TestFlowExecutionResult:
    """Tests for FlowExecutionResult dataclass."""

    def test_should_create_with_defaults(self):
        """Should create with default empty values."""
        result = FlowExecutionResult()

        assert result.result == {}
        assert result.error is None
        assert result.has_error is False
        assert result.has_result is False

    def test_should_detect_error(self):
        """Should detect when error is set."""
        result = FlowExecutionResult(error=ValueError("test"))

        assert result.has_error is True
        assert result.has_result is False

    def test_should_detect_result(self):
        """Should detect when result is set."""
        result = FlowExecutionResult(result={"key": "value"})

        assert result.has_result is True
        assert result.has_error is False

    def test_should_allow_both_result_and_error(self):
        """Should allow both result and error to be set."""
        result = FlowExecutionResult(result={"partial": "data"}, error=ValueError("partial failure"))

        assert result.has_result is True
        assert result.has_error is True


class TestExtractResponseText:
    """Tests for extract_response_text function."""

    def test_should_extract_from_result_key(self):
        """Should extract text from 'result' key."""
        data = {"result": "Hello, world!"}
        result = extract_response_text(data)
        assert result == "Hello, world!"

    def test_should_extract_from_text_key(self):
        """Should extract text from 'text' key when result not present."""
        data = {"text": "Hello from text key"}
        result = extract_response_text(data)
        assert result == "Hello from text key"

    def test_should_extract_from_exception_message(self):
        """Should extract exception message."""
        data = {"exception_message": "Error occurred"}
        result = extract_response_text(data)
        assert result == "Error occurred"

    def test_should_prefer_result_over_text(self):
        """Should prefer 'result' key over 'text' key."""
        data = {"result": "From result", "text": "From text"}
        result = extract_response_text(data)
        assert result == "From result"

    def test_should_return_string_representation_for_unknown_structure(self):
        """Should return string representation for unknown structure."""
        data = {"custom_key": "custom_value", "another": 123}
        result = extract_response_text(data)
        assert "custom_key" in result or "custom_value" in result

    def test_should_handle_empty_dict(self):
        """Should handle empty dictionary."""
        result = extract_response_text({})
        assert result == "{}"


class TestConstants:
    """Tests for module constants."""

    def test_flows_base_path_should_point_to_flows_directory(self):
        """FLOWS_BASE_PATH should point to the flows directory."""
        assert FLOWS_BASE_PATH.name == "flows"
        assert FLOWS_BASE_PATH.parent.name == "agentic"

    def test_streaming_queue_max_size_should_be_reasonable(self):
        """STREAMING_QUEUE_MAX_SIZE should be reasonable."""
        assert STREAMING_QUEUE_MAX_SIZE > 100
        assert STREAMING_QUEUE_MAX_SIZE <= 10000

    def test_streaming_timeout_should_be_reasonable(self):
        """STREAMING_EVENT_TIMEOUT_SECONDS should be reasonable."""
        assert STREAMING_EVENT_TIMEOUT_SECONDS > 30
        assert STREAMING_EVENT_TIMEOUT_SECONDS <= 600


class TestRunGraphWithEvents:
    """Tests for _run_graph_with_events function."""

    @pytest.mark.asyncio
    async def test_should_set_user_and_session_on_graph(self):
        """Should set user_id and session_id on graph when provided."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        event_manager = MagicMock()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value="test",
            global_variables=None,
            user_id="user-1",
            session_id="session-1",
            event_manager=event_manager,
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert mock_graph.user_id == "user-1"
        assert mock_graph.session_id == "session-1"

    @pytest.mark.asyncio
    async def test_should_inject_global_variables_into_context(self):
        """Should merge global_variables into graph.context['request_variables']."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value="test",
            global_variables={"KEY": "value"},
            user_id=None,
            session_id=None,
            event_manager=MagicMock(),
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert mock_graph.context["request_variables"]["KEY"] == "value"

    @pytest.mark.asyncio
    async def test_should_store_error_on_exception(self):
        """Should store exception in execution_result.error."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            msg = "execution failed"
            raise RuntimeError(msg)
            yield

        mock_graph.async_start = mock_async_start

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value="test",
            global_variables=None,
            user_id=None,
            session_id=None,
            event_manager=MagicMock(),
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert execution_result.has_error is True
        assert isinstance(execution_result.error, RuntimeError)

    @pytest.mark.asyncio
    async def test_should_signal_completion_via_queue(self):
        """Should always put None on event_queue, even on error."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            msg = "fail"
            raise ValueError(msg)
            yield

        mock_graph.async_start = mock_async_start

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value="test",
            global_variables=None,
            user_id=None,
            session_id=None,
            event_manager=MagicMock(),
            event_queue=event_queue,
            execution_result=execution_result,
        )

        item = await event_queue.get()
        assert item is None


class TestExecuteFlowFile:
    """Tests for execute_flow_file function."""

    @pytest.mark.asyncio
    async def test_should_raise_404_for_missing_flow_file(self):
        """Should raise HTTPException 404 for missing flow file."""
        with pytest.raises(HTTPException) as exc_info:
            await execute_flow_file("nonexistent_flow.json")

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_should_execute_flow_with_model_injection(self):
        """Should execute flow with model preparation when provider and model specified."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_async_start(*_args, **_kwargs):
            yield {"result": "success"}

        mock_graph.async_start = mock_async_start

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/path/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph) as mock_load,
        ):
            result = await execute_flow_file(
                "test.json",
                input_value="test",
                provider="OpenAI",
                model_name="gpt-4",
            )

        mock_load.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_should_raise_500_on_execution_error(self):
        """Should raise HTTPException 500 on execution error."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_async_start(*_args, **_kwargs):
            msg = "Execution failed"
            raise RuntimeError(msg)
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/path/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
            pytest.raises(HTTPException) as exc_info,
        ):
            await execute_flow_file("test.json")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_should_set_user_and_session_on_loaded_graph(self):
        """Should set user_id and session_id on the loaded graph."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/path/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
        ):
            await execute_flow_file("test.json", input_value="test", user_id="user-1", session_id="session-1")

        assert mock_graph.user_id == "user-1"
        assert mock_graph.session_id == "session-1"

    @pytest.mark.asyncio
    async def test_should_inject_global_variables(self):
        """Should inject global_variables into graph context."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/path/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
        ):
            await execute_flow_file("test.json", input_value="test", global_variables={"API_KEY": "secret"})

        assert mock_graph.context["request_variables"]["API_KEY"] == "secret"

    @pytest.mark.asyncio
    async def test_should_reraise_http_exception_as_is(self):
        """Should re-raise HTTPException without wrapping in 500."""
        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/path/test.json"), "json")),
            patch(
                f"{MODULE}.load_graph_for_execution",
                new_callable=AsyncMock,
                side_effect=HTTPException(status_code=404, detail="Flow not found"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await execute_flow_file("test.json")

        assert exc_info.value.status_code == 404
        assert "Flow not found" in exc_info.value.detail


class TestParseEventData:
    """Tests for parse_event_data function."""

    def test_should_parse_valid_event(self):
        """Should parse valid event data."""
        data = b'{"event": "token", "data": {"chunk": "Hello"}}'
        event_type, event_data = parse_event_data(data)
        assert event_type == "token"
        assert event_data == {"chunk": "Hello"}

    def test_should_return_none_for_empty_data(self):
        """Should return None event type for empty data."""
        event_type, event_data = parse_event_data(b"")
        assert event_type is None
        assert event_data == {}

    def test_should_return_none_for_whitespace_only(self):
        """Should return None for whitespace-only data."""
        event_type, event_data = parse_event_data(b"   \n\t  ")
        assert event_type is None
        assert event_data == {}

    def test_should_handle_event_without_data(self):
        """Should handle event without data field."""
        data = b'{"event": "end"}'
        event_type, event_data = parse_event_data(data)
        assert event_type == "end"
        assert event_data == {}


class TestExecuteFlowFileStreaming:
    """Tests for execute_flow_file_streaming function."""

    @pytest.mark.asyncio
    async def test_should_raise_404_for_missing_flow_file(self):
        """Should raise HTTPException 404 for missing flow file."""
        with pytest.raises(HTTPException) as exc_info:
            async for _ in execute_flow_file_streaming("nonexistent_flow.json"):
                pass
        assert exc_info.value.status_code == 404


class TestExecuteFlowFileStreamingEvents:
    """Tests for execute_flow_file_streaming event handling.

    Note: These tests use 5+ mocks because the streaming architecture requires
    coordinating multiple subsystems (graph loading, event management, background
    task execution, and event consumption). This is inherent to the source code
    architecture, not a test design issue.
    """

    @pytest.mark.asyncio
    async def test_should_yield_end_event_on_success(self):
        """Should yield end event with result on successful execution."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.prepare = MagicMock()

        async def mock_consume(*_args, **_kwargs):
            yield ("token", "chunk1")
            yield ("end", None)

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
            patch(f"{MODULE}.create_default_event_manager"),
            patch(f"{MODULE}.consume_streaming_events", side_effect=mock_consume),
            patch(f"{MODULE}._run_graph_with_events", new_callable=AsyncMock),
        ):
            events = [event async for event in execute_flow_file_streaming("test.json", input_value="hello")]
            event_types = [e[0] for e in events]
            assert "token" in event_types or "end" in event_types

    @pytest.mark.asyncio
    async def test_should_yield_cancelled_on_disconnect(self):
        """Should yield cancelled event when client disconnects."""

        async def mock_consume(*_args, **_kwargs):
            yield ("cancelled", None)

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=MagicMock(context={})),
            patch(f"{MODULE}.create_default_event_manager"),
            patch(f"{MODULE}.consume_streaming_events", side_effect=mock_consume),
            patch(f"{MODULE}._run_graph_with_events", new_callable=AsyncMock),
        ):
            events = [event async for event in execute_flow_file_streaming("test.json")]
            assert ("cancelled", {}) in events

    @pytest.mark.asyncio
    async def test_should_raise_http_on_execution_error(self):
        """Should raise HTTPException when execution result has error."""

        async def mock_consume(*_args, **_kwargs):
            yield ("end", None)

        mock_result = MagicMock()
        mock_result.has_error = True
        mock_result.has_result = False
        mock_result.error = RuntimeError("flow error")

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=MagicMock(context={})),
            patch(f"{MODULE}.create_default_event_manager"),
            patch(f"{MODULE}.consume_streaming_events", side_effect=mock_consume),
            patch(f"{MODULE}._run_graph_with_events", new_callable=AsyncMock),
            patch(f"{MODULE}.FlowExecutionResult", return_value=mock_result),
        ):
            with pytest.raises(HTTPException) as exc_info:
                async for _ in execute_flow_file_streaming("test.json"):
                    pass
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_should_handle_preparation_error(self):
        """Should raise HTTPException on JSONDecodeError/OSError/ValueError."""
        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/test.json"), "json")),
            patch(
                f"{MODULE}.load_graph_for_execution",
                new_callable=AsyncMock,
                side_effect=json.JSONDecodeError("err", "doc", 0),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            async for _ in execute_flow_file_streaming("test.json"):
                pass
        assert exc_info.value.status_code == 500


class TestTracingIntegration:
    """Tests for flow_id and flow_name propagation to enable tracing."""

    @pytest.mark.asyncio
    async def test_run_graph_should_set_flow_id_from_global_variables(self):
        """Should set graph.flow_id from FLOW_ID in global_variables."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.flow_name = None
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value="test",
            global_variables={"FLOW_ID": "abc-123"},
            user_id=None,
            session_id=None,
            event_manager=MagicMock(),
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert mock_graph.flow_id == "abc-123"

    @pytest.mark.asyncio
    async def test_run_graph_should_set_flow_name_when_missing(self):
        """Should set graph.flow_name to 'Assistant Flow' when not already set."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.flow_name = None
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value="test",
            global_variables=None,
            user_id=None,
            session_id=None,
            event_manager=MagicMock(),
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert mock_graph.flow_name == "Assistant Flow"

    @pytest.mark.asyncio
    async def test_run_graph_should_preserve_existing_flow_name(self):
        """Should not overwrite flow_name if already set on graph."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.flow_name = "My Custom Flow"
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value="test",
            global_variables={"FLOW_ID": "abc"},
            user_id=None,
            session_id=None,
            event_manager=MagicMock(),
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert mock_graph.flow_name == "My Custom Flow"

    @pytest.mark.asyncio
    async def test_run_graph_should_not_set_flow_id_when_missing(self):
        """Should not set flow_id when FLOW_ID not in global_variables."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.flow_name = None
        mock_graph.flow_id = None
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value="test",
            global_variables={"OTHER_KEY": "value"},
            user_id=None,
            session_id=None,
            event_manager=MagicMock(),
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert mock_graph.flow_id is None

    @pytest.mark.asyncio
    async def test_execute_flow_file_should_set_flow_id_from_global_variables(self):
        """Should set graph.flow_id from FLOW_ID in global_variables."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.flow_name = None
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
        ):
            await execute_flow_file(
                "test.json",
                input_value="test",
                global_variables={"FLOW_ID": "flow-uuid-456"},
            )

        assert mock_graph.flow_id == "flow-uuid-456"

    @pytest.mark.asyncio
    async def test_execute_flow_file_should_set_flow_name_to_filename(self):
        """Should set graph.flow_name to flow_filename when not already set."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.flow_name = None
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/MyFlow.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
        ):
            await execute_flow_file(
                "MyFlow.json",
                input_value="test",
                global_variables=None,
            )

        assert mock_graph.flow_name == "MyFlow.json"

    @pytest.mark.asyncio
    async def test_execute_flow_file_should_preserve_existing_flow_name(self):
        """Should not overwrite flow_name if already set on graph."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.flow_name = "Existing Name"
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
        ):
            await execute_flow_file("test.json", input_value="test", global_variables={"FLOW_ID": "id"})

        assert mock_graph.flow_name == "Existing Name"

    @pytest.mark.asyncio
    async def test_execute_flow_file_should_not_set_flow_id_when_global_vars_none(self):
        """Should not crash or set flow_id when global_variables is None."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.flow_name = None
        mock_graph.flow_id = None
        mock_graph.prepare = MagicMock()

        async def mock_async_start(**_kwargs):
            yield {"result": "ok"}

        mock_graph.async_start = mock_async_start

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
        ):
            await execute_flow_file("test.json", input_value="test", global_variables=None)

        assert mock_graph.flow_id is None


class TestBugsAndEdgeCases:
    """Tests that challenge the code — exposing real bugs and untested edge cases."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="BUG: L47 graph.context['request_variables'] crashes with TypeError when context is None",
        strict=True,
    )
    async def test_run_graph_context_none_crashes(self):
        """_run_graph_with_events should handle graph.context being None."""
        mock_graph = MagicMock()
        mock_graph.context = None
        mock_graph.prepare = MagicMock()

        async def empty_gen(*_args, **_kwargs):
            return
            yield

        mock_graph.async_start = empty_gen

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=mock_graph,
            input_value=None,
            global_variables={"KEY": "value"},
            user_id=None,
            session_id=None,
            event_manager=MagicMock(),
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert execution_result.error is None

    @pytest.mark.asyncio
    async def test_run_graph_global_vars_overwrite_existing(self):
        """L49: .update(global_variables) silently overwrites existing request_variables."""
        mock_graph = MagicMock()
        mock_graph.context = {"request_variables": {"EXISTING_KEY": "original"}}
        mock_graph.prepare = MagicMock()

        async def empty_gen(*_args, **_kwargs):
            return
            yield

        mock_graph.async_start = empty_gen

        event_queue: asyncio.Queue[str] = asyncio.Queue()
        execution_result = FlowExecutionResult()

        with patch(f"{MODULE}.extract_structured_result", return_value={}):
            await _run_graph_with_events(
                graph=mock_graph,
                input_value=None,
                global_variables={"EXISTING_KEY": "overwritten"},
                user_id=None,
                session_id=None,
                event_manager=MagicMock(),
                event_queue=event_queue,
                execution_result=execution_result,
            )

        assert mock_graph.context["request_variables"]["EXISTING_KEY"] == "overwritten"

    def test_extract_response_text_empty_dict(self):
        """extract_response_text({}) returns stringified '{}' — no special handling."""
        result = extract_response_text({})
        assert result == "{}"

    def test_extract_response_text_with_none_crashes(self):
        """extract_response_text(None) crashes — no None check."""
        with pytest.raises(TypeError):
            extract_response_text(None)

    @pytest.mark.xfail(
        reason="BUG: FlowExecutionResult(result={}).has_result is False — empty dict is falsy",
        strict=True,
    )
    def test_execution_result_empty_dict_should_have_result(self):
        """A flow returning {} legitimately should still report has_result=True."""
        result = FlowExecutionResult(result={})
        assert result.has_result is True

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="BUG: L107 same context None crash — duplicated code, duplicated bug",
        strict=True,
    )
    async def test_execute_flow_file_context_none_crashes(self):
        """execute_flow_file should handle graph.context being None."""
        mock_graph = MagicMock()
        mock_graph.context = None

        async def empty_gen(*_args, **_kwargs):
            return
            yield

        mock_graph.async_start = empty_gen

        with (
            patch(f"{MODULE}.resolve_flow_path", return_value=(Path("/fake/test.json"), "json")),
            patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=mock_graph),
            patch(f"{MODULE}.extract_structured_result", return_value={}),
        ):
            result = await execute_flow_file("test.json", global_variables={"KEY": "val"})

        assert isinstance(result, dict)
