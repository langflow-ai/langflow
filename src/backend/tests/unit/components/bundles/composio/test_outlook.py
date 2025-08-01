from unittest.mock import MagicMock, patch

import pytest
from composio import Action

from lfx.components.composio.outlook_composio import ComposioOutlookAPIComponent
from lfx.schema.dataframe import DataFrame
from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    OUTLOOK_OUTLOOK_SEND_EMAIL = "OUTLOOK_OUTLOOK_SEND_EMAIL"
    OUTLOOK_OUTLOOK_LIST_MESSAGES = "OUTLOOK_OUTLOOK_LIST_MESSAGES"


class TestOutlookComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("lfx.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioOutlookAPIComponent

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
        assert component.display_name == "Outlook"
        assert component.app_name == "outlook"
        assert "OUTLOOK_OUTLOOK_SEND_EMAIL" in component._actions_data
        assert "OUTLOOK_OUTLOOK_LIST_MESSAGES" in component._actions_data

    def test_execute_action_send_email(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "OUTLOOK_OUTLOOK_SEND_EMAIL", MockAction.OUTLOOK_OUTLOOK_SEND_EMAIL)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Send Email"}]
        component.OUTLOOK_OUTLOOK_SEND_EMAIL_subject = "Test Subject"
        component.OUTLOOK_OUTLOOK_SEND_EMAIL_body = "Test Body"
        component.OUTLOOK_OUTLOOK_SEND_EMAIL_to_email = "test@example.com"

        component._actions_data = {
            "OUTLOOK_OUTLOOK_SEND_EMAIL": {
                "display_name": "Send Email",
                "action_fields": [
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_user_id",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_subject",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_body",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_to_email",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_to_name",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_cc_emails",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_bcc_emails",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_is_html",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_save_to_sent_items",
                    "OUTLOOK_OUTLOOK_SEND_EMAIL_attachment",
                ],
            },
        }

        result = component.execute_action()
        assert result == {"result": "mocked response"}

    def test_execute_action_fetch_emails(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "OUTLOOK_OUTLOOK_LIST_MESSAGES", MockAction.OUTLOOK_OUTLOOK_LIST_MESSAGES)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "List Messages"}]
        component.OUTLOOK_OUTLOOK_LIST_MESSAGES_folder = "Inbox"
        component.OUTLOOK_OUTLOOK_LIST_MESSAGES_top = 10

        component._actions_data = {
            "OUTLOOK_OUTLOOK_LIST_MESSAGES": {
                "display_name": "List Messages",
                "action_fields": [
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_user_id",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_folder",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_top",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_skip",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_is_read",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_importance",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_subject",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_gt",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_startswith",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_endswith",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_contains",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_ge",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_lt",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_le",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_from_address",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_has_attachments",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_body_preview_contains",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_sent_date_time_gt",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_sent_date_time_lt",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_categories",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_select",
                    "OUTLOOK_OUTLOOK_LIST_MESSAGES_orderby",
                ],
                "get_result_field": True,
                "result_field": "value",
            },
        }

        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {
            "successful": True,
            "data": {"response_data": {"value": [{"subject": "Test Email", "from": "test@example.com"}]}},
        }

        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            assert result == [{"subject": "Test Email", "from": "test@example.com"}]

    def test_execute_action_invalid_action(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Invalid Action"}]

        with pytest.raises(ValueError, match="Invalid action: Invalid Action"):
            component.execute_action()

    def test_as_dataframe(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "OUTLOOK_OUTLOOK_SEND_EMAIL", MockAction.OUTLOOK_OUTLOOK_SEND_EMAIL)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Send Email"}]
        component.OUTLOOK_OUTLOOK_SEND_EMAIL_subject = "Test Subject"
        component.OUTLOOK_OUTLOOK_SEND_EMAIL_body = "Test Body"
        component.OUTLOOK_OUTLOOK_SEND_EMAIL_to_email = "test@example.com"

        mock_emails = [
            {
                "message": "Email sent successfully.",
            }
        ]
        with patch.object(component, "execute_action", return_value=mock_emails):
            result = component.as_dataframe()

            assert isinstance(result, DataFrame)
            assert not result.empty
            data_str = str(result)
            assert "Email sent successfully." in data_str

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
