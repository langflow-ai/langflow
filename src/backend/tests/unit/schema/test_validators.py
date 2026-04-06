"""Tests for langflow.schema.validators module."""

from datetime import datetime, timezone

import pytest
from langflow.schema.validators import (
    str_to_timestamp,
    timestamp_to_str,
    timestamp_with_fractional_seconds,
)


class TestTimestampToStr:
    """Tests for timestamp_to_str function."""

    def test_datetime_with_utc(self):
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        result = timestamp_to_str(dt)
        assert result == "2024-01-15 10:30:45 UTC"

    def test_datetime_without_timezone(self):
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = timestamp_to_str(dt)
        assert result == "2024-01-15 10:30:45 UTC"

    def test_iso_format_string(self):
        result = timestamp_to_str("2024-01-15T10:30:45")
        assert result == "2024-01-15 10:30:45 UTC"

    def test_standard_format_with_timezone(self):
        result = timestamp_to_str("2024-01-15 10:30:45 UTC")
        assert result == "2024-01-15 10:30:45 UTC"

    def test_format_without_timezone(self):
        result = timestamp_to_str("2024-01-15 10:30:45")
        assert result == "2024-01-15 10:30:45 UTC"

    def test_iso_with_microseconds(self):
        result = timestamp_to_str("2024-01-15T10:30:45.123456")
        assert result == "2024-01-15 10:30:45 UTC"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            timestamp_to_str("not-a-timestamp")

    def test_whitespace_stripped(self):
        result = timestamp_to_str("  2024-01-15T10:30:45  ")
        assert result == "2024-01-15 10:30:45 UTC"


class TestStrToTimestamp:
    """Tests for str_to_timestamp function."""

    def test_valid_format(self):
        result = str_to_timestamp("2024-01-15 10:30:45 UTC")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 45
        assert result.tzinfo == timezone.utc

    def test_datetime_passthrough(self):
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        result = str_to_timestamp(dt)
        assert result is dt

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            str_to_timestamp("2024-01-15T10:30:45")


class TestTimestampWithFractionalSeconds:
    """Tests for timestamp_with_fractional_seconds function."""

    def test_datetime_with_microseconds(self):
        dt = datetime(2024, 1, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
        result = timestamp_with_fractional_seconds(dt)
        assert result == "2024-01-15 10:30:45.123456 UTC"

    def test_datetime_without_timezone(self):
        dt = datetime(2024, 1, 15, 10, 30, 45, 123456)
        result = timestamp_with_fractional_seconds(dt)
        assert result == "2024-01-15 10:30:45.123456 UTC"

    def test_string_iso_with_microseconds(self):
        result = timestamp_with_fractional_seconds("2024-01-15T10:30:45.123456")
        assert result == "2024-01-15 10:30:45.123456 UTC"

    def test_string_without_fractional(self):
        result = timestamp_with_fractional_seconds("2024-01-15 10:30:45 UTC")
        assert result == "2024-01-15 10:30:45.000000 UTC"

    def test_string_without_timezone_no_fractional(self):
        result = timestamp_with_fractional_seconds("2024-01-15 10:30:45")
        assert result == "2024-01-15 10:30:45.000000 UTC"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            timestamp_with_fractional_seconds("not-a-date")

    def test_datetime_zero_microseconds(self):
        dt = datetime(2024, 1, 15, 10, 30, 45, 0, tzinfo=timezone.utc)
        result = timestamp_with_fractional_seconds(dt)
        assert result == "2024-01-15 10:30:45.000000 UTC"
