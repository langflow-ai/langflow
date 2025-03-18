from unittest.mock import MagicMock, patch

import pytest
from composio.client.exceptions import NoItemsFound
from langflow.components.composio.gmail_api import GmailAPIComponent
from langflow.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestGmailAPIComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return GmailAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "api_key": "test_api_key",
            "entity_id": "default",
            "action": "GMAIL_SEND_EMAIL",
            "recipient_email": "test@example.com",
            "subject": "Test Subject",
            "body": "Test Body",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @patch("langflow.components.composio.gmail_api.ComposioToolSet")
    def test_execute_action_send_email_success(self, mock_toolset):
        # Setup mock
        mock_instance = mock_toolset.return_value
        mock_instance.execute_action.return_value = "Email sent successfully"

        # Create component with required parameters
        component = GmailAPIComponent(
            api_key="test_api_key",
            action="Send Email",  # Using display name
            recipient_email="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        # Execute the action
        result = component.execute_action()

        # Verify the result
        assert isinstance(result, Message)
        assert result.text == "Email sent successfully"

        # Verify the mock was called with correct parameters
        mock_instance.execute_action.assert_called_once()
        call_args = mock_instance.execute_action.call_args[1]
        assert call_args["params"]["recipient_email"] == "test@example.com"
        assert call_args["params"]["subject"] == "Test Subject"
        assert call_args["params"]["body"] == "Test Body"

    @patch("langflow.components.composio.gmail_api.ComposioToolSet")
    def test_execute_action_fetch_emails(self, mock_toolset):
        # Setup mock
        mock_instance = mock_toolset.return_value
        mock_instance.execute_action.return_value = "Retrieved 5 emails"

        # Create component
        component = GmailAPIComponent(
            api_key="test_api_key", action="Fetch Emails", max_results=5, query="from:test@example.com"
        )

        # Execute the action
        result = component.execute_action()

        # Verify the result
        assert isinstance(result, Message)
        assert result.text == "Retrieved 5 emails"

        # Verify the mock was called with correct parameters
        mock_instance.execute_action.assert_called_once()
        call_args = mock_instance.execute_action.call_args[1]
        assert call_args["params"]["max_results"] == 5
        assert call_args["params"]["query"] == "from:test@example.com"

    @patch("langflow.components.composio.gmail_api.ComposioToolSet")
    def test_execute_action_error(self, mock_toolset):
        # Setup mock to raise an exception
        mock_instance = mock_toolset.return_value
        mock_instance.execute_action.side_effect = Exception("API Error")

        # Create component
        component = GmailAPIComponent(
            api_key="test_api_key",
            action="Send Email",
            recipient_email="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        # Execute the action and expect an error
        with pytest.raises(ValueError, match="Failed to execute Send Email: API Error"):
            component.execute_action()

    @patch("langflow.components.composio.gmail_api.ComposioToolSet")
    def test_update_build_config_with_valid_api_key(self, mock_toolset):
        # Setup mocks
        mock_instance = mock_toolset.return_value
        mock_entity = MagicMock()
        mock_instance.client.get_entity.return_value = mock_entity

        # Mock successful connection
        mock_entity.get_connection.return_value = "connected"

        # Create component
        component = GmailAPIComponent(api_key="test_api_key")

        # Test update_build_config
        build_config = {
            "auth_status": {"show": False, "value": "Not Connected", "advanced": True},
            "auth_link": {"show": False, "value": "", "advanced": True},
            "action": {"show": True, "options": []},
            # Add all action fields with default show=False
            "recipient_email": {"show": False, "value": ""},
            "subject": {"show": False, "value": ""},
            "body": {"show": False, "value": ""},
            "max_results": {"show": False, "value": ""},
            "query": {"show": False, "value": ""},
            "message_id": {"show": False, "value": ""},
            "thread_id": {"show": False, "value": ""},
            "message_body": {"show": False, "value": ""},
            "label_name": {"show": False, "value": ""},
            "label_id": {"show": False, "value": ""},
            "cc": {"show": False, "value": ""},
            "bcc": {"show": False, "value": ""},
            "is_html": {"show": False, "value": False},
        }

        result = component.update_build_config(build_config, "Send Email", "action")

        # Verify the result
        assert result["auth_status"]["value"] == "✅"
        assert result["auth_link"]["show"] is False
        assert "Send Email" in result["action"]["options"]

        # Verify fields for Send Email are shown
        assert result["recipient_email"]["show"] is True
        assert result["subject"]["show"] is True
        assert result["body"]["show"] is True

    @patch("langflow.components.composio.gmail_api.ComposioToolSet")
    def test_update_build_config_needs_authentication(self, mock_toolset):
        # Setup mocks
        mock_instance = mock_toolset.return_value
        mock_entity = MagicMock()
        mock_instance.client.get_entity.return_value = mock_entity

        # Mock connection not found
        mock_entity.get_connection.side_effect = NoItemsFound("Connection not found")

        # Mock auth scheme
        mock_auth_scheme = MagicMock()
        mock_auth_scheme.auth_mode = "OAUTH2"
        component = GmailAPIComponent(api_key="test_api_key")
        component._get_auth_scheme = MagicMock(return_value=mock_auth_scheme)

        # Mock initiate connection
        component._initiate_default_connection = MagicMock(return_value="https://auth.example.com")

        # Test update_build_config
        build_config = {
            "auth_status": {"show": False, "value": "Not Connected", "advanced": True},
            "auth_link": {"show": False, "value": "", "advanced": True},
            "action": {"show": True, "options": []},
            # Add all action fields with default show=False
            "recipient_email": {"show": False, "value": ""},
            "subject": {"show": False, "value": ""},
            "body": {"show": False, "value": ""},
        }

        result = component.update_build_config(build_config, None, None)

        # Verify the result
        assert result["auth_status"]["value"] == "Click link to authenticate"
        assert result["auth_link"]["show"] is True
        assert result["auth_link"]["value"] == "https://auth.example.com"

    def test_show_hide_fields(self):
        # Create component
        component = GmailAPIComponent()

        # Create a build config with all fields
        build_config = {
            "recipient_email": {"show": False, "value": ""},
            "subject": {"show": False, "value": ""},
            "body": {"show": False, "value": ""},
            "max_results": {"show": False, "value": ""},
            "query": {"show": False, "value": ""},
            "message_id": {"show": False, "value": ""},
            "thread_id": {"show": False, "value": ""},
            "message_body": {"show": False, "value": ""},
            "label_name": {"show": False, "value": ""},
            "label_id": {"show": False, "value": ""},
            "cc": {"show": False, "value": ""},
            "bcc": {"show": False, "value": ""},
            "is_html": {"show": False, "value": False},
        }

        # Test with Send Email action
        component.show_hide_fields(build_config, "Send Email")

        # Verify Send Email fields are shown
        assert build_config["recipient_email"]["show"] is True
        assert build_config["subject"]["show"] is True
        assert build_config["body"]["show"] is True
        assert build_config["cc"]["show"] is True
        assert build_config["bcc"]["show"] is True
        assert build_config["is_html"]["show"] is True

        # Verify other fields are hidden
        assert build_config["max_results"]["show"] is False
        assert build_config["query"]["show"] is False

        # Reset and test with Fetch Emails action
        for config in build_config.values():
            config["show"] = False

        component.show_hide_fields(build_config, "Fetch Emails")

        # Verify Fetch Emails fields are shown
        assert build_config["max_results"]["show"] is True
        assert build_config["query"]["show"] is True

        # Verify other fields are hidden
        assert build_config["recipient_email"]["show"] is False
        assert build_config["subject"]["show"] is False

    @patch("langflow.components.composio.gmail_api.ComposioToolSet")
    async def test_get_tools(self, mock_toolset):
        # Setup mock
        mock_instance = mock_toolset.return_value
        mock_tools = [MagicMock(), MagicMock()]
        # Configure the mock tools to have name attributes
        mock_tools[0].name = "GMAIL_SEND_EMAIL"
        mock_tools[1].name = "GMAIL_FETCH_EMAILS"
        mock_instance.get_tools.return_value = mock_tools

        # Create component
        component = GmailAPIComponent(api_key="test_api_key")

        # Get tools
        tools = await component._get_tools()

        # Verify the result
        assert tools == mock_tools
        assert all(hasattr(tool, "tags") for tool in tools)

        # Verify that each tool has tags that are a list containing a string
        for tool in tools:
            assert isinstance(tool.tags, list), f"Tool tags should be a list, got {type(tool.tags)}"
            assert len(tool.tags) == 1, f"Tool tags should have exactly one element, got {len(tool.tags)}"
            assert isinstance(tool.tags[0], str), f"Tool tag should be a string, got {type(tool.tags[0])}"
            assert tool.tags[0] == tool.name, f"Tool tag should be the tool name, got {tool.tags[0]}"

        # Verify the mock was called with correct parameters
        mock_instance.get_tools.assert_called_once()
        assert set(mock_instance.get_tools.call_args[1]["actions"]) == set(component._actions_data.keys())
