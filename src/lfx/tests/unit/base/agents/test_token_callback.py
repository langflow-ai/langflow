"""Tests for TokenUsageCallbackHandler."""

import threading

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from lfx.base.agents.token_callback import TokenUsageCallbackHandler


def _make_llm_result(*, llm_output=None, generations=None):
    """Helper to build LLMResult with minimal boilerplate."""
    if generations is None:
        generations = [[ChatGeneration(message=AIMessage(content="hi"))]]
    return LLMResult(generations=generations, llm_output=llm_output)


class TestExtractUsageFromLLMOutput:
    """Strategy 1: llm_output['token_usage'] (OpenAI legacy)."""

    def test_extracts_from_llm_output(self):
        handler = TokenUsageCallbackHandler()
        result = _make_llm_result(
            llm_output={
                "token_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                }
            }
        )
        handler.on_llm_end(result)
        usage = handler.get_usage()

        assert usage is not None
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20
        assert usage["total_tokens"] == 30


class TestExtractUsageFromUsageMetadata:
    """Strategy 2: generation.message.usage_metadata (LangChain standard)."""

    def test_extracts_from_usage_metadata(self):
        handler = TokenUsageCallbackHandler()
        message = AIMessage(content="hi")
        message.usage_metadata = {"input_tokens": 15, "output_tokens": 25}
        result = _make_llm_result(generations=[[ChatGeneration(message=message)]])

        handler.on_llm_end(result)
        usage = handler.get_usage()

        assert usage is not None
        assert usage["input_tokens"] == 15
        assert usage["output_tokens"] == 25
        assert usage["total_tokens"] == 40


class TestExtractUsageFromResponseMetadataTokenUsage:
    """Strategy 3: response_metadata['token_usage'] (OpenAI via LC)."""

    def test_extracts_from_response_metadata_token_usage(self):
        handler = TokenUsageCallbackHandler()
        message = AIMessage(
            content="hi",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 100,
                }
            },
        )
        result = _make_llm_result(generations=[[ChatGeneration(message=message)]])

        handler.on_llm_end(result)
        usage = handler.get_usage()

        assert usage is not None
        assert usage["input_tokens"] == 50
        assert usage["output_tokens"] == 100
        assert usage["total_tokens"] == 150


class TestExtractUsageFromResponseMetadataUsage:
    """Strategy 4: response_metadata['usage'] (Anthropic)."""

    def test_extracts_from_anthropic_usage(self):
        handler = TokenUsageCallbackHandler()
        message = AIMessage(
            content="hi",
            response_metadata={
                "usage": {
                    "input_tokens": 200,
                    "output_tokens": 300,
                }
            },
        )
        result = _make_llm_result(generations=[[ChatGeneration(message=message)]])

        handler.on_llm_end(result)
        usage = handler.get_usage()

        assert usage is not None
        assert usage["input_tokens"] == 200
        assert usage["output_tokens"] == 300
        assert usage["total_tokens"] == 500


class TestAccumulation:
    """Token counts accumulate across multiple on_llm_end calls."""

    def test_accumulates_across_multiple_calls(self):
        handler = TokenUsageCallbackHandler()

        result1 = _make_llm_result(llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20}})
        result2 = _make_llm_result(llm_output={"token_usage": {"prompt_tokens": 30, "completion_tokens": 40}})

        handler.on_llm_end(result1)
        handler.on_llm_end(result2)

        usage = handler.get_usage()
        assert usage is not None
        assert usage["input_tokens"] == 40
        assert usage["output_tokens"] == 60
        assert usage["total_tokens"] == 100


class TestNoUsageData:
    """Returns None when no token data is captured."""

    def test_returns_none_when_no_data(self):
        handler = TokenUsageCallbackHandler()
        assert handler.get_usage() is None

    def test_returns_none_for_empty_llm_output(self):
        handler = TokenUsageCallbackHandler()
        result = _make_llm_result(llm_output={})
        handler.on_llm_end(result)
        assert handler.get_usage() is None

    def test_returns_none_for_zero_tokens(self):
        handler = TokenUsageCallbackHandler()
        result = _make_llm_result(llm_output={"token_usage": {"prompt_tokens": 0, "completion_tokens": 0}})
        handler.on_llm_end(result)
        assert handler.get_usage() is None


class TestThreadSafety:
    """Concurrent on_llm_end calls produce correct totals."""

    def test_concurrent_calls(self):
        handler = TokenUsageCallbackHandler()
        num_threads = 10
        tokens_per_call = 100

        def call_on_llm_end():
            result = _make_llm_result(
                llm_output={
                    "token_usage": {
                        "prompt_tokens": tokens_per_call,
                        "completion_tokens": tokens_per_call,
                    }
                }
            )
            handler.on_llm_end(result)

        threads = [threading.Thread(target=call_on_llm_end) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        usage = handler.get_usage()
        assert usage is not None
        assert usage["input_tokens"] == num_threads * tokens_per_call
        assert usage["output_tokens"] == num_threads * tokens_per_call
        assert usage["total_tokens"] == num_threads * tokens_per_call * 2


class TestStrategyPriority:
    """llm_output takes priority over generation-level metadata."""

    def test_llm_output_takes_priority(self):
        handler = TokenUsageCallbackHandler()
        message = AIMessage(
            content="hi",
            response_metadata={"usage": {"input_tokens": 999, "output_tokens": 999}},
        )
        result = LLMResult(
            generations=[[ChatGeneration(message=message)]],
            llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20}},
        )

        handler.on_llm_end(result)
        usage = handler.get_usage()

        assert usage is not None
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20
