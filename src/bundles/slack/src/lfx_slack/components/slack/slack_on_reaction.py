"""Slack: On Reaction -- run a flow when a reaction is added to (or removed from) a message."""

from __future__ import annotations

from lfx.io import DropdownInput, StrInput

from lfx_slack._triggers import (
    REACTION_CAPABILITIES,
    SlackTriggerComponent,
    channels_input,
    trigger_connection_input,
)


class SlackOnReactionTriggerComponent(SlackTriggerComponent):
    display_name = "Slack: On Reaction"
    description = "Run this flow when someone adds or removes an emoji reaction on a Slack message."
    documentation = "https://docs.langflow.org/bundles-slack#slack-on-reaction"
    name = "SlackOnReactionTrigger"

    trigger_kind = "slack.reaction"
    capability_ids = REACTION_CAPABILITIES
    config_fields = ("channels", "emoji", "reaction_events")

    inputs = [
        trigger_connection_input(capabilities=REACTION_CAPABILITIES),
        StrInput(
            name="emoji",
            display_name="Emoji",
            is_list=True,
            value=[],
            info="Emoji names without colons, for example 'rocket'. Leave empty for any reaction.",
        ),
        channels_input(),
        DropdownInput(
            name="reaction_events",
            display_name="Fire when a reaction is",
            options=["added", "removed", "both"],
            value="added",
            info="Added, removed, or either.",
            advanced=True,
        ),
    ]
