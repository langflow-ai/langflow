import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st
from langchain_core.documents import Document
from langflow.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH
from langflow.serialization.serialization import serialize, serialize_or_str
from pydantic import BaseModel as PydanticBaseModel
from pydantic.v1 import BaseModel as PydanticV1BaseModel

# Comprehensive hypothesis strategies
text_strategy = st.text(min_size=0, max_size=MAX_TEXT_LENGTH * 3)
bytes_strategy = st.binary(min_size=0, max_size=MAX_TEXT_LENGTH * 3)
datetime_strategy = st.datetimes(
    min_value=datetime.min,  # noqa: DTZ901 - Hypothesis requires naive datetime bounds
    max_value=datetime.max,  # noqa: DTZ901 - Hypothesis requires naive datetime bounds
    timezones=st.sampled_from([timezone.utc, None]),
)
decimal_strategy = st.decimals(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False, places=10)
uuid_strategy = st.uuids()
list_strategy = st.lists(st.one_of(st.integers(), st.text(), st.floats()), min_size=0, max_size=MAX_ITEMS_LENGTH * 3)
dict_strategy = st.dictionaries(
    keys=st.text(min_size=1),
    values=st.one_of(st.integers(), st.floats(), st.text(), st.booleans(), st.none()),
    min_size=0,
    max_size=MAX_ITEMS_LENGTH,
)

# Complex nested structure strategy
nested_strategy = st.recursive(
    st.one_of(st.integers(), st.floats(), st.text(), st.booleans()),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=10,
)


# Pydantic models for testing
class ModernModel(PydanticBaseModel):
    name: str
    value: int


class LegacyModel(PydanticV1BaseModel):
    name: str
    value: int


class TestSerializationHypothesis:
    """Hypothesis-based property tests for serialization logic."""

    @settings(max_examples=100)
    @given(text=text_strategy)
    def test_string_serialization(self, text: str) -> None:
        result: str = serialize(text)
        if len(text) > MAX_TEXT_LENGTH:
            expected: str = text[:MAX_TEXT_LENGTH] + "..."
            assert result == expected
        else:
            assert result == text

    @settings(max_examples=100)
    @given(data=bytes_strategy)
    def test_bytes_serialization(self, data: bytes) -> None:
        result: str = serialize(data)
        decoded: str = data.decode("utf-8", errors="ignore")
        if len(decoded) > MAX_TEXT_LENGTH:
            expected: str = decoded[:MAX_TEXT_LENGTH] + "..."
            assert result == expected
        else:
            assert result == decoded

    @settings(max_examples=100)
    @given(dt=datetime_strategy)
    def test_datetime_serialization(self, dt: datetime) -> None:
        result: str = serialize(dt)
        assert result == dt.replace(tzinfo=timezone.utc).isoformat()

    @settings(max_examples=100)
    @given(dec=decimal_strategy)
    def test_decimal_serialization(self, dec) -> None:
        result: float = serialize(dec)
        assert result == float(dec)

    @settings(max_examples=100)
    @given(uid=uuid_strategy)
    def test_uuid_serialization(self, uid) -> None:
        result: str = serialize(uid)
        assert result == str(uid)

    @settings(max_examples=100)
    @given(lst=list_strategy)
    def test_list_truncation(self, lst: list) -> None:
        result: list = serialize(lst, max_items=MAX_ITEMS_LENGTH)
        if len(lst) > MAX_ITEMS_LENGTH:
            assert len(result) == MAX_ITEMS_LENGTH + 1
            assert f"... [truncated {len(lst) - MAX_ITEMS_LENGTH} items]" in result
        else:
            assert result == lst

    @settings(max_examples=100)
    @given(dct=dict_strategy)
    def test_dict_serialization(self, dct: dict) -> None:
        result: dict = serialize(dct)
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, int | float | str | bool | type(None))

    @settings(max_examples=100)
    @given(value=st.integers())
    def test_pydantic_modern_model(self, value: int) -> None:
        model: ModernModel = ModernModel(name="test", value=value)
        result: dict = serialize(model)
        assert result == {"name": "test", "value": value}

    @settings(max_examples=100)
    @given(value=st.integers())
    def test_pydantic_v1_model(self, value: int) -> None:
        model: LegacyModel = LegacyModel(name="test", value=value)
        result: dict = serialize(model)
        assert result == {"name": "test", "value": value}

    def test_async_iterator_handling(self) -> None:
        async def async_gen():
            yield 1
            yield 2

        gen = async_gen()
        result: str = serialize(gen)
        assert result == "Unconsumed Stream"

    @settings(max_examples=100)
    @given(data=st.one_of(st.integers(), st.floats(allow_nan=True), st.booleans(), st.none()))
    def test_primitive_types(self, data: float | bool | None) -> None:  # noqa: FBT001
        result: int | float | bool | None = serialize(data)
        if isinstance(data, float) and math.isnan(data) and isinstance(result, float):
            assert math.isnan(result)
        else:
            assert result == data

    @settings(max_examples=100)
    @given(nested=nested_strategy)
    def test_nested_structures(self, nested: Any) -> None:
        result: list | dict | int | float | str | bool = serialize(nested)
        assert isinstance(result, list | dict | int | float | str | bool)

    @settings(max_examples=100)
    @given(text=text_strategy)
    def test_max_length_none(self, text: str) -> None:
        result: str = serialize(text, max_length=None)
        assert result == text

    @settings(max_examples=100)
    @given(lst=list_strategy)
    def test_max_items_none(self, lst: list) -> None:
        result: list = serialize(lst, max_items=None)
        assert result == lst

    @settings(max_examples=100)
    @given(obj=st.builds(object))
    def test_fallback_serialization(self, obj: object) -> None:
        result: str = serialize_or_str(obj)
        assert isinstance(result, str)
        assert str(obj) in result

    def test_document_serialization(self) -> None:
        doc: Document = Document(page_content="test", metadata={"source": "test"})
        result: dict = serialize(doc)
        assert isinstance(result, dict)
        assert "kwargs" in result
        assert "page_content" in result["kwargs"]
        assert result["kwargs"]["page_content"] == "test"
        assert "metadata" in result["kwargs"]
        assert result["kwargs"]["metadata"] == {"source": "test"}

    def test_class_serialization(self) -> None:
        class TestClass:
            def __init__(self, value: Any) -> None:
                self.value = value

        result: str = serialize(TestClass)
        assert result == str(TestClass)

    def test_instance_serialization(self) -> None:
        class TestClass:
            def __init__(self, value: int) -> None:
                self.value = value

        instance: TestClass = TestClass(42)
        result: str = serialize(instance)
        assert result == str(instance)

    def test_pydantic_class_serialization(self) -> None:
        result: str = serialize(ModernModel)
        assert result == repr(ModernModel)

    def test_builtin_type_serialization(self) -> None:
        result: str = serialize(int)
        assert result == repr(int)

    def test_none_serialization(self) -> None:
        result: None = serialize(None)
        assert result is None

    def test_custom_type_serialization(self) -> None:
        from typing import TypeVar

        T = TypeVar("T")
        result: str = serialize(T)
        assert result == repr(T)

    def test_nested_class_serialization(self) -> None:
        class Outer:
            class Inner:
                pass

        result: str = serialize(Outer.Inner)
        assert result == str(Outer.Inner)

    def test_enum_serialization(self) -> None:
        from enum import Enum

        class TestEnum(Enum):
            A = 1
            B = 2

        result: str = serialize(TestEnum.A)
        assert result == "TestEnum.A"

    def test_type_alias_serialization(self) -> None:
        IntList = list[int]  # noqa: N806
        result: str = serialize(IntList)
        assert result == repr(IntList)

    def test_generic_type_serialization(self) -> None:
        from typing import Generic, TypeVar

        T = TypeVar("T")

        class Box(Generic[T]):
            pass

        result: str = serialize(Box[int])
        assert result == repr(Box[int])

    def test_numpy_int64_serialization(self) -> None:
        """Test serialization of numpy.int64 values."""
        np_int = np.int64(42)
        result = serialize(np_int)
        assert result == 42
        assert isinstance(result, int)

    def test_numpy_numeric_serialization(self) -> None:
        """Test serialization of various numpy numeric types."""
        # Test integers
        assert serialize(np.int64(42)) == 42
        assert isinstance(serialize(np.int64(42)), int)

        # Test unsigned integers
        assert serialize(np.uint64(42)) == 42
        assert isinstance(serialize(np.uint64(42)), int)

        # Test floats
        assert serialize(np.float64(math.pi)) == math.pi
        assert isinstance(serialize(np.float64(math.pi)), float)

        # Test float32 (need to account for precision differences)
        float32_val = serialize(np.float32(math.pi))
        assert isinstance(float32_val, float)
        assert abs(float32_val - math.pi) < 1e-6  # Check if close enough

        # Test bool
        assert serialize(np.bool_(True)) is True  # noqa: FBT003
        assert isinstance(serialize(np.bool_(True)), bool)  # noqa: FBT003

        # Test complex numbers
        complex_val = serialize(np.complex64(1 + 2j))
        assert isinstance(complex_val, complex)
        assert abs(complex_val - (1 + 2j)) < 1e-6

        # Test strings
        assert serialize(np.str_("hello")) == "hello"
        assert isinstance(serialize(np.str_("hello")), str)

        # Test bytes
        bytes_val = np.bytes_(b"world")
        assert serialize(bytes_val) == "world"
        assert isinstance(serialize(bytes_val), str)

        # Test unicode
        assert serialize(np.str_("unicode")) == "unicode"
        assert isinstance(serialize(np.str_("unicode")), str)

        # Test object arrays
        obj_array = np.array([1, "two", 3.0], dtype=object)
        result = serialize(obj_array[0])
        assert result == 1
        assert isinstance(result, int)

        result = serialize(obj_array[1])
        assert result == "two"
        assert isinstance(result, str)

        result = serialize(obj_array[2])
        assert result == 3.0
        assert isinstance(result, float)

    def test_pandas_serialization(self) -> None:
        """Test serialization of pandas DataFrame."""
        # Test DataFrame
        test_df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [1.1, 2.2, 3.3]})
        result = serialize(test_df)
        assert isinstance(result, list)  # DataFrame is serialized to list of records
        assert len(result) == 3
        assert all(isinstance(row, dict) for row in result)
        assert all("A" in row and "B" in row and "C" in row for row in result)
        assert result[0] == {"A": 1, "B": "a", "C": 1.1}

        # Test DataFrame truncation
        df_long = pd.DataFrame({"A": range(MAX_ITEMS_LENGTH + 100)})
        result = serialize(df_long, max_items=MAX_ITEMS_LENGTH)
        assert isinstance(result, list)
        assert len(result) == MAX_ITEMS_LENGTH
        assert all("A" in row for row in result)

    def test_series_serialization(self) -> None:
        """Test serialization of pandas Series."""
        # Test Series
        series = pd.Series([1, 2, 3], name="test")
        result = serialize(series)
        assert isinstance(result, dict)
        assert len(result) == 3
        assert all(isinstance(v, int) for v in result.values())

    def test_series_truncation(self) -> None:
        """Test truncation of pandas Series."""
        # Test Series
        series_long = pd.Series(range(MAX_ITEMS_LENGTH + 100), name="test_long")
        result = serialize(series_long, max_items=MAX_ITEMS_LENGTH)
        assert isinstance(result, dict)
        assert len(result) == MAX_ITEMS_LENGTH
        assert all(isinstance(v, int) for v in result.values())
