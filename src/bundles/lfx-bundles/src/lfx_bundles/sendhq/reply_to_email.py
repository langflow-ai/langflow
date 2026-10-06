import os

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.sendhq.sendhq_common import reply_route, request


class SendHQReplyToEmailComponent(Component):
    display_name = "SendHQ Reply to Email"
    description = "Answer a SendHQ email inside the same conversation thread."
    documentation: str = "https://sendhq.cc/docs/inbound"
    icon = "SendHQ"
    name = "SendHQReplyToEmailComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="SendHQ API Key",
            info="An API key from the SendHQ dashboard at sendhq.cc.",
            value=os.getenv("SENDHQ_API_KEY", ""),
            required=True,
        ),
        MessageTextInput(
            name="email_id",
            display_name="Email ID",
            info="ID of the email being answered, which starts with 'em_'.",
            value="",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="body",
            display_name="Reply",
            info="Plain-text reply.",
            value="",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="from_email",
            display_name="From",
            info=(
                "Sender for the reply. Leave empty to reply from the address that received the original "
                "(or sent it, for a follow-up)."
            ),
            value=os.getenv("SENDHQ_FROM_EMAIL", ""),
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        email_id = (self.email_id or "").strip()
        api_key = self.api_key.strip()
        if not email_id:
            result = {"error": "Provide the ID of the email being answered."}
        elif not (self.body or "").strip():
            result = {"error": "Provide a reply."}
        else:
            ok, parent = await request(api_key, "GET", f"/emails/{email_id}")
            if not ok:
                result = parent
            else:
                sender, recipients, subject = reply_route(parent, (self.from_email or "").strip() or None)
                if not sender or not recipients:
                    result = {"error": "Could not work out the sender or recipient of the reply."}
                else:
                    payload = {
                        "from": sender,
                        "to": recipients,
                        "subject": subject,
                        "text": self.body,
                        "reply_to_email_id": email_id,
                    }
                    await logger.ainfo("Sending reply with SendHQ")
                    ok, response = await request(api_key, "POST", "/emails", json=payload)
                    result = (
                        {"id": response.get("id"), "thread_id": response.get("threadId"), "to": recipients}
                        if ok
                        else response
                    )

        self.status = result
        return Data(value=result)
