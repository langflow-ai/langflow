from lfx.io import DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx_turbo_notify import _validation as check
from lfx_turbo_notify._base import TurboNotifyComponent, base_url_input, connection_inputs

DEFAULT_LIMIT = 20


class TurboNotifyGetMessagesComponent(TurboNotifyComponent):
    """Read the recent messages of a number, newest first."""

    display_name = "Turbo Notify: Get Messages"
    description = "Read recent WhatsApp messages of your number, newest first. Filter by direction, contact or group."
    documentation = "https://docs.turbonotify.com/en/messages/list/"

    inputs = [
        *connection_inputs(),
        DropdownInput(
            name="direction",
            display_name="Direction",
            options=list(check.DIRECTIONS),
            value="any",
            info="inbound for messages received, outbound for messages sent, any for both.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="contact_id",
            display_name="Contact ID",
            info="Optional. Only messages this contact sent or received (ct_ and 32 characters).",
            tool_mode=True,
        ),
        MessageTextInput(
            name="group_id",
            display_name="Group ID",
            info="Optional. Only messages of this group (grp_ and 32 characters).",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=DEFAULT_LIMIT,
            info="How many messages to return, from 1 to 200.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="cursor",
            display_name="Cursor",
            info="Optional. The cursor of the previous page, to read the next page of the same filters.",
            advanced=True,
            tool_mode=True,
        ),
        base_url_input(),
    ]

    outputs = [Output(display_name="Messages", name="messages", method="turbo_notify_get_messages")]

    async def turbo_notify_get_messages(self) -> Data:
        """Return ``messages`` (a list), ``has_more`` and the ``cursor`` for the next page."""
        params: dict[str, str | int] = {"limit": check.page_size(self.limit, default=DEFAULT_LIMIT)}
        direction = check.direction(self.direction)
        if direction:
            params["direction"] = direction
        if check.as_text(self.contact_id):
            params["contact_id"] = check.contact_id(self.contact_id)
        if check.as_text(self.group_id):
            params["group_id"] = check.group_id(self.group_id)
        cursor = check.cursor(self.cursor)
        if cursor:
            params["cursor"] = cursor
        client = self.client()
        page = await client.request("GET", client.number_path("/messages"), params=params)
        messages = page.get("data") if isinstance(page.get("data"), list) else []
        self.status = f"{len(messages)} messages."
        return Data(data={"messages": messages, "has_more": bool(page.get("has_more")), "cursor": page.get("cursor")})
