from unittest.mock import MagicMock, patch

import pytest
from composio import Action
from langflow.components.composio.googlemeet_composio import ComposioGooglemeetAPIComponent
from langflow.schema.dataframe import DataFrame

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    GOOGLEMEET_CREATE_MEET = "GOOGLEMEET_CREATE_MEET"
    GOOGLEMEET_GET_MEET = "GOOGLEMEET_GET_MEET"


class TestGoogleMeetComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioGooglemeetAPIComponent

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

    def test_init(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component.display_name == "Google Meet"
        assert component.app_name == "googlemeet"
        assert "GOOGLEMEET_CREATE_MEET" in component._actions_data
        assert "GOOGLEMEET_GET_MEET" in component._actions_data

    def test_execute_action_create_meet(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GOOGLEMEET_CREATE_MEET", MockAction.GOOGLEMEET_CREATE_MEET)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Create Meet"}]
        setattr(component, "GOOGLEMEET_CREATE_MEET-access_type", "OPEN")
        setattr(component, "GOOGLEMEET_CREATE_MEET-entry_point_access", "ALL")

        # For this specific test, customize the _actions_data to not use get_result_field
        component._actions_data = {
            "GOOGLEMEET_CREATE_MEET": {
                "display_name": "Create Meet",
                "action_fields": ["GOOGLEMEET_CREATE_MEET-access_type", "GOOGLEMEET_CREATE_MEET-entry_point_access"],
            },
        }

        # Execute action
        result = component.execute_action()
        assert result == "mocked response"

    def test_execute_action_get_meet(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GOOGLEMEET_GET_MEET", MockAction.GOOGLEMEET_GET_MEET)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get Meet Details"}]
        setattr(component, "GOOGLEMEET_GET_MEET-space_name", "test space")

        # For this specific test, we need to customize the action_data to handle results field
        component._actions_data = {
            "GOOGLEMEET_GET_MEET": {
                "display_name": "Get Meet Details",
                "action_fields": ["GOOGLEMEET_GET_MEET-space_name"],
            },
        }

        # Create a mock for the toolset with specific structure for this test
        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {"successful": True, "data": {"messages": "mocked response"}}

        # Patch the _build_wrapper method
        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            # Based on the component's actual behavior, it returns the entire data dict
            assert result == "mocked response"

    def test_execute_action_invalid_action(self, component_class, default_kwargs):
        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Invalid Action"}]

        # Execute action should raise ValueError
        with pytest.raises(ValueError, match="Invalid action: Invalid Action"):
            component.execute_action()

    def test_as_dataframe(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GOOGLEMEET_GET_MEET", MockAction.GOOGLEMEET_GET_MEET)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get Meet"}]
        setattr(component, "GOOGLEMEET_GET_MEET-space_name", "test space")

        # Create mock email data that would be returned by execute_action
        mock_meet_details = [
            {
                "space_name": "test space",
            },
            {
                "space_name": "test space 2",
            },
        ]

        # Mock the execute_action method to return our mock data
        with patch.object(component, "execute_action", return_value=mock_meet_details):
            # Test as_dataframe method
            result = component.as_dataframe()

            # Verify the result is a DataFrame
            assert isinstance(result, DataFrame)

            # Verify the DataFrame is not empty
            assert not result.empty

            # Check for expected content in the DataFrame string representation
            data_str = str(result)
            assert "test space" in data_str

    def test_update_build_config(self, component_class, default_kwargs):
        # Test that the Google Meet component properly inherits and uses the base component's
        # update_build_config method
        component = component_class(**default_kwargs)
        build_config = {
            "auth_link": {"value": "", "auth_tooltip": ""},
            "action": {
                "options": [],
                "helper_text": "",
                "helper_text_metadata": {},
            },
        }

        # Test with empty API key
        result = component.update_build_config(build_config, "", "api_key")
        assert result["auth_link"]["value"] == ""
        assert "Please provide a valid Composio API Key" in result["auth_link"]["auth_tooltip"]
        assert result["action"]["options"] == []

        # Test with valid API key
        component.api_key = "test_key"
        result = component.update_build_config(build_config, "test_key", "api_key")
        assert len(result["action"]["options"]) > 0  # Should have Google Meet actions
