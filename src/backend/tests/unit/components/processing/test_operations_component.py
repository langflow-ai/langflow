"""Tests for the unified Operations component.

The Operations component merges the legacy JSON Operations, Table Operations,
and Text Operations components into a single component with a flat operation
picker. These tests cover one representative operation from each data type,
the dynamic input/output routing, and the removal of the legacy "Filter
Values" operation.
"""

import pandas as pd
import pytest
from lfx.components.processing.operations import (
    JSON_OPERATIONS,
    OPERATIONS_BY_TYPE,
    TABLE_OPERATIONS,
    TEXT_OPERATIONS,
    OperationsComponent,
)
from lfx.schema import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestOperationsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return OperationsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "text_input": "Hello world",
            "operation": [{"name": "Word Count"}],
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []


class TestOperationCatalog:
    """The unified picker exposes every operation across all three data types.

    The Operation picker is filtered by the Input Type selector, so the picker's
    ``options`` only ever hold one type's operations at a time. These tests
    assert against the full catalog (``OPERATIONS_BY_TYPE``) plus the Text-typed
    default the picker ships with.
    """

    @staticmethod
    def _all_operations():
        """Every operation across all input types (the full catalog)."""
        return [opt for options in OPERATIONS_BY_TYPE.values() for opt in options]

    def test_picker_lists_all_operations(self):
        names = {opt["name"] for opt in self._all_operations()}
        assert names == JSON_OPERATIONS | TABLE_OPERATIONS | TEXT_OPERATIONS

    def test_default_picker_shows_text_operations(self):
        """A freshly dropped component defaults to "Text", so the picker is pre-filtered to Text ops."""
        component = OperationsComponent()
        operation_input = next(i for i in component.inputs if i.name == "operation")
        names = {opt["name"] for opt in operation_input.options}
        assert names == TEXT_OPERATIONS

    def test_filter_values_operation_is_removed(self):
        """The legacy Data-List "Filter Values" remnant must not be carried forward."""
        names = {opt["name"] for opt in self._all_operations()}
        assert "Filter Values" not in names

    def test_every_operation_has_field_mapping(self):
        component = OperationsComponent()
        for opt in self._all_operations():
            assert opt["name"] in component.OPERATION_FIELDS


class TestJsonOperations:
    def test_select_keys(self):
        component = OperationsComponent(
            data=Data(data={"key1": "value1", "key2": "value2", "key3": "value3"}),
            operation=[{"name": "Select Keys"}],
            select_keys_input=["key1", "key2"],
        )
        result = component.as_data()
        assert isinstance(result, Data)
        assert "key1" in result.data
        assert "key3" not in result.data

    def test_remove_keys(self):
        component = OperationsComponent(
            data=Data(data={"key1": "value1", "key2": "value2"}),
            operation=[{"name": "Remove Keys"}],
            remove_keys_input=["key2"],
        )
        result = component.as_data()
        assert "key1" in result.data
        assert "key2" not in result.data

    def test_rename_keys(self):
        component = OperationsComponent(
            data=Data(data={"key1": "value1"}),
            operation=[{"name": "Rename Keys"}],
            rename_keys_input={"key1": "new_key1"},
        )
        result = component.as_data()
        assert "new_key1" in result.data
        assert "key1" not in result.data

    def test_literal_eval(self):
        component = OperationsComponent(
            data=Data(data={"list_as_string": "[1, 2, 3]"}),
            operation=[{"name": "Literal Eval"}],
        )
        result = component.as_data()
        assert result.data["list_as_string"] == [1, 2, 3]

    def test_combine(self):
        component = OperationsComponent(
            data=[Data(data={"key1": "value1"}), Data(data={"key2": "value2"})],
            operation=[{"name": "Combine"}],
        )
        result = component.as_data()
        assert result.data["key1"] == "value1"
        assert result.data["key2"] == "value2"

    def test_append_update(self):
        component = OperationsComponent(
            data=Data(data={"existing_key": "existing_value"}),
            operation=[{"name": "Append or Update"}],
            append_update_data={"new_key": "new_value", "existing_key": "updated_value"},
        )
        result = component.as_data()
        assert result.data["existing_key"] == "updated_value"
        assert result.data["new_key"] == "new_value"

    def test_select_keys_rejects_multiple_data(self):
        component = OperationsComponent(
            data=[Data(data={"key1": "value1"}), Data(data={"key2": "value2"})],
            operation=[{"name": "Select Keys"}],
            select_keys_input=["key1"],
        )
        with pytest.raises(ValueError, match="not supported for multiple data objects"):
            component.as_data()


class TestTableOperations:
    @pytest.fixture
    def sample_dataframe(self):
        data = {
            "name": ["John", "Jane", "Bob", "Alice"],
            "email": ["john@gmail.com", "jane@yahoo.com", "bob@gmail.com", "alice@test.org"],
            "department": ["IT", "HR", "Finance", "IT"],
        }
        return DataFrame(pd.DataFrame(data))

    def test_filter_equals(self, sample_dataframe):
        component = OperationsComponent(
            df=sample_dataframe,
            operation=[{"name": "Filter"}],
            column_name="department",
            filter_operator="equals",
            filter_value="IT",
        )
        result = component.as_dataframe()
        assert len(result) == 2
        assert all(result["department"] == "IT")

    def test_filter_contains(self, sample_dataframe):
        component = OperationsComponent(
            df=sample_dataframe,
            operation=[{"name": "Filter"}],
            column_name="email",
            filter_operator="contains",
            filter_value="gmail",
        )
        result = component.as_dataframe()
        assert len(result) == 2

    def test_drop_column(self, sample_dataframe):
        component = OperationsComponent(
            df=sample_dataframe,
            operation=[{"name": "Drop Column"}],
            column_name="email",
        )
        result = component.as_dataframe()
        assert "email" not in result.columns

    def test_add_column(self, sample_dataframe):
        component = OperationsComponent(
            df=sample_dataframe,
            operation=[{"name": "Add Column"}],
            new_column_name="active",
            new_column_value=True,
        )
        result = component.as_dataframe()
        assert "active" in result.columns
        assert all(result["active"])

    def test_head(self, sample_dataframe):
        component = OperationsComponent(
            df=sample_dataframe,
            operation=[{"name": "Head"}],
            num_rows=2,
        )
        assert len(component.as_dataframe()) == 2

    def test_concatenate(self):
        df1 = DataFrame(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))
        df2 = DataFrame(pd.DataFrame({"id": [3, 4], "name": ["Charlie", "Diana"]}))
        component = OperationsComponent(df=[df1, df2], operation=[{"name": "Concatenate"}])
        result = component.as_dataframe()
        assert len(result) == 4

    def test_merge_inner_join(self):
        df1 = DataFrame(pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]}))
        df2 = DataFrame(pd.DataFrame({"id": [2, 3, 4], "city": ["NYC", "LA", "Chicago"]}))
        component = OperationsComponent(
            operation=[{"name": "Merge"}],
            left_dataframe=df1,
            right_dataframe=df2,
            merge_on_column="id",
            merge_how="inner",
        )
        result = component.as_dataframe()
        assert len(result) == 2
        assert "name" in result.columns
        assert "city" in result.columns


class TestTextOperations:
    def test_word_count_returns_data(self):
        component = OperationsComponent(
            text_input="Hello world this is a test",
            operation=[{"name": "Word Count"}],
            count_words=True,
            count_characters=False,
            count_lines=False,
        )
        result = component.as_data()
        assert isinstance(result, Data)
        assert result.data["word_count"] == 6

    def test_case_conversion_returns_message(self):
        component = OperationsComponent(
            text_input="hello",
            operation=[{"name": "Case Conversion"}],
            case_type="uppercase",
        )
        result = component.as_message()
        assert isinstance(result, Message)
        assert result.text == "HELLO"

    def test_text_replace(self):
        component = OperationsComponent(
            text_input="hello world",
            operation=[{"name": "Text Replace"}],
            search_pattern="world",
            replacement_text="there",
            use_regex=False,
        )
        assert component.as_message().text == "hello there"

    def test_text_join(self):
        component = OperationsComponent(
            text_input="first",
            operation=[{"name": "Text Join"}],
            text_input_2="second",
        )
        assert component.as_message().text == "first\nsecond"
        assert component.as_text().text == "first\nsecond"

    def test_text_to_dataframe(self):
        component = OperationsComponent(
            text_input="name|age\nAlice|30\nBob|25",
            operation=[{"name": "Text to DataFrame"}],
            table_separator="|",
            has_header=True,
        )
        result = component.as_dataframe()
        assert isinstance(result, DataFrame)
        assert list(result.columns) == ["name", "age"]
        assert len(result) == 2

    def test_text_clean(self):
        component = OperationsComponent(
            text_input="hello    world",
            operation=[{"name": "Text Clean"}],
            remove_extra_spaces=True,
        )
        assert component.as_message().text == "hello world"

    def test_text_clean_spaces_and_empty_lines_together(self):
        """remove_extra_spaces must preserve newlines so remove_empty_lines stays effective."""
        component = OperationsComponent(
            text_input="line1  with   spaces\n\n\nline2",
            operation=[{"name": "Text Clean"}],
            remove_extra_spaces=True,
            remove_empty_lines=True,
        )
        assert component.as_message().text == "line1 with spaces\nline2"


class TestDynamicInputs:
    """update_build_config surfaces the input matching the selected Input Type.

    The Input Type selector drives which main input is shown; picking an
    operation then reveals that operation's fields. The build_config is seeded
    like the frontend: an ``input_type`` selector and an ``operation`` picker
    alongside every main and operation-specific field.
    """

    def _build_config(self, input_type="Text"):
        fields = [*OperationsComponent.MAIN_INPUTS, *OperationsComponent.ALL_OPERATION_FIELDS]
        config = dotdict({f: {"show": True, "required": False, "value": None} for f in fields})
        config["input_type"] = {"show": True, "required": False, "value": input_type}
        config["operation"] = {"show": True, "options": OPERATIONS_BY_TYPE.get(input_type, []), "value": []}
        return config

    def test_json_operation_shows_data_input(self):
        component = OperationsComponent()
        result = component.update_build_config(self._build_config("JSON"), [{"name": "Select Keys"}], "operation")
        assert result["data"]["show"] is True
        assert result["data"]["required"] is True
        assert result["df"]["show"] is False
        assert result["text_input"]["show"] is False
        assert result["select_keys_input"]["show"] is True

    def test_table_operation_shows_df_input(self):
        component = OperationsComponent()
        result = component.update_build_config(self._build_config("Table"), [{"name": "Filter"}], "operation")
        assert result["df"]["show"] is True
        assert result["data"]["show"] is False
        assert result["text_input"]["show"] is False
        assert result["column_name"]["show"] is True
        assert result["filter_value"]["show"] is True

    def test_text_operation_shows_text_input(self):
        component = OperationsComponent()
        result = component.update_build_config(self._build_config("Text"), [{"name": "Word Count"}], "operation")
        assert result["text_input"]["show"] is True
        assert result["data"]["show"] is False
        assert result["df"]["show"] is False
        assert result["count_words"]["show"] is True

    def test_combine_sets_data_is_list(self):
        component = OperationsComponent()
        config = self._build_config("JSON")
        config["data"]["is_list"] = False
        result = component.update_build_config(config, [{"name": "Combine"}], "operation")
        assert result["data"]["is_list"] is True

    def test_non_combine_json_op_unsets_data_is_list(self):
        component = OperationsComponent()
        config = self._build_config("JSON")
        config["data"]["is_list"] = True
        result = component.update_build_config(config, [{"name": "Select Keys"}], "operation")
        assert result["data"]["is_list"] is False

    def test_no_operation_shows_only_type_input(self):
        """Clearing the operation leaves just the current input type's main input."""
        component = OperationsComponent()
        result = component.update_build_config(self._build_config("Table"), [], "operation")
        assert result["df"]["show"] is True
        assert result["data"]["show"] is False
        assert result["text_input"]["show"] is False
        # All operation-specific fields hidden.
        assert result["select_keys_input"]["show"] is False
        assert result["column_name"]["show"] is False

    def test_input_type_change_swaps_input_and_picker(self):
        """Switching Input Type reveals its input, clears the operation, refilters the picker, drops stale fields."""
        component = OperationsComponent()
        config = self._build_config("Text")
        # A stale table field is visible before the switch.
        config["column_name"]["show"] = True
        result = component.update_build_config(config, "JSON", "input_type")
        assert result["data"]["show"] is True
        assert result["df"]["show"] is False
        assert result["text_input"]["show"] is False
        assert result["operation"]["value"] == []
        assert {opt["name"] for opt in result["operation"]["options"]} == JSON_OPERATIONS
        assert result["column_name"]["show"] is False

    def test_switching_operation_hides_previous_fields(self):
        component = OperationsComponent()
        config = self._build_config("Table")
        # Select a table op first.
        config = component.update_build_config(config, [{"name": "Filter"}], "operation")
        assert config["column_name"]["show"] is True
        # Switch input type to Text and pick a text op: table fields must hide.
        config["input_type"]["value"] = "Text"
        config = component.update_build_config(config, [{"name": "Word Count"}], "operation")
        assert config["column_name"]["show"] is False
        assert config["filter_value"]["show"] is False
        assert config["count_words"]["show"] is True
        assert config["text_input"]["show"] is True


class TestDynamicOutputs:
    """update_outputs picks the output type appropriate to the operation."""

    def _outputs_for(self, operation_name):
        component = OperationsComponent()
        frontend_node = {"outputs": []}
        result = component.update_outputs(frontend_node, "operation", [{"name": operation_name}])
        return result["outputs"]

    def test_json_operation_emits_data_output(self):
        outputs = self._outputs_for("Select Keys")
        assert [o.name for o in outputs] == ["data_output"]
        assert outputs[0].method == "as_data"

    def test_word_count_emits_data_output(self):
        outputs = self._outputs_for("Word Count")
        assert [o.name for o in outputs] == ["data_output"]

    def test_table_operation_emits_dataframe_output(self):
        outputs = self._outputs_for("Filter")
        assert [o.name for o in outputs] == ["dataframe_output"]
        assert outputs[0].method == "as_dataframe"

    def test_text_to_dataframe_emits_dataframe_output(self):
        outputs = self._outputs_for("Text to DataFrame")
        assert [o.name for o in outputs] == ["dataframe_output"]

    def test_generic_text_operation_emits_message_output(self):
        outputs = self._outputs_for("Case Conversion")
        assert [o.name for o in outputs] == ["message_output"]

    def test_text_join_emits_text_and_message_outputs(self):
        outputs = self._outputs_for("Text Join")
        assert [o.name for o in outputs] == ["text_output", "message_output"]

    def test_no_operation_emits_type_default_output(self):
        """With no operation selected, the component advertises the input type's single default output."""
        component = OperationsComponent()
        cases = {"Text": "message_output", "JSON": "data_output", "Table": "dataframe_output"}
        for input_type, expected in cases.items():
            frontend_node = {"outputs": [], "template": {"input_type": {"value": input_type}}}
            result = component.update_outputs(frontend_node, "operation", [])
            assert [o.name for o in result["outputs"]] == [expected]

    def test_input_type_change_emits_type_default_output(self):
        """Switching the Input Type advertises that type's single default output."""
        component = OperationsComponent()
        cases = {"Text": "message_output", "JSON": "data_output", "Table": "dataframe_output"}
        for input_type, expected in cases.items():
            result = component.update_outputs({"outputs": []}, "input_type", input_type)
            assert [o.name for o in result["outputs"]] == [expected]

    def test_default_outputs_match_default_type(self):
        """The class default output matches the default "Text" type so a fresh component is connectable."""
        names = [o.name for o in OperationsComponent.outputs]
        assert names == ["message_output"]

    def test_mapped_json_refresh_keeps_json_output(self):
        """Refreshing Path Selection's "JSON to Map" field must not swap the JSON output for Message.

        Real-time refreshes rebuild the frontend node with the class default
        (Message) output, so update_outputs has to re-derive the output from
        the saved operation for fields other than input_type/operation.
        """
        component = OperationsComponent()
        frontend_node = {
            "outputs": [],
            "template": {
                "input_type": {"value": "JSON"},
                "operation": {"value": [{"name": "Path Selection"}]},
            },
        }
        result = component.update_outputs(frontend_node, "mapped_json_display", '{"a": {"b": 1}}')
        assert [o.name for o in result["outputs"]] == ["data_output"]
        assert result["outputs"][0].method == "as_data"

    def test_unrelated_field_refresh_without_operation_keeps_type_default(self):
        """A non-operation refresh with no operation selected falls back to the input type's default output."""
        component = OperationsComponent()
        frontend_node = {
            "outputs": [],
            "template": {"input_type": {"value": "JSON"}, "operation": {"value": []}},
        }
        result = component.update_outputs(frontend_node, "mapped_json_display", "{}")
        assert [o.name for o in result["outputs"]] == ["data_output"]


if __name__ == "__main__":
    pytest.main([__file__])
