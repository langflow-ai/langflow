"""Tests for TokenUsageCallbackHandler."""

import threading

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from lfx.base.agents.token_callback import TokenUsageCallbackHandler
from lfx.schema.properties import Usage


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

        assert isinstance(usage, Usage)
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20
        assert usage.total_tokens == 30


class TestExtractUsageFromUsageMetadata:
    """Strategy 2: generation.message.usage_metadata (LangChain standard)."""

    def test_extracts_from_usage_metadata(self):
        handler = TokenUsageCallbackHandler()
        message = AIMessage(content="hi")
        message.usage_metadata = {"input_tokens": 15, "output_tokens": 25}
        result = _make_llm_result(generations=[[ChatGeneration(message=message)]])

        handler.on_llm_end(result)
        usage = handler.get_usage()

        assert isinstance(usage, Usage)
        assert usage.input_tokens == 15
        assert usage.output_tokens == 25
        assert usage.total_tokens == 40


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

        assert isinstance(usage, Usage)
        assert usage.input_tokens == 50
        assert usage.output_tokens == 100
        assert usage.total_tokens == 150


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

        assert isinstance(usage, Usage)
        assert usage.input_tokens == 200
        assert usage.output_tokens == 300
        assert usage.total_tokens == 500


class TestAccumulation:
    """Token counts accumulate across multiple on_llm_end calls."""

    def test_accumulates_across_multiple_calls(self):
        handler = TokenUsageCallbackHandler()

        result1 = _make_llm_result(llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20}})
        result2 = _make_llm_result(llm_output={"token_usage": {"prompt_tokens": 30, "completion_tokens": 40}})

        handler.on_llm_end(result1)
        handler.on_llm_end(result2)

        usage = handler.get_usage()
        assert isinstance(usage, Usage)
        assert usage.input_tokens == 40
        assert usage.output_tokens == 60
        assert usage.total_tokens == 100


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
        assert isinstance(usage, Usage)
        assert usage.input_tokens == num_threads * tokens_per_call
        assert usage.output_tokens == num_threads * tokens_per_call
        assert usage.total_tokens == num_threads * tokens_per_call * 2


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

        assert isinstance(usage, Usage)
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20


class TestErrorPathCaptureInputTokens:
    """QA UI-013 (PR #12992): a failed LLM call must still contribute its input tokens.

    An LLM call that fails (e.g. HTTP 429 quota) must NOT silently contribute 0 tokens
    to the accumulator. The user is billed for the tokens sent in the request body;
    dropping them under-counts real consumption.

    The handler MUST capture an estimate of the input tokens on
    `on_chat_model_start` / `on_llm_start` and flush it into the totals on
    `on_llm_error` (when there is no successful `on_llm_end` to read actual usage
    from). On `on_llm_end`, the actual server-reported usage supersedes the
    estimate (no double counting).
    """

    def test_should_accumulate_estimated_input_tokens_when_chat_model_call_errors(self):
        import uuid

        from langchain_core.messages import HumanMessage, SystemMessage

        handler = TokenUsageCallbackHandler()
        run_id = uuid.uuid4()

        # A roughly 80-char prompt + 200-char system instruction. With the chars/4
        # heuristic that maps to ~70 input tokens — close enough for billing-aware
        # observability without taking on tiktoken as a dependency.
        messages = [
            [
                SystemMessage(content="x" * 200),
                HumanMessage(content="Please look up the latest results for last quarter."),
            ]
        ]
        handler.on_chat_model_start({}, messages, run_id=run_id)

        # No on_llm_end: the call failed before the server returned a usage block.
        handler.on_llm_error(RuntimeError("HTTP 429 insufficient_quota"), run_id=run_id)

        usage = handler.get_usage()
        assert usage is not None, (
            "Tokens sent with a failed LLM call must still be accumulated. Otherwise "
            "the trace under-counts real billed consumption (UI-013 regression)."
        )
        assert usage.input_tokens, (
            f"Expected an input-token estimate from the failed call's messages; got {usage.input_tokens}"
        )
        assert usage.input_tokens >= 50, (
            f"Expected an input-token estimate from the failed call's messages; got {usage.input_tokens}"
        )

    def test_should_not_double_count_input_tokens_when_call_succeeds(self):
        """If on_llm_end fires (call succeeded), prefer server-reported usage.

        Drop the pre-call estimate — otherwise we double-count input tokens.
        """
        import uuid

        from langchain_core.messages import HumanMessage

        handler = TokenUsageCallbackHandler()
        run_id = uuid.uuid4()

        handler.on_chat_model_start({}, [[HumanMessage(content="z" * 400)]], run_id=run_id)
        handler.on_llm_end(
            _make_llm_result(llm_output={"token_usage": {"prompt_tokens": 100, "completion_tokens": 50}}),
            run_id=run_id,
        )

        usage = handler.get_usage()
        assert usage is not None
        assert usage.input_tokens == 100, (
            f"on_llm_end must overwrite the estimate with server-reported usage, got {usage.input_tokens}"
        )
        assert usage.output_tokens == 50

    def test_should_handle_llm_error_without_prior_start_gracefully(self):
        """If the runtime swallowed on_*_start (unusual but possible), tolerate it.

        An error with no recorded estimate must not raise — just count nothing for it.
        """
        import uuid

        handler = TokenUsageCallbackHandler()
        handler.on_llm_error(RuntimeError("boom"), run_id=uuid.uuid4())
        assert handler.get_usage() is None
