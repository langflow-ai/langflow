from unittest.mock import MagicMock, patch

import pytest
from composio import Action
from langflow.schema.dataframe import DataFrame

from lfx.components.composio.slack_composio import ComposioSlackAPIComponent
from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL = "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL"
    SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION = "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION"


class TestSlackComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioSlackAPIComponent

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
        assert component.display_name == "Slack"
        assert component.app_name == "slack"
        assert "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL" in component._actions_data
        assert "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION" in component._actions_data

    def test_execute_action_send_message_to_channel(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(
            Action, "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL", MockAction.SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL
        )

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Post Message To Channel"}]
        component.SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_channel = "random"
        component.SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_text = "Test Body"

        component._actions_data = {
            "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL": {
                "display_name": "Post Message To Channel",
                "action_fields": [
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_as_user",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_attachments",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_blocks",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_channel",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_icon_emoji",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_icon_url",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_link_names",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_mrkdwn",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_parse",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_reply_broadcast",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_text",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_thread_ts",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_unfurl_links",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_unfurl_media",
                    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_username",
                ],
            },
        }

        result = component.execute_action()
        assert result == {"result": "mocked response"}

    def test_execute_action_list_all_slack_team_users(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(
            Action,
            "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION",
            MockAction.SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION,
        )

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "List Users"}]
        component.SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_limit = 1

        component._actions_data = {
            "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION": {
                "display_name": "List Users",
                "action_fields": [
                    "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_limit",
                    "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_cursor",
                    "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_include_locale",
                ],
            },
        }

        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {"successful": True, "data": {"messages": "mocked response"}}

        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            assert result == {"messages": "mocked response"}

    def test_execute_action_invalid_action(self, component_class, default_kwargs):
        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Invalid Action"}]

        # Execute action should raise ValueError
        with pytest.raises(ValueError, match="Invalid action: Invalid Action"):
            component.execute_action()

    def test_as_dataframe(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(
            Action, "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL", MockAction.SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL
        )

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Post Message To Channel"}]
        component.SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_channel = "random"
        component.SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_text = "Test Body"

        mock_slack_messages = [
            {"channel": "channel1", "user": "user1", "text": "text message 1", "ts": "ts1", "team": "team1"},
            {"channel": "channel2", "user": "user2", "text": "text message 2", "ts": "ts2", "team": "team2"},
        ]

        with patch.object(component, "execute_action", return_value=mock_slack_messages):
            result = component.as_dataframe()

            assert isinstance(result, DataFrame)

            assert not result.empty

            data_str = str(result)
            assert "text message 1" in data_str
            assert "text message 2" in data_str

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
