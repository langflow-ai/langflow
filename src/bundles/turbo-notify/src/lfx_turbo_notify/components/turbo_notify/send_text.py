from lfx.io import MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data
from lfx_turbo_notify import _validation as check
from lfx_turbo_notify._base import TurboNotifyComponent, base_url_input, connection_inputs, idempotency_key_input


class TurboNotifySendTextComponent(TurboNotifyComponent):
    """Send a WhatsApp text message to a phone number, a contact or a group."""

    display_name = "Turbo Notify: Send Text"
    description = "Send a WhatsApp text message from your own number to a phone number, a contact or a group."
    documentation = "https://docs.turbonotify.com/en/messages/send/"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="phone",
            display_name="Phone Number",
            info="Recipient phone number in international format, such as +12025550123. Fill in only one recipient.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="contact_id",
            display_name="Contact ID",
            info="A Turbo Notify contact ID (ct_ and 32 characters). Fill in only one recipient.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="group_id",
            display_name="Group ID",
            info="A Turbo Notify group ID (grp_ and 32 characters). Fill in only one recipient.",
            tool_mode=True,
        ),
        MultilineInput(
            name="text",
            display_name="Text",
            required=True,
            info="The message, 1 to 4096 characters.",
            tool_mode=True,
        ),
        idempotency_key_input(),
        base_url_input(),
    ]

    outputs = [Output(display_name="Sent Message", name="message", method="turbo_notify_send_text")]

    async def turbo_notify_send_text(self) -> Data:
        """Send the text and return the API answer (``message_id`` and ``status``)."""
        to = check.recipient(phone=self.phone, contact=self.contact_id, group=self.group_id)
        text = check.require_text(self.text, field="Text", code="invalid_text", maximum=check.MAX_TEXT_LENGTH)
        key = check.idempotency_key(self.idempotency_key)
        client = self.client()
        body = await client.request(
            "POST", client.number_path("/messages"), body={"to": to, "content": {"text": text}}, idempotency_key=key
        )
        self.status = f"Message {body.get('message_id', '')} accepted."
        return Data(data=body)
