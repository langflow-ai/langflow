"""Request shape, validation and results of the six Turbo Notify components.

The network is replaced by an in-memory transport (see ``conftest.py``), so no test
reaches the real API. The phone numbers and the API key are fabricated.

The in-tree component tests inherit ``tests.base.ComponentTestBase*``, which is not
importable inside a standalone bundle; these classes carry the same checks as plain
pytest classes.
"""

from __future__ import annotations

import pytest
from conftest import CONTACT_ID, GROUP_ID, MESSAGE_ID, OTHER_MESSAGE_ID, PHONE, build
from lfx.schema.data import Data
from lfx_turbo_notify import (
    TurboNotifyGetMessagesComponent,
    TurboNotifyGetMessageStatusComponent,
    TurboNotifyListGroupsComponent,
    TurboNotifyReplyComponent,
    TurboNotifySendMediaComponent,
    TurboNotifySendTextComponent,
)
from lfx_turbo_notify._client import TurboNotifyError

ACCEPTED = {"message_id": MESSAGE_ID, "status": {"state": "pending", "at": "2026-11-12T10:00:00Z", "error": None}}


class TestBundleContract:
    """Class names, tool names and icons are identifiers in saved flows: they must not change."""

    COMPONENTS = {
        TurboNotifySendTextComponent: ("turbo_notify_send_text", "Turbo Notify: Send Text"),
        TurboNotifySendMediaComponent: ("turbo_notify_send_media", "Turbo Notify: Send Media"),
        TurboNotifyReplyComponent: ("turbo_notify_reply", "Turbo Notify: Reply"),
        TurboNotifyGetMessagesComponent: ("turbo_notify_get_messages", "Turbo Notify: Get Messages"),
        TurboNotifyGetMessageStatusComponent: ("turbo_notify_get_message_status", "Turbo Notify: Get Message Status"),
        TurboNotifyListGroupsComponent: ("turbo_notify_list_groups", "Turbo Notify: List Groups"),
    }

    @pytest.mark.parametrize(("component_class", "expected"), COMPONENTS.items())
    def test_names_and_icon(self, component_class, expected):
        method, display_name = expected
        assert component_class.display_name == display_name
        assert component_class.icon == "TurboNotify"
        assert [output.method for output in component_class.outputs] == [method]
        assert callable(getattr(component_class, method))

    @pytest.mark.parametrize("component_class", COMPONENTS)
    def test_api_key_is_a_secret_and_base_url_is_advanced(self, component_class):
        inputs = {item.name: item for item in component_class.inputs}
        assert type(inputs["api_key"]).__name__ == "SecretStrInput"
        assert inputs["api_key"].password is True
        assert inputs["api_key"].required is True
        assert not getattr(inputs["api_key"], "tool_mode", False)
        assert inputs["number_alias"].value == "main"
        assert inputs["base_url"].advanced is True
        assert inputs["base_url"].value == "https://api.turbonotify.com"

    @pytest.mark.parametrize("component_class", COMPONENTS)
    def test_connection_inputs_stay_out_of_the_tool_arguments(self, component_class):
        configured = {"api_key", "number_alias", "base_url"}
        tool_inputs = {item.name for item in component_class.inputs if getattr(item, "tool_mode", False)}
        assert tool_inputs
        assert configured.isdisjoint(tool_inputs)


class TestSendText:
    async def test_sends_text_to_a_phone(self, network):
        network.queue(202, ACCEPTED)
        result = await build(TurboNotifySendTextComponent, phone=PHONE, text="Hello").turbo_notify_send_text()
        assert network.last.method == "POST"
        assert network.last.url.path == "/v1/numbers/main/messages"
        assert network.last.url.query == b""
        assert network.last_json == {"to": {"number": PHONE}, "content": {"text": "Hello"}}
        assert isinstance(result, Data)
        assert result.data == ACCEPTED

    @pytest.mark.parametrize(
        ("raw", "cleaned"),
        [
            ("+1 (202) 555-0123", "+12025550123"),
            ("  +12025550123  ", "+12025550123"),
            ("+44 20 7946 0958", "+442079460958"),
            ("+1234567", "+1234567"),
            ("+123456789012345", "+123456789012345"),
        ],
    )
    async def test_phone_is_cleaned(self, network, raw, cleaned):
        network.queue(202, ACCEPTED)
        await build(TurboNotifySendTextComponent, phone=raw, text="Hi").turbo_notify_send_text()
        assert network.last_json["to"] == {"number": cleaned}

    async def test_sends_to_a_contact(self, network):
        network.queue(202, ACCEPTED)
        await build(TurboNotifySendTextComponent, contact_id=CONTACT_ID, text="Hi").turbo_notify_send_text()
        assert network.last_json["to"] == {"contact_id": CONTACT_ID}

    async def test_sends_to_a_group(self, network):
        network.queue(202, ACCEPTED)
        await build(TurboNotifySendTextComponent, group_id=GROUP_ID, text="Hi").turbo_notify_send_text()
        assert network.last_json["to"] == {"group_id": GROUP_ID}

    async def test_text_limits(self, network):
        network.queue(202, ACCEPTED)
        await build(TurboNotifySendTextComponent, phone=PHONE, text="x" * 4096).turbo_notify_send_text()
        assert len(network.last_json["content"]["text"]) == 4096

    @pytest.mark.parametrize(
        "phone",
        ["12025550123", "+0123456789", "+123456", "+1234567890123456", "+1202abc0123", "+1.202.555.0123", "call me"],
    )
    async def test_bad_phone_is_refused(self, network, phone):
        component = build(TurboNotifySendTextComponent, phone=phone, text="Hi")
        with pytest.raises(TurboNotifyError, match=r"^invalid_phone_number:"):
            await component.turbo_notify_send_text()
        assert network.requests == []

    @pytest.mark.parametrize(
        "recipients",
        [
            {"phone": PHONE, "contact_id": CONTACT_ID},
            {"phone": PHONE, "group_id": GROUP_ID},
            {"contact_id": CONTACT_ID, "group_id": GROUP_ID},
            {"phone": PHONE, "contact_id": CONTACT_ID, "group_id": GROUP_ID},
        ],
    )
    async def test_two_recipients_are_refused(self, network, recipients):
        component = build(TurboNotifySendTextComponent, text="Hi", **recipients)
        with pytest.raises(TurboNotifyError, match=r"^invalid_recipient: .*only one"):
            await component.turbo_notify_send_text()
        assert network.requests == []

    async def test_no_recipient_is_refused(self, network):
        with pytest.raises(TurboNotifyError, match=r"^invalid_recipient: Choose who receives"):
            await build(TurboNotifySendTextComponent, text="Hi").turbo_notify_send_text()
        assert network.requests == []

    @pytest.mark.parametrize(
        ("field", "value", "code"),
        [
            ("contact_id", "ct_123", "invalid_contact_id"),
            ("contact_id", "CT_" + "a" * 32, "invalid_contact_id"),
            ("contact_id", GROUP_ID, "invalid_contact_id"),
            ("group_id", "grp_" + "g" * 32, "invalid_group_id"),
            ("group_id", CONTACT_ID, "invalid_group_id"),
        ],
    )
    async def test_bad_ids_are_refused(self, network, field, value, code):
        component = build(TurboNotifySendTextComponent, text="Hi", **{field: value})
        with pytest.raises(TurboNotifyError, match=rf"^{code}:"):
            await component.turbo_notify_send_text()
        assert network.requests == []

    @pytest.mark.parametrize("text", ["", "   \n", "x" * 4097])
    async def test_bad_text_is_refused(self, network, text):
        component = build(TurboNotifySendTextComponent, phone=PHONE, text=text)
        with pytest.raises(TurboNotifyError, match=r"^invalid_text:"):
            await component.turbo_notify_send_text()
        assert network.requests == []

    async def test_api_refusal_is_raised(self, network):
        network.queue(402, {"error": "feature_not_available", "message": "Groups need a higher plan."})
        component = build(TurboNotifySendTextComponent, group_id=GROUP_ID, text="Hi")
        with pytest.raises(TurboNotifyError, match=r"^feature_not_available: Groups need a higher plan."):
            await component.turbo_notify_send_text()


class TestSendMedia:
    @pytest.mark.parametrize("media_type", ["image", "video", "audio", "document", "sticker"])
    async def test_each_media_type_uses_its_url_field(self, network, media_type):
        network.queue(202, ACCEPTED)
        component = build(
            TurboNotifySendMediaComponent, phone=PHONE, media_type=media_type, media_url="https://cdn.example.test/f"
        )
        result = await component.turbo_notify_send_media()
        assert network.last.method == "POST"
        assert network.last.url.path == "/v1/numbers/main/messages"
        assert network.last_json == {
            "to": {"number": PHONE},
            "content": {f"{media_type}_url": "https://cdn.example.test/f"},
        }
        assert result.data == ACCEPTED

    @pytest.mark.parametrize("media_type", ["image", "video", "document"])
    async def test_caption_goes_with_image_video_and_document(self, network, media_type):
        network.queue(202, ACCEPTED)
        component = build(
            TurboNotifySendMediaComponent,
            group_id=GROUP_ID,
            media_type=media_type,
            media_url="http://cdn.example.test/f",
            caption="  Look at this  ",
        )
        await component.turbo_notify_send_media()
        assert network.last_json["content"] == {
            f"{media_type}_url": "http://cdn.example.test/f",
            "caption": "  Look at this  ",
        }

    async def test_filename_goes_with_a_document(self, network):
        network.queue(202, ACCEPTED)
        component = build(
            TurboNotifySendMediaComponent,
            contact_id=CONTACT_ID,
            media_type="document",
            media_url="https://cdn.example.test/invoice.pdf",
            filename="Invoice.pdf",
            caption="Your invoice",
        )
        await component.turbo_notify_send_media()
        assert network.last_json == {
            "to": {"contact_id": CONTACT_ID},
            "content": {
                "document_url": "https://cdn.example.test/invoice.pdf",
                "caption": "Your invoice",
                "filename": "Invoice.pdf",
            },
        }

    async def test_caption_limit(self, network):
        network.queue(202, ACCEPTED)
        component = build(
            TurboNotifySendMediaComponent,
            phone=PHONE,
            media_type="image",
            media_url="https://cdn.example.test/f.jpg",
            caption="c" * 1024,
        )
        await component.turbo_notify_send_media()
        assert len(network.last_json["content"]["caption"]) == 1024

    @pytest.mark.parametrize(
        "media_url",
        [
            "",
            "ftp://cdn.example.test/f.jpg",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "cdn.example.test/f.jpg",
            "https://",
            "https://cdn.example.test/a file.jpg",
            "https://cdn.example.test/" + "a" * 2100,
        ],
    )
    async def test_media_url_must_be_http_or_https(self, network, media_url):
        component = build(TurboNotifySendMediaComponent, phone=PHONE, media_type="image", media_url=media_url)
        with pytest.raises(TurboNotifyError, match=r"^invalid_media_url:"):
            await component.turbo_notify_send_media()
        assert network.requests == []

    async def test_unknown_media_type_is_refused(self, network):
        component = build(
            TurboNotifySendMediaComponent, phone=PHONE, media_type="gif", media_url="https://cdn.example.test/f"
        )
        with pytest.raises(TurboNotifyError, match=r"^invalid_media_type:"):
            await component.turbo_notify_send_media()
        assert network.requests == []

    @pytest.mark.parametrize("media_type", ["audio", "sticker"])
    async def test_audio_and_sticker_take_no_caption(self, network, media_type):
        component = build(
            TurboNotifySendMediaComponent,
            phone=PHONE,
            media_type=media_type,
            media_url="https://cdn.example.test/f",
            caption="no",
        )
        with pytest.raises(TurboNotifyError, match=r"^invalid_caption: .*takes no caption"):
            await component.turbo_notify_send_media()
        assert network.requests == []

    async def test_only_a_document_takes_a_filename(self, network):
        component = build(
            TurboNotifySendMediaComponent,
            phone=PHONE,
            media_type="image",
            media_url="https://cdn.example.test/f.jpg",
            filename="f.jpg",
        )
        with pytest.raises(TurboNotifyError, match=r"^invalid_filename:"):
            await component.turbo_notify_send_media()
        assert network.requests == []

    async def test_caption_over_the_limit_is_refused(self, network):
        component = build(
            TurboNotifySendMediaComponent,
            phone=PHONE,
            media_type="image",
            media_url="https://cdn.example.test/f.jpg",
            caption="c" * 1025,
        )
        with pytest.raises(TurboNotifyError, match=r"^invalid_caption:"):
            await component.turbo_notify_send_media()
        assert network.requests == []

    async def test_one_recipient_is_still_required(self, network):
        component = build(TurboNotifySendMediaComponent, media_type="image", media_url="https://cdn.example.test/f")
        with pytest.raises(TurboNotifyError, match=r"^invalid_recipient:"):
            await component.turbo_notify_send_media()
        assert network.requests == []

    async def test_api_error_path(self, network):
        network.queue(422, {"error": "media_not_supported", "message": "That file type is not supported."})
        component = build(
            TurboNotifySendMediaComponent, phone=PHONE, media_type="sticker", media_url="https://cdn.example.test/f"
        )
        with pytest.raises(TurboNotifyError, match=r"^media_not_supported: That file type is not supported."):
            await component.turbo_notify_send_media()


class TestReply:
    async def test_replies_to_a_message(self, network):
        network.queue(202, ACCEPTED)
        component = build(TurboNotifyReplyComponent, message_id=OTHER_MESSAGE_ID, text="On my way")
        result = await component.turbo_notify_reply()
        assert network.last.method == "POST"
        assert network.last.url.path == f"/v1/numbers/main/messages/{OTHER_MESSAGE_ID}/reply"
        assert network.last_json == {"content": {"text": "On my way"}}
        assert result.data == ACCEPTED

    async def test_uses_the_configured_number(self, network):
        network.queue(202, ACCEPTED)
        component = build(TurboNotifyReplyComponent, number_alias="vendas-sp", message_id=MESSAGE_ID, text="Ok")
        await component.turbo_notify_reply()
        assert network.last.url.path == f"/v1/numbers/vendas-sp/messages/{MESSAGE_ID}/reply"

    @pytest.mark.parametrize(
        "message_id", ["", "msg_123", "MSG_" + "a" * 32, "evt_" + "a" * 32, MESSAGE_ID + "0", MESSAGE_ID.upper()]
    )
    async def test_bad_message_id_is_refused(self, network, message_id):
        component = build(TurboNotifyReplyComponent, message_id=message_id, text="Ok")
        with pytest.raises(TurboNotifyError, match=r"^invalid_message_id:"):
            await component.turbo_notify_reply()
        assert network.requests == []

    @pytest.mark.parametrize("text", ["", "  ", "x" * 4097])
    async def test_bad_text_is_refused(self, network, text):
        component = build(TurboNotifyReplyComponent, message_id=MESSAGE_ID, text=text)
        with pytest.raises(TurboNotifyError, match=r"^invalid_text:"):
            await component.turbo_notify_reply()
        assert network.requests == []

    async def test_api_error_path(self, network):
        network.queue(422, {"error": "message_not_replyable", "message": "The message was deleted."})
        component = build(TurboNotifyReplyComponent, message_id=MESSAGE_ID, text="Ok")
        with pytest.raises(TurboNotifyError, match=r"^message_not_replyable: The message was deleted."):
            await component.turbo_notify_reply()


PAGE = {
    "data": [
        {"id": MESSAGE_ID, "direction": "inbound", "status": {"state": "delivered"}},
        {"id": OTHER_MESSAGE_ID, "direction": "outbound", "status": {"state": "read"}},
    ],
    "cursor": "eyJpZCI6Im1zZ18wMSJ9",
    "has_more": True,
}


class TestGetMessages:
    async def test_reads_the_latest_messages_by_default(self, network):
        network.queue(200, PAGE)
        result = await build(TurboNotifyGetMessagesComponent).turbo_notify_get_messages()
        assert network.last.method == "GET"
        assert network.last.url.path == "/v1/numbers/main/messages"
        assert dict(network.last.url.params) == {"limit": "20"}
        assert network.last.content == b""
        assert result.data == {
            "messages": PAGE["data"],
            "has_more": True,
            "cursor": "eyJpZCI6Im1zZ18wMSJ9",
        }

    async def test_filters_and_cursor(self, network):
        network.queue(200, PAGE)
        component = build(
            TurboNotifyGetMessagesComponent,
            direction="outbound",
            contact_id=CONTACT_ID,
            group_id=GROUP_ID,
            limit=5,
            cursor="eyJpZCI6Im1zZ18wMSJ9",
        )
        await component.turbo_notify_get_messages()
        assert dict(network.last.url.params) == {
            "limit": "5",
            "direction": "outbound",
            "contact_id": CONTACT_ID,
            "group_id": GROUP_ID,
            "cursor": "eyJpZCI6Im1zZ18wMSJ9",
        }

    @pytest.mark.parametrize("direction", ["inbound", "outbound"])
    async def test_direction_filter(self, network, direction):
        network.queue(200, {"data": [], "cursor": None, "has_more": False})
        result = await build(TurboNotifyGetMessagesComponent, direction=direction).turbo_notify_get_messages()
        assert network.last.url.params["direction"] == direction
        assert result.data == {"messages": [], "has_more": False, "cursor": None}

    @pytest.mark.parametrize("limit", [1, 200, "50"])
    async def test_valid_limits(self, network, limit):
        network.queue(200, PAGE)
        await build(TurboNotifyGetMessagesComponent, limit=limit).turbo_notify_get_messages()
        assert network.last.url.params["limit"] == str(int(limit))

    @pytest.mark.parametrize("limit", [0, -1, 201, "many", 2.5, True])
    async def test_invalid_limits_are_refused(self, network, limit):
        with pytest.raises(TurboNotifyError, match=r"^invalid_limit:"):
            await build(TurboNotifyGetMessagesComponent, limit=limit).turbo_notify_get_messages()
        assert network.requests == []

    async def test_invalid_direction_is_refused(self, network):
        with pytest.raises(TurboNotifyError, match=r"^invalid_direction:"):
            await build(TurboNotifyGetMessagesComponent, direction="sideways").turbo_notify_get_messages()
        assert network.requests == []

    @pytest.mark.parametrize(
        ("field", "value", "code"),
        [("contact_id", "ct_zz", "invalid_contact_id"), ("group_id", "grp_zz", "invalid_group_id")],
    )
    async def test_invalid_filter_ids_are_refused(self, network, field, value, code):
        with pytest.raises(TurboNotifyError, match=rf"^{code}:"):
            await build(TurboNotifyGetMessagesComponent, **{field: value}).turbo_notify_get_messages()
        assert network.requests == []

    async def test_cursor_with_spaces_is_refused(self, network):
        with pytest.raises(TurboNotifyError, match=r"^invalid_cursor:"):
            await build(TurboNotifyGetMessagesComponent, cursor="a b").turbo_notify_get_messages()
        assert network.requests == []

    async def test_api_error_path(self, network):
        network.queue(403, {"error": "insufficient_scope", "message": "No.", "required_scope": "messages:read"})
        with pytest.raises(TurboNotifyError, match=r"^insufficient_scope: .*'messages:read' scope"):
            await build(TurboNotifyGetMessagesComponent).turbo_notify_get_messages()


class TestGetMessageStatus:
    async def test_returns_the_state_as_a_field(self, network):
        status = {"state": "delivered", "at": "2026-11-12T10:00:05Z", "error": None}
        network.queue(200, {"message_id": MESSAGE_ID, "status": status})
        result = await build(
            TurboNotifyGetMessageStatusComponent, message_id=MESSAGE_ID
        ).turbo_notify_get_message_status()
        assert network.last.method == "GET"
        assert network.last.url.path == f"/v1/numbers/main/messages/{MESSAGE_ID}/status"
        assert network.last.content == b""
        assert result.data == {
            "message_id": MESSAGE_ID,
            "state": "delivered",
            "at": "2026-11-12T10:00:05Z",
            "error": None,
            "status": status,
        }

    async def test_failed_state_carries_the_error(self, network):
        failure = {
            "code": "media_unreachable",
            "message": "The file could not be downloaded.",
            "hint": "Check the URL.",
        }
        network.queue(200, {"message_id": MESSAGE_ID, "status": {"state": "failed", "at": "t", "error": failure}})
        result = await build(
            TurboNotifyGetMessageStatusComponent, message_id=MESSAGE_ID
        ).turbo_notify_get_message_status()
        assert result.data["state"] == "failed"
        assert result.data["error"] == failure

    @pytest.mark.parametrize("message_id", ["", "msg_1", CONTACT_ID])
    async def test_bad_message_id_is_refused(self, network, message_id):
        component = build(TurboNotifyGetMessageStatusComponent, message_id=message_id)
        with pytest.raises(TurboNotifyError, match=r"^invalid_message_id:"):
            await component.turbo_notify_get_message_status()
        assert network.requests == []

    async def test_api_error_path(self, network):
        network.queue(404, {"error": "not_found", "message": "Nothing was found for that ID."})
        component = build(TurboNotifyGetMessageStatusComponent, message_id=MESSAGE_ID)
        with pytest.raises(TurboNotifyError, match=r"^not_found: Nothing was found for that ID."):
            await component.turbo_notify_get_message_status()


GROUPS = {
    "data": [{"id": GROUP_ID, "name": "Team", "is_active": True, "participants_count": 12}],
    "cursor": None,
    "has_more": False,
}


class TestListGroups:
    async def test_lists_the_groups(self, network):
        network.queue(200, GROUPS)
        result = await build(TurboNotifyListGroupsComponent).turbo_notify_list_groups()
        assert network.last.method == "GET"
        assert network.last.url.path == "/v1/numbers/main/groups"
        assert dict(network.last.url.params) == {"limit": "50"}
        assert result.data == {"groups": GROUPS["data"], "has_more": False, "cursor": None}

    async def test_filters(self, network):
        network.queue(200, GROUPS)
        component = build(TurboNotifyListGroupsComponent, group_name="Team", limit=10, include_left=True, cursor="abc")
        await component.turbo_notify_list_groups()
        assert dict(network.last.url.params) == {
            "limit": "10",
            "name": "Team",
            "include_left": "true",
            "cursor": "abc",
        }

    @pytest.mark.parametrize("limit", [0, 201, "x"])
    async def test_invalid_limit_is_refused(self, network, limit):
        with pytest.raises(TurboNotifyError, match=r"^invalid_limit:"):
            await build(TurboNotifyListGroupsComponent, limit=limit).turbo_notify_list_groups()
        assert network.requests == []

    async def test_api_error_path(self, network):
        network.queue(404, {"error": "number_not_found", "message": "No number matches that alias."})
        with pytest.raises(TurboNotifyError, match=r"^number_not_found:"):
            await build(TurboNotifyListGroupsComponent, number_alias="nope").turbo_notify_list_groups()


class TestToolMode:
    @pytest.mark.parametrize(
        ("component_class", "arguments"),
        [
            (TurboNotifySendTextComponent, {"phone", "contact_id", "group_id", "text"}),
            (
                TurboNotifySendMediaComponent,
                {"phone", "contact_id", "group_id", "media_type", "media_url", "caption", "filename"},
            ),
            (TurboNotifyReplyComponent, {"message_id", "text"}),
            (TurboNotifyGetMessagesComponent, {"direction", "contact_id", "group_id", "limit", "cursor"}),
            (TurboNotifyGetMessageStatusComponent, {"message_id"}),
            (TurboNotifyListGroupsComponent, {"group_name", "limit", "cursor"}),
        ],
    )
    async def test_tool_arguments_leave_the_connection_configured(self, component_class, arguments):
        [tool] = await build(component_class).to_toolkit()
        assert set(tool.args_schema.model_fields) == arguments

    async def test_tool_call_runs_the_request(self, network):
        network.queue(202, ACCEPTED)
        [tool] = await build(TurboNotifySendTextComponent).to_toolkit()
        assert tool.name == "turbo_notify_send_text"
        await tool.ainvoke({"phone": PHONE, "text": "From an agent"})
        assert network.last_json == {"to": {"number": PHONE}, "content": {"text": "From an agent"}}
