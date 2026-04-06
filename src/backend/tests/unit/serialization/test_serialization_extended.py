"""Extended tests for the serialization module - covering internal helpers."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import numpy as np
import pandas as pd
from langflow.serialization.serialization import (
    _serialize_bytes,
    _serialize_dataframe,
    _serialize_datetime,
    _serialize_dispatcher,
    _serialize_numpy_type,
    _serialize_pydantic,
    _serialize_series,
    _serialize_str,
    _truncate_value,
    serialize,
)
from pydantic import BaseModel


class TestSerializeStrEdgeCases:
    """Edge cases for string serialization."""

    def test_unicode_string(self):
        assert _serialize_str("héllo wörld", None, None) == "héllo wörld"

    def test_unicode_truncation(self):
        result = _serialize_str("héllo wörld", 5, None)
        assert result == "héllo..."

    def test_empty_string_with_zero_limit(self):
        assert _serialize_str("", 0, None) == ""

    def test_single_char(self):
        assert _serialize_str("a", 1, None) == "a"
        assert _serialize_str("ab", 1, None) == "a..."


class TestSerializeBytesEdgeCases:
    """Edge cases for bytes serialization."""

    def test_non_utf8_bytes(self):
        result = _serialize_bytes(b"\xff\xfe", None, None)
        assert isinstance(result, str)

    def test_non_utf8_bytes_truncated(self):
        result = _serialize_bytes(b"\xff\xfe\xfd\xfc", 2, None)
        assert isinstance(result, str)


class TestSerializeDatetimeEdgeCases:
    """Edge cases for datetime serialization."""

    def test_min_datetime(self):
        dt = datetime.min.replace(tzinfo=timezone.utc)
        result = _serialize_datetime(dt)
        assert isinstance(result, str)

    def test_datetime_with_microseconds(self):
        dt = datetime(2024, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        result = _serialize_datetime(dt)
        assert "123456" in result


class TestSerializeDispatcher:
    """Tests for _serialize_dispatcher."""

    def test_none(self):
        assert _serialize_dispatcher(None, None, None) is None

    def test_string(self):
        assert _serialize_dispatcher("hello", None, None) == "hello"

    def test_bytes(self):
        assert _serialize_dispatcher(b"hello", None, None) == "hello"

    def test_datetime(self):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = _serialize_dispatcher(dt, None, None)
        assert isinstance(result, str)

    def test_decimal(self):
        assert _serialize_dispatcher(Decimal("3.14"), None, None) == 3.14

    def test_uuid(self):
        uid = uuid4()
        assert _serialize_dispatcher(uid, None, None) == str(uid)

    def test_dict(self):
        result = _serialize_dispatcher({"a": 1}, None, None)
        assert result == {"a": 1}

    def test_list(self):
        result = _serialize_dispatcher([1, 2], None, None)
        assert result == [1, 2]

    def test_tuple(self):
        result = _serialize_dispatcher((1, 2), None, None)
        assert result == [1, 2]

    def test_bool(self):
        assert _serialize_dispatcher(True, None, None) is True
        assert _serialize_dispatcher(False, None, None) is False

    def test_int(self):
        assert _serialize_dispatcher(42, None, None) == 42

    def test_float_nan(self):
        assert _serialize_dispatcher(float("nan"), None, None) is None

    def test_float_inf(self):
        assert _serialize_dispatcher(float("inf"), None, None) is None


class TestSerializeNumpyType:
    """Tests for numpy type serialization."""

    def test_single_element_array(self):
        arr = np.array([42])
        result = _serialize_numpy_type(arr, None, None)
        assert result == 42

    def test_multi_element_numeric_array(self):
        arr = np.array([1, 2, 3])
        result = _serialize_numpy_type(arr, None, None)
        assert result == [1, 2, 3]

    def test_bool_array(self):
        arr = np.array([True])
        result = _serialize_numpy_type(arr, None, None)
        assert result is True

    def test_string_array(self):
        arr = np.array(["hello"])
        result = _serialize_numpy_type(arr, None, None)
        assert isinstance(result, str)


class TestSerializeDataframe:
    """Tests for DataFrame serialization."""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = _serialize_dataframe(df, None, None)
        assert result == []

    def test_dataframe_truncation(self):
        df = pd.DataFrame({"a": range(10)})
        result = _serialize_dataframe(df, None, 3)
        # DataFrame is truncated to 3 rows via head(), then serialized
        assert len(result) == 3

    def test_dataframe_with_mixed_types(self):
        df = pd.DataFrame({"int_col": [1, 2], "str_col": ["a", "b"], "float_col": [1.1, 2.2]})
        result = _serialize_dataframe(df, None, None)
        assert len(result) == 2
        assert result[0]["int_col"] == 1
        assert result[0]["str_col"] == "a"


class TestSerializeSeries:
    """Tests for Series serialization."""

    def test_empty_series(self):
        s = pd.Series([], dtype=float)
        result = _serialize_series(s, None, None)
        assert result == {}

    def test_series_truncation(self):
        s = pd.Series(range(10))
        result = _serialize_series(s, None, 3)
        assert len(result) == 3

    def test_series_with_string_index(self):
        s = pd.Series([1, 2, 3], index=["a", "b", "c"])
        result = _serialize_series(s, None, None)
        assert result == {"a": 1, "b": 2, "c": 3}


class TestTruncateValueEdgeCases:
    """Edge cases for _truncate_value."""

    def test_tuple_truncation(self):
        result = _truncate_value((1, 2, 3, 4, 5), None, 3)
        assert result == (1, 2, 3)

    def test_set_not_truncated(self):
        # Sets don't match the isinstance check for list|tuple
        result = _truncate_value({1, 2, 3}, None, 1)
        assert result == {1, 2, 3}

    def test_dict_not_truncated(self):
        result = _truncate_value({"a": 1, "b": 2}, 1, 1)
        assert result == {"a": 1, "b": 2}


class TestSerializePydantic:
    """Tests for Pydantic model serialization."""

    def test_nested_model(self):
        class Inner(BaseModel):
            value: int

        class Outer(BaseModel):
            name: str
            inner: Inner

        model = Outer(name="test", inner=Inner(value=42))
        result = _serialize_pydantic(model, None, None)
        assert result == {"name": "test", "inner": {"value": 42}}

    def test_model_with_optional(self):
        class TestModel(BaseModel):
            name: str
            optional_field: str | None = None

        model = TestModel(name="test")
        result = _serialize_pydantic(model, None, None)
        assert result == {"name": "test", "optional_field": None}


class TestSerializeComplexCases:
    """Tests for complex serialization scenarios."""

    def test_deeply_nested_structure(self):
        data = {"a": {"b": {"c": {"d": [1, 2, {"e": "deep"}]}}}}
        result = serialize(data)
        assert result == data

    def test_mixed_type_list(self):
        data = [1, "two", 3.0, True, None, {"key": "value"}]
        result = serialize(data)
        assert result == data

    def test_empty_structures(self):
        assert serialize({}) == {}
        assert serialize([]) == []
        assert serialize(()) == []

    def test_serialize_with_all_limits(self):
        data = {"long_string": "a" * 100, "long_list": list(range(50))}
        result = serialize(data, max_length=10, max_items=5)
        assert len(result["long_string"]) <= 13  # 10 + "..."
        assert len(result["long_list"]) == 6  # 5 + truncation message
