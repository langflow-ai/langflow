"""Unit tests for the TwittrAPI extension bundle (``lfx-twittrapi``).

The components call TwittrAPI with ``httpx``; the tests patch ``httpx.get`` in
the shared helper module to return real ``httpx.Response`` objects, so no
network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_twittrapi import (
    TwittrAPIFollowersComponent,
    TwittrAPIGetUserComponent,
    TwittrAPIListTweetsComponent,
    TwittrAPISearchTweetsComponent,
    TwittrAPITrendsComponent,
    TwittrAPIUserTweetsComponent,
)

GET_PATCH_TARGET = "lfx_twittrapi.components.twittrapi._common.httpx.get"
BASE_URL = "https://api.twittrapi.com"
API_KEY = "test-key"  # pragma: allowlist secret

USER = {
    "id": "12",
    "username": "jack",
    "name": "jack",
    "description": "no state is the best state",
    "location": "",
    "url": None,
    "createdAt": "2006-03-21T20:50:14.000Z",
    "avatarUrl": "https://pbs.twimg.com/profile_images/jack.jpg",
    "bannerUrl": None,
    "verified": True,
    "verifiedType": None,
    "protected": False,
    "counts": {"followers": 6000000, "following": 4, "tweets": 30000, "likes": 40000, "media": 3000, "listed": 30000},
    "pinnedTweetIds": [],
    "isAutomated": False,
}

TWEET = {
    "id": "20",
    "url": "https://x.com/jack/status/20",
    "text": "just setting up my twttr",
    "createdAt": "2006-03-21T20:50:14.000Z",
    "lang": "en",
    "author": USER,
    "counts": {"likes": 300000, "retweets": 120000, "replies": 18000, "quotes": 9000, "bookmarks": 4000, "views": None},
    "media": [],
    "urls": [],
    "hashtags": [],
    "mentions": [],
    "replyTo": None,
    "quoted": None,
    "retweetOf": None,
    "conversationId": "20",
    "isPinned": False,
    "source": None,
    "article": None,
}

TWEET_PAGE = {"data": [TWEET], "nextCursor": "cursor-2", "previousCursor": "cursor-0", "hasNextPage": True}
USER_PAGE = {"data": [USER], "nextCursor": None, "previousCursor": None, "hasNextPage": False}
TREND_PAGE = {
    "data": [
        {"name": "#Langflow", "query": "#Langflow", "url": "https://x.com/search?q=%23Langflow", "tweetVolume": 1200}
    ],
    "nextCursor": None,
    "previousCursor": None,
    "hasNextPage": False,
}


def _response(status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", BASE_URL), **kwargs)


def _mock_get(payload: object, status_code: int = 200) -> MagicMock:
    return MagicMock(return_value=_response(status_code, json=payload))


def _make(component_class, **attrs):
    component = component_class()
    component.twittrapi_api_key = API_KEY
    for name, value in attrs.items():
        setattr(component, name, value)
    return component


def _call(mock_get: MagicMock) -> tuple[str, dict, dict]:
    call = mock_get.call_args
    return call.args[0], call.kwargs["params"], call.kwargs["headers"]


# ---------------------------------------------------------------------------
# Shared behavior
# ---------------------------------------------------------------------------


def test_class_names_are_stable():
    """Class names identify components in saved flows and must not change."""
    assert [
        cls.__name__
        for cls in (
            TwittrAPIFollowersComponent,
            TwittrAPIGetUserComponent,
            TwittrAPIListTweetsComponent,
            TwittrAPISearchTweetsComponent,
            TwittrAPITrendsComponent,
            TwittrAPIUserTweetsComponent,
        )
    ] == [
        "TwittrAPIFollowersComponent",
        "TwittrAPIGetUserComponent",
        "TwittrAPIListTweetsComponent",
        "TwittrAPISearchTweetsComponent",
        "TwittrAPITrendsComponent",
        "TwittrAPIUserTweetsComponent",
    ]


def test_api_key_input_defaults_to_global_variable():
    """The key input is a secret that loads the TWITTRAPI_API_KEY variable by default."""
    key_input = next(i for i in TwittrAPISearchTweetsComponent.inputs if i.name == "twittrapi_api_key")
    assert key_input.value == "TWITTRAPI_API_KEY"
    assert key_input.load_from_db is True
    assert key_input.password is True


def test_request_sends_key_header_and_simple_format():
    component = _make(TwittrAPISearchTweetsComponent, search_query="langflow", category="Latest", count=20, cursor="")
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        component.fetch_content()
    url, params, headers = _call(mock_get)
    assert url == f"{BASE_URL}/search"
    assert headers["X-API-KEY"] == API_KEY
    assert headers["User-Agent"] == "langflow-twittrapi-bundle"
    assert params == {"searchItem": "langflow", "category": "Latest", "count": 20, "format": "simple"}


def test_missing_api_key_returns_error_row_without_request():
    component = _make(TwittrAPISearchTweetsComponent, search_query="langflow", category="Top", count=20, cursor="")
    component.twittrapi_api_key = ""
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        rows = component.fetch_content()
    mock_get.assert_not_called()
    assert len(rows) == 1
    assert "TwittrAPI key is required" in rows[0].data["error"]


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (401, {"error": "Invalid API key"}, "TwittrAPI error 401: Invalid API key"),
        (402, {"error": "Insufficient balance"}, "TwittrAPI error 402: Insufficient balance"),
        (
            429,
            {"error": "Rate limit exceeded", "errorCode": "rate_limited"},
            "TwittrAPI error 429: Rate limit exceeded",
        ),
    ],
)
def test_api_error_message_is_surfaced(status_code, body, expected):
    component = _make(TwittrAPIUserTweetsComponent, user="jack", count=20, cursor="")
    with patch(GET_PATCH_TARGET, _mock_get(body, status_code)):
        rows = component.fetch_content()
    assert len(rows) == 1
    assert rows[0].data["error"] == expected


def test_non_json_error_falls_back_to_reason_phrase():
    component = _make(TwittrAPITrendsComponent, location_id="1")
    mock_get = MagicMock(return_value=_response(502, text="upstream down"))
    with patch(GET_PATCH_TARGET, mock_get):
        rows = component.fetch_content()
    assert rows[0].data["error"] == "TwittrAPI error 502: Bad Gateway"


def test_transport_error_becomes_error_row():
    component = _make(TwittrAPITrendsComponent, location_id="1")
    with patch(GET_PATCH_TARGET, MagicMock(side_effect=httpx.ConnectError("boom"))):
        rows = component.fetch_content()
    assert len(rows) == 1
    assert "boom" in rows[0].data["error"]


def test_non_object_payload_becomes_error_row():
    component = _make(TwittrAPITrendsComponent, location_id="1")
    with patch(GET_PATCH_TARGET, _mock_get(["unexpected"])):
        rows = component.fetch_content()
    assert "unexpected response" in rows[0].data["error"]


def test_malformed_rows_are_skipped():
    component = _make(TwittrAPIListTweetsComponent, list_id="123", count=20, cursor="")
    with patch(GET_PATCH_TARGET, _mock_get({"data": ["not-an-object", TWEET], "nextCursor": None})):
        rows = component.fetch_content()
    assert [row.data["id"] for row in rows] == ["20"]


def test_next_cursor_is_logged():
    component = _make(TwittrAPIUserTweetsComponent, user="12", count=20, cursor="")
    with patch(GET_PATCH_TARGET, _mock_get(TWEET_PAGE)):
        component.fetch_content()
    assert any(log.name == "next_cursor" and log.message == "cursor-2" for log in component._logs)


# ---------------------------------------------------------------------------
# Search Tweets
# ---------------------------------------------------------------------------


def test_search_maps_tweets():
    component = _make(TwittrAPISearchTweetsComponent, search_query="twttr", category="Top", count=20, cursor="")
    with patch(GET_PATCH_TARGET, _mock_get(TWEET_PAGE)):
        rows = component.fetch_content()
    assert len(rows) == 1
    row = rows[0]
    assert row.text == "just setting up my twttr"
    assert row.data["authorUsername"] == "jack"
    assert row.data["likes"] == 300000
    assert row.data["views"] is None
    assert row.data["url"] == "https://x.com/jack/status/20"


def test_search_people_maps_users_and_passes_cursor():
    component = _make(TwittrAPISearchTweetsComponent, search_query="jack", category="People", count=5, cursor="abc")
    mock_get = _mock_get(USER_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        rows = component.fetch_content()
    _, params, _ = _call(mock_get)
    assert params["category"] == "People"
    assert params["count"] == 5
    assert params["cursor"] == "abc"
    assert rows[0].data["username"] == "jack"
    assert rows[0].data["followers"] == 6000000


def test_search_unknown_category_falls_back_to_top_and_bad_count_to_default():
    component = _make(TwittrAPISearchTweetsComponent, search_query="x", category="Bogus", count=0, cursor="")
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        component.fetch_content()
    _, params, _ = _call(mock_get)
    assert params["category"] == "Top"
    assert params["count"] == 20


def test_search_requires_query():
    component = _make(TwittrAPISearchTweetsComponent, search_query="  ", category="Top", count=20, cursor="")
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        rows = component.fetch_content()
    mock_get.assert_not_called()
    assert rows[0].data["error"] == "A search query is required."


def test_search_dataframe_shape():
    component = _make(TwittrAPISearchTweetsComponent, search_query="twttr", category="Top", count=20, cursor="")
    with patch(GET_PATCH_TARGET, _mock_get(TWEET_PAGE)):
        frame = component.twittrapi_search_tweets()
    assert len(frame) == 1
    assert "authorUsername" in frame.columns


# ---------------------------------------------------------------------------
# Get User
# ---------------------------------------------------------------------------


def test_get_user_strips_at_and_maps_profile():
    component = _make(TwittrAPIGetUserComponent, username="@jack")
    mock_get = _mock_get({"data": USER})
    with patch(GET_PATCH_TARGET, mock_get):
        result = component.twittrapi_get_user()
    url, params, _ = _call(mock_get)
    assert url == f"{BASE_URL}/user/by/username/jack"
    assert params == {"format": "simple"}
    assert result.data["id"] == "12"
    assert result.text == "jack (@jack)"


def test_get_user_not_found():
    component = _make(TwittrAPIGetUserComponent, username="nobody_here")
    with patch(GET_PATCH_TARGET, _mock_get({"data": None})):
        result = component.twittrapi_get_user()
    assert result.data["error"] == "User @nobody_here not found."


def test_get_user_rejects_invalid_handle_without_request():
    component = _make(TwittrAPIGetUserComponent, username="not a/handle")
    mock_get = _mock_get({"data": USER})
    with patch(GET_PATCH_TARGET, mock_get):
        result = component.twittrapi_get_user()
    mock_get.assert_not_called()
    assert "valid X username" in result.data["error"]


# ---------------------------------------------------------------------------
# User Tweets and Followers
# ---------------------------------------------------------------------------


def test_user_tweets_by_numeric_id():
    component = _make(TwittrAPIUserTweetsComponent, user="12", count=20, cursor="")
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        component.fetch_content()
    url, params, _ = _call(mock_get)
    assert url == f"{BASE_URL}/user/12/tweets"
    assert "username" not in params


@pytest.mark.parametrize("value", ["jack", "@jack", "@123456"])
def test_user_tweets_by_username_uses_minus_one(value):
    component = _make(TwittrAPIUserTweetsComponent, user=value, count=20, cursor="")
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        component.fetch_content()
    url, params, _ = _call(mock_get)
    assert url == f"{BASE_URL}/user/-1/tweets"
    assert params["username"] == value.lstrip("@")


def test_followers_maps_users():
    component = _make(TwittrAPIFollowersComponent, user="jack", count=50, cursor="c1")
    mock_get = _mock_get(USER_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        frame = component.twittrapi_followers()
    url, params, _ = _call(mock_get)
    assert url == f"{BASE_URL}/user/-1/followers"
    assert params == {"username": "jack", "count": 50, "cursor": "c1", "format": "simple"}
    assert list(frame["username"]) == ["jack"]


def test_followers_rejects_invalid_user():
    component = _make(TwittrAPIFollowersComponent, user="", count=20, cursor="")
    mock_get = _mock_get(USER_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        rows = component.fetch_content()
    mock_get.assert_not_called()
    assert "valid X username" in rows[0].data["error"]


# ---------------------------------------------------------------------------
# List Tweets and Trends
# ---------------------------------------------------------------------------


def test_list_tweets_sends_list_id():
    component = _make(TwittrAPIListTweetsComponent, list_id=" 1234 ", count=20, cursor="")
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        component.fetch_content()
    url, params, _ = _call(mock_get)
    assert url == f"{BASE_URL}/lists/tweets"
    assert params["listId"] == "1234"


def test_list_tweets_rejects_non_numeric_id():
    component = _make(TwittrAPIListTweetsComponent, list_id="abc", count=20, cursor="")
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        rows = component.fetch_content()
    mock_get.assert_not_called()
    assert rows[0].data["error"] == "List ID must be digits only."


def test_trends_maps_rows_and_defaults_to_worldwide():
    component = _make(TwittrAPITrendsComponent, location_id="")
    mock_get = _mock_get(TREND_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        frame = component.twittrapi_trends()
    url, params, _ = _call(mock_get)
    assert url == f"{BASE_URL}/trends/1"
    assert params == {"format": "simple"}
    assert list(frame["name"]) == ["#Langflow"]
    assert list(frame["tweetVolume"]) == [1200]


def test_trends_rejects_path_characters():
    component = _make(TwittrAPITrendsComponent, location_id="1/../x")
    mock_get = _mock_get(TREND_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        rows = component.fetch_content()
    mock_get.assert_not_called()
    assert rows[0].data["error"] == "Location ID must be digits only."


# ---------------------------------------------------------------------------
# Tool mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("component_class", "tool_name"),
    [
        (TwittrAPISearchTweetsComponent, "twittrapi_search_tweets"),
        (TwittrAPIGetUserComponent, "twittrapi_get_user"),
        (TwittrAPIUserTweetsComponent, "twittrapi_user_tweets"),
        (TwittrAPIFollowersComponent, "twittrapi_followers"),
        (TwittrAPIListTweetsComponent, "twittrapi_list_tweets"),
        (TwittrAPITrendsComponent, "twittrapi_trends"),
    ],
)
def test_tool_names_are_vendor_specific(component_class, tool_name):
    """Each component exposes one tool whose name cannot collide with other bundles."""
    component = component_class(twittrapi_api_key=API_KEY)
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == [tool_name]


def test_search_tool_invocation():
    """An Agent passes the query and, optionally, the category."""
    component = TwittrAPISearchTweetsComponent(twittrapi_api_key=API_KEY, count=20)
    tools = asyncio.run(component.to_toolkit())
    mock_get = _mock_get(TWEET_PAGE)
    with patch(GET_PATCH_TARGET, mock_get):
        output = asyncio.run(tools[0].ainvoke({"search_query": "langflow", "category": "Latest"}))
    _, params, _ = _call(mock_get)
    assert params["searchItem"] == "langflow"
    assert params["category"] == "Latest"
    assert list(output["text"]) == ["just setting up my twttr"]
