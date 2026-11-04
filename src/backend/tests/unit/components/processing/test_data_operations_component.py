import copy
import importlib
import sys

import pytest
from lfx.components.processing.data_operations import ACTION_CONFIG, DataOperationsComponent
from lfx.components.processing.operations import OperationsComponent
from lfx.custom.utils import build_custom_component_template
from lfx.exceptions.component import ComponentBuildError
from lfx.graph.graph.base import Graph
from lfx.inputs.inputs import instantiate_input
from lfx.io import Output
from lfx.schema import Data
from lfx.schema.dotdict import dotdict

from tests.base import ComponentTestBaseWithoutClient


def test_should_import_module_when_jq_not_installed(monkeypatch):
    """Module must be importable even when jq is not installed (e.g. on Windows).

    The jq library is a C extension not available on Windows. The module-level
    import was removed so that update_build_config and non-jq operations work
    on all platforms. jq is only imported lazily inside json_query/json_path.
    """
    # Remove jq from sys.modules and block re-import
    monkeypatch.delitem(sys.modules, "jq", raising=False)
    real_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == "jq":
            msg = "No module named 'jq'"
            raise ModuleNotFoundError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", mock_import)

    # Force reimport of the module
    monkeypatch.delitem(sys.modules, "lfx.components.processing.data_operations", raising=False)

    # This must NOT raise ModuleNotFoundError
    mod = importlib.import_module("lfx.components.processing.data_operations")
    component_cls = mod.DataOperationsComponent

    # Non-jq operations must work
    component = component_cls(
        data=Data(data={"key1": "value1", "key2": "value2"}),
        operations=[{"name": "Select Keys"}],
        select_keys_input=["key1"],
    )
    result = component.as_data()
    assert "key1" in result.data


class TestDataOperationsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return DataOperationsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "data": Data(data={"key1": "value1", "key2": "value2", "key3": "value3"}),
            "actions": [{"name": "Select Keys"}],
            "select_keys_input": ["key1", "key2"],
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def test_select_keys(self):
        """Test the Select Keys operation."""
        component = DataOperationsComponent(
            data=Data(data={"key1": "value1", "key2": "value2", "key3": "value3"}),
            operations=[{"name": "Select Keys"}],
            select_keys_input=["key1", "key2"],
        )

        result = component.as_data()
        assert isinstance(result, Data)
        assert "key1" in result.data
        assert "key2" in result.data
        assert "key3" not in result.data
        assert result.data["key1"] == "value1"
        assert result.data["key2"] == "value2"

    def test_remove_keys(self):
        """Test the Remove Keys operation."""
        component = DataOperationsComponent(
            data=Data(data={"key1": "value1", "key2": "value2", "key3": "value3"}),
            operations=[{"name": "Remove Keys"}],
            remove_keys_input=["key3"],
        )

        result = component.as_data()
        assert isinstance(result, Data)
        assert "key1" in result.data
        assert "key2" in result.data
        assert "key3" not in result.data

    def test_rename_keys(self):
        """Test the Rename Keys operation."""
        component = DataOperationsComponent(
            data=Data(data={"key1": "value1", "key2": "value2"}),
            operations=[{"name": "Rename Keys"}],
            rename_keys_input={"key1": "new_key1"},
        )

        result = component.as_data()
        assert isinstance(result, Data)
        assert "new_key1" in result.data
        assert "key1" not in result.data
        assert result.data["new_key1"] == "value1"

    def test_literal_eval(self):
        """Test the Literal Eval operation."""
        component = DataOperationsComponent(
            data=Data(data={"list_as_string": "[1, 2, 3]", "dict_as_string": "{'a': 1, 'b': 2}"}),
            operations=[{"name": "Literal Eval"}],
        )

        result = component.as_data()
        assert isinstance(result, Data)
        assert isinstance(result.data["list_as_string"], list)
        assert result.data["list_as_string"] == [1, 2, 3]
        assert isinstance(result.data["dict_as_string"], dict)
        assert result.data["dict_as_string"] == {"a": 1, "b": 2}

    def test_combine(self):
        """Test the Combine operation."""
        data1 = Data(data={"key1": "value1"})
        data2 = Data(data={"key2": "value2"})

        component = DataOperationsComponent(
            data=[data1, data2],
            operations=[{"name": "Combine"}],
        )

        result = component.as_data()
        assert isinstance(result, Data)
        assert "key1" in result.data
        assert "key2" in result.data
        assert result.data["key1"] == "value1"
        assert result.data["key2"] == "value2"

    def test_combine_with_overlapping_keys(self):
        """Test the Combine operation with overlapping keys."""
        data1 = Data(data={"common_key": "value1", "key1": "value1"})
        data2 = Data(data={"common_key": "value2", "key2": "value2"})

        component = DataOperationsComponent(
            data=[data1, data2],
            operations=[{"name": "Combine"}],
        )

        result = component.as_data()
        assert isinstance(result, Data)
        assert result.data["common_key"] == ["value1", "value2"]  # Combined string values
        assert result.data["key1"] == "value1"
        assert result.data["key2"] == "value2"

    def test_append_update(self):
        """Test the Append or Update Data operation."""
        component = DataOperationsComponent(
            data=Data(data={"existing_key": "existing_value"}),
            operations=[{"name": "Append or Update"}],
            append_update_data={"new_key": "new_value", "existing_key": "updated_value"},
        )

        result = component.as_data()
        assert isinstance(result, Data)
        assert result.data["existing_key"] == "updated_value"
        assert result.data["new_key"] == "new_value"

    def test_no_actions(self):
        """Test behavior when no actions are specified."""
        component = DataOperationsComponent(
            data=Data(data={"key1": "value1"}),
            operations=[],
        )

        result = component.as_data()
        assert isinstance(result, Data)
        assert result.data == {}

    def test_get_normalized_data(self):
        """Test the get_normalized_data helper method."""
        component = DataOperationsComponent(
            data=Data(data={"key1": "value1"}),
            operations=[],
        )

        # Add data under the "data" key
        component.data = Data(data={"test": {"key2": "value2"}})
        normalized = component.get_normalized_data()
        assert normalized == {"test": {"key2": "value2"}}

        # Test without the "data" key
        component.data = Data(data={"key3": "value3"})
        normalized = component.get_normalized_data()
        assert normalized == {"key3": "value3"}

    def test_validate_single_data_with_multiple_data(self):
        """Test that operations that don't support multiple data objects raise an error."""
        component = DataOperationsComponent(
            data=[Data(data={"key1": "value1"}), Data(data={"key2": "value2"})],
            operations=[{"name": "Select Keys"}],
            select_keys_input=["key1"],
        )

        with pytest.raises(ValueError, match="Select Keys operation is not supported for multiple data objects"):
            component.as_data()

    def test_removed_operation_raises_instead_of_returning_empty(self):
        """A persisted flow referencing the removed 'Filter Values' op fails fast, not silently."""
        component = DataOperationsComponent(
            data=Data(data={"items": [{"name": "a"}]}),
            operations=[{"name": "Filter Values"}],
        )
        with pytest.raises(ValueError, match="no longer supported"):
            component.as_data()

    def test_update_build_config_clears_input_fields_when_operation_removed(self):
        """Test that removing the selected operation hides all operation-specific input fields."""
        from lfx.schema.dotdict import dotdict

        component = DataOperationsComponent(
            data=Data(data={"key1": "value1"}),
            operations=[],
        )
        # Simulate build_config after "Rename Keys" was selected (operation-specific fields visible)
        build_config = dotdict(
            {
                "operations": {"value": [], "show": True},
                "data": {"value": None, "show": True},
                "rename_keys_input": {"value": {"old_key": "new_key"}, "show": True},
                "remove_keys_input": {"value": [], "show": True},
                "select_keys_input": {"value": [], "show": False},
            }
        )
        result = component.update_build_config(build_config, [], "operations")

        # All operation-specific fields should be hidden when no operation is selected
        assert result["rename_keys_input"]["show"] is False
        assert result["remove_keys_input"]["show"] is False
        assert result["select_keys_input"]["show"] is False
        # Default fields (operations, data) should remain visible
        assert result["operations"]["show"] is True
        assert result["data"]["show"] is True


class TestUpdateFrontendNodeRestoresVisibility:
    """Clicking Update on a saved JSON Operations node must keep its operation's fields visible.

    ``update_frontend_node`` rebuilds the template from class defaults, where every operation field
    has ``show=False``. The generic merge restores only values, so before the fix the selected
    operation's input disappeared and ``ParameterHandler`` dropped it from the run.
    """

    NODE_ID = "DataOperations-test"

    @staticmethod
    def _saved_node(operation: str | None, **values) -> dict:
        """Return a node as the canvas saves it after the user picks ``operation`` and fills ``values``."""
        node, _ = build_custom_component_template(DataOperationsComponent(), user_id="test-user")
        template = node["template"]
        component = DataOperationsComponent()
        component.update_build_config(template, [{"name": operation}] if operation else [], "operations")
        for field, value in values.items():
            template[field]["value"] = value
            if field == "mapped_json_display":
                component.update_build_config(template, value, field)
        return node

    @staticmethod
    async def _update(saved: dict) -> dict:
        """Run the Update Component path: a fresh class-default node merged with the saved one."""
        fresh, _ = build_custom_component_template(DataOperationsComponent(), user_id="test-user")
        return await DataOperationsComponent().update_frontend_node(fresh, copy.deepcopy(saved))

    def _run(self, node: dict, data: Data) -> Data:
        """Run ``node`` with the params a graph build hands the component, which skips hidden fields."""
        payload = {
            "nodes": [{"id": self.NODE_ID, "data": {"id": self.NODE_ID, "type": "DataOperations", "node": node}}],
            "edges": [],
        }
        graph = Graph.from_payload(payload, flow_id="test-flow", user_id="test-user")
        params = {k: v for k, v in graph.get_vertex(self.NODE_ID).params.items() if k != "code"}
        return DataOperationsComponent(data=data, **params).as_data()

    @staticmethod
    def _visibility(template: dict) -> dict[str, bool]:
        return {field: template[field]["show"] for field in DataOperationsComponent.ALL_OPERATION_FIELDS}

    @pytest.mark.parametrize("operation", list(DataOperationsComponent.actions_data))
    async def test_update_keeps_saved_visibility(self, operation):
        saved = self._saved_node(operation)
        template = (await self._update(saved))["template"]

        shown = {field for field, show in self._visibility(template).items() if show}
        assert shown == set(DataOperationsComponent.actions_data[operation]) - {"operations"}
        assert self._visibility(template) == self._visibility(saved["template"])
        assert template["data"]["show"] is True
        assert template["operations"]["show"] is True
        assert template["data"]["list"] is (operation == "Combine")
        assert "is_list" not in template["data"]
        assert template["operations"]["value"] == [{"name": operation}]

    async def test_saved_select_keys_value_survives(self):
        template = (await self._update(self._saved_node("Select Keys", select_keys_input=["text"])))["template"]
        assert template["select_keys_input"]["show"] is True
        assert template["select_keys_input"]["value"] == ["text"]
        assert template["data"]["list"] is False
        assert "is_list" not in template["data"]

    async def test_no_operation_hides_all_operation_fields(self):
        template = (await self._update(self._saved_node(None)))["template"]
        assert not any(self._visibility(template).values())
        assert template["data"]["show"] is True

    async def test_removed_operation_hides_all_operation_fields(self):
        template = (await self._update(self._saved_node("Filter Values")))["template"]
        assert not any(self._visibility(template).values())
        assert template["data"]["show"] is True

    async def test_path_selection_rebuilds_selected_key_options(self):
        saved = self._saved_node("Path Selection", mapped_json_display='{"a": {"b": 1}}', selected_key=".a.b")
        template = (await self._update(saved))["template"]
        assert template["selected_key"]["show"] is True
        assert template["selected_key"]["value"] == ".a.b"
        assert template["selected_key"]["options"] == [".a", ".a.b"]

    async def test_path_selection_with_invalid_saved_json_hides_selected_key(self):
        saved = self._saved_node("Path Selection", mapped_json_display="{not json")
        template = (await self._update(saved))["template"]
        assert template["mapped_json_display"]["show"] is True
        assert template["selected_key"]["show"] is False

    @pytest.mark.parametrize(
        ("operation", "values", "expected"),
        [
            ("Select Keys", {"select_keys_input": ["text"]}, {"text": "hello"}),
            ("Remove Keys", {"remove_keys_input": ["extra"]}, {"text": "hello"}),
            ("Rename Keys", {"rename_keys_input": {"text": "body"}}, {"body": "hello", "extra": 1}),
            ("Append or Update", {"append_update_data": {"tag": "new"}}, {"text": "hello", "extra": 1, "tag": "new"}),
            ("JQ Expression", {"query": ".text"}, {"result": "hello"}),
            (
                "Path Selection",
                {"mapped_json_display": '{"text": "x", "extra": 0}', "selected_key": ".text"},
                {"result": "hello"},
            ),
        ],
    )
    async def test_run_output_unchanged_after_update(self, operation, values, expected):
        """The smoke-test case: Select Keys ``['text']`` returned ``{}`` after Update."""
        saved = self._saved_node(operation, **values)
        updated = await self._update(saved)
        data = Data(data={"text": "hello", "extra": 1})

        assert self._run(saved, data).data == expected
        assert self._run(updated, data).data == expected


class TestDataListFlagOnSerializedTemplate:
    """Only Combine lets the JSON input take several edges, checked on the template the canvas reads.

    The serialized template stores ``Input.is_list`` under ``list``. The canvas
    (``isValidConnection``) and the graph (``ParameterHandler``) read that key to
    decide whether ``data`` accepts more than one edge. The component used to
    write ``is_list`` instead, so ``list`` kept its class default (``True``) for
    every operation and the stray key was saved into flows.
    """

    @staticmethod
    def _template() -> dotdict:
        node, _ = build_custom_component_template(DataOperationsComponent(), user_id="test-user")
        return dotdict(node["template"])

    def test_serialized_data_field_uses_list_key(self):
        data_field = self._template()["data"]
        assert data_field["list"] is True
        assert "is_list" not in data_field

    @pytest.mark.parametrize("action", sorted(ACTION_CONFIG))
    def test_only_combine_accepts_many_edges(self, action):
        result = DataOperationsComponent().update_build_config(self._template(), [{"name": action}], "operations")
        assert result["data"]["list"] is (action == "Combine")
        assert "is_list" not in result["data"]

    def test_stray_is_list_from_an_earlier_save_is_dropped(self):
        template = self._template()
        template["data"]["is_list"] = False
        result = DataOperationsComponent().update_build_config(template, [{"name": "Combine"}], "operations")
        assert result["data"]["list"] is True
        assert "is_list" not in result["data"]

    @pytest.mark.parametrize(("action", "expected"), [("Combine", True), ("Select Keys", False)])
    def test_updated_data_field_rebuilds_as_input_with_matching_flag(self, action, expected):
        """The flag reaches the input model, and no stray key breaks rebuilding the field."""
        template = self._template()
        template["data"]["is_list"] = not expected
        result = DataOperationsComponent().update_build_config(template, [{"name": action}], "operations")
        field = copy.deepcopy(dict(result["data"]))
        rebuilt = instantiate_input(field.pop("_input_type"), {**field, "name": "data"})
        assert rebuilt.is_list is expected


class TestExtraDataEdgesFailLoudly:
    """A single-input JSON operation must refuse to run when several JSON edges feed the node.

    A node keeps its edges when its operation changes, and nothing prunes extra edges when ``data``
    stops being a list. With ``list`` false the graph passes only the last edge's data, so without
    this check the run would use partial input and report no error.
    """

    class _WordCount(OperationsComponent):
        # A JSON-producing source: Word Count on text, advertised through the JSON output.
        outputs = [Output(display_name="JSON", name="data_output", method="as_data")]

    async def _run(self, action: str, texts: list[str], *, list_flag: bool) -> dict:
        sources = []
        for index, text in enumerate(texts):
            source = self._WordCount(_id=f"source-{index}")
            source.set(input_type="Text", operation=[{"name": "Word Count"}], text_input=text)
            sources.append(source)
        target = DataOperationsComponent(_id="target")
        target.set(
            operations=[{"name": action}],
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
