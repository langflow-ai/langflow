"""Slack: List Channel Members (as app) -- Web API ``conversations.members``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.io import BoolInput, IntInput, Output, StrInput
from lfx.schema.data import Data

from lfx_slack._base import BOT_IDENTITY, SlackBaseComponent, bot_connection_input
from lfx_slack._client import next_cursor

if TYPE_CHECKING:
    from lfx_slack._client import SlackClient

CAPABILITY_ID = "slack.bot.list_channel_members"
API_METHOD = "conversations_members"
USERS_INFO_METHOD = "users_info"

# Declared here in the same shape the capability manifest uses so the manifest
# test can prove the component's connection field and the manifest agree.
CONDITIONAL_SCOPES = [
    {"scope": "groups:read", "role": "optional", "condition": {"kind": "input_truthy", "input": "channel_is_private"}},
    {"scope": "users:read", "role": "optional", "condition": {"kind": "input_truthy", "input": "resolve_names"}},
]


class SlackListChannelMembersComponent(SlackBaseComponent):
    display_name = "Slack: List Channel Members (as app)"
    description = "List the members of a Slack conversation the app's bot user can see."
    name = "SlackListChannelMembers"

    capability_id = CAPABILITY_ID
    slack_identity = BOT_IDENTITY

    inputs = [
        bot_connection_input(
            capability=CAPABILITY_ID,
            required_scopes=["channels:read"],
            conditional_scopes=CONDITIONAL_SCOPES,
        ),
        StrInput(
            name="channel",
            display_name="Channel ID",
            required=True,
            info="Conversation ID, for example C0SLACKDEMO.",
        ),
        BoolInput(
            name="channel_is_private",
            display_name="Private channel",
            value=False,
            info="Requests the groups:read scope. The bot must be a member of the private channel.",
        ),
        BoolInput(
            name="resolve_names",
            display_name="Resolve display names",
            value=False,
            info="Calls users.info for each member, which requires the users:read scope.",
        ),
        IntInput(
            name="limit",
            display_name="Members per page",
            value=200,
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
        Output(display_name="Members", name="members", method="build_members"),
        Output(display_name="Pagination", name="pagination", method="build_pagination"),
    ]

    async def _members(self) -> dict:
        channel = (self.channel or "").strip()
        if not channel:
            msg = "Channel ID is required."
            raise ValueError(msg)
        limit = int(self.limit) if self.limit else None
        if limit is not None and limit < 1:
            msg = f"Members per page must be positive; got {limit}."
            raise ValueError(msg)
        cursor = (self.cursor or "").strip() or None
        resolve_names = bool(self.resolve_names)

        async def call(client: SlackClient) -> dict:
            body = await client.call(API_METHOD, channel=channel, limit=limit, cursor=cursor)
            ids = [member for member in body.get("members", []) if isinstance(member, str)]
            if resolve_names:
                body = dict(body)
                body["resolved_members"] = [await self._describe(client, user_id) for user_id in ids]
            return body

        return await self.run_action(call)

    @staticmethod
    async def _describe(client: SlackClient, user_id: str) -> dict:
        """Return the non-secret profile fields for one member."""
        info = await client.call(USERS_INFO_METHOD, user=user_id)
        user = info.get("user")
        user = user if isinstance(user, dict) else {}
        profile = user.get("profile")
        profile = profile if isinstance(profile, dict) else {}
        return {
            "id": user.get("id", user_id),
            "name": user.get("name"),
            "real_name": user.get("real_name") or profile.get("real_name"),
            "display_name": profile.get("display_name"),
            "is_bot": user.get("is_bot"),
        }

    async def build_members(self) -> list[Data]:
        """Return one Data per member, resolved to profile fields when asked."""
        body = await self._members()
        resolved = body.get("resolved_members")
        if isinstance(resolved, list):
            results = [Data(data=member) for member in resolved]
        else:
            results = [Data(data={"id": member}) for member in body.get("members", []) if isinstance(member, str)]
        self.status = f"{len(results)} member(s)"
        return results

    async def build_pagination(self) -> Data:
        """Return the cursor for the next page of members."""
        body = await self._members()
        return Data(data={"next_cursor": next_cursor(body)})
