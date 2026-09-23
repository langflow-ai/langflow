"""Slack: On Message -- run a flow when a message is posted where the app can see it."""

from __future__ import annotations

from lfx.io import BoolInput, MultiselectInput, Output
from lfx.schema.message import Message

from lfx_slack._triggers import (
    MESSAGE_CAPABILITIES,
    SlackTriggerComponent,
    channels_input,
    trigger_connection_input,
)

CONVERSATION_TYPES = ["channel", "group", "im", "mpim"]


class SlackOnMessageTriggerComponent(SlackTriggerComponent):
    display_name = "Slack: On Message"
    description = (
        "Run this flow when someone posts in Slack: in a channel, a private channel, a direct message or a "
        "group DM, or when they mention the app."
    )
    documentation = "https://docs.langflow.org/bundles-slack#slack-on-message"
    name = "SlackOnMessageTrigger"

    trigger_kind = "slack.message"
    capability_ids = MESSAGE_CAPABILITIES
    config_fields = (
        "channels",
        "conversation_types",
        "mentions_only",
        "include_thread_replies",
        "include_bot_messages",
        "include_edits",
    )

    inputs = [
        trigger_connection_input(capabilities=MESSAGE_CAPABILITIES),
        BoolInput(
            name="mentions_only",
            display_name="Only when the app is mentioned",
            value=False,
            info="Fire only for messages that @-mention the app, instead of every message it can see.",
        ),
        channels_input(),
        MultiselectInput(
            name="conversation_types",
            display_name="Conversation types",
            options=CONVERSATION_TYPES,
            value=list(CONVERSATION_TYPES),
            info=(
                "channel: public channels. group: private channels. im: direct messages with the app. "
                "mpim: group direct messages."
            ),
            advanced=True,
        ),
        BoolInput(
            name="include_thread_replies",
            display_name="Include thread replies",
            value=True,
            info="Replies share their thread's session, so an agent keeps the whole thread as memory.",
            advanced=True,
        ),
        BoolInput(
            name="include_bot_messages",
            display_name="Include messages from other bots",
            value=False,
            info="This app's own messages never fire the trigger, so a flow that replies cannot trigger itself.",
            advanced=True,
        ),
        BoolInput(
            name="include_edits",
            display_name="Include edits and deletions",
            value=False,
            info="Also fire when a message is edited or deleted; the event's subtype says which.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Event", name="trigger_event", method="build_event"),
        Output(display_name="Message", name="message", method="build_message"),
    ]

    def build_message(self) -> Message:
        """The message text, ready to hand to an agent or a prompt."""
        event = self.slack_event()
        text = event.get("text") or ""
        self.status = text or "No Slack message: this run was not started by a trigger."
        return Message(text=text)
