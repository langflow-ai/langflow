import json

import httpx
import pytest
import respx
from lfx_sendblue import SendblueComponent

TEST_SECRET = "test-secret"  # noqa: S105


@pytest.mark.asyncio
@respx.mock
async def test_send_requires_explicit_enable_and_uses_fixed_destination():
    c = SendblueComponent(
        api_key="test-key",
        api_secret=TEST_SECRET,
        operation="Send Message",
        number="+15555550123",
        content="Hello",
        from_number="+15555550124",
    )
    route = respx.post("https://api.sendblue.co/api/send-message").mock(
        return_value=httpx.Response(200, json={"message_handle": "test"})
    )
    with pytest.raises(ValueError, match="Enable Allow Sending"):
        await c.build_result()
    assert route.call_count == 0
    c.set(allow_sending=True)
    result = await c.build_result()
    assert result.data == {"message_handle": "test"}
    assert json.loads(route.calls[0].request.content) == {
        "number": "+15555550123",
        "content": "Hello",
        "from_number": "+15555550124",
    }
    assert route.calls[0].request.headers["sb-api-secret-key"] == "test-secret"


@pytest.mark.asyncio
@respx.mock
async def test_timeout_is_not_retried():
    route = respx.post("https://api.sendblue.co/api/send-message").mock(side_effect=httpx.ReadTimeout("test"))
    c = SendblueComponent(
        api_key="test-key",
        api_secret=TEST_SECRET,
        operation="Send Message",
        allow_sending=True,
        number="+15555550123",
        content="Hello",
    )
    result = await c.build_result()
    assert "Check message history" in result.data["error"]
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_history_is_bounded_and_errors_are_redacted():
    c = SendblueComponent(api_key="test-key", api_secret=TEST_SECRET, operation="List Messages", limit=101)
    with pytest.raises(ValueError, match="Limit"):
        await c.build_result()
    c.set(limit=20, offset=40, number="+15555550123")
    route = respx.get("https://api.sendblue.co/api/v2/messages").mock(
        return_value=httpx.Response(401, text="test-secret")
    )
    result = await c.build_result()
    assert result.data == {"error": "Sendblue returned HTTP 401"}
    assert dict(route.calls[0].request.url.params) == {"limit": "20", "offset": "40", "number": "+15555550123"}


def test_secrets_not_exposed_as_tool_arguments():
    inputs = {x.name: x for x in SendblueComponent.inputs}
    assert not getattr(inputs["api_key"], "tool_mode", False)
    assert not getattr(inputs["api_secret"], "tool_mode", False)
    assert not getattr(inputs["allow_sending"], "tool_mode", False)


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    ("operation", "path", "kwargs", "response_data"),
    [
        ("List Lines", "/api/v2/lines/state", {}, [{"number": "+15555550124"}]),
        ("Get Message Status", "/api/status", {"handle": "a&b"}, {"status": "DELIVERED"}),
    ],
)
async def test_read_operations(operation, path, kwargs, response_data):
    route = respx.get("https://api.sendblue.co" + path).mock(return_value=httpx.Response(200, json=response_data))
    component = SendblueComponent(api_key="test-key", api_secret=TEST_SECRET, operation=operation, **kwargs)
    result = await component.build_result()
    assert result.data == (response_data if isinstance(response_data, dict) else {"data": response_data})
    if operation == "Get Message Status":
        assert route.calls[0].request.url.params["handle"] == "a&b"
