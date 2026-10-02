"""Slack: Read Thread (as user) -- Web API ``conversations.replies``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.io import IntInput, Output, StrInput
from lfx.schema.data import Data

from lfx_slack._base import USER_IDENTITY, SlackBaseComponent, user_connection_input
from lfx_slack._client import next_cursor

if TYPE_CHECKING:
    from lfx_slack._client import SlackClient

CAPABILITY_ID = "slack.user.read_thread"
API_METHOD = "conversations_replies"

REQUIRED_SCOPES = ["channels:history", "groups:history", "im:history", "mpim:history"]


class SlackReadThreadComponent(SlackBaseComponent):
    display_name = "Slack: Read Thread (as user)"
    description = "Read the replies of one Slack thread the connected user can see."
    name = "SlackReadThread"

    capability_id = CAPABILITY_ID
    slack_identity = USER_IDENTITY

    inputs = [
        user_connection_input(capability=CAPABILITY_ID, required_scopes=REQUIRED_SCOPES),
        StrInput(
            name="channel",
            display_name="Channel ID",
            required=True,
            info="Conversation ID, for example C0SLACKDEMO.",
        ),
        StrInput(
            name="ts",
            display_name="Thread timestamp",
            required=True,
            info="Timestamp of the thread's parent message, for example 1700000000.000100.",
        ),
        IntInput(
            name="limit",
            display_name="Replies per page",
            value=100,
            advanced=True,
            info=(
                "Slack caps this at 15 for commercially distributed apps that are not listed in the Slack Marketplace."
            ),
        ),
        StrInput(
            name="cursor",
            display_name="Cursor",
            info="Cursor from a previous run's Pagination output. Leave empty for the first page.",
            advanced=True,
        ),
        StrInput(
            name="oldest",
            display_name="Oldest",
            info="Only replies at or after this timestamp.",
            advanced=True,
        ),
        StrInput(
            name="latest",
            display_name="Latest",
            info="Only replies at or before this timestamp.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Messages", name="messages", method="build_messages"),
        Output(display_name="Pagination", name="pagination", method="build_pagination"),
    ]

    async def _replies(self) -> dict:
        channel = (self.channel or "").strip()
        ts = (self.ts or "").strip()
        if not channel:
            msg = "Channel ID is required."
            raise ValueError(msg)
        if not ts:
            msg = "Thread timestamp is required."
            raise ValueError(msg)
        limit = int(self.limit) if self.limit else None
        if limit is not None and limit < 1:
            msg = f"Replies per page must be positive; got {limit}."
            raise ValueError(msg)

        async def call(client: SlackClient) -> dict:
            return await client.call(
                API_METHOD,
                channel=channel,
                ts=ts,
                limit=limit,
                cursor=(self.cursor or "").strip() or None,
                oldest=(self.oldest or "").strip() or None,
                latest=(self.latest or "").strip() or None,
            )

        return await self.run_action(call)

    async def build_messages(self) -> list[Data]:
        """Return one Data per reply, parent message first."""
        body = await self._replies()
        messages = body.get("messages", [])
        results = [Data(data=message) for message in messages if isinstance(message, dict)]
        self.status = f"{len(results)} message(s)"
        return results

    async def build_pagination(self) -> Data:
        """Return ``has_more`` and the cursor for the next page."""
        body = await self._replies()
        return Data(data={"has_more": bool(body.get("has_more", False)), "next_cursor": next_cursor(body)})
