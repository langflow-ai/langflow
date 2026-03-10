"""Tests for lfx.schema.token_usage shared extraction functions."""

from types import SimpleNamespace

from langchain_core.messages import AIMessage
from lfx.schema.properties import Usage
from lfx.schema.token_usage import (
    _normalize_usage_metadata,
    accumulate_usage,
    extract_usage_from_chunk,
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
