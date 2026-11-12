from lfx.io import BoolInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx_turbo_notify import _validation as check
from lfx_turbo_notify._base import TurboNotifyComponent, base_url_input, connection_inputs

DEFAULT_LIMIT = 50


class TurboNotifyListGroupsComponent(TurboNotifyComponent):
    """List the WhatsApp groups the number takes part in."""

    display_name = "Turbo Notify: List Groups"
    description = "List the WhatsApp groups of your number with their IDs, to send to a group or read its messages."
    documentation = "https://docs.turbonotify.com/en/groups/overview/"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="group_name",
            display_name="Name Contains",
            info="Optional. Only groups whose name contains this text.",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=DEFAULT_LIMIT,
            info="How many groups to return, from 1 to 200.",
            tool_mode=True,
        ),
        BoolInput(
            name="include_left",
            display_name="Include Groups Left",
            value=False,
            info="Also list groups the number has already left.",
            advanced=True,
        ),
        MessageTextInput(
            name="cursor",
            display_name="Cursor",
            info="Optional. The cursor of the previous page, to read the next page.",
            advanced=True,
            tool_mode=True,
        ),
        base_url_input(),
    ]

    outputs = [Output(display_name="Groups", name="groups", method="turbo_notify_list_groups")]

    async def turbo_notify_list_groups(self) -> Data:
        """Return ``groups`` (a list), ``has_more`` and the ``cursor`` for the next page."""
        params: dict[str, str | int | bool] = {"limit": check.page_size(self.limit, default=DEFAULT_LIMIT)}
        name = check.as_text(self.group_name)
        if name:
            params["name"] = name
        if self.include_left:
            params["include_left"] = "true"
        cursor = check.cursor(self.cursor)
        if cursor:
            params["cursor"] = cursor
        client = self.client()
        page = await client.request("GET", client.number_path("/groups"), params=params)
        groups = page.get("data") if isinstance(page.get("data"), list) else []
        self.status = f"{len(groups)} groups."
        return Data(data={"groups": groups, "has_more": bool(page.get("has_more")), "cursor": page.get("cursor")})
