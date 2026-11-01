"""Send a fax: prepare a document, quote it to one number, queue the fax, optionally wait."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.faxforagents._common import (
    DEFAULT_BASE_URL,
    E164_RE,
    TERMINAL_STATES,
    FaxForAgentsError,
    agent_evidence,
    call_api,
    error_data,
    require_id,
)


class FaxForAgentsSendFaxComponent(Component):
    display_name = "Send Fax"
    description = (
        "Prepare a document from text or Markdown, quote it to one fax number and queue the fax through "
        "Fax for Agents. Answers queued unless Wait for delivery is on."
    )
    documentation: str = "https://faxforagents.com/docs/api/"
    icon = "FaxForAgents"
    name = "FaxForAgentsSendFaxComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Fax for Agents API Key",
            info=(
                "From app.faxforagents.com. An ffa_test_ key reaches the sandbox only, "
                "an ffa_live_ key spends the wallet."
            ),
            required=True,
        ),
        MessageTextInput(
            name="to",
            display_name="To",
            info=(
                "The destination fax number in E.164, for example +12025550123. "
                "With a test key +15550000001 is delivered."
            ),
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="content",
            display_name="Content",
            info="The text or Markdown of the fax, rendered to a letter PDF.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="content_format",
            display_name="Content format",
            options=["text", "markdown"],
            value="text",
            info="How the content is rendered.",
        ),
        MessageTextInput(
            name="cover_subject",
            display_name="Cover sheet subject",
            info="Any cover field adds a billable cover page in front of the document.",
            advanced=True,
        ),
        MessageTextInput(name="cover_message", display_name="Cover sheet message", advanced=True),
        MessageTextInput(name="cover_to_name", display_name="Cover sheet, to name", advanced=True),
        MessageTextInput(name="cover_from_name", display_name="Cover sheet, from name", advanced=True),
        MessageTextInput(
            name="approval_id",
            display_name="Approval ID",
            info=(
                "An approved request bound to this send (apr_...), "
                "when the account needs a human approval for live sends."
            ),
            advanced=True,
        ),
        MessageTextInput(
            name="client_reference",
            display_name="Client reference",
            info="Your own reference stored on the fax, up to 200 characters.",
            advanced=True,
        ),
        MessageTextInput(
            name="idempotency_key",
            display_name="Idempotency key",
            info=(
                "Sent as the Idempotency-Key header. Empty derives it from the send inputs (destination, content, "
                "format, cover fields, approval id, client reference and base URL), so a re-run with identical "
                "inputs within 24 hours is refused instead of sending and billing a second fax. "
                "A different key sends it again."
            ),
            advanced=True,
        ),
        BoolInput(
            name="wait_for_delivery",
            display_name="Wait for delivery",
            value=False,
            info="Poll until delivered, partial, failed or unknown. Off answers once the fax is queued.",
            advanced=True,
        ),
        IntInput(
            name="wait_timeout",
            display_name="Wait timeout (seconds)",
            value=600,
            advanced=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="API base URL",
            value=DEFAULT_BASE_URL,
            info="Only change it to point the component at a test double.",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Fax", name="fax", method="send")]

    poll_interval: float = 3.0

    def _cover(self) -> dict[str, str]:
        return {
            k: v.strip()
            for k, v in (
                ("subject", self.cover_subject),
                ("message", self.cover_message),
                ("to_name", self.cover_to_name),
                ("from_name", self.cover_from_name),
            )
            if v and v.strip()
        }

    def derived_idempotency_key(self) -> str:
        """``langflow:`` plus the SHA-256 of every input that shapes the document, the quote and the send.

        Computed before any call, so a re-run with identical inputs presents the same key with a new quote id
        in the body, which the API refuses with 409 ``idempotency_key_conflict`` instead of billing twice.
        """
        inputs: dict[str, Any] = {
            "base_url": (self.base_url or DEFAULT_BASE_URL).rstrip("/"),
            "to": (self.to or "").strip(),
            "content_format": self.content_format or "text",
            "content": self.content or "",
            "cover": self._cover(),
            "approval_id": (self.approval_id or "").strip(),
            "client_reference": (self.client_reference or "").strip()[:200],
        }
        canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "langflow:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def send(self) -> Data:
        try:
            to = (self.to or "").strip()
            if not E164_RE.match(to):
                msg = "To must be a fax number in E.164, for example +12025550123."
                raise ValueError(msg)
            if not (self.content or "").strip():
                msg = "Content is empty."
                raise ValueError(msg)
            base = self.base_url or DEFAULT_BASE_URL
            own_key = (self.idempotency_key or "").strip()
            key = own_key or self.derived_idempotency_key()
            await logger.ainfo("Fax for Agents: preparing the document")
            document = await call_api(
                self.api_key, "POST", "/v1/documents", base_url=base, json={self.content_format or "text": self.content}
            )
            cover = self._cover()
            quote = await call_api(
                self.api_key,
                "POST",
                "/v1/fax-quotes",
                base_url=base,
                json={"document_id": document["id"], "to": to, "cover": cover or None},
            )
            approval = require_id(self.approval_id, "Approval ID") if (self.approval_id or "").strip() else None
            if quote.get("authorization_required") and not approval:
                result = {
                    "error": (
                        "This send needs a human approval. A person approves the quote in the dashboard, then pass "
                        "the approval id. Nothing was sent."
                    ),
                    "error_code": "approval_required",
                    "quote_id": quote["id"],
                    "document_id": document["id"],
                    "quote": quote,
                }
                self.status = result
                return Data(data=result)
            try:
                job = await call_api(
                    self.api_key,
                    "POST",
                    "/v1/faxes",
                    base_url=base,
                    json={
                        "quote_id": quote["id"],
                        "approval_id": approval,
                        "client_reference": (self.client_reference or "").strip()[:200] or None,
                    },
                    headers={"Idempotency-Key": key},
                )
            except FaxForAgentsError as exc:
                if exc.code != "idempotency_key_conflict":
                    raise
                await logger.awarning("Fax for Agents: the idempotency key was already used, nothing was sent")
                if own_key:
                    explanation = (
                        "This idempotency key was already used for a different send in the last 24 hours, "
                        "so this run sent nothing. A different idempotency key sends it again."
                    )
                else:
                    explanation = (
                        "A fax with the same inputs was already sent in the last 24 hours, so this run sent nothing. "
                        "A different idempotency key sends it again."
                    )
                result = {
                    "error": explanation,
                    "error_code": exc.code,
                    "http_status": exc.status,
                    "idempotency_key": key,
                    "quote_id": quote["id"],
                    "document_id": document["id"],
                }
                self.status = result
                return Data(data=result)
            await logger.ainfo("Fax for Agents: fax queued")
            poll_error: dict[str, Any] | None = None
            if self.wait_for_delivery:
                try:
                    deadline = asyncio.get_running_loop().time() + float(self.wait_timeout or 600)
                    while job.get("state") not in TERMINAL_STATES and asyncio.get_running_loop().time() < deadline:
                        await asyncio.sleep(self.poll_interval)
                        job = await call_api(self.api_key, "GET", f"/v1/faxes/{job['id']}", base_url=base)
                except Exception as exc:  # noqa: BLE001
                    await logger.aexception("Fax for Agents: the fax is queued but polling its status failed")
                    poll_error = error_data(exc)
            result = {
                "fax_id": job["id"],
                "state": job.get("state"),
                "quote_id": quote["id"],
                "document_id": document["id"],
                "billable_pages": quote.get("billable_pages"),
                "amount_micro": quote.get("amount_micro"),
                "idempotency_key": key,
                "fax": agent_evidence(job),
            }
            if poll_error is not None:
                result["poll_error"] = poll_error
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("Fax for Agents: send failed")
            result = error_data(exc)
        self.status = result
        return Data(data=result)
