"""Shared pieces of the two Slack trigger components.

A Slack trigger node is a declaration, like every trigger node: it never opens
a socket or verifies a request. The server reads its fields on each flow save,
decides which Slack transport the trigger runs on from the connection it names
(an OAuth bot installation receives the Events API, an app-level token connection
holds a Socket Mode socket), and at run time the node hands the firing event to
the rest of the flow. The flow never names a transport, so the same flow JSON
runs on hosted Langflow, a self-managed instance, and Langflow Desktop.
"""

from __future__ import annotations

from typing import Any, ClassVar

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import ConnectionRefInput, StrInput

from lfx_slack._base import CONNECTION_FIELD
from lfx_slack._client import PROVIDER_ID

#: One capability per trigger per transport: the Events API on a bot
#: installation, Socket Mode on an app-level token.
MESSAGE_CAPABILITIES = ("slack.trigger.message.events_api", "slack.trigger.message.socket_mode")
REACTION_CAPABILITIES = ("slack.trigger.reaction.events_api", "slack.trigger.reaction.socket_mode")


def trigger_connection_input(*, capabilities: tuple[str, ...]) -> ConnectionRefInput:
    """The connection a Slack trigger listens through.

    No ``auth_profile_id`` and no required scopes, on purpose: either Slack
    connection type can back a trigger, and which one decides the transport.
    Not required either, so the downstream flow can be built and run by hand
    before a connection exists; the trigger simply cannot be armed until one is
    chosen.
    """
    return ConnectionRefInput(
        name=CONNECTION_FIELD,
        display_name="Slack Connection",
        provider=PROVIDER_ID,
        auth_profile_id="",
        required_scopes=[],
        # The picker's vocabulary, which maps bot identities to "instance".
        identity_kind="instance",
        # Trigger arming requires a connection owned by the flow owner.
        ownership_mode="user",
        capabilities=list(capabilities),
        required=False,
        info=(
            "Either a Slack app installation (hosted, or self-managed with a public URL: events arrive through "
            "the Slack Events API) or an app-level token connection (Langflow Desktop, or an instance Slack "
            "cannot reach: events arrive over Socket Mode). Required before the trigger can be armed."
        ),
    )


def channels_input() -> StrInput:
    return StrInput(
        name="channels",
        display_name="Channel IDs",
        is_list=True,
        value=[],
        info=(
            "Only fire for these conversations, by ID (for example C0123456789, from the channel's details). "
            "Leave empty for every conversation the app can see."
        ),
    )


class SlackTriggerComponent(BaseTriggerComponent):
    """Base for the Slack trigger nodes."""

    icon = "Slack"
    provider = PROVIDER_ID
    needs_connection = True

    #: Manifest capabilities this node can arm, one per transport.
    capability_ids: ClassVar[tuple[str, ...]] = ()
    #: Node fields copied into the stored configuration on flow save.
    config_fields: ClassVar[tuple[str, ...]] = ()

    def trigger_config(self) -> dict[str, Any]:
        """The raw field values; the server normalizes and validates them on save."""
        config = {name: getattr(self, name, None) for name in self.config_fields}
        config[CONNECTION_FIELD] = getattr(self, CONNECTION_FIELD, None) or None
        return config

    def slack_event(self) -> dict[str, Any]:
        """The normalized Slack event this run was started with, or ``{}``."""
        event, _problem = self._firing_event()
        payload = event.get("payload")
        return payload if isinstance(payload, dict) else {}
