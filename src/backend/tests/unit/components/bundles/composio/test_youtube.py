from unittest.mock import MagicMock, patch

import pytest
from composio import Action
from langflow.components.composio.youtube_composio import ComposioYoutubeAPIComponent
from langflow.schema.dataframe import DataFrame

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    YOUTUBE_GET_CHANNEL_ID_BY_HANDLE = "YOUTUBE_GET_CHANNEL_ID_BY_HANDLE"
    YOUTUBE_LIST_CHANNEL_VIDEOS = "YOUTUBE_LIST_CHANNEL_VIDEOS"


class TestYoutubeComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioYoutubeAPIComponent

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
        assert component.display_name == "Youtube"
        assert component.app_name == "youtube"
        assert "YOUTUBE_GET_CHANNEL_ID_BY_HANDLE" in component._actions_data
        assert "YOUTUBE_LIST_CHANNEL_VIDEOS" in component._actions_data

    def test_execute_action_get_channel_id_by_handle(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "YOUTUBE_GET_CHANNEL_ID_BY_HANDLE", MockAction.YOUTUBE_GET_CHANNEL_ID_BY_HANDLE)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get Channel ID by Handle"}]
        component.channel_handle = "test_handle"

        component._actions_data = {
            "YOUTUBE_GET_CHANNEL_ID_BY_HANDLE": {
                "display_name": "Get Channel ID by Handle",
                "action_fields": ["channel_handle"],
            }
        }

        # Execute action
        result = component.execute_action()
        # assert result == {"result": "mocked response"}
        assert result == "mocked response"

    def test_execute_action_list_channel_videos(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "YOUTUBE_LIST_CHANNEL_VIDEOS", MockAction.YOUTUBE_LIST_CHANNEL_VIDEOS)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "List Channel Videos"}]
        component.channel_id = "test_channel_id"

        # For this specific test, we need to customize the action_data to handle results field
        component._actions_data = {
            "YOUTUBE_LIST_CHANNEL_VIDEOS": {
                "display_name": "List Channel Videos",
                "action_fields": ["channel_id"],
            }
        }

        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {"successful": True, "data": {"videos": "mocked response"}}

        # Patch the _build_wrapper method
        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            # Based on the component's actual behavior, it returns the result_field directly
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
        monkeypatch.setattr(Action, "YOUTUBE_GET_CHANNEL_ID_BY_HANDLE", MockAction.YOUTUBE_GET_CHANNEL_ID_BY_HANDLE)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get Channel ID by Handle"}]
        component.channel_handle = "test_handle"

        # Create mock email data that would be returned by execute_action
        mock_emails = [
            {
                "channel_handle": "channel1",
            },
            {
                "channel_handle": "channel2",
            },
        ]

        # Mock the execute_action method to return our mock data
        with patch.object(component, "execute_action", return_value=mock_emails):
            # Test as_dataframe method
            result = component.as_dataframe()

            # Verify the result is a DataFrame
            assert isinstance(result, DataFrame)

            # Verify the DataFrame is not empty
            assert not result.empty

            # Check for expected content in the DataFrame string representation
            data_str = str(result)
            assert "channel1" in data_str

    def test_update_build_config(self, component_class, default_kwargs):
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
        assert len(result["action"]["options"]) > 0  
