import os

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.sendhq.sendhq_common import request, split_addresses


class SendHQSendEmailComponent(Component):
    display_name = "SendHQ Send Email"
    description = "Send an email from your verified domain with SendHQ."
    documentation: str = "https://sendhq.cc/docs/sending"
    icon = "SendHQ"
    name = "SendHQSendEmailComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="SendHQ API Key",
            info="An API key from the SendHQ dashboard at sendhq.cc.",
            value=os.getenv("SENDHQ_API_KEY", ""),
            required=True,
        ),
        MessageTextInput(
            name="from_email",
            display_name="From",
            info="Sender, such as 'Support <support@example.com>'. The domain must be verified in SendHQ.",
            value=os.getenv("SENDHQ_FROM_EMAIL", ""),
            required=True,
        ),
        MessageTextInput(
            name="to",
            display_name="To",
            info="Recipient address. Separate several with commas.",
            value="",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="subject",
            display_name="Subject",
            info="Subject line.",
            value="",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="body",
            display_name="Body",
            info="Plain-text message body.",
            value="",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="cc",
            display_name="CC",
            info="Carbon-copy addresses, separated with commas. Optional.",
            value="",
            advanced=True,
        ),
        MessageTextInput(
            name="reply_to",
            display_name="Reply-To",
            info="Address that replies should go to. Optional.",
            value="",
            advanced=True,
        ),
        MultilineInput(
            name="html",
            display_name="HTML Body",
            info="Optional HTML version of the body.",
            value="",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        recipients = split_addresses(self.to)
        payload = {
            "from": (self.from_email or "").strip(),
            "to": recipients,
            "subject": self.subject or "",
            "text": self.body or "",
        }
        if self.html:
            payload["html"] = self.html
        if split_addresses(self.cc):
            payload["cc"] = split_addresses(self.cc)
        if (self.reply_to or "").strip():
            payload["reply_to"] = self.reply_to.strip()

        if not recipients:
            result = {"error": "Provide at least one recipient."}
        elif not payload["text"].strip():
            result = {"error": "Provide a message body."}
        else:
            await logger.ainfo("Sending email with SendHQ")
            ok, response = await request(self.api_key.strip(), "POST", "/emails", json=payload)
            if ok:
                result = {"id": response.get("id"), "thread_id": response.get("threadId"), "to": recipients}
                await logger.ainfo("SendHQ accepted the email")
            else:
                result = response
                await logger.awarning("SendHQ did not accept the email")

        self.status = result
        return Data(value=result)
