"""Tests for the unified Operations component.

The Operations component merges the legacy JSON Operations, Table Operations,
and Text Operations components into a single component with a flat operation
picker. These tests cover one representative operation from each data type,
the dynamic input/output routing, and the removal of the legacy "Filter
Values" operation.
"""

import copy

import pandas as pd
import pytest
from lfx.components.processing.data_operations import DataOperationsComponent
from lfx.components.processing.dataframe_operations import DataFrameOperationsComponent
from lfx.components.processing.operations import (
    JSON_OPERATIONS,
    OPERATIONS_BY_TYPE,
    TABLE_OPERATIONS,
    TEXT_OPERATIONS,
    OperationsComponent,
)
from lfx.components.processing.parse_json_data import ParseJSONDataComponent
from lfx.components.processing.text_operations import TextOperations
from lfx.custom.utils import build_custom_component_template
from lfx.exceptions.component import ComponentBuildError
from lfx.graph import Graph
from lfx.inputs.inputs import instantiate_input
from lfx.io import Output
from lfx.schema import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.utils.jq_security import validate_jq_program

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


@pytest.mark.parametrize(
    "legacy_component",
    [DataOperationsComponent, DataFrameOperationsComponent, TextOperations],
)
def test_legacy_operations_components_point_to_unified_replacement(legacy_component):
    assert legacy_component.replacement == ["processing.Operations"]


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

    @pytest.mark.parametrize("component_class", [OperationsComponent, DataOperationsComponent])
    @pytest.mark.parametrize(
        "payload",
        [
            {"data": {"id": 1}},
            {"data": 42},
            {"text_key": "body", "default_value": "fallback", "body": "content"},
            {"text_key": ["literal"], "default_value": {"missing": True}},
        ],
    )
    def test_combine_preserves_payload_keys(self, component_class, payload):
        """Business keys must not be interpreted as Data constructor fields."""
        original = Data(data=payload)
        operation_field = "operation" if component_class is OperationsComponent else "operations"
        component = component_class(
            data=[original, Data(data={"source": "memo"})],
            **{operation_field: [{"name": "Combine"}]},
        )
        result = component.as_data()
        assert result.data == {**payload, "source": "memo"}
        assert result.text_key == "text"
        assert result.default_value == ""
        assert original.data == payload

    def test_append_update(self):
        component = OperationsComponent(
            data=Data(data={"existing_key": "existing_value"}),
            operation=[{"name": "Append or Update"}],
            append_update_data={"new_key": "new_value", "existing_key": "updated_value"},
        )
        result = component.as_data()
        assert result.data["existing_key"] == "updated_value"
        assert result.data["new_key"] == "new_value"

    @pytest.mark.parametrize("component_class", [OperationsComponent, DataOperationsComponent])
    @pytest.mark.parametrize("value", ["hello", [1, 2], 3, 0.5, True, False, None])
    def test_select_data_key_preserves_non_dict_value(self, component_class, value):
        operation_field = "operation" if component_class is OperationsComponent else "operations"
        component = component_class(
            data=Data(data={"data": value, "other": "dropped"}),
            select_keys_input=["data"],
            **{operation_field: [{"name": "Select Keys"}]},
        )

        result = component.as_data()

        assert result.data == {"data": value}

    @pytest.mark.parametrize("component_class", [OperationsComponent, DataOperationsComponent])
    @pytest.mark.parametrize("value", [{"inner": 1}, {}])
    def test_select_data_key_unwraps_dict_value(self, component_class, value):
        operation_field = "operation" if component_class is OperationsComponent else "operations"
        component = component_class(
            data=Data(data={"data": value}),
            select_keys_input=["data"],
            **{operation_field: [{"name": "Select Keys"}]},
        )

        result = component.as_data()

        assert result.data == value

    @pytest.mark.parametrize("component_class", [OperationsComponent, DataOperationsComponent])
    def test_select_data_key_missing_raises_value_error(self, component_class):
        operation_field = "operation" if component_class is OperationsComponent else "operations"
        component = component_class(
            data=Data(data={"other": 1}),
            select_keys_input=["data"],
            **{operation_field: [{"name": "Select Keys"}]},
        )

        with pytest.raises(ValueError, match="Select key not found in data"):
            component.as_data()

    def test_select_keys_rejects_multiple_data(self):
        component = OperationsComponent(
            data=[Data(data={"key1": "value1"}), Data(data={"key2": "value2"})],
            operation=[{"name": "Select Keys"}],
            select_keys_input=["key1"],
        )
        with pytest.raises(ValueError, match="not supported for multiple data objects"):
            component.as_data()


class TestJqProgramSecurity:
    """jq programs must never reach the server environment (H1-3977755 / LE-2550).

    The JQ Expression / Path Selection operations and the legacy Parse JSON /
    JSON Operations components evaluate a user-supplied jq program with the
    in-process libjq binding, where ``$ENV`` / ``env`` expose the whole server
    process environment (LANGFLOW_SECRET_KEY, database URL, provider API keys).
    """

    CANARY = "le-2550-canary-secret"

    @pytest.fixture(autouse=True)
    def _canary_env(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SECRET_KEY", self.CANARY)

    @pytest.mark.parametrize(
        "payload", ["$ENV", "env", "env.LANGFLOW_SECRET_KEY", '"\\(env)"', "{a: if true then 1, env else 2 end}"]
    )
    def test_operations_json_query_rejects_env_access(self, payload):
        component = OperationsComponent(
            data=Data(data={"key1": "value1"}),
            operation=[{"name": "JQ Expression"}],
            query=payload,
        )
        with pytest.raises(ValueError, match="not allowed"):
            component.json_query()

    @pytest.mark.parametrize("payload", ["$ENV", "env.LANGFLOW_SECRET_KEY", "{a: if true then 1, env else 2 end}"])
    def test_operations_json_path_rejects_env_access(self, payload):
        component = OperationsComponent(
            data=Data(data={"key1": "value1"}),
            operation=[{"name": "Path Selection"}],
            selected_key=payload,
        )
        result = component.json_path()
        assert "error" in result.data
        assert "not allowed" in result.data["error"]
        assert self.CANARY not in str(result.data)

    def test_operations_json_query_still_allows_normal_queries(self):
        component = OperationsComponent(
            data=Data(data={"key1": "value1"}),
            operation=[{"name": "JQ Expression"}],
            query=".key1",
        )
        result = component.json_query()
        assert result.data == {"result": "value1"}

    @pytest.mark.parametrize("payload", ["$ENV", "env", "{a: if true then 1, env else 2 end}"])
    def test_legacy_data_operations_json_query_rejects_env_access(self, payload):
        component = DataOperationsComponent(
            data=Data(data={"key1": "value1"}),
            operations=[{"name": "JQ Expression"}],
            query=payload,
        )
        with pytest.raises(ValueError, match="not allowed"):
            component.json_query()

    @pytest.mark.parametrize("payload", ["$ENV", "env.LANGFLOW_SECRET_KEY", "{a: if true then 1, env else 2 end}"])
    def test_legacy_parse_json_data_rejects_env_access(self, payload):
        component = ParseJSONDataComponent(
            input_value=Data(data={"key1": "value1"}),
            query=payload,
        )
        with pytest.raises(ValueError, match="not allowed"):
            component.filter_data()


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

    @pytest.mark.parametrize(
        ("operator", "expected_names"),
        [("equals", ["Bob", "Carol"]), ("not equals", ["Ann"])],
    )
    def test_filter_numeric_column_by_text_value(self, operator, expected_names):
        component = OperationsComponent(
            df=DataFrame(pd.DataFrame({"name": ["Ann", "Bob", "Carol"], "score": [2.5, 7.0, 7.0]})),
            operation=[{"name": "Filter"}],
            column_name="score",
            filter_operator=operator,
            filter_value="7",
        )
        result = component.as_dataframe()
        assert result["name"].tolist() == expected_names

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

    @pytest.mark.parametrize(
        ("component_class", "output_method"),
        [(OperationsComponent, "as_dataframe"), (DataFrameOperationsComponent, "perform_operation")],
    )
    @pytest.mark.parametrize("merge_on", ["id", ""])
    @pytest.mark.parametrize("overlapping_value", [False, True])
    def test_merge_preserves_original_suffix_columns(self, component_class, output_method, merge_on, overlapping_value):
        left = DataFrame({"id": [1, 2], "value": [None, "left"], "value_right": ["metadata", "keep"]})
        right = DataFrame({"id": [1, 2], "value_right_right": ["source", "keep too"]})
        if overlapping_value:
            right["value"] = ["right", "ignored"]
        left_before, right_before = left.copy(), right.copy()
        component = component_class(
            operation=[{"name": "Merge"}],
            left_dataframe=left,
            right_dataframe=right,
            merge_on_column=merge_on,
        )

        result = getattr(component, output_method)()

        assert result.to_dict(orient="list") == {
            "id": [1, 2],
            "value": ["right" if overlapping_value else None, "left"],
            "value_right": ["metadata", "keep"],
            "value_right_right": ["source", "keep too"],
        }
        pd.testing.assert_frame_equal(left, left_before)
        pd.testing.assert_frame_equal(right, right_before)

    @pytest.mark.parametrize("component_class", [OperationsComponent, DataFrameOperationsComponent])
    def test_merge_preserves_distinct_column_label_types(self, component_class):
        left = DataFrame({1: [None, "left number"], "1": ["left string", None]})
        right = DataFrame({1: ["right number", "ignored"], "1": ["ignored", "right string"]})
        component = component_class(left_dataframe=left, right_dataframe=right)

        result = component.merge_dataframes()

        assert result.to_dict(orient="list") == {
            1: ["right number", "left number"],
            "1": ["left string", "right string"],
        }


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

    def test_text_to_dataframe_skips_markdown_delimiter_row(self):
        component = OperationsComponent(
            text_input="| name | age |\n|:-----|----:|\n| Alice | 30 |\n| Bob | 25 |",
            operation=[{"name": "Text to DataFrame"}],
            table_separator="|",
            has_header=True,
        )
        result = component.as_dataframe()
        assert list(result.columns) == ["name", "age"]
        assert result["name"].tolist() == ["Alice", "Bob"]
        assert result["age"].tolist() == [30, 25]

    def test_text_to_dataframe_preserves_headerless_delimiter_like_rows(self):
        component = OperationsComponent(
            text_input="Alice|30\n---|:--\nBob|25",
            operation=[{"name": "Text to DataFrame"}],
            table_separator="|",
            has_header=False,
        )

        result = component.as_dataframe()

        assert result.to_numpy().tolist() == [["Alice", "30"], ["---", ":--"], ["Bob", "25"]]

    def test_text_to_dataframe_handles_empty_markdown_table(self):
        component = OperationsComponent(
            text_input="| name | age |\n|---|---|",
            operation=[{"name": "Text to DataFrame"}],
            table_separator="|",
            has_header=True,
        )

        result = component.as_dataframe()

        assert result.empty
        assert list(result.columns) == ["name", "age"]

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

    def test_combine_sets_data_list(self):
        component = OperationsComponent()
        config = self._build_config("JSON")
        config["data"]["list"] = False
        result = component.update_build_config(config, [{"name": "Combine"}], "operation")
        assert result["data"]["list"] is True
        assert "is_list" not in result["data"]

    def test_non_combine_json_op_unsets_data_list(self):
        component = OperationsComponent()
        config = self._build_config("JSON")
        config["data"]["list"] = True
        result = component.update_build_config(config, [{"name": "Select Keys"}], "operation")
        assert result["data"]["list"] is False
        assert "is_list" not in result["data"]

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


class TestReplaceValueTableOperation:
    """Test Replace Value table operation in unified OperationsComponent."""

    def test_replace_value_integer_column(self):
        """Test replacing integer values where input arrives as text strings."""
        df = DataFrame(pd.DataFrame({"id": [1, 2, 3], "score": [20, 50, 20]}))
        component = OperationsComponent(
            df=df,
            operation=[{"name": "Replace Value"}],
            column_name="score",
            replace_value="20",
            replacement_value="99",
        )
        result = component.as_dataframe()
        assert result["score"].tolist() == [99, 50, 99]
        assert pd.api.types.is_integer_dtype(result["score"])

    def test_replace_value_float_column(self):
        """Test replacing float values where input arrives as text strings."""
        df = DataFrame(pd.DataFrame({"ratio": [1.25, 2.5, 3.75]}))
        component = OperationsComponent(
            df=df,
            operation=[{"name": "Replace Value"}],
            column_name="ratio",
            replace_value="2.5",
            replacement_value="8.5",
        )
        result = component.as_dataframe()
        assert result["ratio"].tolist() == [1.25, 8.5, 3.75]
        assert pd.api.types.is_float_dtype(result["ratio"])

    def test_replace_value_string_column(self):
        """Test string/object column replacement remains unchanged."""
        df = DataFrame(pd.DataFrame({"city": ["Paris", "London", "Paris"]}))
        component = OperationsComponent(
            df=df,
            operation=[{"name": "Replace Value"}],
            column_name="city",
            replace_value="Paris",
            replacement_value="Tokyo",
        )
        result = component.as_dataframe()
        assert result["city"].tolist() == ["Tokyo", "London", "Tokyo"]
        assert pd.api.types.is_object_dtype(result["city"]) or pd.api.types.is_string_dtype(result["city"])

    def test_replace_value_non_numeric_fallback(self):
        """Test replacing a number with a non-numeric string gracefully casts column."""
        df = DataFrame(pd.DataFrame({"score": [10, 20, 30]}))
        component = OperationsComponent(
            df=df,
            operation=[{"name": "Replace Value"}],
            column_name="score",
            replace_value="20",
            replacement_value="N/A",
        )
        result = component.as_dataframe()
        assert result["score"].tolist() == [10, "N/A", 30]
        assert result["score"].dtype == object

    def test_replace_value_blank_input_does_not_match_missing_cells(self):
        df = DataFrame(pd.DataFrame({"score": [10.0, None, 30.0]}))
        component = OperationsComponent(
            df=df,
            operation=[{"name": "Replace Value"}],
            column_name="score",
            replace_value="",
            replacement_value="0",
        )
        result = component.as_dataframe()
        assert result["score"].iloc[0] == 10.0
        assert pd.isna(result["score"].iloc[1])
        assert result["score"].iloc[2] == 30.0


@pytest.mark.parametrize(
    ("component_class", "output_method"),
    [
        (OperationsComponent, "as_dataframe"),
        (DataFrameOperationsComponent, "perform_operation"),
    ],
)
class TestNullableIntegerReplaceValue:
    @pytest.mark.parametrize(
        ("replacement", "expected_value", "expected_dtype"),
        [
            ("2.5", 2.5, "Float64"),
            ("-2.5", -2.5, "Float64"),
            ("99", 99, "Int64"),
            ("99.0", 99, "Int64"),
            ("N/A", "N/A", "object"),
            ("", "", "object"),
        ],
    )
    def test_replacement_preserves_missing_cells(
        self, component_class, output_method, replacement, expected_value, expected_dtype
    ):
        original = pd.Series([10, 20, pd.NA], dtype="Int64", name="score")
        df = DataFrame(pd.DataFrame({"score": original.copy()}))
        component = component_class(
            df=df,
            operation=[{"name": "Replace Value"}],
            column_name="score",
            replace_value="20",
            replacement_value=replacement,
        )

        result = getattr(component, output_method)()

        expected = pd.Series([10, expected_value, pd.NA], dtype=expected_dtype, name="score")
        pd.testing.assert_series_equal(result["score"], expected)
        pd.testing.assert_series_equal(df["score"], original)

    @pytest.mark.parametrize("large_value", [2**53 + 1, 2**63 - 1])
    def test_fractional_replacement_preserves_large_integers(self, component_class, output_method, large_value):
        original = pd.Series([large_value, 20, pd.NA], dtype="Int64", name="score")
        component = component_class(
            df=DataFrame(pd.DataFrame({"score": original})),
            operation=[{"name": "Replace Value"}],
            column_name="score",
            replace_value="20",
            replacement_value="2.5",
        )

        result = getattr(component, output_method)()

        expected = pd.Series([large_value, 2.5, pd.NA], dtype=object, name="score")
        pd.testing.assert_series_equal(result["score"], expected)

    @pytest.mark.parametrize("replacement", ["2.5", "N/A", ""])
    def test_no_match_preserves_dtype(self, component_class, output_method, replacement):
        original = pd.Series([10, 20, pd.NA], dtype="Int64", name="score")
        component = component_class(
            df=DataFrame(pd.DataFrame({"score": original.copy()})),
            operation=[{"name": "Replace Value"}],
            column_name="score",
            replace_value="99",
            replacement_value=replacement,
        )

        result = getattr(component, output_method)()

        pd.testing.assert_series_equal(result["score"], original)


if __name__ == "__main__":
    pytest.main([__file__])


class TestJqGuardLibjqConformance:
    """The guard's allow/deny sets are checked against the real libjq compiler.

    These live in the backend suite rather than beside ``jq_security`` because
    ``jq`` is a ``langflow-base`` dependency: the lfx-only test environment has
    no libjq, so a conformance test there would silently skip.
    """

    ALLOWED = [
        # Object keys that merely share a name with a builtin (LE-2550 follow-up).
        "{env: .a}",
        "{input: .a}",
        "{inputs: .a}",
        "{env : .a}",
        '{"env": .a}',
        "{env}",
        "{input}",
        "{a: .x, env: .y}",
        "{outer: {env: .a}}",
        ". as {env: $e} | $e",
        "{a: if true then 1, 2 else 3 end, env: .a}",
        "{a: if true then {env: .a} else {input: .b} end, inputs}",
        "{if: .a, end: .b, env}",
        "{a: .if, env: .end}",
        # getpath only indexes the value it is applied to.
        'getpath(["nested", "id"])',
        'getpath(["data", "id"])',
        # Ordinary selections.
        ".env",
        ".data",
    ]

    # Programs that demonstrably emit server environment data.
    REJECTED = [
        "env",
        "$ENV",
        "{a: env}",
        "{(env.LF_JQ_CANARY_2550): 1}",
        "{$ENV}",
        '{"\\(env)": 1}',
        "{a: if true then 1, env else 2 end}",
        "{a: if false then 1 else 2, env end}",
        "{a: if true then if false then 0 else 1, env end else 2 end}",
        "{a: if true then 1, {env: 2}, env else 3 end}",
    ]

    # Programs the guard must reject that libjq evaluates but cannot emit --
    # ``{(env): 1}`` resolves the builtin and then fails on "object as object
    # key", so it proves reachability of the call, not of the output.
    REJECTED_UNEMITTABLE = ["{(env): 1}", "{(env): .a}"]

    @pytest.mark.parametrize("program", ALLOWED)
    def test_allowed_programs_compile_and_read_only_their_input(self, program, monkeypatch):
        import jq

        validate_jq_program(program)
        monkeypatch.setenv("LF_JQ_CANARY_2550", "canary-value")
        document = {
            "a": 1,
            "x": 2,
            "y": 3,
            "env": "from-input",
            "input": "from-input",
            "data": {"id": 7},
            "nested": {"id": 9},
        }
        # Compiles under real libjq, and its output carries nothing from the
        # process environment.
        assert "canary-value" not in str(jq.compile(program).input(document).all())

    @pytest.mark.parametrize("program", REJECTED)
    def test_rejected_programs_really_reach_the_environment(self, program, monkeypatch):
        """Each negative case is rejected because it leaks, not by coincidence."""
        import jq

        monkeypatch.setenv("LF_JQ_CANARY_2550", "canary-value")
        assert "canary-value" in str(jq.compile(program).input({"a": 1}).all())
        with pytest.raises(ValueError, match="not allowed"):
            validate_jq_program(program)

    @pytest.mark.parametrize("program", REJECTED_UNEMITTABLE)
    def test_computed_key_builtin_calls_are_rejected(self, program):
        """A builtin inside a computed key ``{(expr): v}`` is a call, not a key name."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_jq_program(program)


class TestUpdateFrontendNodeRestoresVisibility:
    """A saved node must come back with the ``show``/``required`` flags of *its* input type and operation.

    ``update_frontend_node`` rebuilds the template from class defaults (Text input
    visible). Before the fix only options and outputs were re-synced, so a saved
    JSON node returned with ``data`` hidden and the canvas dropped its edge.
    """

    async def _updated_template(self, input_type: str, operation: str = "") -> dict:
        saved, _ = build_custom_component_template(OperationsComponent(), user_id="test-user")
        fresh = copy.deepcopy(saved)
        saved["template"]["input_type"]["value"] = input_type
        if operation:
            saved["template"]["operation"]["value"] = [{"name": operation}]
        updated = await OperationsComponent().update_frontend_node(fresh, saved)
        return updated["template"]

    async def test_json_combine_shows_list_data_input(self):
        template = await self._updated_template("JSON", "Combine")
        assert template["data"]["show"] is True
        assert template["data"]["required"] is True
        assert template["data"]["list"] is True
        assert "is_list" not in template["data"]
        assert template["text_input"]["show"] is False
        assert template["df"]["show"] is False
        assert template["input_type"]["value"] == "JSON"
        assert template["operation"]["value"] == [{"name": "Combine"}]

    async def test_json_select_keys_shows_operation_fields_only(self):
        template = await self._updated_template("JSON", "Select Keys")
        assert template["data"]["show"] is True
        assert template["data"]["list"] is False
        assert "is_list" not in template["data"]
        for field in OperationsComponent.ALL_OPERATION_FIELDS:
            if field in template:
                expected = field in OperationsComponent.OPERATION_FIELDS["Select Keys"]
                assert template[field]["show"] is expected, field

    async def test_saved_operation_field_values_survive(self):
        saved, _ = build_custom_component_template(OperationsComponent(), user_id="test-user")
        fresh = copy.deepcopy(saved)
        saved["template"]["input_type"]["value"] = "JSON"
        saved["template"]["operation"]["value"] = [{"name": "Select Keys"}]
        saved["template"]["select_keys_input"]["value"] = ["a", "b"]
        updated = await OperationsComponent().update_frontend_node(fresh, saved)
        assert updated["template"]["select_keys_input"]["value"] == ["a", "b"]

    async def test_table_operation_shows_df_input(self):
        template = await self._updated_template("Table", OPERATIONS_BY_TYPE["Table"][0]["name"])
        assert template["df"]["show"] is True
        assert template["df"]["required"] is True
        assert template["text_input"]["show"] is False
        assert template["data"]["show"] is False

    async def test_text_without_operation_shows_required_text_input(self):
        template = await self._updated_template("Text")
        assert template["text_input"]["show"] is True
        assert template["text_input"]["required"] is True
        assert template["data"]["show"] is False
        assert template["df"]["show"] is False
        for field in OperationsComponent.ALL_OPERATION_FIELDS:
            if field in template:
                assert template[field]["show"] is False, field

    async def test_removed_operation_name_hides_all_operation_fields(self):
        template = await self._updated_template("JSON", "Filter Values")
        assert template["data"]["show"] is True
        for field in OperationsComponent.ALL_OPERATION_FIELDS:
            if field in template:
                assert template[field]["show"] is False, field

    async def test_table_merge_shows_both_dataframe_inputs(self):
        template = await self._updated_template("Table", "Merge")
        assert template["left_dataframe"]["show"] is True
        assert template["right_dataframe"]["show"] is True

    async def test_path_selection_rebuilds_selected_key_options(self):
        saved, _ = build_custom_component_template(OperationsComponent(), user_id="test-user")
        fresh = copy.deepcopy(saved)
        saved["template"]["input_type"]["value"] = "JSON"
        saved["template"]["operation"]["value"] = [{"name": "Path Selection"}]
        saved["template"]["mapped_json_display"]["value"] = '{"a":{"b":1}}'
        saved["template"]["selected_key"]["value"] = ".a.b"
        template = (await OperationsComponent().update_frontend_node(fresh, saved))["template"]
        assert template["selected_key"]["show"] is True
        assert template["selected_key"]["value"] == ".a.b"
        assert ".a.b" in template["selected_key"]["options"]

    async def test_path_selection_with_invalid_saved_json_hides_selected_key(self):
        saved, _ = build_custom_component_template(OperationsComponent(), user_id="test-user")
        fresh = copy.deepcopy(saved)
        saved["template"]["input_type"]["value"] = "JSON"
        saved["template"]["operation"]["value"] = [{"name": "Path Selection"}]
        saved["template"]["mapped_json_display"]["value"] = "{not json"
        template = (await OperationsComponent().update_frontend_node(fresh, saved))["template"]
        assert template["selected_key"]["show"] is False


class TestDataListFlagOnSerializedTemplate:
    """Only Combine lets the JSON input take several edges, checked on the template the canvas reads.

    The serialized template stores ``Input.is_list`` under ``list``. The canvas
    (``isValidConnection``) and the graph (``ParameterHandler``) read that key to
    decide whether ``data`` accepts more than one edge. The component used to
    write ``is_list`` instead, so ``list`` kept its class default (``True``) for
    every operation and the stray key was saved into flows.
    """

    @staticmethod
    def _json_template() -> dotdict:
        node, _ = build_custom_component_template(OperationsComponent(), user_id="test-user")
        template = dotdict(node["template"])
        template["input_type"]["value"] = "JSON"
        return template

    def test_serialized_data_field_uses_list_key(self):
        data_field = self._json_template()["data"]
        assert data_field["list"] is True
        assert "is_list" not in data_field

    @pytest.mark.parametrize("operation", sorted(JSON_OPERATIONS))
    def test_only_combine_accepts_many_edges(self, operation):
        result = OperationsComponent().update_build_config(self._json_template(), [{"name": operation}], "operation")
        assert result["data"]["list"] is (operation == "Combine")
        assert "is_list" not in result["data"]

    def test_switching_input_type_to_json_starts_single(self):
        result = OperationsComponent().update_build_config(self._json_template(), "JSON", "input_type")
        assert result["data"]["list"] is False

    def test_stray_is_list_from_an_earlier_save_is_dropped(self):
        template = self._json_template()
        template["data"]["is_list"] = False
        result = OperationsComponent().update_build_config(template, [{"name": "Combine"}], "operation")
        assert result["data"]["list"] is True
        assert "is_list" not in result["data"]

    @pytest.mark.parametrize(("operation", "expected"), [("Combine", True), ("Select Keys", False)])
    def test_updated_data_field_rebuilds_as_input_with_matching_flag(self, operation, expected):
        """The flag reaches the input model, and no stray key breaks rebuilding the field."""
        template = self._json_template()
        template["data"]["is_list"] = not expected
        result = OperationsComponent().update_build_config(template, [{"name": operation}], "operation")
        field = copy.deepcopy(dict(result["data"]))
        rebuilt = instantiate_input(field.pop("_input_type"), {**field, "name": "data"})
        assert rebuilt.is_list is expected


class TestExtraDataEdgesFailLoudly:
    """A single-input JSON operation must refuse to run when several JSON edges feed the node.

    A node keeps its edges when its operation changes, and nothing prunes extra edges when ``data``
    stops being a list. With ``list`` false the graph passes only the last edge's data, so without
    this check the run would use partial input and report no error.
    """

    class _JsonOperations(OperationsComponent):
        # A saved JSON node advertises the JSON output; the class default is the Text one.
        outputs = [Output(display_name="JSON", name="data_output", method="as_data")]

    async def _run(self, operation: str, texts: list[str], *, list_flag: bool) -> dict:
        sources = []
        for index, text in enumerate(texts):
            source = self._JsonOperations(_id=f"source-{index}")
            source.set(input_type="Text", operation=[{"name": "Word Count"}], text_input=text)
            sources.append(source)
        target = self._JsonOperations(_id="target")
        target.set(
            input_type="JSON",
            operation=[{"name": operation}],
            select_keys_input=["word_count"],
            data=[source.as_data for source in sources],
        )
        graph = Graph(start=sources[0], end=target)
        # Mirror a saved node whose "list" flag follows its operation.
        graph.get_vertex("target").data["node"]["template"]["data"]["list"] = list_flag
        _ = [result async for result in graph.async_start()]
        return graph.get_vertex("target").results

    @pytest.mark.parametrize("list_flag", [False, True])
    async def test_single_input_operation_with_two_edges_fails(self, list_flag):
        with pytest.raises(ComponentBuildError, match="Select Keys operation is not supported for multiple data"):
            await self._run("Select Keys", ["one two", "three"], list_flag=list_flag)

    async def test_single_input_operation_with_one_edge_runs(self):
        results = await self._run("Select Keys", ["one two"], list_flag=False)
        assert results["data_output"].data == {"word_count": 2}

    async def test_combine_with_two_edges_runs(self):
        results = await self._run("Combine", ["one two", "three"], list_flag=True)
        assert sorted(results["data_output"].data["word_count"]) == [1, 2]
