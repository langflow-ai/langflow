"""Receive Discord guild message events through the listener process."""

from lfx_discord._triggers import DiscordTriggerComponent, trigger_inputs


class DiscordOnMessageTriggerComponent(DiscordTriggerComponent):
    display_name = "Discord: On Message"
    description = "Receive new human messages in explicitly allowed guild channels."
    name = "DiscordOnMessage"
    trigger_kind = "discord.message"
    inputs = trigger_inputs("message")
