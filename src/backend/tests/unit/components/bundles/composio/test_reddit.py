from unittest.mock import MagicMock, patch

import pytest
from composio import Action
from langflow.components.composio.reddit_composio import ComposioRedditAPIComponent
from langflow.schema.dataframe import DataFrame

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    REDDIT_RETRIEVE_REDDIT_POST = "REDDIT_RETRIEVE_REDDIT_POST"
    REDDIT_CREATE_REDDIT_POST = "REDDIT_CREATE_REDDIT_POST"


class TestRedditComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioRedditAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "",
            "entity_id": "default",
            "action": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.17", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.0.18", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.0.19", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "composio", "file_name": DID_NOT_EXIST},
        ]

    def test_init(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component.display_name == "Reddit"
        assert component.name == "RedditAPI"
        assert component.app_name == "reddit"
        assert "REDDIT_RETRIEVE_REDDIT_POST" in component._actions_data
        assert "REDDIT_CREATE_REDDIT_POST" in component._actions_data

    def test_execute_action_retrieve_reddit_post(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "REDDIT_RETRIEVE_REDDIT_POST", MockAction.REDDIT_RETRIEVE_REDDIT_POST)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Retrieve Reddit Post"}]
        component.REDDIT_RETRIEVE_REDDIT_POST_size = 10
        component.REDDIT_RETRIEVE_REDDIT_POST_subreddit = "test"

        component._actions_data = {
            "REDDIT_RETRIEVE_REDDIT_POST": {
                "display_name": "Retrieve Reddit Post",
                "action_fields": ["REDDIT_RETRIEVE_REDDIT_POST_size", "REDDIT_RETRIEVE_REDDIT_POST_subreddit"],
                "get_result_field": True,
                "result_field": "posts_list",
            },
        }

        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {
            "successful": True,
            "data": {"posts_list": [{"title": "Test Post", "url": "https://reddit.com/test"}]},
        }

        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], dict)
            assert "0" in result[0]

    def test_execute_action_create_post(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "REDDIT_CREATE_REDDIT_POST", MockAction.REDDIT_CREATE_REDDIT_POST)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Create Reddit Post"}]
        component.REDDIT_CREATE_REDDIT_POST_flair_id = "test_flair_id"
        component.REDDIT_CREATE_REDDIT_POST_kind = "test_kind"
        component.REDDIT_CREATE_REDDIT_POST_subreddit = "test_subreddit"
        component.REDDIT_CREATE_REDDIT_POST_text = "test_text"
        component.REDDIT_CREATE_REDDIT_POST_title = "test_title"
        component.REDDIT_CREATE_REDDIT_POST_url = "test_url"

        component._actions_data = {
            "REDDIT_CREATE_REDDIT_POST": {
                "display_name": "Create Reddit Post",
                "action_fields": [
                    "REDDIT_CREATE_REDDIT_POST_flair_id",
                    "REDDIT_CREATE_REDDIT_POST_kind",
                    "REDDIT_CREATE_REDDIT_POST_subreddit",
                    "REDDIT_CREATE_REDDIT_POST_text",
                    "REDDIT_CREATE_REDDIT_POST_title",
                    "REDDIT_CREATE_REDDIT_POST_url",
                ],
                "get_result_field": True,
                "result_field": "items",
            }
        }

        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {"successful": True, "data": {"items": "mocked response"}}

        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0] == {"value": "mocked response"}

    def test_execute_action_invalid_action(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Invalid Action"}]

        with pytest.raises(ValueError, match="Invalid action: Invalid Action"):
            component.execute_action()

    def test_as_dataframe(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "REDDIT_RETRIEVE_REDDIT_POST", MockAction.REDDIT_RETRIEVE_REDDIT_POST)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Retrieve Reddit Post"}]
        component.REDDIT_RETRIEVE_REDDIT_POST_size = 10
        component.REDDIT_RETRIEVE_REDDIT_POST_subreddit = "test"

        mock_posts_list = [
            {
                "title": "Test Post 1",
                "url": "https://reddit.com/test1",
            },
            {
                "title": "Test Post 2",
                "url": "https://reddit.com/test2",
            },
        ]

        with patch.object(component, "execute_action", return_value=mock_posts_list):
            result = component.as_dataframe()

            assert isinstance(result, DataFrame)

            assert not result.empty

            data_str = str(result)
            assert "Test Post 1" in data_str
            assert "Test Post 2" in data_str

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

        result = component.update_build_config(build_config, "", "api_key")
        assert result["auth_link"]["value"] == ""
        assert "Please provide a valid Composio API Key" in result["auth_link"]["auth_tooltip"]
        assert result["action"]["options"] == []

        component.api_key = "test_key"
        result = component.update_build_config(build_config, "test_key", "api_key")
        assert len(result["action"]["options"]) > 0
