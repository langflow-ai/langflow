"""Sendblue fixed-destination REST operations for Langflow."""

import re

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.schema.data import Data

MAX_PAGE_SIZE = 100


class SendblueComponent(Component):
    display_name = "Sendblue"
    description = "Send text messages and read message history, delivery status, and sending lines."
    documentation = "https://docs.sendblue.com/"
    icon = "Sendblue"
    name = "Sendblue"

    inputs = [
        SecretStrInput(name="api_key", display_name="API Key", required=True),
        SecretStrInput(name="api_secret", display_name="API Secret", required=True),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["List Messages", "List Lines", "Get Message Status", "Send Message"],
            value="List Messages",
        ),
        MessageTextInput(
            name="number",
            display_name="Phone Number",
            info="E.164 recipient for sends; optional conversation filter for message history.",
            value="",
            tool_mode=True,
        ),
        MultilineInput(
            name="content", display_name="Message", info="Exact text approved for sending.", value="", tool_mode=True
        ),
        MessageTextInput(
            name="from_number",
            display_name="Sending Line",
            info="Your Sendblue E.164 line. Required for free shared-line plans.",
            value="",
        ),
        MessageTextInput(
            name="handle",
            display_name="Message Handle",
            info="Handle returned by Sendblue when sending.",
            value="",
            tool_mode=True,
        ),
        IntInput(name="limit", display_name="Limit", value=20, info="Maximum history results, 1 to 100."),
        IntInput(name="offset", display_name="Offset", value=0, advanced=True),
        BoolInput(
            name="allow_sending",
            display_name="Allow Sending",
            value=False,
            info=(
                "Enable only after reviewing this flow. "
                "For agents, require human approval of the recipient and exact text."
            ),
        ),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]

    async def build_result(self) -> Data:
        if not self.api_key or not self.api_secret:
            msg = "Both Sendblue API key and API secret are required"
            raise ValueError(msg)
        method, path, params, body = "GET", "", None, None
        if self.operation == "List Lines":
            path = "/api/v2/lines/state"
        elif self.operation == "List Messages":
            if not 1 <= self.limit <= MAX_PAGE_SIZE or self.offset < 0:
                msg = "Limit must be between 1 and 100; offset must be non-negative"
                raise ValueError(msg)
            path = "/api/v2/messages"
            params = {"limit": self.limit, "offset": self.offset}
            if self.number:
                params["number"] = self.number
        elif self.operation == "Get Message Status":
            if not self.handle.strip():
                msg = "Message handle is required"
                raise ValueError(msg)
            path, params = "/api/status", {"handle": self.handle}
        elif self.operation == "Send Message":
            if not self.allow_sending:
                msg = "Enable Allow Sending only after reviewing the flow and approving recipient and content"
                raise ValueError(msg)
            if not re.fullmatch(r"\+[1-9]\d{7,14}", self.number) or (
                self.from_number and not re.fullmatch(r"\+[1-9]\d{7,14}", self.from_number)
            ):
                msg = "Phone numbers must use E.164 format"
                raise ValueError(msg)
            if not self.content.strip():
                msg = "Message text is required"
                raise ValueError(msg)
            method, path = "POST", "/api/send-message"
            body = {"number": self.number, "content": self.content}
            if self.from_number:
                body["from_number"] = self.from_number
        else:
            msg = "Unknown Sendblue operation"
            raise ValueError(msg)
        headers = {"sb-api-key-id": self.api_key, "sb-api-secret-key": self.api_secret}
        try:
            # A timeout can happen after a send is accepted. Never retry writes.
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
                response = await client.request(
                    method, "https://api.sendblue.co" + path, headers=headers, params=params, json=body
                )
            if not response.is_success:
                result = {"error": f"Sendblue returned HTTP {response.status_code}"}
            else:
                data = response.json()
                result = data if isinstance(data, dict) else {"data": data}
        except httpx.RequestError:
            result = {"error": "Sendblue request failed. Check message history before retrying a send."}
        except ValueError:
            result = {"error": "Sendblue returned invalid JSON"}
        self.status = result
        return Data(data=result)
