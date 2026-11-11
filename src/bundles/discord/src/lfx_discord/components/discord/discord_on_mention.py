"""Receive Discord guild mention events through the listener process."""

from lfx_discord._triggers import DiscordTriggerComponent, trigger_inputs


class DiscordOnMentionTriggerComponent(DiscordTriggerComponent):
    display_name = "Discord: On Mention"
    description = "Receive new human mentions in explicitly allowed guild channels."
    name = "DiscordOnMention"
    trigger_kind = "discord.mention"
    inputs = trigger_inputs("mention")
