"""Boolean values entered as text must work with boolean Table columns."""

import pandas as pd
import pytest
from lfx.components.processing.converter import TypeConverterComponent
from lfx.components.processing.dataframe_operations import DataFrameOperationsComponent
from lfx.components.processing.operations import OperationsComponent
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


@pytest.fixture(params=[OperationsComponent, DataFrameOperationsComponent])
def component(request):
    return request.param()


def _run_operation(component):
    if isinstance(component, OperationsComponent):
        return component.as_dataframe()
    return component.perform_operation()


@pytest.mark.parametrize(
    ("operator", "filter_value", "expected_names"),
    [
        ("equals", "True", ["Alice"]),
        ("equals", "False", ["Bob"]),
        ("not equals", "True", ["Bob"]),
        ("not equals", "False", ["Alice"]),
        ("equals", " true ", ["Alice"]),
        ("equals", "FALSE", ["Bob"]),
    ],
)
def test_filter_boolean_column_from_auto_parsed_csv(component, operator, filter_value, expected_names):
    converter = TypeConverterComponent(
        input_data=Message(text="name,active\nAlice,True\nBob,False\n"),
        auto_parse=True,
    )
    table = converter.convert_to_dataframe()
    component.set(
        df=table,
        operation=[{"name": "Filter"}],
        column_name="active",
        filter_operator=operator,
        filter_value=filter_value,
    )

    result = _run_operation(component)

    assert result["name"].tolist() == expected_names
    assert table["active"].tolist() == [True, False]


@pytest.mark.parametrize(
    ("operator", "filter_value", "expected_names"),
    [
        ("equals", "True", ["Alice"]),
        ("equals", "False", ["Bob"]),
        ("not equals", "True", ["Bob"]),
        ("not equals", "False", ["Alice"]),
    ],
)
def test_filter_nullable_boolean_column(component, operator, filter_value, expected_names):
    table = DataFrame({"name": ["Alice", "Bob", "Unknown"], "active": pd.array([True, False, None], dtype="boolean")})
    component.set(
        df=table,
        operation=[{"name": "Filter"}],
        column_name="active",
        filter_operator=operator,
        filter_value=filter_value,
    )

    assert _run_operation(component)["name"].tolist() == expected_names


@pytest.mark.parametrize(
    ("operator", "filter_value", "expected_names"),
    [
        ("equals", "True", ["Alice"]),
        ("not equals", "True", ["Bob"]),
        ("equals", "true", []),
        ("not equals", "true", ["Alice", "Bob"]),
    ],
)
def test_boolean_looking_text_column_keeps_exact_comparison(component, operator, filter_value, expected_names):
    component.set(
        df=DataFrame({"name": ["Alice", "Bob"], "active": ["True", "False"]}),
        operation=[{"name": "Filter"}],
        column_name="active",
        filter_operator=operator,
        filter_value=filter_value,
    )

    assert _run_operation(component)["name"].tolist() == expected_names


@pytest.mark.parametrize("filter_value", ["1", "yes"])
def test_unrecognized_boolean_filter_is_not_coerced(component, filter_value):
    component.set(
        df=DataFrame({"name": ["Alice", "Bob"], "active": [True, False]}),
        operation=[{"name": "Filter"}],
        column_name="active",
        filter_operator="equals",
        filter_value=filter_value,
    )

    assert _run_operation(component).empty


@pytest.mark.parametrize(
    ("old", "new", "expected"), [("True", "False", [False, False]), ("False", "True", [True, True])]
)
def test_replace_boolean_value_keeps_boolean_column(component, old, new, expected):
    component.set(
        df=DataFrame({"active": [True, False]}),
        operation=[{"name": "Replace Value"}],
        column_name="active",
        replace_value=old,
        replacement_value=new,
    )

    result = _run_operation(component)

    assert result["active"].tolist() == expected
    assert pd.api.types.is_bool_dtype(result["active"])
