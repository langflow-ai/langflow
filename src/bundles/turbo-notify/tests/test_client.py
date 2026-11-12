"""Transport behavior shared by all components: URL, auth, errors."""

from __future__ import annotations

import httpx
import pytest
from conftest import API_KEY, MESSAGE_ID, PHONE, build
from lfx_turbo_notify import TurboNotifyGetMessageStatusComponent, TurboNotifySendTextComponent
from lfx_turbo_notify._client import TurboNotifyError, normalize_base_url


async def send(**inputs):
    component = build(TurboNotifySendTextComponent, phone=PHONE, text="hello", **inputs)
    return await component.turbo_notify_send_text()


class TestRequestShape:
    async def test_sends_bearer_key_and_json_to_the_default_origin(self, network):
        network.queue(202, {"message_id": MESSAGE_ID, "status": {"state": "pending"}})
        await send()
        request = network.last
        assert request.method == "POST"
        assert str(request.url) == "https://api.turbonotify.com/v1/numbers/main/messages"
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["user-agent"] == "langflow-turbo-notify-bundle"

    @pytest.mark.parametrize(
        "base_url",
        ["https://example.test", "https://example.test/", "https://example.test/v1", "https://example.test/v1/"],
    )
    async def test_base_url_is_normalized(self, network, base_url):
        network.queue(202, {"message_id": MESSAGE_ID})
        await send(base_url=base_url)
        assert str(network.last.url) == "https://example.test/v1/numbers/main/messages"

    async def test_empty_base_url_falls_back_to_the_default(self, network):
        network.queue(202, {"message_id": MESSAGE_ID})
        await send(base_url="")
        assert network.last.url.host == "api.turbonotify.com"

    @pytest.mark.parametrize(
        "alias",
        ["vendas-sp", "num_" + "0a1b2c3d4e5f6071" * 2],
    )
    async def test_number_alias_goes_in_the_path(self, network, alias):
        network.queue(202, {"message_id": MESSAGE_ID})
        await send(number_alias=alias)
        assert network.last.url.path == f"/v1/numbers/{alias}/messages"

    async def test_number_alias_is_percent_encoded(self, network):
        network.queue(202, {"message_id": MESSAGE_ID})
        await send(number_alias="a/b?c")
        assert network.last.url.raw_path.decode() == "/v1/numbers/a%2Fb%3Fc/messages"

    async def test_empty_number_alias_means_main(self, network):
        network.queue(202, {"message_id": MESSAGE_ID})
        await send(number_alias="  ")
        assert network.last.url.path == "/v1/numbers/main/messages"

    async def test_redirects_are_not_followed(self):
        client = _make_client_for_redirect_check()
        assert client.follow_redirects is False


def _make_client_for_redirect_check() -> httpx.AsyncClient:
    from lfx_turbo_notify._client import make_http_client

    return make_http_client(5.0)


class TestInputsRefusedBeforeAnyRequest:
    @pytest.mark.parametrize("key", ["", "   ", None])
    async def test_missing_api_key(self, network, key):
        component = TurboNotifySendTextComponent(api_key=key, phone=PHONE, text="hello")
        with pytest.raises(TurboNotifyError, match=r"^missing_api_key:"):
            await component.turbo_notify_send_text()
        assert network.requests == []

    @pytest.mark.parametrize("key", ["two words", "tab\tkey", "line\nbreak"])
    async def test_api_key_that_cannot_be_a_header_value(self, network, key):
        component = TurboNotifySendTextComponent(api_key=key, phone=PHONE, text="hello")
        with pytest.raises(TurboNotifyError, match=r"^invalid_api_key:"):
            await component.turbo_notify_send_text()
        assert network.requests == []

    @pytest.mark.parametrize(
        "base_url",
        ["ftp://example.test", "example.test", "https://user:pw@example.test", "https://example.test?x=1", "https://"],
    )
    async def test_unusable_base_url(self, network, base_url):
        with pytest.raises(TurboNotifyError, match=r"^invalid_base_url:"):
            await send(base_url=base_url)
        assert network.requests == []

    def test_normalize_base_url_default(self):
        assert normalize_base_url(None) == "https://api.turbonotify.com"


class TestApiErrors:
    async def test_error_code_comes_first_then_the_description(self, network):
        network.queue(404, {"error": "number_not_found", "message": "No number matches that alias."})
        with pytest.raises(TurboNotifyError) as caught:
            await send()
        assert str(caught.value) == "number_not_found: No number matches that alias."
        assert caught.value.code == "number_not_found"
        assert caught.value.status == 404

    async def test_insufficient_scope_names_the_required_scope(self, network):
        network.queue(
            403,
            {"error": "insufficient_scope", "message": "Forbidden.", "required_scope": "messages:send"},
        )
        with pytest.raises(TurboNotifyError) as caught:
            await send()
        assert str(caught.value).startswith("insufficient_scope: Forbidden.")
        assert "messages:send" in str(caught.value)

    async def test_rate_limit_carries_retry_after(self, network):
        network.queue(
            429,
            {"error": "send_rate_spacing", "message": "Sent too fast."},
            headers={"Retry-After": "7"},
        )
        with pytest.raises(TurboNotifyError) as caught:
            await send()
        assert str(caught.value).startswith("send_rate_spacing: Sent too fast.")
        assert "Retry after 7 seconds." in str(caught.value)
        assert caught.value.retry_after == 7

    async def test_rate_limit_without_retry_after_header(self, network):
        network.queue(429, {"error": "rate_limit_exceeded", "message": "Slow down."})
        with pytest.raises(TurboNotifyError, match=r"Wait a moment and try again"):
            await send()

    async def test_validation_error_lists_the_rejected_fields(self, network):
        network.queue(
            422,
            {
                "error": "validation_error",
                "message": "Invalid request.",
                "details": {"errors": [{"loc": ["body", "content", "text"], "msg": "too long"}]},
            },
        )
        with pytest.raises(TurboNotifyError, match=r"^validation_error: content\.text: too long"):
            await send()

    async def test_hint_follows_the_message(self, network):
        network.queue(409, {"error": "number_not_connected", "message": "Not connected.", "hint": "Reconnect it."})
        with pytest.raises(TurboNotifyError, match=r"^number_not_connected: Not connected. Reconnect it."):
            await send()

    async def test_nested_error_object(self, network):
        network.queue(400, {"error": {"code": "invalid_recipient", "message": "Bad recipient."}})
        with pytest.raises(TurboNotifyError, match=r"^invalid_recipient: Bad recipient."):
            await send()

    async def test_server_failure_on_a_send_warns_the_message_may_have_gone_out(self, network):
        network.queue(502, text="<html>Bad gateway</html>")
        with pytest.raises(TurboNotifyError, match=r"^http_502: .*may have gone out") as caught:
            await send()
        assert caught.value.status == 502

    async def test_server_failure_on_a_read_has_no_send_warning(self, network):
        network.queue(503, {"error": "service_unavailable", "message": "Try later."})
        component = build(TurboNotifyGetMessageStatusComponent, message_id=MESSAGE_ID)
        with pytest.raises(TurboNotifyError) as caught:
            await component.turbo_notify_get_message_status()
        assert "may have gone out" not in str(caught.value)

    async def test_timeout(self, network):
        network.queue_error(httpx.ReadTimeout("slow"))
        with pytest.raises(TurboNotifyError, match=r"^timeout: .*within 60 seconds.*Get Messages"):
            await send()

    async def test_unreachable(self, network):
        network.queue_error(httpx.ConnectError("refused"))
        with pytest.raises(TurboNotifyError, match=r"^unreachable: Could not reach Turbo Notify"):
            await send()

    async def test_success_that_is_not_a_json_object(self, network):
        network.queue(200, ["not", "an", "object"])
        with pytest.raises(TurboNotifyError, match=r"^unexpected_response:"):
            await send()

    async def test_the_api_key_never_appears_in_an_error(self, network):
        network.queue(401, {"error": "not_authenticated", "message": "The API key was not accepted."})
        with pytest.raises(TurboNotifyError) as caught:
            await send()
        assert API_KEY not in str(caught.value)
        assert caught.value.code == "not_authenticated"
