"""Boolean values entered as text must work with boolean Table columns."""

import pandas as pd
import pytest
from lfx.components.processing.converter import TypeConverterComponent
from lfx.components.processing.dataframe_operations import DataFrameOperationsComponent
from lfx.components.processing.operations import OperationsComponent
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient

COMPONENT_CLASSES = [OperationsComponent, DataFrameOperationsComponent]


def _run_operation(component):
    if isinstance(component, OperationsComponent):
        return component.as_dataframe()
    return component.perform_operation()


class TestBooleanTableValues(ComponentTestBaseWithoutClient):
    """Text that looks boolean is compared against a boolean column exactly."""

    @pytest.fixture(params=COMPONENT_CLASSES)
    def component_class(self, request):
        """Return the component class to test."""
        return request.param

    @pytest.fixture
    def default_kwargs(self, component_class):
        """Return the default kwargs for the component."""
        if component_class is OperationsComponent:
            return {"text_input": "Hello world", "operation": [{"name": "Word Count"}]}
        return {
            "df": DataFrame({"name": ["Alice"], "active": [True]}),
            "operation": [{"name": "Filter"}],
            "column_name": "active",
            "filter_value": "True",
            "filter_operator": "equals",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    async def component(self, component_class, default_kwargs):
        """Return the component under test."""
        return await self.component_setup(component_class, default_kwargs)

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
    async def test_filter_boolean_column_from_auto_parsed_csv(self, component, operator, filter_value, expected_names):
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
            ("equals", "false", ["Bob"]),
            ("not equals", "True", ["Bob", "Carol"]),
            ("not equals", "False", ["Alice", "Carol"]),
        ],
    )
    async def test_filter_auto_parsed_csv_boolean_column_with_missing_cell(
        self, component, operator, filter_value, expected_names
    ):
        converter = TypeConverterComponent(
            input_data=Message(text="name,active\nAlice,True\nBob,False\nCarol,\n"),
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

        assert table["active"].dtype == object
        assert result["name"].tolist() == expected_names

    @pytest.mark.parametrize(
        ("operator", "filter_value", "expected_names"),
        [
            ("equals", "True", ["Alice"]),
            ("equals", "False", ["Bob"]),
            ("not equals", "True", ["Bob"]),
            ("not equals", "False", ["Alice"]),
        ],
    )
    async def test_filter_nullable_boolean_column(self, component, operator, filter_value, expected_names):
        table = DataFrame(
            {"name": ["Alice", "Bob", "Unknown"], "active": pd.array([True, False, None], dtype="boolean")},
        )
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
            ("equals", "False", ["Bob"]),
            ("not equals", "True", ["Bob"]),
            ("not equals", "False", ["Alice"]),
            ("equals", "true", []),
            ("not equals", "true", ["Alice", "Bob"]),
        ],
    )
    async def test_boolean_looking_text_column_keeps_exact_comparison(
        self, component, operator, filter_value, expected_names
    ):
        component.set(
            df=DataFrame({"name": ["Alice", "Bob"], "active": ["True", "False"]}),
            operation=[{"name": "Filter"}],
            column_name="active",
            filter_operator=operator,
            filter_value=filter_value,
        )

        assert _run_operation(component)["name"].tolist() == expected_names

    @pytest.mark.parametrize("filter_value", ["1", "yes"])
    async def test_unrecognized_boolean_filter_is_not_coerced(self, component, filter_value):
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
    async def test_replace_boolean_value_keeps_boolean_column(self, component, old, new, expected):
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
