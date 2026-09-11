from uuid import UUID

import pytest
from langflow.services.database.utils import parse_uuid


class TestParseUuid:
    """Tests for the shared parse_uuid utility."""

    def test_passthrough_uuid(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        assert parse_uuid(uid) is uid

    def test_valid_string_uuid(self):
        raw = "12345678-1234-5678-1234-567812345678"
        result = parse_uuid(raw)
        assert isinstance(result, UUID)
        assert str(result) == raw

    def test_strips_whitespace(self):
        raw = "  12345678-1234-5678-1234-567812345678  "
        result = parse_uuid(raw)
        assert str(result) == "12345678-1234-5678-1234-567812345678"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_uuid("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_uuid("   ")

    def test_invalid_string_raises_with_field_name(self):
        with pytest.raises(ValueError, match="my_field is not a valid UUID"):
            parse_uuid("not-a-uuid", field_name="my_field")

    def test_default_field_name_in_error(self):
        with pytest.raises(ValueError, match="value is not a valid UUID"):
            parse_uuid("not-a-uuid")

    def test_unsupported_type_raises_type_error(self):
        with pytest.raises(TypeError, match="my_field must be a UUID or string, got int"):
            parse_uuid(12345, field_name="my_field")  # type: ignore[arg-type]

    def test_unsupported_type_default_field_name(self):
        with pytest.raises(TypeError, match="value must be a UUID or string, got list"):
            parse_uuid([], field_name="value")  # type: ignore[arg-type]
