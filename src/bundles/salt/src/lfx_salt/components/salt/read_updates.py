# Salt Read Updates (was Salt Trigger/Listen): read this agent's Salt
# updates for whatever is new since the last check, in exactly ONE call,
# instead of Langflow's built-in Webhook component. See saltapp-langflow AGENTS.md and
# saltapp-langflow README.md for why not the built-in Webhook (short version: Webhook
# exposes only the request BODY, never headers, and Salt's signature
# lives in a header; an unverified card_interaction/invoice_paid/
# chat_opened payload is plaintext and actionable, so it must never be
# trusted unverified).
#
# On demand, not poll-and-wait: this component's build method runs once
# per flow invocation and returns immediately with whatever one
# GET /api/v1/agent/updates call finds -- no loop, no sleep, no wait
# budget. It is meant to sit at the start of a flow that is itself
# triggered on its own schedule/cron/manual run and pick up whatever is
# new since last time. Genuine push needs a persistent process outside
# this package; see saltapp-langflow README.md's "Push vs. on-demand" section.
#
# ONE POLLER PER AGENT, still, even after 2026-09-26: this is now the
# ONLY component in this package that reads GET /api/v1/agent/updates
# (Salt Ask Human moved to reading its own card directly and no longer
# shares this cursor -- see _salt_common.get_card's docstring and
# saltapp-langflow HANDOFF.md's 2026-09-26 entry). salt-api keeps exactly ONE
# `agent_updates_acked_id` per agent, not one per caller, so running two
# concurrent checks against the SAME agent_id (two Read Updates calls, or
# one beside a socket-mode Agent/any other consumer of that agent's
# outbox) can still resolve rows out from under one another. Never wire
# this component into Salt Ask Human's check -- Ask Human must keep
# reading its own card, never this outbox.
from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, MultilineSecretInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx_salt.components.salt import _salt_common as sc

KNOWN_EVENT_TYPES = {
    "message",
    "card_interaction",
    "invoice_paid",
    "chat_opened",
    "handoff_confirmed",
    "handoff_received",
}


class SaltReadUpdatesComponent(Component):
    display_name = "Salt Read Updates"
    description = (
        "Check once for this agent's new Salt events (message, card tap, payment, chat opened, or "
        "hand-off) since the last check, verifying each one's signature first. "
        "ONE POLLER PER AGENT: this agent has a single shared position server-side, so running this "
        "concurrently with another Read Updates check (or any other consumer of this agent's updates) "
        "against the same agent can silently miss events."
    )
    icon = "radio"
    name = "SaltReadUpdates"

    inputs = [
        StrInput(
            name="host",
            display_name="Salt Host",
            value=sc.SALT_HOST_DEFAULT,
            info="The Salt deployment this agent is registered on.",
        ),
        StrInput(
            name="agent_id",
            display_name="Agent ID",
            info="This agent's own Salt id, used to namespace this component's local check-cursor file.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="This agent's Salt API key.",
        ),
        MultilineSecretInput(
            name="private_key",
            display_name="Agent Private Key (optional)",
            required=False,
            info=(
                "Not needed here: every event this returns is metadata or structured data, "
                f"never PGP ciphertext. {sc.KEYLESS_INFO}"
            ),
        ),
        SecretStrInput(
            name="passphrase",
            display_name="Private Key Passphrase (optional)",
            required=False,
            info="Not needed here -- this component never decrypts anything.",
        ),
        MessageTextInput(
            name="event_types",
            display_name="Event Types",
            required=False,
            info=(
                "Comma-separated event types to look for: message, card_interaction, invoice_paid, "
                "chat_opened, handoff_confirmed, handoff_received. Blank means any of them."
            ),
        ),
    ]

    outputs = [Output(display_name="Events", name="events", method="read")]

    def read(self) -> Data:
        wanted = {t for t in sc.parse_options(self.event_types) if t in KNOWN_EVENT_TYPES}

        client = sc.get_client(self.host)
        try:
            identity = sc.resolve_identity(client, self.api_key)
            secret = identity.get("webhook_secret")
            agent_id = self.agent_id or identity.get("agent_id") or ""
            if not secret:
                self.status = "This agent has no webhook secret yet; cannot verify events."
                return Data(data={"status": "no_secret"})

            def matches(event: Any) -> bool:
                if event.type == "unknown":
                    return False
                return not wanted or event.type in wanted

            # This package's own local mirror of the one true position
            # salt-api keeps for this agent (see
            # sc.READ_UPDATES_POLL_PURPOSE's docstring) -- not shared with
            # any other component in this package any more (Salt Ask
            # Human no longer polls this outbox at all), but still not
            # safe to run concurrently with another consumer of the same
            # agent's outbox; see this module's own header comment.
            cursor = sc.PersistentCursor(sc.state_dir(agent_id, sc.READ_UPDATES_POLL_PURPOSE) / "cursor.json")
            events, _new_cursor = sc.check_for_event(
                client,
                self.api_key,
                secret=secret,
                cursor=cursor,
                predicate=matches,
            )
        finally:
            client.close()

        if not events:
            self.status = "No new events since last check."
            return Data(data={"status": "no_new_events", "events": []})

        self.status = f"{len(events)} new event(s)."
        return Data(
            data={
                "status": "events",
                "events": [
                    {
                        "event_type": event.type,
                        "delivery_id": event.delivery_id,
                        "created_at": event.created_at,
                        "body": event.body,
                    }
                    for event in events
                ],
            }
        )
