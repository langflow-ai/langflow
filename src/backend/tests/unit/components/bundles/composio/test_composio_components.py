"""Unit tests for Composio components cloud validation."""

import os
from unittest.mock import MagicMock, patch

import pytest
from lfx.base.composio.composio_base import ComposioBaseComponent
from lfx.components.composio.composio_api import ComposioAPIComponent
from lfx.components.composio.outlook_composio import ComposioOutlookAPIComponent
from lfx.schema.data import Data
from lfx.schema.message import Message


@pytest.mark.unit
class TestComposioCloudValidation:
    """Test Composio components cloud validation."""

    def test_composio_api_disabled_in_astra_cloud(self):
        """Test that ComposioAPI build_tool raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = ComposioAPIComponent(api_key="test-key")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.build_tool()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg

    def test_composio_base_execute_disabled_in_astra_cloud(self):
        """Test that ComposioBase execute_action raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "false"}):
            component = ComposioBaseComponent(api_key="test-key")

        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.execute_action()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg


def _make_component(action_key: str, fields: dict) -> ComposioOutlookAPIComponent:
    """Build a ComposioOutlookAPIComponent pre-wired with test data, bypassing real API calls."""
    with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "false"}):
        component = ComposioOutlookAPIComponent(api_key="test-key")

    component.entity_id = "default"
    component.action_button = [{"name": "Send Email"}]

    component._actions_data = {
        action_key: {
            "display_name": "Send Email",
            "action_fields": list(fields.keys()),
            "version": None,
        }
    }
    component._action_schemas = {
        action_key: {
            "input_parameters": {
                "type": "object",
                "properties": {k: {"type": "string"} for k in fields},
                "required": list(fields.keys()),
            }
        }
    }
    component._display_to_key_map = {"Send Email": action_key}
    component._key_to_display_map = {action_key: "Send Email"}

    for name, value in fields.items():
        setattr(component, name, value)

    return component


@pytest.mark.unit
class TestExecuteActionRichTypeCoercion:
    """Regression: Message and Data objects must be coerced to primitives before being passed to the Composio API.

    When a ChatInput node is wired to a str field (e.g. subject, body), Langflow
    stores a Message object in the component attribute.  execute_action previously
    forwarded the raw object to composio.tools.execute, which caused the API call
    to fail or send a stringified object instead of plain text.
    """

    ACTION_KEY = "OUTLOOK_SEND_EMAIL"

    def _run(self, fields: dict) -> dict:
        """Execute the action and return the captured arguments dict."""
        component = _make_component(self.ACTION_KEY, fields)

        captured = {}

        def fake_execute(**kwargs):
            captured.update(kwargs.get("arguments", {}))
            return {"successful": True, "data": {"message": "sent"}}

        mock_composio = MagicMock()
        mock_composio.tools.execute.side_effect = fake_execute

        with (
            patch.object(type(component), "_build_wrapper", return_value=mock_composio),
            patch.object(type(component), "_populate_actions_data"),
            patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "false"}),
        ):
            component.execute_action()

        return captured

    def test_message_coerced_to_text_for_str_field(self):
        args = self._run({"subject": Message(text="Hello world"), "body": "body text"})
        assert args["subject"] == "Hello world"

    def test_data_coerced_to_dict_for_object_field(self):
        payload = {"key": "value"}
        args = self._run({"subject": "hi", "body": Data(data=payload)})
        assert args["body"] == payload

    def test_plain_string_passed_through_unchanged(self):
        args = self._run({"subject": "plain subject", "body": "plain body"})
        assert args["subject"] == "plain subject"
        assert args["body"] == "plain body"

    def test_message_with_empty_text_is_skipped(self):
        args = self._run({"subject": Message(text=""), "body": "body text"})
        assert "subject" not in args

    def test_multiple_message_fields_all_coerced(self):
        args = self._run(
            {
                "subject": Message(text="Subject line"),
                "body": Message(text="Body content"),
            }
        )
        assert args["subject"] == "Subject line"
        assert args["body"] == "Body content"

    def test_none_field_is_skipped(self):
        args = self._run({"subject": "hi", "body": None})
        assert "body" not in args

    def test_message_coercion_happens_before_json_parse(self):
        # body contains JSON-like text — should be passed as a string (schema type is str)
        args = self._run({"subject": "hi", "body": Message(text='{"key": "val"}')})
        assert args["body"] == '{"key": "val"}'
