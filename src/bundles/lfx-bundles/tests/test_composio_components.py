"""Unit tests for Composio components cloud validation."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")

from lfx.base.composio.composio_base import ComposioBaseComponent
from lfx.base.composio.safe_provider import SafeLangchainProvider, _drop_blank_optional_arguments, _is_blank_value
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx_bundles.composio.composio_api import ComposioAPIComponent
from lfx_bundles.composio.outlook_composio import ComposioOutlookAPIComponent


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


@pytest.mark.unit
class TestIsBlankValue:
    """Unit coverage for the leaf-level blank check used to filter LLM-supplied tool arguments."""

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            [],
            (),
            set(),
            {},
            {"name": "", "data": ""},
            {"nested": {"a": "", "b": None}},
        ],
    )
    def test_blank_values(self, value):
        assert _is_blank_value(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "test",
            0,
            False,
            ["item"],
            {"name": "file.txt", "data": ""},
        ],
    )
    def test_non_blank_values(self, value):
        assert _is_blank_value(value) is False


@pytest.mark.unit
class TestDropBlankOptionalArguments:
    """Unit coverage for stripping blank optional arguments before they reach Composio."""

    INPUT_PARAMETERS = {
        "type": "object",
        "properties": {
            "recipient_email": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "attachment": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "data": {"type": "string"}},
            },
        },
        "required": ["recipient_email", "subject"],
    }

    def test_blank_optional_object_field_is_dropped(self):
        arguments = {
            "recipient_email": "me",
            "subject": "test",
            "attachment": {"name": "", "data": ""},
        }
        cleaned = _drop_blank_optional_arguments(arguments, self.INPUT_PARAMETERS)
        assert "attachment" not in cleaned
        assert cleaned == {"recipient_email": "me", "subject": "test"}

    def test_blank_optional_string_field_is_dropped(self):
        arguments = {"recipient_email": "me", "subject": "test", "body": ""}
        cleaned = _drop_blank_optional_arguments(arguments, self.INPUT_PARAMETERS)
        assert "body" not in cleaned

    def test_non_blank_optional_field_is_kept(self):
        arguments = {
            "recipient_email": "me",
            "subject": "test",
            "attachment": {"name": "report.pdf", "data": "base64data"},
        }
        cleaned = _drop_blank_optional_arguments(arguments, self.INPUT_PARAMETERS)
        assert cleaned["attachment"] == {"name": "report.pdf", "data": "base64data"}

    def test_blank_required_field_is_never_dropped(self):
        # Required fields are always forwarded so Composio's own validation still
        # sees (and can report on) a genuinely missing required value.
        arguments = {"recipient_email": "", "subject": "test"}
        cleaned = _drop_blank_optional_arguments(arguments, self.INPUT_PARAMETERS)
        assert cleaned == {"recipient_email": "", "subject": "test"}

    def test_non_dict_arguments_are_returned_unchanged(self):
        assert _drop_blank_optional_arguments("not-a-dict", self.INPUT_PARAMETERS) == "not-a-dict"

    def test_non_dict_input_parameters_are_returned_unchanged(self):
        arguments = {"subject": ""}
        assert _drop_blank_optional_arguments(arguments, None) == arguments


@pytest.mark.unit
class TestSafeLangchainProviderDropsBlankOptionalArguments:
    """Regression test for issue #14715.

    When Gmail is used as a Tool by an agent, the underlying LLM would routinely
    fill the optional consolidated "attachment" field with an empty placeholder
    (``{"name": "", "data": ""}``) even when no attachment was requested. Composio
    rejected that payload with "Tool input validation error". The direct
    ``execute_action`` component path already dropped blank optional values, but
    the agent Tool-calling path (``SafeLangchainProvider.wrap_tool``) forwarded the
    LLM's raw arguments untouched. This exercises the real wrap_tool wiring, not
    just the helper functions above.
    """

    def test_gmail_create_draft_tool_call_drops_blank_attachment_and_body(self):
        tool = SimpleNamespace(
            slug="GMAIL_CREATE_EMAIL_DRAFT",
            description="Create a Gmail draft",
            input_parameters={
                "type": "object",
                "title": "GmailCreateEmailDraftRequest",
                "properties": {
                    "user_id": {"type": "string"},
                    "recipient_email": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "is_html": {"type": "boolean"},
                    "attachment": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "data": {"type": "string"}},
                    },
                },
                "required": ["user_id", "recipient_email", "subject"],
            },
        )

        captured = {}

        def fake_execute_tool(slug, arguments):
            captured["slug"] = slug
            captured["arguments"] = arguments
            return {"successful": True, "data": {}, "error": None}

        structured_tool = SafeLangchainProvider().wrap_tool(tool, fake_execute_tool)

        # Exact payload the LLM produced in issue #14715.
        structured_tool.func(
            user_id="me",
            recipient_email="me",
            subject="test",
            body="",
            is_html=False,
            attachment={"name": "", "data": ""},
        )

        assert captured["slug"] == "GMAIL_CREATE_EMAIL_DRAFT"
        assert captured["arguments"] == {
            "user_id": "me",
            "recipient_email": "me",
            "subject": "test",
            "is_html": False,
        }

    def test_required_blank_field_still_reaches_execute_tool(self):
        tool = SimpleNamespace(
            slug="GMAIL_SEND_EMAIL",
            description="Send a Gmail email",
            input_parameters={
                "type": "object",
                "title": "GmailSendEmailRequest",
                "properties": {"recipient_email": {"type": "string"}},
                "required": ["recipient_email"],
            },
        )

        captured = {}

        def fake_execute_tool(slug, arguments):  # noqa: ARG001 - signature must match AgenticProviderExecuteFn
            captured["arguments"] = arguments
            return {"successful": False, "data": None, "error": "missing recipient"}

        structured_tool = SafeLangchainProvider().wrap_tool(tool, fake_execute_tool)
        structured_tool.func(recipient_email="")

        assert captured["arguments"] == {"recipient_email": ""}
