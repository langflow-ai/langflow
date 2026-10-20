# Salt Interests: set, read, or clear this agent's follow settings for a
# chat -- who gets notified of a new message in a room nobody @mentioned
# or replied to it in (saltapp 0.2.0's `mode`: "addressed", today's
# unwritten default, "keywords", or "all"). Thin wrapper over
# SaltClient.get_chat_subscription/set_chat_subscription/
# clear_chat_subscription (`/api/v1/chats/:id/subscription`); salt-api
# itself refuses this against an encrypted chat (422, "Salt cannot read
# an encrypted room, so it cannot follow it for you.") -- this component
# does not pre-check that, it just relays whatever the server says.
#
# No private_key/passphrase fields: unlike the other components in this
# package, which keep those two fields present-but-unused for a
# consistent field layout (see saltapp-langflow AGENTS.md, "The keyless boundary"), a
# subscription is a plain per-agent setting record with no message
# content anywhere near it, so there is no future path where this
# component would start using them either.
from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from . import _salt_common as sc

VALID_ACTIONS = {"set", "get", "clear"}
VALID_MODES = {"addressed", "keywords", "all"}


class SaltInterestsComponent(Component):
    display_name = "Salt Interests"
    description = "Set, read, or clear this agent's follow settings (interests) for a Salt chat."
    icon = "bell"
    name = "SaltInterests"

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
            required=False,
            info="This agent's own Salt id. Kept for consistency with the other Salt components; not sent to the API.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="This agent's Salt API key.",
        ),
        MessageTextInput(
            name="chat_id",
            display_name="Chat ID",
            tool_mode=True,
            info="The Salt chat to set, read, or clear this agent's interests for.",
        ),
        DropdownInput(
            name="action",
            display_name="Action",
            options=sorted(VALID_ACTIONS),
            value="set",
            tool_mode=True,
            info='What to do: "set" (subscribe using mode/keywords), "get" (read the current setting), '
            'or "clear" (revert to the default, "addressed").',
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=sorted(VALID_MODES),
            required=False,
            tool_mode=True,
            info='Required when action is "set": "addressed" (mentions/replies only, today\'s default), '
            '"keywords", or "all" (every message).',
        ),
        MessageTextInput(
            name="keywords",
            display_name="Keywords",
            required=False,
            tool_mode=True,
            info='Comma-separated keywords. Only used when mode is "keywords".',
        ),
    ]

    outputs = [Output(display_name="Result", name="result", method="apply")]

    def apply(self) -> Data:
        action = (self.action or "").strip().lower()
        if action not in VALID_ACTIONS:
            self.status = f'Unknown action {self.action!r}; expected "set", "get", or "clear".'
            return Data(data={"status": "error", "error": self.status})

        mode = (self.mode or "").strip().lower() or None
        if action == "set" and mode not in VALID_MODES:
            self.status = 'action="set" needs a mode: "addressed", "keywords", or "all".'
            return Data(data={"status": "error", "error": self.status})

        client = sc.get_client(self.host)
        try:
            if action == "set":
                keywords = sc.parse_options(self.keywords) if mode == "keywords" else None
                result = client.set_chat_subscription(self.api_key, self.chat_id, mode, keywords=keywords)
                self.status = f"Set interests for chat {self.chat_id} to {mode!r}."
            elif action == "get":
                result = client.get_chat_subscription(self.api_key, self.chat_id)
                self.status = f"Interests for chat {self.chat_id}: {result.get('mode', 'unknown')!r}."
            else:  # action == "clear"
                result = client.clear_chat_subscription(self.api_key, self.chat_id)
                self.status = f"Cleared interests for chat {self.chat_id} (back to the default)."
        finally:
            client.close()

        return Data(data=result)
