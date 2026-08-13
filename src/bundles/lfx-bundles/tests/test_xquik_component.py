from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from lfx.schema import Data, DataFrame
from lfx.schema.message import Message
from lfx_bundles.xquik import XquikComponent

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def default_kwargs() -> dict:
    return {
        "operation": XquikComponent.SEARCH_TWEETS,
        "api_key": "xq_test_key",  # pragma: allowlist secret
        "query": "langflow",
        "tweet_id": "",
        "user_identifier": "",
        "query_type": "Latest",
        "limit": 20,
        "cursor": "",
        "woeid": 1,
        "include_replies": False,
        "include_parent_tweet": False,
        "timeout": 30,
    }


def use_handler(monkeypatch: pytest.MonkeyPatch, handler: Handler, timeouts: list[int] | None = None) -> None:
    def build_client(_self: XquikComponent, timeout: int) -> httpx.AsyncClient:
        if timeouts is not None:
            timeouts.append(timeout)
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            timeout=timeout,
            follow_redirects=False,
        )

    monkeypatch.setattr(XquikComponent, "_build_client", build_client)


def test_component_identity_is_stable() -> None:
    assert XquikComponent.__name__ == "XquikComponent"
    assert XquikComponent.name == "Xquik"


def test_update_build_config_ignores_unrelated_fields() -> None:
    component = XquikComponent()
    build_config = {"query": {"show": True, "required": True}}

    assert component.update_build_config(build_config, "ignored", "query") is build_config


def test_update_build_config_for_get_tweet() -> None:
    component = XquikComponent()
    build_config = {
        name: {"show": True, "required": name == "query"}
        for name in (
            "query",
            "tweet_id",
            "user_identifier",
            "query_type",
            "limit",
            "cursor",
            "woeid",
            "include_replies",
            "include_parent_tweet",
        )
    }

    updated = component.update_build_config(build_config, XquikComponent.GET_TWEET, "operation")

    assert updated["tweet_id"] == {"show": True, "required": True}
    assert updated["query"] == {"show": False, "required": False}
    assert updated["user_identifier"] == {"show": False, "required": False}
    assert all(
        not updated[name]["show"]
        for name in ("query_type", "limit", "cursor", "woeid", "include_replies", "include_parent_tweet")
    )


def test_update_build_config_for_user_search() -> None:
    component = XquikComponent()
    build_config = {
        name: {"show": False, "required": False}
        for name in (
            "query",
            "tweet_id",
            "user_identifier",
            "query_type",
            "limit",
            "cursor",
            "woeid",
            "include_replies",
            "include_parent_tweet",
        )
    }

    updated = component.update_build_config(build_config, XquikComponent.SEARCH_USERS, "operation")

    assert updated["query"] == {"show": True, "required": True}
    assert updated["limit"]["show"]
    assert updated["cursor"]["show"]
    assert not updated["query_type"]["show"]


@pytest.mark.parametrize(
    ("operation", "updates", "expected_url", "expected_params"),
    [
        (
            XquikComponent.SEARCH_TWEETS,
            {},
            "https://xquik.com/api/v1/x/tweets/search",
            {"q": "langflow", "queryType": "Latest", "limit": 20},
        ),
        (
            XquikComponent.GET_TWEET,
            {"tweet_id": "123"},
            "https://xquik.com/api/v1/x/tweets/123",
            {},
        ),
        (
            XquikComponent.GET_USER,
            {"user_identifier": "xquik"},
            "https://xquik.com/api/v1/x/users/xquik",
            {},
        ),
        (
            XquikComponent.SEARCH_USERS,
            {"cursor": "user-next"},
            "https://xquik.com/api/v1/x/users/search",
            {"q": "langflow", "pageSize": 20, "cursor": "user-next"},
        ),
        (
            XquikComponent.USER_TWEETS,
            {"user_identifier": "xquik", "cursor": "tweet-next", "include_replies": True},
            "https://xquik.com/api/v1/x/users/xquik/tweets",
            {
                "pageSize": 20,
                "includeReplies": True,
                "includeParentTweet": False,
                "cursor": "tweet-next",
            },
        ),
        (
            XquikComponent.TRENDS,
            {"limit": 99},
            "https://xquik.com/api/v1/x/trends",
            {"woeid": 1, "count": 50},
        ),
    ],
)
def test_builds_operation_requests(
    default_kwargs: dict,
    operation: str,
    updates: dict,
    expected_url: str,
    expected_params: dict,
) -> None:
    component = XquikComponent(**{**default_kwargs, "operation": operation, **updates})

    assert component._build_url(operation) == expected_url
    assert component._build_params(operation) == expected_params


def test_path_identifier_is_url_encoded(default_kwargs: dict) -> None:
    component = XquikComponent(**{**default_kwargs, "user_identifier": "name/with space"})

    assert component._build_url(XquikComponent.GET_USER) == "https://xquik.com/api/v1/x/users/name%2Fwith%20space"


@pytest.mark.parametrize(
    ("operation", "configured", "parameter", "maximum"),
    [
        (XquikComponent.SEARCH_TWEETS, 20000, "limit", 10000),
        (XquikComponent.SEARCH_USERS, 200, "pageSize", 100),
        (XquikComponent.USER_TWEETS, 500, "pageSize", 300),
        (XquikComponent.TRENDS, 100, "count", 50),
    ],
)
def test_operation_limits_match_the_public_contract(
    default_kwargs: dict,
    operation: str,
    configured: int,
    parameter: str,
    maximum: int,
) -> None:
    component = XquikComponent(
        **{
            **default_kwargs,
            "operation": operation,
            "limit": configured,
            "user_identifier": "xquik",
        }
    )

    assert component._build_params(operation)[parameter] == maximum


@pytest.mark.parametrize(
    ("operation", "field_name", "expected_message"),
    [
        (XquikComponent.GET_TWEET, "tweet_id", "Tweet Id is required"),
        (XquikComponent.GET_USER, "user_identifier", "User Identifier is required"),
        (XquikComponent.USER_TWEETS, "user_identifier", "User Identifier is required"),
    ],
)
def test_missing_path_identifier_raises(
    default_kwargs: dict,
    operation: str,
    field_name: str,
    expected_message: str,
) -> None:
    component = XquikComponent(**{**default_kwargs, "operation": operation, field_name: ""})

    with pytest.raises(ValueError, match=expected_message):
        component._build_url(operation)


def test_missing_query_raises(default_kwargs: dict) -> None:
    component = XquikComponent(**{**default_kwargs, "query": ""})

    with pytest.raises(ValueError, match="Query is required"):
        component._build_params(XquikComponent.SEARCH_TWEETS)


def test_missing_api_key_raises(default_kwargs: dict) -> None:
    component = XquikComponent(**{**default_kwargs, "api_key": ""})

    with pytest.raises(ValueError, match="Xquik API key is required"):
        component._api_key_value()


def test_unknown_operation_raises(default_kwargs: dict) -> None:
    component = XquikComponent(**default_kwargs)

    with pytest.raises(ValueError, match="Unsupported Xquik operation"):
        component._build_url("Unknown")


def test_empty_numeric_input_uses_default(default_kwargs: dict) -> None:
    component = XquikComponent(**{**default_kwargs, "limit": ""})

    assert component._bounded_int("limit", default=20, minimum=1, maximum=100) == 20


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"result": [1, {"id": "2"}]}, [{"value": 1}, {"id": "2"}]),
        ({"result": {"id": "1"}}, [{"id": "1"}]),
        ({"metadata": "value"}, [{"metadata": "value"}]),
    ],
)
def test_record_normalization(default_kwargs: dict, payload: dict, expected: list[dict]) -> None:
    component = XquikComponent(**default_kwargs)

    assert component._records_from_payload(payload) == expected


@pytest.mark.asyncio
async def test_client_disables_redirects_and_applies_timeout(default_kwargs: dict) -> None:
    component = XquikComponent(**default_kwargs)
    client = component._build_client(12)

    try:
        assert not client.follow_redirects
        assert client.timeout.connect == 12
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_run_table_uses_fixed_origin_contract_and_secret_header(
    monkeypatch: pytest.MonkeyPatch,
    default_kwargs: dict,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "xquik.com"
        assert request.url.path == "/api/v1/x/tweets/search"
        assert request.url.params["q"] == "langflow"
        assert request.headers["x-api-key"] == "xq_test_key"
        assert request.headers["xquik-api-contract"] == "2026-04-29"
        return httpx.Response(200, json={"tweets": [{"id": "1", "text": "Hello Langflow"}]})

    use_handler(monkeypatch, handler)
    component = XquikComponent(**default_kwargs)

    result = await component.run_table()

    assert isinstance(result, DataFrame)
    assert result.iloc[0]["id"] == "1"
    assert component.status == "Returned 1 record(s)."


@pytest.mark.asyncio
async def test_run_json_preserves_payload(monkeypatch: pytest.MonkeyPatch, default_kwargs: dict) -> None:
    use_handler(monkeypatch, lambda _request: httpx.Response(200, json={"tweets": [{"id": "1"}]}))
    component = XquikComponent(**default_kwargs)

    result = await component.run_json()

    assert isinstance(result, Data)
    assert result.data == {"tweets": [{"id": "1"}], "operation": XquikComponent.SEARCH_TWEETS}


@pytest.mark.asyncio
async def test_run_text_returns_json_lines(monkeypatch: pytest.MonkeyPatch, default_kwargs: dict) -> None:
    use_handler(monkeypatch, lambda _request: httpx.Response(200, json={"users": [{"id": "42", "username": "xquik"}]}))
    component = XquikComponent(**default_kwargs)

    result = await component.run_text()

    assert isinstance(result, Message)
    assert result.text == '{"id": "42", "username": "xquik"}'
    assert result.data["users"] == [{"id": "42", "username": "xquik"}]


@pytest.mark.asyncio
async def test_non_json_response_is_preserved(monkeypatch: pytest.MonkeyPatch, default_kwargs: dict) -> None:
    use_handler(monkeypatch, lambda _request: httpx.Response(200, text="plain response"))
    component = XquikComponent(**default_kwargs)

    result = await component.run_text()

    assert result.text == "plain response"
    assert result.data["text"] == "plain response"
    assert result.data["operation"] == XquikComponent.SEARCH_TWEETS


@pytest.mark.asyncio
async def test_non_object_json_is_wrapped(monkeypatch: pytest.MonkeyPatch, default_kwargs: dict) -> None:
    use_handler(monkeypatch, lambda _request: httpx.Response(200, json=[{"id": "1"}]))
    component = XquikComponent(**default_kwargs)

    result = await component.run_json()

    assert result.data == {
        "result": [{"id": "1"}],
        "operation": XquikComponent.SEARCH_TWEETS,
    }


@pytest.mark.asyncio
async def test_empty_results_have_clear_text(monkeypatch: pytest.MonkeyPatch, default_kwargs: dict) -> None:
    use_handler(monkeypatch, lambda _request: httpx.Response(200, json={"tweets": []}))
    component = XquikComponent(**default_kwargs)

    result = await component.run_text()

    assert result.text == "No Xquik records returned."


@pytest.mark.asyncio
async def test_http_error_returns_bounded_error_payload(monkeypatch: pytest.MonkeyPatch, default_kwargs: dict) -> None:
    use_handler(monkeypatch, lambda _request: httpx.Response(429, text="provider details"))
    component = XquikComponent(**default_kwargs)

    result = await component.run_json()

    assert result.data == {
        "error": "Xquik request failed with HTTP 429.",
        "operation": XquikComponent.SEARCH_TWEETS,
        "status_code": 429,
    }
    assert "provider details" not in str(result.data)


@pytest.mark.asyncio
async def test_connection_error_does_not_expose_transport_details(
    monkeypatch: pytest.MonkeyPatch,
    default_kwargs: dict,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        detail = "internal connection detail"
        raise httpx.ConnectError(detail, request=request)

    use_handler(monkeypatch, handler)
    component = XquikComponent(**default_kwargs)

    result = await component.run_json()

    assert result.data == {
        "error": "Xquik request failed before receiving a response.",
        "operation": XquikComponent.SEARCH_TWEETS,
    }


@pytest.mark.asyncio
async def test_timeout_does_not_expose_transport_details(
    monkeypatch: pytest.MonkeyPatch,
    default_kwargs: dict,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        detail = "internal transport detail"
        raise httpx.ReadTimeout(detail, request=request)

    use_handler(monkeypatch, handler)
    component = XquikComponent(**default_kwargs)

    result = await component.run_json()

    assert result.data == {
        "error": "Xquik request timed out.",
        "operation": XquikComponent.SEARCH_TWEETS,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(("configured", "expected"), [(0, 1), (-1, 1), (999, 300)])
async def test_timeout_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
    default_kwargs: dict,
    configured: int,
    expected: int,
) -> None:
    timeouts: list[int] = []
    use_handler(monkeypatch, lambda _request: httpx.Response(200, json={"tweets": []}), timeouts)
    component = XquikComponent(**{**default_kwargs, "timeout": configured})

    await component.run_json()

    assert timeouts == [expected]
