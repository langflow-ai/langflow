from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data
from lfx_turbo_notify import _validation as check
from lfx_turbo_notify._base import TurboNotifyComponent, base_url_input, connection_inputs


class TurboNotifyGetMessageStatusComponent(TurboNotifyComponent):
    """Read the delivery state of one message."""

    display_name = "Turbo Notify: Get Message Status"
    description = "Check whether a message you sent is pending, sent, delivered, read or failed."
    documentation = "https://docs.turbonotify.com/en/messages/status/"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="message_id",
            display_name="Message ID",
            required=True,
            info="The message_id returned when the message was sent (msg_ and 32 characters).",
            tool_mode=True,
        ),
        base_url_input(),
    ]

    outputs = [Output(display_name="Status", name="status_result", method="turbo_notify_get_message_status")]

    async def turbo_notify_get_message_status(self) -> Data:
        """Return ``message_id``, ``state``, ``at`` and ``error``, plus the API ``status`` object."""
        message = check.message_id(self.message_id)
        client = self.client()
        body = await client.request("GET", client.number_path(f"/messages/{message}/status"))
        status = body.get("status") if isinstance(body.get("status"), dict) else {}
        result = {
            "message_id": body.get("message_id", message),
            "state": status.get("state"),
            "at": status.get("at"),
            "error": status.get("error"),
            "status": status,
        }
        self.status = f"State: {result['state']}."
        return Data(data=result)
