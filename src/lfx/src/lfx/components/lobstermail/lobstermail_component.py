"""LobsterMail component for Langflow.

Email infrastructure for AI agents — create inboxes, send/receive email,
and search messages via the LobsterMail API.

API docs: https://lobstermail.ai/docs
OpenAPI spec: https://api.lobstermail.ai/v1/docs/openapi
"""

from __future__ import annotations

from typing import Any

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import (
    DropdownInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from lfx.schema.data import Data

BASE_URL = "https://api.lobstermail.ai"


class LobsterMailComponent(Component):
    display_name = "LobsterMail"
    description = "Email infrastructure for AI agents — create inboxes, send and receive email, and search messages."
    documentation = "https://lobstermail.ai/docs"
    icon = "Mail"
    name = "LobsterMail"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info=("LobsterMail API key (lm_sk_test_... or lm_sk_live_...). Get one free at https://lobstermail.ai"),
            required=True,
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=[
                "Create Inbox",
                "List Inboxes",
                "Send Email",
                "List Emails",
                "Get Email",
                "Search Emails",
                "Get Account",
            ],
            value="Create Inbox",
            info="The LobsterMail operation to perform.",
            real_time_refresh=True,
        ),
        # ── Create Inbox fields ────────────────────────────────────────
        MessageTextInput(
            name="display_name_field",
            display_name="Display Name",
            info="Human-friendly name for the inbox (optional).",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="local_part",
            display_name="Local Part",
            info="Local part of the address (before @). Auto-generated if empty.",
            required=False,
            advanced=True,
        ),
        # ── Send Email fields ──────────────────────────────────────────
        MessageTextInput(
            name="from_address",
            display_name="From",
            info="Sender email address (must be an active inbox).",
            required=False,
        ),
        MessageTextInput(
            name="to_addresses",
            display_name="To",
            info="Recipient email addresses (comma-separated).",
            required=False,
        ),
        MessageTextInput(
            name="subject",
            display_name="Subject",
            info="Email subject line.",
            required=False,
        ),
        MultilineInput(
            name="body_text",
            display_name="Body (Text)",
            info="Plain text email body.",
            required=False,
        ),
        MultilineInput(
            name="body_html",
            display_name="Body (HTML)",
            info="HTML email body (optional).",
            required=False,
            advanced=True,
        ),
        # ── List/Get/Search fields ─────────────────────────────────────
        MessageTextInput(
            name="inbox_id",
            display_name="Inbox ID",
            info="The inbox ID (e.g. ibx_...).",
            required=False,
        ),
        MessageTextInput(
            name="email_id",
            display_name="Email ID",
            info="The email ID (e.g. eml_...). Required for Get Email.",
            required=False,
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Full-text search query. Required for Search Emails.",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="execute_operation"),
    ]

    async def execute_operation(self) -> Data:
        """Execute the selected LobsterMail operation."""
        operation = self.operation
        headers = {
            "Authorization": f"Bearer {self.api_key!s}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=30.0) as client:
            result = await self._dispatch(client, operation)

        return Data(data=result)

    async def _dispatch(self, client: httpx.AsyncClient, operation: str) -> dict[str, Any]:
        if operation == "Create Inbox":
            body: dict[str, str] = {}
            if self.display_name_field:
                body["displayName"] = self.display_name_field
            if self.local_part:
                body["localPart"] = self.local_part
            resp = await client.post("/v1/inboxes", json=body)

        elif operation == "List Inboxes":
            resp = await client.get("/v1/inboxes")

        elif operation == "Send Email":
            if not self.from_address:
                msg = "Send Email requires a 'From' address."
                raise ValueError(msg)
            if not self.to_addresses:
                msg = "Send Email requires at least one 'To' address."
                raise ValueError(msg)
            if not self.subject:
                msg = "Send Email requires a 'Subject'."
                raise ValueError(msg)
            to_list = [a.strip() for a in self.to_addresses.split(",") if a.strip()]
            body_inner: dict[str, str] = {}
            if self.body_text:
                body_inner["text"] = self.body_text
            if self.body_html:
                body_inner["html"] = self.body_html
            payload: dict[str, Any] = {
                "from": self.from_address,
                "to": to_list,
                "subject": self.subject,
                "body": body_inner,
            }
            resp = await client.post("/v1/emails/send", json=payload)

        elif operation == "List Emails":
            if not self.inbox_id:
                msg = "List Emails requires an 'Inbox ID'."
                raise ValueError(msg)
            resp = await client.get(f"/v1/inboxes/{self.inbox_id}/emails")

        elif operation == "Get Email":
            if not self.inbox_id:
                msg = "Get Email requires an 'Inbox ID'."
                raise ValueError(msg)
            if not self.email_id:
                msg = "Get Email requires an 'Email ID'."
                raise ValueError(msg)
            resp = await client.get(f"/v1/inboxes/{self.inbox_id}/emails/{self.email_id}")

        elif operation == "Search Emails":
            if not self.search_query:
                msg = "Search Emails requires a 'Search Query'."
                raise ValueError(msg)
            params: dict[str, str] = {"q": self.search_query}
            if self.inbox_id:
                params["inboxId"] = self.inbox_id
            resp = await client.get("/v1/emails/search", params=params)

        elif operation == "Get Account":
            resp = await client.get("/v1/account")

        else:
            msg = f"Unknown operation: {operation}"
            raise ValueError(msg)

        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
