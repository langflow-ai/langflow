import pytest

from lfx.schema.dataframe import Table
from lfx.schema.schema import get_message, get_type


def test_get_message_does_not_use_pandas_dataframe_data_attribute():
    table = Table([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])

    message = get_message(table)

    # For a Table/DataFrame payload, get_message should return the payload itself,
    # not pandas' internal BlockManager (`.data`).
    assert message is table
    assert get_type(table) == "array"


def test_table_serializes_to_records_for_ui():
    table = Table([{"a": 1}, {"a": 2}])

    # What the UI ultimately needs is records-like data.
    records = table.to_dict(orient="records")
    assert records == [{"a": 1}, {"a": 2}]
