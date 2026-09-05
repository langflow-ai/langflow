"""Slack: Search (as user) -- Web API ``search.messages``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, StrInput
from lfx.schema.data import Data

from lfx_slack._base import USER_IDENTITY, SlackBaseComponent, user_connection_input
from lfx_slack._client import next_cursor

if TYPE_CHECKING:
    from lfx_slack._client import SlackClient

CAPABILITY_ID = "slack.user.search"
API_METHOD = "search_messages"

MAX_COUNT = 100
MIN_COUNT = 1


class SlackSearchComponent(SlackBaseComponent):
    display_name = "Slack: Search (as user)"
    description = "Search Slack messages with the connected user's visibility."
    name = "SlackSearch"

    capability_id = CAPABILITY_ID
    slack_identity = USER_IDENTITY

    inputs = [
        user_connection_input(capability=CAPABILITY_ID, required_scopes=["search:read"]),
        MessageTextInput(
            name="query",
            display_name="Query",
            required=True,
            info="Slack search query, using the same modifiers as the Slack search bar (for example 'in:#general').",
        ),
        IntInput(
            name="count",
            display_name="Results per page",
            value=20,
            info=f"Between {MIN_COUNT} and {MAX_COUNT}.",
            advanced=True,
        ),
        DropdownInput(
            name="sort",
            display_name="Sort by",
            options=["score", "timestamp"],
            value="score",
            advanced=True,
        ),
        DropdownInput(
            name="sort_dir",
            display_name="Sort direction",
            options=["desc", "asc"],
            value="desc",
            advanced=True,
        ),
        StrInput(
            name="cursor",
            display_name="Cursor",
            info="Cursor from a previous run's Pagination output. Leave empty for the first page.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Matches", name="matches", method="build_matches"),
        Output(display_name="Pagination", name="pagination", method="build_pagination"),
    ]

    def _request_count(self) -> int:
        count = int(self.count or 20)
        if not MIN_COUNT <= count <= MAX_COUNT:
            msg = f"Results per page must be between {MIN_COUNT} and {MAX_COUNT}; got {count}."
            raise ValueError(msg)
        return count

    async def _search(self) -> dict:
        query = (self.query or "").strip()
        if not query:
            msg = "Query is required."
            raise ValueError(msg)
        count = self._request_count()
        cursor = (self.cursor or "").strip() or None

        async def call(client: SlackClient) -> dict:
            return await client.call(
                API_METHOD,
                query=query,
                count=count,
                sort=self.sort or "score",
                sort_dir=self.sort_dir or "desc",
                cursor=cursor,
            )

        return await self.run_action(call)

    async def build_matches(self) -> list[Data]:
        """Return one Data per matching message."""
        body = await self._search()
        messages = body.get("messages")
        matches = messages.get("matches", []) if isinstance(messages, dict) else []
        results = [Data(data=match) for match in matches if isinstance(match, dict)]
        self.status = f"{len(results)} match(es)"
        return results

    async def build_pagination(self) -> Data:
        """Return Slack's pagination block plus the cursor for the next page."""
        body = await self._search()
        messages = body.get("messages")
        pagination = messages.get("pagination", {}) if isinstance(messages, dict) else {}
        payload = dict(pagination) if isinstance(pagination, dict) else {}
        payload["next_cursor"] = next_cursor(body)
        return Data(data=payload)
