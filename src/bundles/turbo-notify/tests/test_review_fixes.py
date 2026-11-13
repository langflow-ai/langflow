"""Regression tests for the review comments: https, idempotency, delivery hints, 2xx, media hosts, limits, text.

The network is the in-memory transport from ``conftest.py``; keys and phone numbers are fabricated.
"""

from __future__ import annotations

import httpx
import pytest
from conftest import GROUP_ID, MESSAGE_ID, PHONE, build
from lfx_turbo_notify import (
    TurboNotifyGetMessagesComponent,
    TurboNotifyGetMessageStatusComponent,
    TurboNotifyListGroupsComponent,
    TurboNotifyReplyComponent,
    TurboNotifySendMediaComponent,
    TurboNotifySendTextComponent,
)
from lfx_turbo_notify import _validation as check
from lfx_turbo_notify._client import TurboNotifyError, normalize_base_url

ACCEPTED = {"message_id": MESSAGE_ID, "status": {"state": "pending", "at": "2026-11-12T10:00:00Z", "error": None}}


async def send_text(**inputs):
    return await build(TurboNotifySendTextComponent, phone=PHONE, text="hello", **inputs).turbo_notify_send_text()


class TestBaseUrlNeedsHttps:
    @pytest.mark.parametrize(
        "base_url",
        [
            "http://example.test",
            "http://api.turbonotify.com",
            "http://192.168.1.5:8080",
            "http://localhost.example.test",
            "http://127.0.0.1.example.test",
            "http://[2001:4860:4860::8888]",
        ],
    )
    async def test_plain_http_is_refused_for_remote_hosts(self, network, base_url):
        with pytest.raises(TurboNotifyError, match=r"^invalid_base_url: .*https") as caught:
            await send_text(base_url=base_url)
        assert caught.value.code == "invalid_base_url"
        assert network.requests == []

    @pytest.mark.parametrize(
        ("base_url", "origin"),
        [
            ("http://localhost:8000", "http://localhost:8000"),
            ("http://LOCALHOST:8000/", "http://LOCALHOST:8000"),
            ("http://127.0.0.1:8000/v1", "http://127.0.0.1:8000"),
            ("http://[::1]:8000", "http://[::1]:8000"),
            ("https://example.test", "https://example.test"),
        ],
    )
    def test_http_is_allowed_for_this_machine_only(self, base_url, origin):
        assert normalize_base_url(base_url) == origin

    async def test_local_http_reaches_the_transport(self, network):
        network.queue(202, ACCEPTED)
        await send_text(base_url="http://127.0.0.1:9000")
        assert str(network.last.url) == "http://127.0.0.1:9000/v1/numbers/main/messages"


SEND_COMPONENTS = [
    (TurboNotifySendTextComponent, {"phone": PHONE, "text": "hi"}, "turbo_notify_send_text"),
    (
        TurboNotifySendMediaComponent,
        {"phone": PHONE, "media_type": "image", "media_url": "https://cdn.example.test/f.jpg"},
        "turbo_notify_send_media",
    ),
    (TurboNotifyReplyComponent, {"message_id": MESSAGE_ID, "text": "hi"}, "turbo_notify_reply"),
]


class TestIdempotencyKey:
    @pytest.mark.parametrize("component_class", [case[0] for case in SEND_COMPONENTS])
    def test_input_is_optional_and_advanced(self, component_class):
        field = {item.name: item for item in component_class.inputs}["idempotency_key"]
        assert field.advanced is True
        assert not field.required
        assert type(field).__name__ == "MessageTextInput"

    @pytest.mark.parametrize("component_class", [TurboNotifyGetMessagesComponent, TurboNotifyListGroupsComponent])
    def test_reads_have_no_idempotency_key(self, component_class):
        assert "idempotency_key" not in {item.name for item in component_class.inputs}
        assert "idempotency_key" not in {item.name for item in TurboNotifyGetMessageStatusComponent.inputs}

    @pytest.mark.parametrize(("component_class", "inputs", "method"), SEND_COMPONENTS)
    async def test_key_goes_in_the_header(self, network, component_class, inputs, method):
        network.queue(202, ACCEPTED)
        await getattr(build(component_class, idempotency_key="order-4711", **inputs), method)()
        assert network.last.headers["idempotency-key"] == "order-4711"

    @pytest.mark.parametrize(("component_class", "inputs", "method"), SEND_COMPONENTS)
    @pytest.mark.parametrize("blank", [None, "", "   "])
    async def test_no_header_without_a_key(self, network, component_class, inputs, method, blank):
        network.queue(202, ACCEPTED)
        await getattr(build(component_class, idempotency_key=blank, **inputs), method)()
        assert "idempotency-key" not in network.last.headers

    @pytest.mark.parametrize(("component_class", "inputs", "method"), SEND_COMPONENTS)
    @pytest.mark.parametrize("key", ["a" * 255, "order 4711", "  order-4711  "])
    async def test_valid_keys(self, network, component_class, inputs, method, key):
        network.queue(202, ACCEPTED)
        await getattr(build(component_class, idempotency_key=key, **inputs), method)()
        assert network.last.headers["idempotency-key"] == key.strip()

    @pytest.mark.parametrize(("component_class", "inputs", "method"), SEND_COMPONENTS)
    @pytest.mark.parametrize("key", ["a" * 256, "a\tb", "a\nb", "a\x00b", "café", "a\x7fb"])
    async def test_invalid_keys_are_refused_before_any_request(self, network, component_class, inputs, method, key):
        component = build(component_class, idempotency_key=key, **inputs)
        with pytest.raises(TurboNotifyError, match=r"^invalid_idempotency_key:"):
            await getattr(component, method)()
        assert network.requests == []

    async def test_repeating_with_the_same_key_sends_the_same_header(self, network):
        network.queue(202, ACCEPTED)
        network.queue(202, ACCEPTED)
        await send_text(idempotency_key="order-4711")
        await send_text(idempotency_key="order-4711")
        assert [r.headers["idempotency-key"] for r in network.requests] == ["order-4711", "order-4711"]


class TestDeliveryHintOnTransportFailures:
    HINT = "may have gone out"

    @pytest.mark.parametrize(
        "error", [httpx.ReadError("reset"), httpx.WriteError("broken pipe"), httpx.RemoteProtocolError("closed")]
    )
    async def test_send_that_may_have_been_transmitted_carries_the_hint(self, network, error):
        network.queue_error(error)
        with pytest.raises(TurboNotifyError, match=self.HINT) as caught:
            await send_text()
        assert caught.value.code == "unreachable"

    async def test_read_timeout_on_a_send_carries_the_hint(self, network):
        network.queue_error(httpx.ReadTimeout("slow"))
        with pytest.raises(TurboNotifyError, match=self.HINT) as caught:
            await send_text()
        assert caught.value.code == "timeout"

    async def test_connect_error_failed_before_transmitting(self, network):
        network.queue_error(httpx.ConnectError("refused"))
        with pytest.raises(TurboNotifyError) as caught:
            await send_text()
        assert caught.value.code == "unreachable"
        assert self.HINT not in str(caught.value)

    async def test_connect_timeout_failed_before_transmitting(self, network):
        network.queue_error(httpx.ConnectTimeout("no route"))
        with pytest.raises(TurboNotifyError) as caught:
            await send_text()
        assert caught.value.code == "timeout"
        assert self.HINT not in str(caught.value)

    async def test_reads_never_carry_the_hint(self, network):
        network.queue_error(httpx.ReadError("reset"))
        component = build(TurboNotifyGetMessageStatusComponent, message_id=MESSAGE_ID)
        with pytest.raises(TurboNotifyError) as caught:
            await component.turbo_notify_get_message_status()
        assert self.HINT not in str(caught.value)


class TestOnly2xxIsSuccess:
    @pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
    async def test_redirects_are_errors_and_not_followed(self, network, status):
        network.queue(status, headers={"Location": "https://elsewhere.test/v1/numbers/main/messages"})
        with pytest.raises(TurboNotifyError, match=rf"^http_{status}: .*redirect") as caught:
            await send_text()
        assert caught.value.status == status
        assert len(network.requests) == 1

    async def test_redirect_with_a_json_body_is_still_an_error(self, network):
        network.queue(302, {"message_id": MESSAGE_ID})
        with pytest.raises(TurboNotifyError, match=r"^http_302:"):
            await send_text()

    async def test_not_modified_on_a_read_is_an_error(self, network):
        network.queue(304)
        component = build(TurboNotifyGetMessageStatusComponent, message_id=MESSAGE_ID)
        with pytest.raises(TurboNotifyError, match=r"^http_304:"):
            await component.turbo_notify_get_message_status()

    @pytest.mark.parametrize("status", [200, 201, 202])
    async def test_2xx_with_a_json_object_succeeds(self, network, status):
        network.queue(status, ACCEPTED)
        result = await send_text()
        assert result.data == ACCEPTED


class TestMediaUrlMustBePublic:
    @staticmethod
    def media(url):
        return build(TurboNotifySendMediaComponent, phone=PHONE, media_type="image", media_url=url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/f.jpg",
            "https://LOCALHOST:8443/f.jpg",
            "https://localhost./f.jpg",
            "https://files.localhost/f.jpg",
            "http://127.0.0.1/f.jpg",
            "http://127.1/f.jpg",
            "http://2130706433/f.jpg",
            "http://0x7f.0.0.1/f.jpg",
            "http://0.0.0.0/f.jpg",
            "https://10.0.0.5/f.jpg",
            "https://172.16.0.1/f.jpg",
            "https://192.168.1.10/f.jpg",
            "https://169.254.169.254/latest/meta-data",
            "https://100.64.0.1/f.jpg",
            "http://[::1]/f.jpg",
            "http://[::]/f.jpg",
            "http://[fe80::1]/f.jpg",
            "http://[fc00::1]/f.jpg",
            "http://[::ffff:127.0.0.1]/f.jpg",
            "http://[::ffff:10.0.0.1]/f.jpg",
        ],
    )
    async def test_local_private_and_unspecified_hosts_are_refused(self, network, url):
        with pytest.raises(TurboNotifyError, match=r"^invalid_media_url: .*(local|private)"):
            await self.media(url).turbo_notify_send_media()
        assert network.requests == []

    @pytest.mark.parametrize(
        "url",
        [
            "https://cdn.example.test/f.jpg",
            "https://8.8.8.8/f.jpg",
            "http://[2001:4860:4860::8888]/f.jpg",
            "https://localhost.example.test/f.jpg",
            "https://notlocalhost/f.jpg",
        ],
    )
    async def test_public_hosts_pass(self, network, url):
        network.queue(202, ACCEPTED)
        await self.media(url).turbo_notify_send_media()
        assert network.last_json["content"]["image_url"] == url

    def test_docstring_states_what_is_not_covered(self):
        doc = check.http_url.__doc__ or ""
        assert "DNS" in doc
        assert "resolve" in doc


class TestPageSizeRejectsNonFiniteNumbers:
    BAD = [float("nan"), float("inf"), float("-inf"), "nan", "NaN", "inf", "-inf", "Infinity", "1e999", 10**400]

    @pytest.mark.parametrize("value", BAD)
    def test_page_size(self, value):
        with pytest.raises(TurboNotifyError, match=r"^invalid_limit:"):
            check.page_size(value, default=20)

    @pytest.mark.parametrize("value", BAD)
    async def test_get_messages(self, network, value):
        with pytest.raises(TurboNotifyError, match=r"^invalid_limit:"):
            await build(TurboNotifyGetMessagesComponent, limit=value).turbo_notify_get_messages()
        assert network.requests == []

    @pytest.mark.parametrize("value", BAD)
    async def test_list_groups(self, network, value):
        with pytest.raises(TurboNotifyError, match=r"^invalid_limit:"):
            await build(TurboNotifyListGroupsComponent, limit=value).turbo_notify_list_groups()
        assert network.requests == []

    @pytest.mark.parametrize(("value", "expected"), [(1, 1), ("200", 200), (50.0, 50), (None, 20), ("", 20)])
    def test_valid_values_still_pass(self, value, expected):
        assert check.page_size(value, default=20) == expected


class TestTextIsSentAsWritten:
    async def test_send_text_keeps_the_original(self, network):
        network.queue(202, ACCEPTED)
        text = "  Hello,\n  world \n"
        await build(TurboNotifySendTextComponent, phone=PHONE, text=text).turbo_notify_send_text()
        assert network.last_json["content"]["text"] == text

    async def test_reply_keeps_the_original(self, network):
        network.queue(202, ACCEPTED)
        text = "\tOn my way  "
        await build(TurboNotifyReplyComponent, message_id=MESSAGE_ID, text=text).turbo_notify_reply()
        assert network.last_json["content"]["text"] == text

    async def test_caption_keeps_the_original(self, network):
        network.queue(202, ACCEPTED)
        component = build(
            TurboNotifySendMediaComponent,
            group_id=GROUP_ID,
            media_type="image",
            media_url="https://cdn.example.test/f.jpg",
            caption="  Look at this  ",
        )
        await component.turbo_notify_send_media()
        assert network.last_json["content"]["caption"] == "  Look at this  "

    async def test_file_name_is_still_trimmed(self, network):
        network.queue(202, ACCEPTED)
        component = build(
            TurboNotifySendMediaComponent,
            phone=PHONE,
            media_type="document",
            media_url="https://cdn.example.test/f.pdf",
            filename="  Invoice.pdf ",
        )
        await component.turbo_notify_send_media()
        assert network.last_json["content"]["filename"] == "Invoice.pdf"

    @pytest.mark.parametrize("text", ["", " ", "\n\t  \n"])
    async def test_blank_text_is_still_refused(self, network, text):
        with pytest.raises(TurboNotifyError, match=r"^invalid_text:"):
            await build(TurboNotifySendTextComponent, phone=PHONE, text=text).turbo_notify_send_text()
        assert network.requests == []

    @pytest.mark.parametrize("blank_caption", ["", "   ", "\n"])
    async def test_blank_caption_is_left_out(self, network, blank_caption):
        network.queue(202, ACCEPTED)
        component = build(
            TurboNotifySendMediaComponent,
            phone=PHONE,
            media_type="image",
            media_url="https://cdn.example.test/f.jpg",
            caption=blank_caption,
        )
        await component.turbo_notify_send_media()
        assert "caption" not in network.last_json["content"]

    async def test_limit_counts_what_is_sent(self, network):
        with pytest.raises(TurboNotifyError, match=r"^invalid_text: .*4098 characters"):
            await build(TurboNotifySendTextComponent, phone=PHONE, text="x" * 4096 + "  ").turbo_notify_send_text()
        assert network.requests == []

    async def test_text_of_exactly_the_limit_with_padding_is_accepted(self, network):
        network.queue(202, ACCEPTED)
        text = " " * 3 + "x" * 4090 + " " * 3
        await build(TurboNotifySendTextComponent, phone=PHONE, text=text).turbo_notify_send_text()
        assert network.last_json["content"]["text"] == text
