"""Tests for langflow.services.database.utils pure utility functions."""

from uuid import UUID

import pytest

from langflow.services.database.utils import (
    Result,
    TableResults,
    normalize_string_or_none,
    parse_uuid,
    validate_non_empty_string,
    validate_non_empty_string_optional,
)


# -- helpers to simulate pydantic FieldValidationInfo --
class _FakeInfo:
    def __init__(self, field_name: str):
        self.field_name = field_name


class TestValidateNonEmptyString:
    def test_valid(self):
        assert validate_non_empty_string("hello", _FakeInfo("name")) == "hello"

    def test_strips_whitespace(self):
        assert validate_non_empty_string("  hello  ", _FakeInfo("name")) == "hello"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            validate_non_empty_string("", _FakeInfo("name"))

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="title must not be empty"):
            validate_non_empty_string("   ", _FakeInfo("title"))

    def test_info_without_field_name(self):
        """When info has no field_name attr, falls back to 'Field'."""

        class _NoFieldInfo:
            pass

        with pytest.raises(ValueError, match="Field must not be empty"):
            validate_non_empty_string("", _NoFieldInfo())


class TestValidateNonEmptyStringOptional:
    def test_none_passthrough(self):
        assert validate_non_empty_string_optional(None, _FakeInfo("x")) is None

    def test_valid_string(self):
        assert validate_non_empty_string_optional("ok", _FakeInfo("x")) == "ok"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_non_empty_string_optional("", _FakeInfo("x"))


class TestNormalizeStringOrNone:
    def test_none(self):
        assert normalize_string_or_none(None) is None

    def test_non_empty(self):
        assert normalize_string_or_none("  hi  ") == "hi"

    def test_empty_becomes_none(self):
        assert normalize_string_or_none("") is None

    def test_whitespace_becomes_none(self):
        assert normalize_string_or_none("   ") is None


class TestParseUuid:
    def test_uuid_passthrough(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        assert parse_uuid(uid) is uid

    def test_valid_string(self):
        result = parse_uuid("12345678-1234-5678-1234-567812345678")
        assert isinstance(result, UUID)

    def test_string_stripped(self):
        result = parse_uuid("  12345678-1234-5678-1234-567812345678  ")
        assert isinstance(result, UUID)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_uuid("")

    def test_whitespace_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_uuid("   ")

    def test_invalid_uuid_raises(self):
        with pytest.raises(ValueError, match="not a valid UUID"):
            parse_uuid("not-a-uuid")

    def test_custom_field_name(self):
        with pytest.raises(ValueError, match="flow_id must not be empty"):
            parse_uuid("", field_name="flow_id")

    def test_wrong_type_raises(self):
        with pytest.raises(TypeError, match="must be a UUID or string"):
            parse_uuid(12345, field_name="id")


class TestDataclasses:
    def test_result(self):
        r = Result(name="col1", type="VARCHAR", success=True)
        assert r.name == "col1"
        assert r.type == "VARCHAR"
        assert r.success is True

    def test_table_results(self):
        tr = TableResults(
            table_name="users",
            results=[Result(name="id", type="INTEGER", success=True)],
        )
        assert tr.table_name == "users"
        assert len(tr.results) == 1
