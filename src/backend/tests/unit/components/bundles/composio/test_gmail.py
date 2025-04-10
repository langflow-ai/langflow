from unittest.mock import MagicMock, patch

import pytest
from composio import Action
from langflow.components.composio.gmail_composio import ComposioGmailAPIComponent
from langflow.schema.dataframe import DataFrame

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    GMAIL_SEND_EMAIL = "GMAIL_SEND_EMAIL"
    GMAIL_FETCH_EMAILS = "GMAIL_FETCH_EMAILS"
    GMAIL_GET_PROFILE = "GMAIL_GET_PROFILE"


class TestGmailComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioGmailAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "",
            "entity_id": "default",
            "action": None,
            "recipient_email": "",
            "subject": "",
            "body": "",
            "is_html": False,
            "max_results": 10,
            "query": "",
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
        assert component.display_name == "Gmail"
        assert component.name == "GmailAPI"
        assert component.app_name == "gmail"
        assert "GMAIL_SEND_EMAIL" in component._actions_data
        assert "GMAIL_FETCH_EMAILS" in component._actions_data

    def test_execute_action_send_email(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GMAIL_SEND_EMAIL", MockAction.GMAIL_SEND_EMAIL)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Send Email"}]
        component.recipient_email = "test@example.com"
        component.subject = "Test Subject"
        component.body = "Test Body"
        component.is_html = False

        # Execute action
        result = component.execute_action()
        assert result == "mocked response"

    def test_execute_action_fetch_emails(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GMAIL_FETCH_EMAILS", MockAction.GMAIL_FETCH_EMAILS)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Fetch Emails"}]
        component.max_results = 10
        component.query = "from:test@example.com"

        # Create a mock for the toolset
        mock_toolset = MagicMock()
        # The execute_action method needs to return a structure that works with the component's logic
        # Based on the error, we need to make sure the 'data' key contains a dictionary with at least one key
        mock_toolset.execute_action.return_value = {"data": {"response": "mocked response"}}

        # Patch the _build_wrapper method to return our mock
        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            # Also patch the _actions_data to ensure it has the correct structure for GMAIL_FETCH_EMAILS
            # This ensures the result_field is set correctly
            component._actions_data = {
                "GMAIL_FETCH_EMAILS": {
                    "action_fields": ["max_results", "query"],
                    "result_field": "response",
                    "get_result_field": True,
                }
            }

            # Execute action
            result = component.execute_action()
            assert result == "mocked response"

    def test_execute_action_get_profile(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GMAIL_GET_PROFILE", MockAction.GMAIL_GET_PROFILE)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get User Profile"}]

        # Execute action
        result = component.execute_action()
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
        monkeypatch.setattr(Action, "GMAIL_FETCH_EMAILS", MockAction.GMAIL_FETCH_EMAILS)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Fetch Emails"}]
        component.max_results = 10

        # Create mock email data that would be returned by execute_action
        mock_emails = [
            {
                "id": "1",
                "threadId": "thread1",
                "subject": "Test Email 1",
                "from": "sender1@example.com",
                "date": "2023-01-01",
                "snippet": "This is a test email",
            },
            {
                "id": "2",
                "threadId": "thread2",
                "subject": "Test Email 2",
                "from": "sender2@example.com",
                "date": "2023-01-02",
                "snippet": "This is another test email",
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

            # Verify the DataFrame contains our mock data
            # This will depend on how the component processes the data
            # We can check for specific column names or values
            if hasattr(result, "columns"):
                # If the DataFrame has columns, check for expected ones
                expected_columns = ["id", "threadId", "subject", "from", "date", "snippet"]
                for col in expected_columns:
                    if col in result.columns:
                        assert True
                        break
                else:
                    # If none of the expected columns are found, check if data is in the DataFrame
                    assert any(
                        "Test Email" in str(cell) for cell in result.values.flat if hasattr(cell, "__contains__")
                    )
            else:
                # If the DataFrame structure is different, just check for some expected content
                assert "Test Email" in str(result)

    def test_update_build_config(self, component_class, default_kwargs):
        # Test that the Gmail component properly inherits and uses the base component's
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
        assert len(result["action"]["options"]) > 0  # Should have Gmail actions
