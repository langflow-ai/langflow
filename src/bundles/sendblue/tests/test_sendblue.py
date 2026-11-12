import json

import httpx
import pytest
from lfx_sendblue import SendblueComponent
from lfx_sendblue.components.sendblue import sendblue as sendblue_module

TEST_SECRET = "test-secret"  # noqa: S105


@pytest.fixture
def mock_api(monkeypatch):
    original_client = httpx.AsyncClient

    def configure(response):
        requests = []

        def handle(request):
            requests.append(request)
            if isinstance(response, Exception):
                raise response
            return response

        transport = httpx.MockTransport(handle)
        monkeypatch.setattr(
            sendblue_module.httpx,
            "AsyncClient",
            lambda **kwargs: original_client(transport=transport, **kwargs),
        )
        return requests

    return configure


@pytest.mark.asyncio
async def test_send_requires_explicit_enable_and_uses_fixed_destination(mock_api):
    requests = mock_api(httpx.Response(200, json={"message_handle": "test"}))
    component = SendblueComponent(
        api_key="test-key",
        api_secret=TEST_SECRET,
        operation="Send Message",
        number="+15555550123",
        content="Hello",
        from_number="+15555550124",
    )
    with pytest.raises(ValueError, match="Enable Allow Sending"):
        await component.build_result()
    assert requests == []
    component.set(allow_sending=True)
    result = await component.build_result()
    assert result.data == {"message_handle": "test"}
    assert len(requests) == 1
    assert requests[0].url == "https://api.sendblue.co/api/send-message"
    assert requests[0].method == "POST"
    assert json.loads(requests[0].content) == {
        "number": "+15555550123",
        "content": "Hello",
        "from_number": "+15555550124",
    }
    assert requests[0].headers["sb-api-secret-key"] == TEST_SECRET


@pytest.mark.asyncio
async def test_timeout_is_not_retried(mock_api):
    requests = mock_api(httpx.ReadTimeout("test"))
    component = SendblueComponent(
        api_key="test-key",
        api_secret=TEST_SECRET,
        operation="Send Message",
        allow_sending=True,
        number="+15555550123",
        content="Hello",
    )
    result = await component.build_result()
    assert "Check message history" in result.data["error"]
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_history_is_bounded_and_errors_are_redacted(mock_api):
    requests = mock_api(httpx.Response(401, text=TEST_SECRET))
    component = SendblueComponent(api_key="test-key", api_secret=TEST_SECRET, operation="List Messages", limit=101)
    with pytest.raises(ValueError, match="Limit"):
        await component.build_result()
    assert requests == []
    component.set(limit=20, offset=40, number="+15555550123")
    result = await component.build_result()
    assert result.data == {"error": "Sendblue returned HTTP 401"}
    assert dict(requests[0].url.params) == {"limit": "20", "offset": "40", "number": "+15555550123"}


def test_secrets_not_exposed_as_tool_arguments():
    inputs = {x.name: x for x in SendblueComponent.inputs}
    assert not getattr(inputs["api_key"], "tool_mode", False)
    assert not getattr(inputs["api_secret"], "tool_mode", False)
    assert not getattr(inputs["allow_sending"], "tool_mode", False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "path", "kwargs", "response_data"),
    [
        ("List Lines", "/api/v2/lines/state", {}, [{"number": "+15555550124"}]),
        ("Get Message Status", "/api/status", {"handle": "a&b"}, {"status": "DELIVERED"}),
    ],
)
async def test_read_operations(mock_api, operation, path, kwargs, response_data):
    requests = mock_api(httpx.Response(200, json=response_data))
    component = SendblueComponent(api_key="test-key", api_secret=TEST_SECRET, operation=operation, **kwargs)
    result = await component.build_result()
    assert result.data == (response_data if isinstance(response_data, dict) else {"data": response_data})
    assert requests[0].method == "GET"
    assert requests[0].url.path == path
    if operation == "Get Message Status":
        assert requests[0].url.params["handle"] == "a&b"
