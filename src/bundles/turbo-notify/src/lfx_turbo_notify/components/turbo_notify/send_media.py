from lfx.io import DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx_turbo_notify import _validation as check
from lfx_turbo_notify._base import TurboNotifyComponent, base_url_input, connection_inputs


class TurboNotifySendMediaComponent(TurboNotifyComponent):
    """Send an image, video, audio file, document or sticker from a public web address."""

    display_name = "Turbo Notify: Send Media"
    description = "Send an image, video, audio file, document or sticker from a public URL on your own WhatsApp number."
    documentation = "https://docs.turbonotify.com/en/messages/send-media/"

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
        DropdownInput(
            name="media_type",
            display_name="Media Type",
            options=list(check.MEDIA_TYPES),
            value="image",
            info="What the file is. Turbo Notify downloads it from the URL before it goes to WhatsApp.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="media_url",
            display_name="Media URL",
            required=True,
            info="A public http:// or https:// address of the file.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="caption",
            display_name="Caption",
            info="Optional, 1 to 1024 characters. For an image, video or document only.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="filename",
            display_name="File Name",
            info="Optional name shown on a document in the chat. For a document only.",
            advanced=True,
            tool_mode=True,
        ),
        base_url_input(),
    ]

    outputs = [Output(display_name="Sent Message", name="message", method="turbo_notify_send_media")]

    async def turbo_notify_send_media(self) -> Data:
        """Send the media and return the API answer (``message_id`` and ``status``)."""
        to = check.recipient(phone=self.phone, contact=self.contact_id, group=self.group_id)
        content = check.media_content(
            media_type=self.media_type, media_url=self.media_url, caption=self.caption, filename=self.filename
        )
        client = self.client()
        body = await client.request("POST", client.number_path("/messages"), body={"to": to, "content": content})
        self.status = f"Message {body.get('message_id', '')} accepted."
        return Data(data=body)
