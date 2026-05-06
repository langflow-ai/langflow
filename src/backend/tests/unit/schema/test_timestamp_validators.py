"""Unit tests for timestamp validator functions in both langflow and lfx schemas."""

from datetime import datetime, timezone

import langflow.schema.validators as lf_validators
import lfx.schema.validators as lfx_validators
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(year, month, day, hour, minute, second, microsecond=0):
    return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Parametrize over both implementations so every test runs for both
# ---------------------------------------------------------------------------

VALIDATOR_MODULES = [
    pytest.param(lf_validators, id="langflow"),
    pytest.param(lfx_validators, id="lfx"),
]


@pytest.mark.parametrize("mod", VALIDATOR_MODULES)
class TestTimestampToStr:
    """timestamp_to_str converts various inputs to the canonical string format."""

    def test_datetime_with_microseconds_preserved(self, mod):
        dt = _utc(2024, 1, 15, 10, 30, 45, 123456)
        result = mod.timestamp_to_str(dt)
        assert result == "2024-01-15 10:30:45.123456 UTC"

    def test_datetime_without_microseconds_zero_padded(self, mod):
        dt = _utc(2024, 6, 1, 0, 0, 0, 0)
        result = mod.timestamp_to_str(dt)
        assert result == "2024-06-01 00:00:00.000000 UTC"

    def test_datetime_naive_treated_as_utc(self, mod):
        dt = datetime(2024, 3, 10, 8, 0, 0, 500000)  # noqa: DTZ001 — intentionally naive to test the fallback
        result = mod.timestamp_to_str(dt)
        assert result == "2024-03-10 08:00:00.500000 UTC"

    def test_string_old_format_no_microseconds(self, mod):
        """Backward compat: old format without microseconds must still parse."""
        result = mod.timestamp_to_str("2024-06-15 10:30:00 UTC")
        assert result == "2024-06-15 10:30:00.000000 UTC"

    def test_string_new_format_with_microseconds(self, mod):
        result = mod.timestamp_to_str("2024-01-15 10:30:45.123456 UTC")
        assert result == "2024-01-15 10:30:45.123456 UTC"

    def test_string_iso_with_numeric_tz_offset_positive(self, mod):
        """Non-UTC numeric offset must be converted correctly, not silently corrupted."""
        # +05:00 means real UTC is 05:30:45
        result = mod.timestamp_to_str("2024-01-15T10:30:45+05:00")
        assert result == "2024-01-15 05:30:45.000000 UTC"

    def test_string_iso_with_numeric_tz_offset_negative(self, mod):
        # -03:00 means real UTC is 13:30:45
        result = mod.timestamp_to_str("2024-01-15T10:30:45-03:00")
        assert result == "2024-01-15 13:30:45.000000 UTC"

    def test_string_invalid_format_raises(self, mod):
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            mod.timestamp_to_str("not-a-date")


@pytest.mark.parametrize("mod", VALIDATOR_MODULES)
class TestStrToTimestamp:
    """str_to_timestamp converts strings (and datetimes) back to datetime objects."""

    def test_new_format_with_microseconds(self, mod):
        result = mod.str_to_timestamp("2024-01-15 10:30:45.123456 UTC")
        assert result == _utc(2024, 1, 15, 10, 30, 45, 123456)

    def test_old_format_without_microseconds_backward_compat(self, mod):
        """Old-format strings must parse without crashing."""
        result = mod.str_to_timestamp("2024-06-15 10:30:00 UTC")
        assert result == _utc(2024, 6, 15, 10, 30, 0, 0)

    def test_iso_with_numeric_tz_offset(self, mod):
        result = mod.str_to_timestamp("2024-01-15T10:30:45+05:00")
        assert result == _utc(2024, 1, 15, 5, 30, 45, 0)

    def test_passthrough_for_datetime_object(self, mod):
        dt = _utc(2024, 5, 20, 12, 0, 0, 999)
        assert mod.str_to_timestamp(dt) is dt

    def test_invalid_string_raises(self, mod):
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            mod.str_to_timestamp("not-a-date")


@pytest.mark.parametrize("mod", VALIDATOR_MODULES)
class TestRoundtrip:
    """timestamp_to_str ↔ str_to_timestamp must be lossless for microseconds."""

    def test_microseconds_survive_roundtrip(self, mod):
        original = _utc(2024, 11, 3, 22, 59, 59, 999999)
        as_str = mod.timestamp_to_str(original)
        recovered = mod.str_to_timestamp(as_str)
        assert recovered == original

    def test_zero_microseconds_survive_roundtrip(self, mod):
        original = _utc(2024, 1, 1, 0, 0, 0, 0)
        as_str = mod.timestamp_to_str(original)
        recovered = mod.str_to_timestamp(as_str)
        assert recovered == original


@pytest.mark.parametrize("mod", VALIDATOR_MODULES)
class TestMessageOrdering:
    """Two messages differing only by microseconds must maintain correct order."""

    def test_sub_second_ordering(self, mod):
        earlier = _utc(2024, 6, 15, 12, 0, 0, 1)
        later = _utc(2024, 6, 15, 12, 0, 0, 999999)

        earlier_str = mod.timestamp_to_str(earlier)
        later_str = mod.timestamp_to_str(later)

        # String comparison must preserve chronological order
        assert earlier_str < later_str

        # And roundtrip back to datetime must also preserve order
        assert mod.str_to_timestamp(earlier_str) < mod.str_to_timestamp(later_str)


class TestEncoderCompatibility:
    """encode_datetime output must be parseable by both validator chains."""

    def test_encode_datetime_parseable_by_langflow_str_to_timestamp(self):
        from langflow.schema.encoders import encode_datetime

        dt = _utc(2024, 8, 20, 14, 0, 0, 654321)
        encoded = encode_datetime(dt)
        recovered = lf_validators.str_to_timestamp(encoded)
        assert recovered == dt

    def test_encode_datetime_parseable_by_lfx_str_to_timestamp(self):
        from langflow.schema.encoders import encode_datetime

        dt = _utc(2024, 8, 20, 14, 0, 0, 654321)
        encoded = encode_datetime(dt)
        recovered = lfx_validators.str_to_timestamp(encoded)
        assert recovered == dt

    def test_encode_datetime_includes_microseconds(self):
        from langflow.schema.encoders import encode_datetime

        dt = _utc(2024, 1, 1, 0, 0, 0, 123456)
        result = encode_datetime(dt)
        assert "123456" in result
