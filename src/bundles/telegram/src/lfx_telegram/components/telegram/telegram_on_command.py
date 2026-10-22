"""Declare a trigger for commands addressed to a Telegram bot."""

from lfx.io import StrInput

from lfx_telegram._triggers import TelegramTriggerComponent, trigger_inputs


class TelegramOnCommandTriggerComponent(TelegramTriggerComponent):
    display_name = "Telegram: On Command"
    description = "Receive bot commands in explicitly allowed chats, with optional command and sender filters."
    name = "TelegramOnCommandTrigger"
    trigger_kind = "telegram.command"
    capability_ids = ("telegram.trigger.command.webhook", "telegram.trigger.command.poll")
    config_fields = (*TelegramTriggerComponent.config_fields, "commands")
    inputs = [
        *trigger_inputs("command"),
        StrInput(
            name="commands",
            display_name="Commands",
            is_list=True,
            value=[],
            info="Command names without the leading slash. Empty means every command addressed to this bot.",
        ),
    ]
