from lfx.io import MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data
from lfx_turbo_notify import _validation as check
from lfx_turbo_notify._base import TurboNotifyComponent, base_url_input, connection_inputs, idempotency_key_input


class TurboNotifyReplyComponent(TurboNotifyComponent):
    """Quote an earlier message in the same chat and reply to it."""

    display_name = "Turbo Notify: Reply"
    description = "Reply to an earlier WhatsApp message, quoting it in the chat."
    documentation = "https://docs.turbonotify.com/en/messages/send/"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="message_id",
            display_name="Message ID",
            required=True,
            info="The ID of the message to quote (msg_ and 32 characters), from the same number.",
            tool_mode=True,
        ),
        MultilineInput(
            name="text",
            display_name="Text",
            required=True,
            info="The reply, 1 to 4096 characters.",
            tool_mode=True,
        ),
        idempotency_key_input(),
        base_url_input(),
    ]

    outputs = [Output(display_name="Sent Message", name="message", method="turbo_notify_reply")]

    async def turbo_notify_reply(self) -> Data:
        """Send the reply and return the API answer (``message_id`` and ``status``)."""
        quoted = check.message_id(self.message_id)
        text = check.require_text(self.text, field="Text", code="invalid_text", maximum=check.MAX_TEXT_LENGTH)
        key = check.idempotency_key(self.idempotency_key)
        client = self.client()
        body = await client.request(
            "POST",
            client.number_path(f"/messages/{quoted}/reply"),
            body={"content": {"text": text}},
            idempotency_key=key,
        )
        self.status = f"Reply {body.get('message_id', '')} accepted."
        return Data(data=body)
