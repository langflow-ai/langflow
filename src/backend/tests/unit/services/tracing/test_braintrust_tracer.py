"""Tests for the BraintrustTracer implementation."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.tracing.braintrust import BraintrustTracer

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def trace_id():
    return uuid.uuid4()


@pytest.fixture
def mock_logger():
    """Create a mock Braintrust logger with start_span support."""
    logger = MagicMock()
    root_span = MagicMock()
    child_span = MagicMock()
    root_span.start_span.return_value = child_span
    logger.start_span.return_value = root_span
    return logger, root_span, child_span


@pytest.fixture
def tracer(mock_logger, trace_id):
    """Create a BraintrustTracer with mocked Braintrust SDK."""
    logger, root_span, _child_span = mock_logger
    with patch.dict("os.environ", {"BRAINTRUST_API_KEY": "sk-test-key"}):
        with patch("braintrust.init_logger", return_value=logger):
            t = BraintrustTracer(
                trace_name="Test Flow - flow-123",
                trace_type="chain",
                project_name="TestProject",
                trace_id=trace_id,
                user_id="user-1",
                session_id="session-1",
            )
    return t


# ------------------------------------------------------------------
# Configuration tests
# ------------------------------------------------------------------


class TestGetConfig:
    """Tests for _get_config() environment variable parsing."""

    def test_returns_empty_when_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            assert BraintrustTracer._get_config() == {}

    def test_returns_api_key_only(self):
        with patch.dict("os.environ", {"BRAINTRUST_API_KEY": "sk-test"}, clear=True):
            config = BraintrustTracer._get_config()
            assert config == {"api_key": "sk-test"}

    def test_returns_all_config(self):
        env = {
            "BRAINTRUST_API_KEY": "sk-test",
            "BRAINTRUST_API_URL": "https://custom.api.dev",
            "BRAINTRUST_PROJECT": "MyProject",
        }
        with patch.dict("os.environ", env, clear=True):
            config = BraintrustTracer._get_config()
            assert config == {
                "api_key": "sk-test",
                "api_url": "https://custom.api.dev",
                "project": "MyProject",
            }

    def test_ignores_empty_api_key(self):
        with patch.dict("os.environ", {"BRAINTRUST_API_KEY": ""}, clear=True):
            assert BraintrustTracer._get_config() == {}


# ------------------------------------------------------------------
# Initialization tests
# ------------------------------------------------------------------


class TestInitialization:
    """Tests for BraintrustTracer initialization and setup."""

    def test_ready_when_configured(self, tracer):
        assert tracer.ready is True

    def test_not_ready_when_no_api_key(self, trace_id):
        with patch.dict("os.environ", {}, clear=True):
            t = BraintrustTracer(
                trace_name="Test",
                trace_type="chain",
                project_name="TestProject",
                trace_id=trace_id,
            )
        assert t.ready is False

    def test_not_ready_when_import_fails(self, trace_id):
        with patch.dict("os.environ", {"BRAINTRUST_API_KEY": "sk-test"}):
            with patch("builtins.__import__", side_effect=ImportError("no braintrust")):
                t = BraintrustTracer(
                    trace_name="Test",
                    trace_type="chain",
                    project_name="TestProject",
                    trace_id=trace_id,
                )
        assert t.ready is False

    def test_not_ready_when_sdk_raises(self, trace_id):
        with patch.dict("os.environ", {"BRAINTRUST_API_KEY": "sk-test"}):
            with patch("braintrust.init_logger", side_effect=RuntimeError("connection failed")):
                t = BraintrustTracer(
                    trace_name="Test",
                    trace_type="chain",
                    project_name="TestProject",
                    trace_id=trace_id,
                )
        assert t.ready is False

    def test_flow_id_extracted_from_trace_name(self, tracer):
        assert tracer.flow_id == "flow-123"

    def test_flow_id_when_no_separator(self, mock_logger, trace_id):
        logger, _root_span, _child_span = mock_logger
        with patch.dict("os.environ", {"BRAINTRUST_API_KEY": "sk-test"}):
            with patch("braintrust.init_logger", return_value=logger):
                t = BraintrustTracer(
                    trace_name="simple-name",
                    trace_type="chain",
                    project_name="TestProject",
                    trace_id=trace_id,
                )
        assert t.flow_id == "simple-name"

    def test_root_span_created_with_metadata(self, mock_logger, trace_id):
        logger, _root_span, _child_span = mock_logger
        with patch.dict("os.environ", {"BRAINTRUST_API_KEY": "sk-test"}):
            with patch("braintrust.init_logger", return_value=logger):
                BraintrustTracer(
                    trace_name="Test Flow - flow-123",
                    trace_type="chain",
                    project_name="TestProject",
                    trace_id=trace_id,
                    user_id="user-1",
                    session_id="session-1",
                )
        logger.start_span.assert_called_once()
        call_kwargs = logger.start_span.call_args[1]
        assert call_kwargs["name"] == "flow-123"
        assert call_kwargs["metadata"]["langflow_trace_id"] == str(trace_id)
        assert call_kwargs["metadata"]["user_id"] == "user-1"
        assert call_kwargs["metadata"]["session_id"] == "session-1"
        assert call_kwargs["metadata"]["created_from"] == "langflow"

    def test_uses_env_project_over_param(self, mock_logger, trace_id):
        logger, _root_span, _child_span = mock_logger
        env = {"BRAINTRUST_API_KEY": "sk-test", "BRAINTRUST_PROJECT": "EnvProject"}
        with patch.dict("os.environ", env), patch("braintrust.init_logger", return_value=logger) as mock_init:
            BraintrustTracer(
                trace_name="Test",
                trace_type="chain",
                project_name="ParamProject",
                trace_id=trace_id,
            )
        mock_init.assert_called_once()
        assert mock_init.call_args[1]["project"] == "EnvProject"

    def test_falls_back_to_param_project(self, mock_logger, trace_id):
        logger, _root_span, _child_span = mock_logger
        with patch.dict("os.environ", {"BRAINTRUST_API_KEY": "sk-test"}):
            with patch("braintrust.init_logger", return_value=logger) as mock_init:
                BraintrustTracer(
                    trace_name="Test",
                    trace_type="chain",
                    project_name="ParamProject",
                    trace_id=trace_id,
                )
        assert mock_init.call_args[1]["project"] == "ParamProject"

    def test_falls_back_to_langflow_default_project(self, mock_logger, trace_id):
        logger, _root_span, _child_span = mock_logger
        with patch.dict("os.environ", {"BRAINTRUST_API_KEY": "sk-test"}):
            with patch("braintrust.init_logger", return_value=logger) as mock_init:
                BraintrustTracer(
                    trace_name="Test",
                    trace_type="chain",
                    project_name="",
                    trace_id=trace_id,
                )
        assert mock_init.call_args[1]["project"] == "Langflow"


# ------------------------------------------------------------------
# Span lifecycle tests
# ------------------------------------------------------------------


class TestSpanLifecycle:
    """Tests for add_trace / end_trace / end span management."""

    def test_add_trace_creates_child_span(self, tracer, mock_logger):
        _logger, root_span, _child_span = mock_logger
        tracer.add_trace(
            trace_id="comp-1",
            trace_name="OpenAI (comp-1)",
            trace_type="llm",
            inputs={"prompt": "hello"},
            metadata={"model": "gpt-4"},
        )
        root_span.start_span.assert_called_once()
        call_kwargs = root_span.start_span.call_args[1]
        assert call_kwargs["name"] == "OpenAI"
        assert call_kwargs["input"] == {"prompt": "hello"}
        assert call_kwargs["metadata"]["trace_type"] == "llm"
        assert call_kwargs["metadata"]["component_id"] == "comp-1"
        assert call_kwargs["metadata"]["from_langflow_component"] is True
        assert "comp-1" in tracer.spans

    def test_add_trace_no_op_when_not_ready(self, trace_id):
        with patch.dict("os.environ", {}, clear=True):
            t = BraintrustTracer(
                trace_name="Test",
                trace_type="chain",
                project_name="P",
                trace_id=trace_id,
            )
        t.add_trace(trace_id="c1", trace_name="X", trace_type="llm", inputs={})
        assert len(t.spans) == 0

    def test_end_trace_logs_and_closes_span(self, tracer, mock_logger):
        _logger, _root_span, child_span = mock_logger
        tracer.add_trace(
            trace_id="comp-1",
            trace_name="OpenAI (comp-1)",
            trace_type="llm",
            inputs={"prompt": "hello"},
        )
        tracer.end_trace(
            trace_id="comp-1",
            trace_name="OpenAI (comp-1)",
            outputs={"result": "world"},
        )
        child_span.log.assert_called_once()
        assert child_span.log.call_args[1]["output"] == {"result": "world"}
        assert child_span.log.call_args[1]["error"] is None
        child_span.end.assert_called_once()
        assert "comp-1" not in tracer.spans

    def test_end_trace_with_error(self, tracer, mock_logger):
        _logger, _root_span, child_span = mock_logger
        tracer.add_trace(
            trace_id="comp-1",
            trace_name="Fail (comp-1)",
            trace_type="llm",
            inputs={},
        )
        error = ValueError("something went wrong")
        tracer.end_trace(
            trace_id="comp-1",
            trace_name="Fail (comp-1)",
            error=error,
        )
        assert child_span.log.call_args[1]["error"] == "something went wrong"

    def test_end_trace_with_logs(self, tracer, mock_logger):
        _logger, _root_span, child_span = mock_logger
        tracer.add_trace(
            trace_id="comp-1",
            trace_name="X (comp-1)",
            trace_type="llm",
            inputs={},
        )
        tracer.end_trace(
            trace_id="comp-1",
            trace_name="X (comp-1)",
            outputs={"out": "value"},
            logs=[{"step": 1}, {"step": 2}],
        )
        output = child_span.log.call_args[1]["output"]
        assert output["out"] == "value"
        assert output["logs"] == [{"step": 1}, {"step": 2}]

    def test_end_trace_missing_span_warns(self, tracer):
        # Should not raise, just warn
        tracer.end_trace(
            trace_id="nonexistent",
            trace_name="Gone",
        )

    def test_end_closes_root_span(self, tracer, mock_logger):
        _logger, root_span, _child_span = mock_logger
        tracer.end(
            inputs={"user_input": "hi"},
            outputs={"bot_output": "hello"},
            metadata={"duration": 1.5},
        )
        root_span.log.assert_called_once()
        call_kwargs = root_span.log.call_args[1]
        assert call_kwargs["input"] == {"user_input": "hi"}
        assert call_kwargs["output"] == {"bot_output": "hello"}
        assert call_kwargs["metadata"] == {"duration": 1.5}
        assert call_kwargs["error"] is None
        root_span.end.assert_called_once()

    def test_end_with_error(self, tracer, mock_logger):
        _logger, root_span, _child_span = mock_logger
        error = RuntimeError("flow failed")
        tracer.end(inputs={}, outputs={}, error=error)
        assert root_span.log.call_args[1]["error"] == "flow failed"

    def test_end_no_op_when_not_ready(self, trace_id):
        with patch.dict("os.environ", {}, clear=True):
            t = BraintrustTracer(
                trace_name="Test",
                trace_type="chain",
                project_name="P",
                trace_id=trace_id,
            )
        # Should not raise
        t.end(inputs={}, outputs={})


# ------------------------------------------------------------------
# LangChain callback tests
# ------------------------------------------------------------------


class TestGetLangchainCallback:
    """Tests for get_langchain_callback() integration with braintrust-langchain."""

    def test_returns_none_when_not_ready(self, trace_id):
        with patch.dict("os.environ", {}, clear=True):
            t = BraintrustTracer(
                trace_name="Test",
                trace_type="chain",
                project_name="P",
                trace_id=trace_id,
            )
        assert t.get_langchain_callback() is None

    def test_returns_none_when_import_fails(self, tracer):
        with patch.dict("sys.modules", {"braintrust_langchain": None}):
            with patch("builtins.__import__", side_effect=ImportError("no braintrust_langchain")):
                result = tracer.get_langchain_callback()
        assert result is None

    def test_returns_handler_with_root_span_when_no_component_spans(self, tracer, mock_logger):
        _logger, root_span, _child_span = mock_logger
        mock_handler = MagicMock()
        with patch("braintrust_langchain.BraintrustCallbackHandler", return_value=mock_handler) as mock_cls:
            result = tracer.get_langchain_callback()
        assert result is mock_handler
        mock_cls.assert_called_once_with(logger=root_span)

    def test_returns_handler_with_most_recent_component_span(self, tracer, mock_logger):
        _logger, root_span, child_span = mock_logger

        # Add a component span
        tracer.add_trace(
            trace_id="comp-1",
            trace_name="OpenAI (comp-1)",
            trace_type="llm",
            inputs={},
        )

        mock_handler = MagicMock()
        with patch("braintrust_langchain.BraintrustCallbackHandler", return_value=mock_handler) as mock_cls:
            result = tracer.get_langchain_callback()
        assert result is mock_handler
        # Should use child_span (the most recent component span), not root_span
        mock_cls.assert_called_once_with(logger=child_span)


# ------------------------------------------------------------------
# Type conversion tests
# ------------------------------------------------------------------


class TestConvertToLoggable:
    """Tests for _convert_to_loggable() type conversion."""

    def test_plain_dict(self, tracer):
        assert tracer._convert_to_loggable({"key": "value"}) == {"key": "value"}

    def test_plain_list(self, tracer):
        assert tracer._convert_to_loggable([1, 2, 3]) == [1, 2, 3]

    def test_nested_dict(self, tracer):
        data = {"outer": {"inner": "value"}}
        assert tracer._convert_to_loggable(data) == {"outer": {"inner": "value"}}

    def test_langflow_message(self, tracer):
        msg = Message(text="hello world")
        assert tracer._convert_to_loggable(msg) == "hello world"

    def test_langflow_data(self, tracer):
        data = Data(text_key="content", data={"content": "test data"})
        result = tracer._convert_to_loggable(data)
        assert isinstance(result, str)

    def test_langchain_human_message(self, tracer):
        msg = HumanMessage(content="user input")
        assert tracer._convert_to_loggable(msg) == "user input"

    def test_langchain_system_message(self, tracer):
        msg = SystemMessage(content="system prompt")
        assert tracer._convert_to_loggable(msg) == "system prompt"

    def test_langchain_ai_message(self, tracer):
        msg = AIMessage(content="ai response")
        assert tracer._convert_to_loggable(msg) == "ai response"

    def test_langchain_document(self, tracer):
        doc = Document(page_content="document text")
        assert tracer._convert_to_loggable(doc) == "document text"

    def test_generator_type(self, tracer):
        gen = (x for x in range(3))
        result = tracer._convert_to_loggable(gen)
        assert isinstance(result, str)
        assert "generator" in result

    def test_none_type(self, tracer):
        result = tracer._convert_to_loggable(None)
        assert result == "None"

    def test_primitive_passthrough(self, tracer):
        assert tracer._convert_to_loggable(42) == 42
        assert tracer._convert_to_loggable(3.14) == 3.14
        assert tracer._convert_to_loggable("string") == "string"
        assert tracer._convert_to_loggable(True) is True

    def test_dict_with_none_keys_excluded(self, tracer):
        data = {"valid": "value", None: "excluded"}
        result = tracer._convert_to_loggable(data)
        assert result == {"valid": "value"}

    def test_mixed_types_in_dict(self, tracer):
        msg = HumanMessage(content="hello")
        doc = Document(page_content="world")
        data = {"message": msg, "document": doc, "plain": "text"}
        result = tracer._convert_to_loggable(data)
        assert result == {"message": "hello", "document": "world", "plain": "text"}

    def test_list_of_messages(self, tracer):
        messages = [
            HumanMessage(content="q1"),
            AIMessage(content="a1"),
            HumanMessage(content="q2"),
        ]
        result = tracer._convert_to_loggable(messages)
        assert result == ["q1", "a1", "q2"]
