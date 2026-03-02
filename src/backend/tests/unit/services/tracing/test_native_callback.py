"""Unit tests for NativeCallbackHandler."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID, uuid4

from langflow.services.tracing.native_callback import NativeCallbackHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handler(parent_span_id: UUID | None = None) -> tuple[NativeCallbackHandler, MagicMock]:
    """Return (handler, mock_tracer)."""
    mock_tracer = MagicMock()
    mock_tracer._current_component_id = None
    handler = NativeCallbackHandler(tracer=mock_tracer, parent_span_id=parent_span_id)
    return handler, mock_tracer


def _make_llm_result(
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    *,
    use_llm_output: bool = False,
    use_usage_metadata: bool = False,
    use_response_metadata: bool = False,
    use_generation_info: bool = False,
) -> MagicMock:
    """Build a mock LLMResult with configurable token sources."""
    result = MagicMock()

    if use_llm_output:
        result.llm_output = {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        }
        result.generations = []
    elif use_usage_metadata:
        # Modern LangChain: AIMessage.usage_metadata
        message = MagicMock()
        message.usage_metadata = {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        message.response_metadata = {}
        gen = MagicMock()
        gen.message = message
        gen.generation_info = {}
        result.llm_output = {}
        result.generations = [[gen]]
    elif use_response_metadata:
        # Provider-specific: AIMessage.response_metadata
        message = MagicMock()
        message.usage_metadata = None
        message.response_metadata = {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        }
        gen = MagicMock()
        gen.message = message
        gen.generation_info = {}
        result.llm_output = {}
        result.generations = [[gen]]
    elif use_generation_info:
        # generation_info path
        message = MagicMock()
        message.usage_metadata = None
        message.response_metadata = {}
        gen = MagicMock()
        gen.message = message
        gen.generation_info = {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        }
        result.llm_output = {}
        result.generations = [[gen]]
    else:
        result.llm_output = {}
        result.generations = []

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestInternalHelpers:
    def test_get_span_id_creates_new_uuid_for_unknown_run(self):
        handler, _ = _make_handler()
        run_id = uuid4()
        span_id = handler._get_span_id(run_id)
        assert isinstance(span_id, UUID)

    def test_get_span_id_returns_same_id_for_same_run(self):
        handler, _ = _make_handler()
        run_id = uuid4()
        id1 = handler._get_span_id(run_id)
        id2 = handler._get_span_id(run_id)
        assert id1 == id2

    def test_get_start_time_returns_now_for_unknown_run(self):
        handler, _ = _make_handler()
        from datetime import datetime, timezone

        before = datetime.now(timezone.utc)
        t = handler._get_start_time(uuid4())
        after = datetime.now(timezone.utc)
        assert before <= t <= after

    def test_calculate_latency_returns_non_negative(self):
        handler, _ = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)  # registers start time
        latency = handler._calculate_latency(run_id)
        assert latency >= 0

    def test_cleanup_run_removes_span(self):
        handler, _ = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        assert run_id in handler._spans
        handler._cleanup_run(run_id)
        assert run_id not in handler._spans

    def test_cleanup_run_noop_for_unknown_run(self):
        handler, _ = _make_handler()
        # Should not raise
        handler._cleanup_run(uuid4())


# ---------------------------------------------------------------------------
# LLM callbacks
# ---------------------------------------------------------------------------


class TestOnLlmStart:
    def test_on_llm_start_calls_add_langchain_span(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_llm_start(
            serialized={"name": "ChatOpenAI", "id": ["langchain", "ChatOpenAI"]},
            prompts=["Hello"],
            run_id=run_id,
            invocation_params={"model_name": "gpt-4"},
        )
        mock_tracer.add_langchain_span.assert_called_once()
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["span_type"] == "llm"
        assert "gpt-4" in call_kwargs["name"]

    def test_on_llm_start_uses_parent_span_id_when_no_parent_run(self):
        parent_id = uuid4()
        handler, mock_tracer = _make_handler(parent_span_id=parent_id)
        run_id = uuid4()
        handler.on_llm_start(
            serialized={},
            prompts=["hi"],
            run_id=run_id,
        )
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["parent_span_id"] == parent_id

    def test_on_llm_start_uses_parent_run_id_when_provided(self):
        handler, mock_tracer = _make_handler()
        parent_run_id = uuid4()
        run_id = uuid4()
        # Register parent run first
        handler._get_span_id(parent_run_id)
        handler.on_llm_start(
            serialized={},
            prompts=["hi"],
            run_id=run_id,
            parent_run_id=parent_run_id,
        )
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        # parent_span_id should be the span id of the parent run
        assert call_kwargs["parent_span_id"] == handler._spans[parent_run_id]["span_id"]

    def test_on_llm_start_extracts_model_from_invocation_params(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_llm_start(
            serialized={"name": "OpenAI"},
            prompts=["hi"],
            run_id=run_id,
            invocation_params={"model": "gpt-3.5-turbo"},
        )
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["model_name"] == "gpt-3.5-turbo"

    def test_on_llm_start_handles_empty_serialized(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_llm_start(serialized={}, prompts=["hi"], run_id=run_id)
        mock_tracer.add_langchain_span.assert_called_once()


class TestOnChatModelStart:
    def test_on_chat_model_start_calls_add_langchain_span(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        msg = MagicMock()
        msg.type = "human"
        msg.content = "hello"
        handler.on_chat_model_start(
            serialized={"name": "ChatOpenAI"},
            messages=[[msg]],
            run_id=run_id,
            invocation_params={"model_name": "gpt-4"},
        )
        mock_tracer.add_langchain_span.assert_called_once()
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["span_type"] == "llm"
        assert "messages" in call_kwargs["inputs"]

    def test_on_chat_model_start_formats_messages(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        msg = MagicMock()
        msg.type = "human"
        msg.content = "test message"
        handler.on_chat_model_start(
            serialized={},
            messages=[[msg]],
            run_id=run_id,
        )
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        formatted = call_kwargs["inputs"]["messages"]
        assert formatted == [[{"type": "human", "content": "test message"}]]


class TestOnLlmEnd:
    def test_on_llm_end_legacy_llm_output_tokens(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)

        response = _make_llm_result(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            use_llm_output=True,
        )
        handler.on_llm_end(response, run_id=run_id)

        mock_tracer.end_langchain_span.assert_called_once()
        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["prompt_tokens"] == 10
        assert call_kwargs["completion_tokens"] == 20
        assert call_kwargs["total_tokens"] == 30

    def test_on_llm_end_usage_metadata_tokens(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)

        response = _make_llm_result(
            prompt_tokens=5,
            completion_tokens=15,
            total_tokens=20,
            use_usage_metadata=True,
        )
        handler.on_llm_end(response, run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["total_tokens"] == 20

    def test_on_llm_end_response_metadata_tokens(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)

        response = _make_llm_result(
            prompt_tokens=8,
            completion_tokens=12,
            total_tokens=20,
            use_response_metadata=True,
        )
        handler.on_llm_end(response, run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["total_tokens"] == 20

    def test_on_llm_end_generation_info_tokens(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)

        response = _make_llm_result(
            prompt_tokens=3,
            completion_tokens=7,
            total_tokens=10,
            use_generation_info=True,
        )
        handler.on_llm_end(response, run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["total_tokens"] == 10

    def test_on_llm_end_no_tokens_when_none_available(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)

        response = _make_llm_result()  # no token info
        handler.on_llm_end(response, run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs.get("total_tokens") is None

    def test_on_llm_end_cleans_up_run(self):
        handler, _mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        response = _make_llm_result()
        handler.on_llm_end(response, run_id=run_id)
        assert run_id not in handler._spans

    def test_on_llm_end_extracts_generation_text(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)

        gen = MagicMock()
        gen.text = "hello world"
        gen.generation_info = {"finish_reason": "stop"}
        gen.message = None

        response = MagicMock()
        response.llm_output = {}
        response.generations = [[gen]]

        handler.on_llm_end(response, run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        outputs = call_kwargs["outputs"]
        assert outputs["generations"][0][0]["text"] == "hello world"


class TestOnLlmError:
    def test_on_llm_error_calls_end_langchain_span_with_error(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)

        handler.on_llm_error(ValueError("LLM failed"), run_id=run_id)

        mock_tracer.end_langchain_span.assert_called_once()
        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["error"] == "LLM failed"

    def test_on_llm_error_cleans_up_run(self):
        handler, _mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_llm_error(RuntimeError("boom"), run_id=run_id)
        assert run_id not in handler._spans


# ---------------------------------------------------------------------------
# Chain callbacks
# ---------------------------------------------------------------------------


class TestChainCallbacks:
    def test_on_chain_start_calls_add_langchain_span(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "LLMChain"},
            inputs={"question": "what?"},
            run_id=run_id,
        )
        mock_tracer.add_langchain_span.assert_called_once()
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["span_type"] == "chain"
        assert call_kwargs["name"] == "LLMChain"

    def test_on_chain_start_uses_id_list_fallback(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_chain_start(
            serialized={"id": ["langchain", "chains", "MyChain"]},
            inputs={},
            run_id=run_id,
        )
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["name"] == "MyChain"

    def test_on_chain_end_calls_end_langchain_span(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_chain_end({"result": "done"}, run_id=run_id)

        mock_tracer.end_langchain_span.assert_called_once()
        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["outputs"] == {"result": "done"}

    def test_on_chain_end_cleans_up_run(self):
        handler, _mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_chain_end({}, run_id=run_id)
        assert run_id not in handler._spans

    def test_on_chain_error_calls_end_langchain_span_with_error(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_chain_error(RuntimeError("chain broke"), run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["error"] == "chain broke"

    def test_on_chain_error_cleans_up_run(self):
        handler, _mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_chain_error(RuntimeError("err"), run_id=run_id)
        assert run_id not in handler._spans


# ---------------------------------------------------------------------------
# Tool callbacks
# ---------------------------------------------------------------------------


class TestToolCallbacks:
    def test_on_tool_start_calls_add_langchain_span(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_tool_start(
            serialized={"name": "SearchTool"},
            input_str="query",
            run_id=run_id,
        )
        mock_tracer.add_langchain_span.assert_called_once()
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["span_type"] == "tool"
        assert call_kwargs["name"] == "SearchTool"

    def test_on_tool_start_uses_inputs_dict_when_provided(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_tool_start(
            serialized={"name": "Tool"},
            input_str="fallback",
            run_id=run_id,
            inputs={"query": "actual input"},
        )
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["inputs"] == {"query": "actual input"}

    def test_on_tool_start_falls_back_to_input_str(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_tool_start(
            serialized={"name": "Tool"},
            input_str="my query",
            run_id=run_id,
        )
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["inputs"] == {"input": "my query"}

    def test_on_tool_end_with_string_output(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_tool_end("search result", run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["outputs"] == {"output": "search result"}

    def test_on_tool_end_with_dict_output(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_tool_end({"result": "data"}, run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["outputs"] == {"output": {"result": "data"}}

    def test_on_tool_end_cleans_up_run(self):
        handler, _mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_tool_end("result", run_id=run_id)
        assert run_id not in handler._spans

    def test_on_tool_error_calls_end_langchain_span_with_error(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_tool_error(RuntimeError("tool failed"), run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["error"] == "tool failed"

    def test_on_tool_error_cleans_up_run(self):
        handler, _mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_tool_error(RuntimeError("err"), run_id=run_id)
        assert run_id not in handler._spans


# ---------------------------------------------------------------------------
# Retriever callbacks
# ---------------------------------------------------------------------------


class TestRetrieverCallbacks:
    def test_on_retriever_start_calls_add_langchain_span(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_retriever_start(
            serialized={"name": "VectorStoreRetriever"},
            query="find docs",
            run_id=run_id,
        )
        mock_tracer.add_langchain_span.assert_called_once()
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["span_type"] == "retriever"
        assert call_kwargs["inputs"] == {"query": "find docs"}

    def test_on_retriever_start_uses_id_list_fallback(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler.on_retriever_start(
            serialized={"id": ["langchain", "MyRetriever"]},
            query="q",
            run_id=run_id,
        )
        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["name"] == "MyRetriever"

    def test_on_retriever_end_serializes_documents(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)

        doc1 = MagicMock()
        doc1.page_content = "content 1"
        doc1.metadata = {"source": "file.txt"}
        doc2 = MagicMock()
        doc2.page_content = "content 2"
        doc2.metadata = {}

        handler.on_retriever_end([doc1, doc2], run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        docs = call_kwargs["outputs"]["documents"]
        assert len(docs) == 2
        assert docs[0]["page_content"] == "content 1"
        assert docs[0]["metadata"] == {"source": "file.txt"}
        assert docs[1]["page_content"] == "content 2"

    def test_on_retriever_end_handles_empty_documents(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_retriever_end([], run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["outputs"]["documents"] == []

    def test_on_retriever_end_cleans_up_run(self):
        handler, _mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_retriever_end([], run_id=run_id)
        assert run_id not in handler._spans

    def test_on_retriever_error_calls_end_langchain_span_with_error(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_retriever_error(RuntimeError("retriever failed"), run_id=run_id)

        call_kwargs = mock_tracer.end_langchain_span.call_args[1]
        assert call_kwargs["error"] == "retriever failed"

    def test_on_retriever_error_cleans_up_run(self):
        handler, _mock_tracer = _make_handler()
        run_id = uuid4()
        handler._get_span_id(run_id)
        handler.on_retriever_error(RuntimeError("err"), run_id=run_id)
        assert run_id not in handler._spans


# ---------------------------------------------------------------------------
# Parent span ID propagation
# ---------------------------------------------------------------------------


class TestParentSpanPropagation:
    def test_parent_span_id_used_when_no_parent_run(self):
        parent_id = uuid4()
        handler, mock_tracer = _make_handler(parent_span_id=parent_id)
        run_id = uuid4()

        handler.on_chain_start(serialized={}, inputs={}, run_id=run_id)

        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["parent_span_id"] == parent_id

    def test_parent_run_id_takes_precedence_over_parent_span_id(self):
        parent_id = uuid4()
        handler, mock_tracer = _make_handler(parent_span_id=parent_id)

        parent_run_id = uuid4()
        child_run_id = uuid4()
        # Register parent run
        handler._get_span_id(parent_run_id)
        parent_span_id_from_run = handler._spans[parent_run_id]["span_id"]

        handler.on_chain_start(
            serialized={},
            inputs={},
            run_id=child_run_id,
            parent_run_id=parent_run_id,
        )

        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        # Should use the parent run's span id, not the handler's parent_span_id
        assert call_kwargs["parent_span_id"] == parent_span_id_from_run

    def test_no_parent_span_id_when_neither_provided(self):
        handler, mock_tracer = _make_handler(parent_span_id=None)
        run_id = uuid4()

        handler.on_chain_start(serialized={}, inputs={}, run_id=run_id)

        call_kwargs = mock_tracer.add_langchain_span.call_args[1]
        assert call_kwargs["parent_span_id"] is None


# ---------------------------------------------------------------------------
# Agent callbacks (no-ops)
# ---------------------------------------------------------------------------


class TestAgentCallbacks:
    def test_on_agent_action_does_not_call_tracer(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        action = MagicMock()
        # Should not raise and should not call tracer methods
        handler.on_agent_action(action, run_id=run_id)
        mock_tracer.add_langchain_span.assert_not_called()
        mock_tracer.end_langchain_span.assert_not_called()

    def test_on_agent_finish_does_not_call_tracer(self):
        handler, mock_tracer = _make_handler()
        run_id = uuid4()
        finish = MagicMock()
        handler.on_agent_finish(finish, run_id=run_id)
        mock_tracer.add_langchain_span.assert_not_called()
        mock_tracer.end_langchain_span.assert_not_called()
