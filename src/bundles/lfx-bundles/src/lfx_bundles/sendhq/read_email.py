import os

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_bundles.sendhq.sendhq_common import detail, path_id, request


class SendHQReadEmailComponent(Component):
    display_name = "SendHQ Read Email"
    description = "Read one SendHQ email, or its whole conversation."
    documentation: str = "https://sendhq.cc/docs/api-reference/emails"
    icon = "SendHQ"
    name = "SendHQReadEmailComponent"

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
            info="The email's ID, which starts with 'em_'.",
            value="",
            required=True,
            tool_mode=True,
        ),
        BoolInput(
            name="whole_thread",
            display_name="Whole Conversation",
            value=False,
            info="Return every sent and received message in the email's thread, oldest first.",
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        email_id = (self.email_id or "").strip()
        api_key = self.api_key.strip()
        if not email_id:
            result = {"error": "Provide an email ID."}
        else:
            ok, email = await request(api_key, "GET", f"/emails/{path_id(email_id)}")
            if not ok:
                result = email
            elif not self.whole_thread:
                result = detail(email)
            else:
                thread_id = email.get("threadId") or email_id
                ok, thread = await request(api_key, "GET", f"/threads/{path_id(thread_id)}")
                result = (
                    {
                        "thread_id": thread.get("id"),
                        "subject": thread.get("subject"),
                        "messages": [detail(message) for message in thread.get("data", [])],
                    }
                    if ok
                    else thread
                )

        self.status = result
        return Data(value=result)
