from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from .textkit_common import DOCUMENTATION_URL, TextKitError, error_data, textkit_request

DEFAULT_LIMIT = 25
MIN_LIMIT = 1
MAX_LIMIT = 100
ANY = "any"
DIRECTIONS = [ANY, "outbound", "inbound"]
STATUSES = [ANY, "queued", "sent", "delivered", "failed", "blocked", "received"]
MESSAGE_FIELDS = ("id", "to", "from", "body", "direction", "status", "created_at")


class TextKitListMessagesComponent(Component):
    """List sent and received messages from TextKit."""

    display_name = "TextKit List Messages"
    description = "List your sent and received texts, newest first."
    documentation = DOCUMENTATION_URL
    icon = "MessagesSquare"

    inputs = [
        SecretStrInput(
            name="textkit_api_key",
            display_name="TextKit API Key",
            required=True,
            info="Your TextKit API key (ssms_sk_...).",
        ),
        MessageTextInput(
            name="phone_number",
            display_name="Phone Number",
            required=False,
            info="Only messages to or from this number, in E.164 format.",
            tool_mode=True,
        ),
        DropdownInput(
            name="message_direction",
            display_name="Direction",
            options=DIRECTIONS,
            value=ANY,
            required=False,
            advanced=True,
            info="Only sent (outbound) or received (inbound) messages.",
        ),
        DropdownInput(
            name="message_status",
            display_name="Status",
            options=STATUSES,
            value=ANY,
            required=False,
            advanced=True,
            info="Only messages with this status.",
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=DEFAULT_LIMIT,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=MIN_LIMIT, max=MAX_LIMIT, step=1, step_type="int"),
            info="How many messages to return (1-100).",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Table", name="dataframe", method="textkit_list_messages"),
    ]

    def _params(self) -> dict[str, str | int]:
        requested = DEFAULT_LIMIT if self.limit is None else int(self.limit)
        params: dict[str, str | int] = {"limit": max(MIN_LIMIT, min(requested, MAX_LIMIT))}
        phone_number = (self.phone_number or "").strip()
        if phone_number:
            params["number"] = phone_number
        if self.message_direction and self.message_direction != ANY:
            params["direction"] = self.message_direction
        if self.message_status and self.message_status != ANY:
            params["status"] = self.message_status
        return params

    @staticmethod
    def _to_row(message: dict) -> Data:
        return Data(text=message.get("body") or "", data={field: message.get(field) for field in MESSAGE_FIELDS})

    async def textkit_list_messages(self) -> DataFrame:
        """Fetch one page of messages and return them as a table."""
        try:
            payload = await textkit_request(self.textkit_api_key, "GET", "/messages", params=self._params())
        except TextKitError as e:
            rows = [error_data(str(e))]
        else:
            rows = [self._to_row(message) for message in payload.get("data") or [] if isinstance(message, dict)]
        self.status = rows
        return DataFrame(rows)
