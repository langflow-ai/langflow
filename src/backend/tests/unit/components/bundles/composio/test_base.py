from unittest.mock import MagicMock, patch

import pytest
from langflow.base.composio.composio_base import ComposioBaseComponent

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient


class MockComposioToolSet:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.client = MagicMock()

    def get_tools(self, *_):
        return []

    def execute_action(self, *_, **__):
        return {"successful": True, "data": {"result": "mocked response"}}


class TestComposioBase(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        class TestComponent(ComposioBaseComponent):
            def execute_action(self):
                return []

        return TestComponent

    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "",
            "entity_id": "default",
            "action": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        # Component not yet released, mark all versions as non-existent
        return [
            {"version": "1.0.17", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.0.18", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.0.19", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "composio", "file_name": DID_NOT_EXIST},
        ]

    def test_build_wrapper_no_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Please provide a valid Composio API Key in the component settings"):
            component._build_wrapper()

    def test_build_wrapper_with_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        wrapper = component._build_wrapper()
        assert isinstance(wrapper, MockComposioToolSet)
        assert wrapper.api_key == "test_key"

    def test_build_action_maps(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        # Test with empty actions data
        component._actions_data = {}
        component._build_action_maps()
        assert component._display_to_key_map == {}
        assert component._key_to_display_map == {}
        assert component._sanitized_names == {}

        # Test with sample actions data
        component._actions_data = {
            "ACTION_1": {"display_name": "Action One"},
            "ACTION_2": {"display_name": "Action Two"},
        }
        component._build_action_maps()
        assert component._display_to_key_map == {
            "Action One": "ACTION_1",
            "Action Two": "ACTION_2",
        }
        assert component._key_to_display_map == {
            "ACTION_1": "Action One",
            "ACTION_2": "Action Two",
        }

    def test_get_action_fields(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component._actions_data = {
            "ACTION_1": {"action_fields": ["field1", "field2"]},
            "ACTION_2": {"action_fields": ["field3"]},
        }

        # Test with valid action key
        fields = component._get_action_fields("ACTION_1")
        assert fields == {"field1", "field2"}

        # Test with non-existent action key
        fields = component._get_action_fields("NON_EXISTENT")
        assert fields == set()

        # Test with None action key
        fields = component._get_action_fields(None)
        assert fields == set()

    def test_show_hide_fields(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component._all_fields = {"field1", "field2"}
        component._bool_variables = {"field2"}
        component._actions_data = {
            "ACTION_1": {"display_name": "Action One", "action_fields": ["field1"]},
        }

        build_config = {
            "field1": {"show": False, "value": "old_value"},
            "field2": {"show": False, "value": True},
        }

        # Test with no field value
        component.show_hide_fields(build_config, None)
        assert not build_config["field1"]["show"]
        assert not build_config["field2"]["show"]
        assert build_config["field1"]["value"] == ""
        assert build_config["field2"]["value"] is False

        # Test with valid action
        component.show_hide_fields(build_config, [{"name": "Action One"}])
        assert build_config["field1"]["show"]  # Should be shown since it's in ACTION_1's fields
        assert not build_config["field2"]["show"]  # Should remain hidden
