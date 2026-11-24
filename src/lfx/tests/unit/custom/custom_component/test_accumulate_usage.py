"""Tests for shared token usage accumulation and normalization functions.

These tests validate the accumulate_usage() and _normalize_usage_metadata()
functions from the shared lfx.schema.token_usage module.
"""

from lfx.schema.properties import Usage
from lfx.schema.token_usage import _normalize_usage_metadata, accumulate_usage


class TestAccumulateUsage:
    """Tests for accumulate_usage()."""

    def test_first_chunk_sets_usage(self):
        """When existing is None, returns the new chunk as-is."""
        new = Usage(input_tokens=100, output_tokens=50, total_tokens=150)

        result = accumulate_usage(None, new)

        assert result is new

    def test_accumulates_split_anthropic_chunks(self):
        """Anthropic sends input_tokens on message_start, output_tokens on message_delta."""
        start_chunk = Usage(input_tokens=100, output_tokens=0, total_tokens=100)
        delta_chunk = Usage(input_tokens=0, output_tokens=50, total_tokens=50)

        result = accumulate_usage(None, start_chunk)
        result = accumulate_usage(result, delta_chunk)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150

    def test_single_chunk_with_all_data(self):
        """OpenAI sends all usage on a single final chunk."""
        chunk = Usage(input_tokens=200, output_tokens=80, total_tokens=280)

        result = accumulate_usage(None, chunk)

        assert result.input_tokens == 200
        assert result.output_tokens == 80
        assert result.total_tokens == 280

    def test_handles_none_values_in_new_chunk(self):
        """None values in chunk are treated as 0 and don't overwrite existing."""
        existing = Usage(input_tokens=100, output_tokens=0, total_tokens=100)
        new = Usage(input_tokens=None, output_tokens=50, total_tokens=None)

        result = accumulate_usage(existing, new)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150

    def test_handles_none_values_in_existing(self):
        """None values in existing are treated as 0 during accumulation."""
        existing = Usage(input_tokens=None, output_tokens=None, total_tokens=None)
        new = Usage(input_tokens=50, output_tokens=30, total_tokens=80)

        result = accumulate_usage(existing, new)

        assert result.input_tokens == 50
        assert result.output_tokens == 30
        assert result.total_tokens == 80

    def test_zero_values_dont_overwrite(self):
        """Zero-value tokens in new chunk don't overwrite existing non-zero values."""
        existing = Usage(input_tokens=100, output_tokens=50, total_tokens=150)
        new = Usage(input_tokens=0, output_tokens=0, total_tokens=0)

        result = accumulate_usage(existing, new)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150


class TestNormalizeUsageMetadata:
    """Tests for _normalize_usage_metadata()."""

    def test_extracts_from_dict(self):
        um = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}

        result = _normalize_usage_metadata(um)

        assert isinstance(result, Usage)
        assert result.input_tokens == 10
        assert result.output_tokens == 20
        assert result.total_tokens == 30

    def test_extracts_from_object(self):
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
