"""Shared request, input and row-mapping helpers for the TwittrAPI components.

Every TwittrAPI endpoint used here is a GET on ``https://api.twittrapi.com`` with
the key in the ``X-API-KEY`` header.  The components always ask for
``format=simple``, which returns flat camelCase JSON in a fixed envelope:
``{"data": ..., "nextCursor": ..., "previousCursor": ..., "hasNextPage": ...}``.
Errors are ``{"error": "<message>"}`` with a non-2xx status.

This module holds no ``Component`` subclass on purpose, so the bundle loader
does not register anything from it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data

if TYPE_CHECKING:
    from collections.abc import Callable

API_BASE_URL = "https://api.twittrapi.com"
API_KEY_VARIABLE = "TWITTRAPI_API_KEY"
USER_AGENT = "langflow-twittrapi-bundle"
# Search retries an empty upstream timeline a few times before answering, so
# allow more than the usual 30 seconds.
REQUEST_TIMEOUT = 60
DEFAULT_COUNT = 20

USERNAME_PATTERN = re.compile(r"^@?([A-Za-z0-9_]{2,15})$")
USER_ID_PATTERN = re.compile(r"^[0-9]{1,30}$")
LIST_ID_PATTERN = re.compile(r"^[0-9]+$")
LOCATION_ID_PATTERN = re.compile(r"^[0-9]{1,12}$")


class TwittrAPIError(Exception):
    """A non-2xx TwittrAPI response, carrying the API's own error message."""


# ---------------------------------------------------------------------------
# Inputs shared by every component
# ---------------------------------------------------------------------------


def api_key_input() -> SecretStrInput:
    return SecretStrInput(
        name="twittrapi_api_key",
        display_name="TwittrAPI Key",
        info="Your TwittrAPI key. Get one at https://www.twittrapi.com.",
        value=API_KEY_VARIABLE,
        required=True,
    )


def count_input() -> IntInput:
    return IntInput(
        name="count",
        display_name="Count",
        value=DEFAULT_COUNT,
        required=False,
        advanced=True,
        info="Number of items to ask for. X treats it as a hint, so a page can hold more or fewer.",
    )


def cursor_input() -> MessageTextInput:
    return MessageTextInput(
        name="cursor",
        display_name="Cursor",
        required=False,
        advanced=True,
        info="Cursor from a previous page (logged as next_cursor). Leave empty for the first page.",
    )


# ---------------------------------------------------------------------------
# Input normalization
# ---------------------------------------------------------------------------


def clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def count_value(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return DEFAULT_COUNT
    return count if count >= 1 else DEFAULT_COUNT


def normalize_username(value: Any) -> str:
    """Return a handle without the leading ``@``, or raise ``ValueError``."""
    match = USERNAME_PATTERN.match(clean(value))
    if not match:
        msg = "Enter a valid X username: 2 to 15 letters, digits or underscores, with or without @."
        raise ValueError(msg)
    return match.group(1)


def user_path_and_params(user: Any, suffix: str) -> tuple[str, dict[str, str]]:
    """Map a numeric user ID or a handle to ``/user/{userId}/<suffix>``.

    Digits are used as the user ID.  Anything else is treated as a handle and
    sent as ``username`` with ``-1`` in the path, which the API resolves itself.
    Prefix a digits-only handle with ``@`` to look it up as a handle.
    """
    value = clean(user)
    if USER_ID_PATTERN.match(value):
        return f"/user/{value}/{suffix}", {}
    return f"/user/-1/{suffix}", {"username": normalize_username(value)}


def require_digits(value: Any, pattern: re.Pattern[str], label: str) -> str:
    text = clean(value)
    if not pattern.match(text):
        msg = f"{label} must be digits only."
        raise ValueError(msg)
    return text


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def error_message(response: httpx.Response) -> str:
    """Describe a non-2xx response, keeping the API's own ``{"error": "..."}`` text."""
    detail = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        detail = payload["error"]
    reason = detail or response.reason_phrase or "request failed"
    return f"TwittrAPI error {response.status_code}: {reason}"


def get_json(api_key: Any, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET ``path`` with ``format=simple`` and return the decoded JSON object."""
    if not api_key:
        msg = "TwittrAPI key is required. Set the TwittrAPI Key input."
        raise ValueError(msg)

    query = {key: value for key, value in (params or {}).items() if value not in (None, "")}
    query["format"] = "simple"
    headers = {
        "X-API-KEY": api_key,
        "Accept": "application/json",
        # Identify the integration to the API; keeps traffic attributable.
        "User-Agent": USER_AGENT,
    }
    response = httpx.get(f"{API_BASE_URL}{path}", params=query, headers=headers, timeout=REQUEST_TIMEOUT)
    if response.is_error:
        raise TwittrAPIError(error_message(response))
    payload = response.json()
    if not isinstance(payload, dict):
        msg = "TwittrAPI returned an unexpected response (expected a JSON object)."
        raise TwittrAPIError(msg)
    return payload


# ---------------------------------------------------------------------------
# Row mapping (simple format -> Data)
# ---------------------------------------------------------------------------


def _counts(item: dict[str, Any]) -> dict[str, Any]:
    counts = item.get("counts")
    return counts if isinstance(counts, dict) else {}


def tweet_to_data(tweet: dict[str, Any]) -> Data:
    author = tweet.get("author") if isinstance(tweet.get("author"), dict) else {}
    reply_to = tweet.get("replyTo") if isinstance(tweet.get("replyTo"), dict) else {}
    quoted = tweet.get("quoted") if isinstance(tweet.get("quoted"), dict) else {}
    retweet_of = tweet.get("retweetOf") if isinstance(tweet.get("retweetOf"), dict) else {}
    counts = _counts(tweet)
    text = tweet.get("text") or ""
    return Data(
        text=text,
        data={
            "id": tweet.get("id"),
            "url": tweet.get("url"),
            "text": text,
            "createdAt": tweet.get("createdAt"),
            "lang": tweet.get("lang"),
            "authorId": author.get("id"),
            "authorUsername": author.get("username"),
            "authorName": author.get("name"),
            "likes": counts.get("likes"),
            "retweets": counts.get("retweets"),
            "replies": counts.get("replies"),
            "quotes": counts.get("quotes"),
            "bookmarks": counts.get("bookmarks"),
            "views": counts.get("views"),
            "conversationId": tweet.get("conversationId"),
            "replyToTweetId": reply_to.get("tweetId"),
            "quotedTweetId": quoted.get("id"),
            "retweetOfId": retweet_of.get("id"),
        },
    )


def user_to_data(user: dict[str, Any]) -> Data:
    counts = _counts(user)
    username = user.get("username") or ""
    name = user.get("name") or ""
    return Data(
        text=f"{name} (@{username})" if username else name,
        data={
            "id": user.get("id"),
            "username": username,
            "name": name,
            "description": user.get("description"),
            "location": user.get("location"),
            "url": user.get("url"),
            "createdAt": user.get("createdAt"),
            "avatarUrl": user.get("avatarUrl"),
            "verified": user.get("verified"),
            "verifiedType": user.get("verifiedType"),
            "protected": user.get("protected"),
            "followers": counts.get("followers"),
            "following": counts.get("following"),
            "tweets": counts.get("tweets"),
            "likes": counts.get("likes"),
            "listed": counts.get("listed"),
        },
    )


def trend_to_data(trend: dict[str, Any]) -> Data:
    name = trend.get("name") or ""
    return Data(
        text=name,
        data={
            "name": name,
            "query": trend.get("query"),
            "url": trend.get("url"),
            "tweetVolume": trend.get("tweetVolume"),
        },
    )


def page_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the object rows of a simple-format page, skipping malformed entries."""
    items = payload.get("data")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def error_data(message: str) -> Data:
    return Data(text=message, data={"error": message})


def fetch_page(
    component: Any,
    path: str,
    params: dict[str, Any],
    to_data: Callable[[dict[str, Any]], Data],
) -> list[Data]:
    """Fetch one simple-format page and map its rows; failures become one error row.

    The next-page cursor is logged as ``next_cursor`` so a flow builder can feed
    it back into the Cursor input.
    """
    try:
        payload = get_json(component.twittrapi_api_key, path, params)
    except httpx.HTTPError as e:
        rows = [error_data(f"TwittrAPI request failed: {e}")]
    except (TwittrAPIError, ValueError) as e:
        rows = [error_data(str(e))]
    else:
        rows = [to_data(item) for item in page_items(payload)]
        next_cursor = payload.get("nextCursor")
        if next_cursor:
            component.log(next_cursor, name="next_cursor")
    component.status = rows
    return rows
