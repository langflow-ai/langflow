from __future__ import annotations

import json
from typing import Any

import pandas as pd
import requests
from pydantic import SecretStr

from lfx.custom import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema import Data, DataFrame
from lfx.schema.message import Message


class XquikComponent(Component):
    display_name = "Xquik"
    description = "Read X/Twitter data with Xquik."
    documentation: str = "https://docs.langflow.org/xquik"
    icon = "search"
    name = "Xquik"

    SEARCH_TWEETS = "Search Tweets"
    GET_TWEET = "Get Tweet"
    GET_USER = "Get User"
    SEARCH_USERS = "Search Users"
    USER_TWEETS = "User Tweets"
    TRENDS = "Trends"

    _OPERATION_PATHS = {
        SEARCH_TWEETS: "/x/tweets/search",
        GET_TWEET: "/x/tweets/{id}",
        GET_USER: "/x/users/{id}",
        SEARCH_USERS: "/x/users/search",
        USER_TWEETS: "/x/users/{id}/tweets",
        TRENDS: "/trends",
    }

    inputs = [
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=[SEARCH_TWEETS, GET_TWEET, GET_USER, SEARCH_USERS, USER_TWEETS, TRENDS],
            value=SEARCH_TWEETS,
            info="Read-only Xquik operation to run.",
            real_time_refresh=True,
            tool_mode=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Xquik API Key",
            info="Xquik API key from your dashboard account page.",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Search query for tweet or user search operations.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="tweet_id",
            display_name="Tweet ID",
            info="Tweet ID for the Get Tweet operation.",
            show=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="user_identifier",
            display_name="User ID or Username",
            info="User ID or username for user lookup or user tweets.",
            show=False,
            tool_mode=True,
        ),
        DropdownInput(
            name="query_type",
            display_name="Query Type",
            options=["Latest", "Top"],
            value="Latest",
            info="Search mode for tweet search.",
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="Maximum records to return when supported by the operation.",
            value=20,
            advanced=True,
        ),
        MessageTextInput(
            name="cursor",
            display_name="Cursor",
            info="Pagination cursor returned by a previous call.",
            required=False,
            advanced=True,
        ),
        IntInput(
            name="woeid",
            display_name="WOEID",
            info="Yahoo Where On Earth ID for trends. Use 1 for worldwide.",
            value=1,
            advanced=True,
        ),
        BoolInput(
            name="include_replies",
            display_name="Include Replies",
            info="Include replies in user tweet results.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="include_parent_tweet",
            display_name="Include Parent Tweet",
            info="Include parent tweet data when supported.",
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            info="Xquik API base URL.",
            value="https://xquik.com/api/v1",
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for the request in seconds.",
            value=30,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="table", method="run_table"),
        Output(display_name="JSON", name="json_data", method="run_json"),
        Output(display_name="Text", name="text", method="run_text"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name != "operation":
            return build_config

        operation = str(field_value)
        needs_query = operation in {self.SEARCH_TWEETS, self.SEARCH_USERS}
        needs_tweet_id = operation == self.GET_TWEET
        needs_user_id = operation in {self.GET_USER, self.USER_TWEETS}
        is_tweet_search = operation == self.SEARCH_TWEETS
        is_user_tweets = operation == self.USER_TWEETS
        is_trends = operation == self.TRENDS

        self._set_visible(build_config, "query", visible=needs_query)
        self._set_visible(build_config, "tweet_id", visible=needs_tweet_id)
        self._set_visible(build_config, "user_identifier", visible=needs_user_id)
        self._set_visible(build_config, "query_type", visible=is_tweet_search)
        self._set_visible(build_config, "limit", visible=operation in {self.SEARCH_TWEETS, self.TRENDS})
        self._set_visible(
            build_config,
            "cursor",
            visible=operation in {self.SEARCH_TWEETS, self.SEARCH_USERS, self.USER_TWEETS},
        )
        self._set_visible(build_config, "woeid", visible=is_trends)
        self._set_visible(build_config, "include_replies", visible=is_user_tweets)
        self._set_visible(build_config, "include_parent_tweet", visible=is_user_tweets)
        return build_config

    def run_table(self) -> DataFrame:
        payload = self._run_operation()
        records = self._records_from_payload(payload)
        self.status = f"Returned {len(records)} record(s)."
        return DataFrame(pd.DataFrame(records))

    def run_json(self) -> Data:
        payload = self._run_operation()
        return Data(data=payload)

    def run_text(self) -> Message:
        payload = self._run_operation()
        return Message(text=self._payload_to_text(payload), data=payload)

    def _run_operation(self) -> dict[str, Any]:
        operation = str(getattr(self, "operation", self.SEARCH_TWEETS))
        url = self._build_url(operation)
        params = self._build_params(operation)
        headers = {
            "accept": "application/json",
            "x-api-key": self._api_key_value(),
            "xquik-api-contract": "2026-04-29",
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            msg = f"Xquik request failed: {e!s}"
            self.status = msg
            return {"error": msg, "operation": operation, "url": url}

        try:
            payload = response.json()
        except ValueError:
            return {"text": response.text, "operation": operation, "url": url}

        if isinstance(payload, dict):
            payload.setdefault("operation", operation)
            return payload

        return {"result": payload, "operation": operation, "url": url}

    def _build_url(self, operation: str) -> str:
        path = self._OPERATION_PATHS.get(operation)
        if path is None:
            msg = f"Unsupported Xquik operation: {operation}"
            raise ValueError(msg)

        if "{id}" in path:
            value = self._required_value("tweet_id" if operation == self.GET_TWEET else "user_identifier")
            path = path.format(id=value)

        return f"{self.base_url.rstrip('/')}{path}"

    def _build_params(self, operation: str) -> dict[str, Any]:
        params: dict[str, Any] = {}

        if operation in {self.SEARCH_TWEETS, self.SEARCH_USERS}:
            params["q"] = self._required_value("query")
        if operation == self.SEARCH_TWEETS:
            params["queryType"] = self.query_type
            params["limit"] = self._bounded_int("limit", default=20, minimum=1, maximum=200)
        if operation == self.TRENDS:
            params["woeid"] = self._bounded_int("woeid", default=1, minimum=1, maximum=None)
            params["count"] = self._bounded_int("limit", default=20, minimum=1, maximum=50)
        if operation == self.USER_TWEETS:
            params["includeReplies"] = bool(self.include_replies)
            params["includeParentTweet"] = bool(self.include_parent_tweet)
        if operation in {self.SEARCH_TWEETS, self.SEARCH_USERS, self.USER_TWEETS} and self.cursor:
            params["cursor"] = self.cursor

        return params

    def _api_key_value(self) -> str:
        value = self.api_key
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        value = str(value or "").strip()
        if not value:
            msg = "Xquik API key is required."
            raise ValueError(msg)
        return value

    def _required_value(self, field_name: str) -> str:
        value = str(getattr(self, field_name, "") or "").strip()
        if not value:
            msg = f"{field_name.replace('_', ' ').title()} is required for this operation."
            raise ValueError(msg)
        return value

    def _bounded_int(self, field_name: str, *, default: int, minimum: int, maximum: int | None) -> int:
        raw_value = getattr(self, field_name, default) or default
        value = int(raw_value)
        if value < minimum:
            return minimum
        if maximum is not None and value > maximum:
            return maximum
        return value

    def _records_from_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("tweets", "users", "trends", "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [self._record_from_value(item) for item in value]

        result = payload.get("result")
        if isinstance(result, list):
            return [self._record_from_value(item) for item in result]
        if isinstance(result, dict):
            return [self._record_from_value(result)]

        return [self._record_from_value(payload)]

    def _record_from_value(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {"value": value}

    def _payload_to_text(self, payload: dict[str, Any]) -> str:
        records = self._records_from_payload(payload)
        if not records:
            return "No Xquik records returned."
        return "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records)

    def _set_visible(self, build_config: dict, field_name: str, *, visible: bool) -> None:
        if field_name in build_config:
            build_config[field_name]["show"] = visible
