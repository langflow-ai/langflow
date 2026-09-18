"""Post a message into a Teams chat (POST /chats/{id}/messages)."""

from __future__ import annotations

from typing import Any

from lfx_microsoft.base import (
    Data,
    DataInput,
    DropdownInput,
    MessageTextInput,
    MicrosoftGraphComponent,
    MultilineInput,
    Output,
    as_dict_list,
)
from lfx_microsoft.manifest import connection_input

CONTENT_TYPES = ["text", "html"]


class TeamsChatPostComponent(MicrosoftGraphComponent):
    """Send a chat message as the connected user.

    Personal Microsoft accounts are not supported by Graph for this action, and
    the action posts into an existing chat; it cannot create one.
    """

    display_name = "Teams: Post Chat Message"
    description = "Post a message into an existing Microsoft Teams chat."
    documentation = "https://learn.microsoft.com/en-us/graph/api/chat-post-messages"
    name = "TeamsPostChatMessage"
    capability_id = "microsoft.teams.chat_post"

    inputs = [
        connection_input(capability_id),
        MessageTextInput(
            name="chat_id",
            display_name="Chat ID",
            info="The id of an existing chat the connected user belongs to.",
            required=True,
        ),
        MultilineInput(name="content", display_name="Message", required=True),
        DropdownInput(
            name="content_type",
            display_name="Content Type",
            options=CONTENT_TYPES,
            value="text",
            advanced=True,
        ),
        DataInput(name="mentions", display_name="Mentions", is_list=True, advanced=True),
        DataInput(name="attachments", display_name="Attachments", is_list=True, advanced=True),
    ]

    outputs = [Output(display_name="Message", name="message", method="post_message")]

    def _payload(self) -> dict[str, Any]:
        content_type = self.content_type if self.content_type in CONTENT_TYPES else "text"
        payload: dict[str, Any] = {"body": {"contentType": content_type, "content": self.content}}
        if mentions := as_dict_list(self.mentions):
            payload["mentions"] = mentions
        if attachments := as_dict_list(self.attachments):
            payload["attachments"] = attachments
        return payload

    async def post_message(self) -> Data:
        """Post the message and return the created chatMessage resource."""
        chat_id = (self.chat_id or "").strip()
        lease = self.lease()
        async with self.action(lease) as client:
            response = await client.request(
                "POST",
                f"/chats/{chat_id}/messages",
                json_body=self._payload(),
            )
        created = response.json() if response.content else {}
        result = Data(data=created if isinstance(created, dict) else {"response": created})
        self.status = result.data.get("id", "posted")
        return result
