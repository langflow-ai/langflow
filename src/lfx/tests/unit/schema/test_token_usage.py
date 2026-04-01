"""Tests for lfx.schema.token_usage shared extraction functions."""

from types import SimpleNamespace

from langchain_core.messages import AIMessage
from lfx.schema.properties import Usage
from lfx.schema.token_usage import (
    _normalize_usage_metadata,
    accumulate_usage,
    extract_usage_from_chunk,
    extract_usage_from_llm_result,
    extract_usage_from_message,
)


class TestExtractUsageFromMessage:
    """Tests for extract_usage_from_message()."""

    def test_extracts_from_usage_metadata(self):
        message = AIMessage(content="hi")
        message.usage_metadata = {"input_tokens": 15, "output_tokens": 25}

        result = extract_usage_from_message(message)

        assert isinstance(result, Usage)
        assert result.input_tokens == 15
        assert result.output_tokens == 25
        assert result.total_tokens == 40

    def test_extracts_from_openai_response_metadata(self):
        message = AIMessage(
            content="hi",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 100,
                    "total_tokens": 150,
                }
            },
        )

        result = extract_usage_from_message(message)

        assert isinstance(result, Usage)
        assert result.input_tokens == 50
        assert result.output_tokens == 100
        assert result.total_tokens == 150

    def test_extracts_from_anthropic_response_metadata(self):
        message = AIMessage(
            content="hi",
            response_metadata={
                "usage": {
                    "input_tokens": 200,
                    "output_tokens": 300,
                }
            },
        )

        result = extract_usage_from_message(message)

        assert isinstance(result, Usage)
        assert result.input_tokens == 200
        assert result.output_tokens == 300
        assert result.total_tokens == 500

    def test_returns_none_for_no_metadata(self):
        message = AIMessage(content="hi")

        result = extract_usage_from_message(message)

        assert result is None

    def test_returns_none_for_empty_response_metadata(self):
        message = AIMessage(content="hi", response_metadata={})

        result = extract_usage_from_message(message)

        assert result is None

    def test_returns_none_for_zero_usage_metadata(self):
        message = AIMessage(content="hi")
        message.usage_metadata = {"input_tokens": 0, "output_tokens": 0}

        result = extract_usage_from_message(message)

        assert result is None

    def test_usage_metadata_takes_priority_over_response_metadata(self):
        message = AIMessage(
            content="hi",
            response_metadata={"usage": {"input_tokens": 999, "output_tokens": 999}},
        )
        message.usage_metadata = {"input_tokens": 10, "output_tokens": 20}

        result = extract_usage_from_message(message)

        assert result is not None
        assert result.input_tokens == 10
        assert result.output_tokens == 20

    def test_openai_takes_priority_over_anthropic(self):
        message = AIMessage(
            content="hi",
            response_metadata={
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                "usage": {"input_tokens": 999, "output_tokens": 999},
            },
        )

        result = extract_usage_from_message(message)

        assert result is not None
        assert result.input_tokens == 10
        assert result.output_tokens == 20

    def test_anthropic_total_tokens_calculated_when_both_present(self):
        message = AIMessage(
            content="hi",
            response_metadata={
                "usage": {"input_tokens": 100, "output_tokens": 200},
            },
        )

        result = extract_usage_from_message(message)

        assert result is not None
        assert result.total_tokens == 300

    def test_anthropic_total_tokens_none_when_both_missing(self):
        message = AIMessage(
            content="hi",
            response_metadata={
                "usage": {"input_tokens": None, "output_tokens": None},
            },
        )

        result = extract_usage_from_message(message)

        assert result is not None
        assert result.total_tokens is None


class TestExtractUsageFromLlmResult:
    """Tests for extract_usage_from_llm_result()."""

    @staticmethod
    def _make_llm_result(llm_output=None, generations=None):
        """Create a duck-typed LLMResult-like object for testing."""
        return SimpleNamespace(
            llm_output=llm_output,
            generations=generations or [],
        )

    @staticmethod
    def _make_generation(message=None, generation_info=None):
        """Create a duck-typed generation object."""
        return SimpleNamespace(message=message, generation_info=generation_info)

    def test_extracts_from_llm_output_token_usage(self):
        """Strategy 1: llm_output['token_usage'] (legacy OpenAI path)."""
        result_obj = self._make_llm_result(
            llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}},
        )

        result = extract_usage_from_llm_result(result_obj)

        assert isinstance(result, Usage)
        assert result.input_tokens == 10
        assert result.output_tokens == 20
        assert result.total_tokens == 30

    def test_extracts_from_usage_metadata_via_message(self):
        """Strategy 2: generations[].message.usage_metadata via extract_usage_from_message()."""
        message = AIMessage(content="hi")
        message.usage_metadata = {"input_tokens": 15, "output_tokens": 25}
        gen = self._make_generation(message=message)
        result_obj = self._make_llm_result(generations=[[gen]])

        result = extract_usage_from_llm_result(result_obj)

        assert isinstance(result, Usage)
        assert result.input_tokens == 15
        assert result.output_tokens == 25
        assert result.total_tokens == 40

    def test_extracts_from_response_metadata_token_usage(self):
        """Strategy 2: generations[].message.response_metadata['token_usage'] via extract_usage_from_message()."""
        message = AIMessage(
            content="hi",
            response_metadata={"token_usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150}},
        )
        gen = self._make_generation(message=message)
        result_obj = self._make_llm_result(generations=[[gen]])

        result = extract_usage_from_llm_result(result_obj)

        assert isinstance(result, Usage)
        assert result.input_tokens == 50
        assert result.output_tokens == 100
        assert result.total_tokens == 150

    def test_extracts_from_response_metadata_usage_anthropic(self):
        """Strategy 2: generations[].message.response_metadata['usage'] via extract_usage_from_message()."""
        message = AIMessage(
            content="hi",
            response_metadata={"usage": {"input_tokens": 200, "output_tokens": 300}},
        )
        gen = self._make_generation(message=message)
        result_obj = self._make_llm_result(generations=[[gen]])

        result = extract_usage_from_llm_result(result_obj)

        assert isinstance(result, Usage)
        assert result.input_tokens == 200
        assert result.output_tokens == 300
        assert result.total_tokens == 500

    def test_extracts_from_generation_info_token_usage(self):
        """Strategy 3: generation_info['token_usage'] fallback (older adapters)."""
        gen = self._make_generation(
            message=None,
            generation_info={"token_usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}},
        )
        result_obj = self._make_llm_result(generations=[[gen]])

        result = extract_usage_from_llm_result(result_obj)

        assert isinstance(result, Usage)
        assert result.input_tokens == 5
        assert result.output_tokens == 10
        assert result.total_tokens == 15

    def test_extracts_from_generation_info_usage_anthropic(self):
        """Strategy 3: generation_info['usage'] fallback (older Anthropic adapters)."""
        gen = self._make_generation(
            message=None,
            generation_info={"usage": {"input_tokens": 30, "output_tokens": 40}},
        )
        result_obj = self._make_llm_result(generations=[[gen]])

        result = extract_usage_from_llm_result(result_obj)

        assert isinstance(result, Usage)
        assert result.input_tokens == 30
        assert result.output_tokens == 40
        assert result.total_tokens == 70

    def test_returns_none_when_no_usage_data(self):
        result_obj = self._make_llm_result(llm_output={}, generations=[[]])

        result = extract_usage_from_llm_result(result_obj)

        assert result is None

    def test_returns_none_for_empty_result(self):
        result_obj = self._make_llm_result()

        result = extract_usage_from_llm_result(result_obj)

        assert result is None

    def test_llm_output_takes_priority_over_usage_metadata(self):
        """llm_output strategy should win over message-level extraction."""
        message = AIMessage(content="hi")
        message.usage_metadata = {"input_tokens": 999, "output_tokens": 999}
        gen = self._make_generation(message=message)
        result_obj = self._make_llm_result(
            llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}},
            generations=[[gen]],
        )

        result = extract_usage_from_llm_result(result_obj)

        assert result.input_tokens == 10
        assert result.output_tokens == 20

    def test_message_takes_priority_over_generation_info(self):
        """Message-level extraction should win over generation_info fallback."""
        message = AIMessage(content="hi")
        message.usage_metadata = {"input_tokens": 10, "output_tokens": 20}
        gen = self._make_generation(
            message=message,
            generation_info={"token_usage": {"prompt_tokens": 999, "completion_tokens": 999}},
        )
        result_obj = self._make_llm_result(generations=[[gen]])

        result = extract_usage_from_llm_result(result_obj)

        assert result.input_tokens == 10
        assert result.output_tokens == 20

    def test_skips_zero_llm_output_falls_through_to_message(self):
        """Zero values in llm_output should fall through to message strategies."""
        message = AIMessage(content="hi")
        message.usage_metadata = {"input_tokens": 15, "output_tokens": 25}
        gen = self._make_generation(message=message)
        result_obj = self._make_llm_result(
            llm_output={"token_usage": {"prompt_tokens": 0, "completion_tokens": 0}},
            generations=[[gen]],
        )

        result = extract_usage_from_llm_result(result_obj)

        assert result.input_tokens == 15
        assert result.output_tokens == 25

    def test_returns_none_for_none_response(self):
        """Passing None should not raise and should return None."""
        result = extract_usage_from_llm_result(None)

        assert result is None

    def test_total_tokens_is_recalculated_from_sum(self):
        """total_tokens is always recalculated as input + output, not taken from provider."""
        result_obj = self._make_llm_result(
            llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 999}},
        )

        result = extract_usage_from_llm_result(result_obj)

        # The function recalculates total_tokens rather than using the provider value
        assert result.total_tokens == 30


class TestExtractUsageFromChunk:
    """Tests for extract_usage_from_chunk()."""

    def test_extracts_from_usage_metadata_dict(self):
        chunk = SimpleNamespace(
            content="hi",
            usage_metadata={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            response_metadata=None,
        )

        result = extract_usage_from_chunk(chunk)

        assert isinstance(result, Usage)
        assert result.input_tokens == 10
        assert result.output_tokens == 20
        assert result.total_tokens == 30

    def test_extracts_from_response_metadata_token_usage(self):
        chunk = SimpleNamespace(
            content="hi",
            usage_metadata=None,
            response_metadata={"token_usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150}},
        )

        result = extract_usage_from_chunk(chunk)

        assert isinstance(result, Usage)
        assert result.input_tokens == 50
        assert result.output_tokens == 100
        assert result.total_tokens == 150

    def test_extracts_from_response_metadata_usage(self):
        chunk = SimpleNamespace(
            content="hi",
            usage_metadata=None,
            response_metadata={"usage": {"input_tokens": 200, "output_tokens": 300}},
        )

        result = extract_usage_from_chunk(chunk)

        assert isinstance(result, Usage)
        assert result.input_tokens == 200
        assert result.output_tokens == 300
        assert result.total_tokens is None

    def test_returns_none_for_no_metadata(self):
        chunk = SimpleNamespace(content="hi", usage_metadata=None, response_metadata=None)

        result = extract_usage_from_chunk(chunk)

        assert result is None

    def test_returns_none_for_empty_usage_metadata(self):
        chunk = SimpleNamespace(content="hi", usage_metadata={}, response_metadata=None)

        result = extract_usage_from_chunk(chunk)

        assert result is None


class TestAccumulateUsage:
    """Tests for accumulate_usage()."""

    def test_first_chunk_returns_new(self):
        new = Usage(input_tokens=100, output_tokens=50, total_tokens=150)

        result = accumulate_usage(None, new)

        assert result is new

    def test_none_new_returns_existing(self):
        existing = Usage(input_tokens=100, output_tokens=50, total_tokens=150)

        result = accumulate_usage(existing, None)

        assert result is existing

    def test_both_none_returns_none(self):
        result = accumulate_usage(None, None)

        assert result is None

    def test_accumulates_split_anthropic_chunks(self):
        start = Usage(input_tokens=100, output_tokens=0, total_tokens=100)
        delta = Usage(input_tokens=0, output_tokens=50, total_tokens=50)

        result = accumulate_usage(None, start)
        result = accumulate_usage(result, delta)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150

    def test_accumulates_multiple_chunks(self):
        chunk1 = Usage(input_tokens=10, output_tokens=20, total_tokens=30)
        chunk2 = Usage(input_tokens=30, output_tokens=40, total_tokens=70)

        result = accumulate_usage(None, chunk1)
        result = accumulate_usage(result, chunk2)

        assert result.input_tokens == 40
        assert result.output_tokens == 60
        assert result.total_tokens == 100

    def test_handles_none_values_in_new(self):
        existing = Usage(input_tokens=100, output_tokens=0, total_tokens=100)
        new = Usage(input_tokens=None, output_tokens=50, total_tokens=None)

        result = accumulate_usage(existing, new)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150


class TestStreamingTokenAccumulation:
    """Tests for streaming token accumulation across multiple chunks."""

    def test_accumulates_openai_format_chunks(self):
        # Simulate OpenAI streaming where usage arrives in response_metadata.token_usage
        chunks = [
            SimpleNamespace(
                content="Hello",
                usage_metadata=None,
                response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
            ),
            SimpleNamespace(
                content=" world",
                usage_metadata=None,
                response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}},
            ),
            SimpleNamespace(
                content="!",
                usage_metadata=None,
                response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}},
            ),
        ]

        usage_data = None
        for chunk in chunks:
            chunk_usage = extract_usage_from_chunk(chunk)
            usage_data = accumulate_usage(usage_data, chunk_usage)

        assert usage_data is not None
        assert usage_data.input_tokens == 30
        assert usage_data.output_tokens == 30
        assert usage_data.total_tokens == 60

    def test_accumulates_anthropic_format_chunks(self):
        # Simulate Anthropic streaming where input comes first, then output
        start_chunk = SimpleNamespace(
            content="", usage_metadata=None, response_metadata={"usage": {"input_tokens": 100, "output_tokens": 0}}
        )
        delta_chunk = SimpleNamespace(
            content="response text",
            usage_metadata=None,
            response_metadata={"usage": {"input_tokens": 0, "output_tokens": 50}},
        )

        usage_data = None
        for chunk in [start_chunk, delta_chunk]:
            chunk_usage = extract_usage_from_chunk(chunk)
            usage_data = accumulate_usage(usage_data, chunk_usage)

        assert usage_data is not None
        assert usage_data.input_tokens == 100
        assert usage_data.output_tokens == 50

    def test_accumulates_usage_metadata_chunks(self):
        # Simulate standard LangChain usage_metadata format
        chunks = [
            SimpleNamespace(
                content="part1",
                usage_metadata={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
                response_metadata=None,
            ),
            SimpleNamespace(
                content="part2",
                usage_metadata={"input_tokens": 5, "output_tokens": 7, "total_tokens": 12},
                response_metadata=None,
            ),
        ]

        usage_data = None
        for chunk in chunks:
            chunk_usage = extract_usage_from_chunk(chunk)
            usage_data = accumulate_usage(usage_data, chunk_usage)

        assert usage_data is not None
        assert usage_data.input_tokens == 10
        assert usage_data.output_tokens == 10
        assert usage_data.total_tokens == 20

    def test_skips_chunks_without_usage_data(self):
        # Intermediate streaming chunks typically have no usage — only the last chunk does
        chunks = [
            SimpleNamespace(content="token1", usage_metadata=None, response_metadata=None),
            SimpleNamespace(content="token2", usage_metadata=None, response_metadata=None),
            SimpleNamespace(
                content="token3",
                usage_metadata={"input_tokens": 20, "output_tokens": 30, "total_tokens": 50},
                response_metadata=None,
            ),
        ]

        usage_data = None
        for chunk in chunks:
            chunk_usage = extract_usage_from_chunk(chunk)
            usage_data = accumulate_usage(usage_data, chunk_usage)

        assert usage_data is not None
        assert usage_data.input_tokens == 20
        assert usage_data.output_tokens == 30
        assert usage_data.total_tokens == 50

    def test_all_chunks_without_usage_returns_none(self):
        # If no chunk carries usage, result should be None
        chunks = [
            SimpleNamespace(content="a", usage_metadata=None, response_metadata=None),
            SimpleNamespace(content="b", usage_metadata=None, response_metadata=None),
        ]

        usage_data = None
        for chunk in chunks:
            chunk_usage = extract_usage_from_chunk(chunk)
            usage_data = accumulate_usage(usage_data, chunk_usage)

        assert usage_data is None


class TestNormalizeUsageMetadata:
    """Tests for _normalize_usage_metadata()."""

    def test_from_dict(self):
        um = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}

        result = _normalize_usage_metadata(um)

        assert isinstance(result, Usage)
        assert result.input_tokens == 10
        assert result.output_tokens == 20
        assert result.total_tokens == 30

    def test_from_object(self):
        class UsageMeta:
            input_tokens = 15
            output_tokens = 25
            total_tokens = 40

        result = _normalize_usage_metadata(UsageMeta())

        assert isinstance(result, Usage)
        assert result.input_tokens == 15
        assert result.output_tokens == 25
        assert result.total_tokens == 40

    def test_handles_missing_attrs_on_object(self):
        class Partial:
            input_tokens = 10

        result = _normalize_usage_metadata(Partial())

        assert result.input_tokens == 10
        assert result.output_tokens is None
        assert result.total_tokens is None
