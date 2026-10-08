import os

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_bundles.sendhq.sendhq_common import request, summary

DIRECTIONS = {"Received": "in", "Sent": "out", "All": None}


class SendHQListEmailsComponent(Component):
    display_name = "SendHQ List Emails"
    description = "List received or sent email in SendHQ, newest first, without full bodies."
    documentation: str = "https://sendhq.cc/docs/inbound"
    icon = "SendHQ"
    name = "SendHQListEmailsComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="SendHQ API Key",
            info="An API key from the SendHQ dashboard at sendhq.cc.",
            value=os.getenv("SENDHQ_API_KEY", ""),
            required=True,
        ),
        DropdownInput(
            name="direction",
            display_name="Direction",
            options=list(DIRECTIONS),
            value="Received",
            info="Received mail (your inbox addresses), sent mail, or both.",
        ),
        BoolInput(
            name="unread_only",
            display_name="Unread Only",
            value=False,
            info="Return only unread messages.",
        ),
        MessageTextInput(
            name="query",
            display_name="Search",
            info="Search subjects, bodies, addresses, and attachment names. Optional.",
            value="",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=10,
            info="Number of emails to return (1-100).",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        params: dict = {"limit": max(1, min(int(self.limit or 10), 100))}
        direction = DIRECTIONS.get(self.direction, "in")
        if direction:
            params["direction"] = direction
        if self.unread_only:
            params["unread"] = "true"
        if (self.query or "").strip():
            params["query"] = self.query.strip()

        ok, response = await request(self.api_key.strip(), "GET", "/emails", params=params)
        if ok:
            emails = [summary(email) for email in response.get("data", [])]
            result = {"emails": emails, "count": len(emails)}
        else:
            result = response

        self.status = result
        return Data(value=result)
