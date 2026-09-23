"""Fire a flow when a third-party system posts a signed request to Langflow."""

from __future__ import annotations

import json
from typing import Any

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import BoolInput, MultilineInput


class InboundWebhookTriggerError(ValueError):
    """The webhook cannot be armed as configured."""


def validate_payload_schema(raw: str) -> dict[str, Any] | None:
    """Parse the optional payload schema, or return None when it is empty.

    Deliberately shallow: this checks that the schema is a JSON object, not that
    it is valid JSON Schema. The server applies it, and a component that
    duplicated the server's validation logic would be a second opinion about
    what a caller's payload must look like.
    """
    if not raw or raw.isspace():
        return None
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        msg = "The payload schema must be valid JSON, or empty to accept any body."
        raise InboundWebhookTriggerError(msg) from exc
    if not isinstance(parsed, dict):
        msg = "The payload schema must be a JSON object."
        raise InboundWebhookTriggerError(msg)
    return parsed


class InboundWebhookTriggerComponent(BaseTriggerComponent):
    display_name = "Inbound Webhook"
    description = "Run this flow when a signed HTTP request arrives at this trigger's own URL."
    documentation: str = "https://docs.langflow.org/triggers"
    name = "InboundWebhookTrigger"
    icon = "Webhook"

    trigger_kind = "inbound_webhook"

    inputs = [
        MultilineInput(
            name="payload_schema",
            display_name="Payload schema",
            value="",
            info=(
                "Optional JSON object describing the body you expect. "
                "Leave empty to accept any JSON body. It documents the contract for whoever "
                "calls this webhook; it does not replace the signature check."
            ),
            input_types=[],
            advanced=True,
        ),
        BoolInput(
            name="share_session",
            display_name="Share session across deliveries",
            value=False,
            info=(
                "Off: every delivery gets its own session. On: all deliveries share one session, "
                "so an agent downstream keeps memory between calls."
            ),
            advanced=True,
        ),
    ]

    def trigger_config(self) -> dict[str, Any]:
        """The JSON the flow-save reconciler copies onto the trigger row.

        The URL and the signing secret are deliberately absent: they are minted
        by the server and live on the trigger row, because a secret on the
        canvas would travel in every flow export and every screenshot.
        """
        schema = validate_payload_schema(self.payload_schema or "")
        config: dict[str, Any] = {"share_session": bool(self.share_session)}
        if schema is not None:
            config["payload_schema"] = schema
        return config
