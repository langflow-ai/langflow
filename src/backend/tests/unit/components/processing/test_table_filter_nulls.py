"""Table string filters must not turn missing cells into searchable text."""

import math

import pandas as pd
import pytest
from lfx.components.processing.dataframe_operations import DataFrameOperationsComponent
from lfx.components.processing.operations import OperationsComponent
from lfx.schema.dataframe import DataFrame


@pytest.mark.parametrize("component_type", [DataFrameOperationsComponent, OperationsComponent])
@pytest.mark.parametrize(
    ("operator", "query", "expected_ids"),
    [
        ("contains", "nan", [0, 4]),
        ("not contains", "nan", [1, 2, 3, 5, 6, 7]),
        ("starts with", "nan", [4]),
        ("ends with", "nan", [4]),
        ("contains", "None", [5]),
        ("contains", "<NA>", [6]),
        ("contains", "123", [7]),
        ("contains", "", [0, 4, 5, 6, 7]),
        ("not contains", "", [1, 2, 3]),
    ],
)
def test_text_filter_treats_missing_cells_as_nonmatches(component_type, operator, query, expected_ids):
    component = component_type()
    values = pd.Series(["banana", None, math.nan, pd.NA, "nan", "None", "<NA>", 123], dtype=object)
    component.df = DataFrame(pd.DataFrame({"id": range(len(values)), "value": values}))
    component.operation = [{"name": "Filter"}]
    component.column_name = "value"
    component.filter_operator = operator
    component.filter_value = query

    result = (
        component.perform_operation() if component_type is DataFrameOperationsComponent else component.as_dataframe()
    )

    assert result["id"].tolist() == expected_ids
