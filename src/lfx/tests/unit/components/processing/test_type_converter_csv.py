"""Tests for CSV auto-parsing in the Type Convert component."""

import json

from lfx.components.processing.converter import TypeConverterComponent
from lfx.schema.message import Message


def _to_json_records(csv_text: str) -> list[dict]:
    component = TypeConverterComponent(input_data=Message(text=csv_text), output_type="JSON", auto_parse=True)
    return component.convert_to_data().data["records"]


def test_blank_csv_cells_become_null():
    records = _to_json_records("name,age,score,active\nAna,28,1.5,true\nBruno,,,\n,34,2.0,false\n")

    assert records == [
        {"name": "Ana", "age": 28, "score": 1.5, "active": True},
        {"name": "Bruno", "age": None, "score": None, "active": None},
        {"name": None, "age": 34, "score": 2.0, "active": False},
    ]
    # NaN is not valid JSON, so strict serialization must succeed.
    json.dumps(records, allow_nan=False)


def test_csv_without_blank_cells_is_unchanged():
    records = _to_json_records("name,age,price\nAna,28,1.0\nBruno,34,2.5\n")

    assert records == [
        {"name": "Ana", "age": 28, "price": 1.0},
        {"name": "Bruno", "age": 34, "price": 2.5},
    ]
    assert all(isinstance(record["age"], int) for record in records)
    assert all(isinstance(record["price"], float) for record in records)


def test_blank_csv_cells_in_table_output():
    component = TypeConverterComponent(
        input_data=Message(text="name,age\nAna,28\nBruno,\n"), output_type="Table", auto_parse=True
    )
    result = component.convert_to_dataframe()

    assert list(result["name"]) == ["Ana", "Bruno"]
    assert result["age"].iloc[0] == 28
    assert result["age"].isna().iloc[1]
