"""Declare a trigger for messages from explicitly allowed Telegram chats."""

from lfx_telegram._triggers import TelegramTriggerComponent, trigger_inputs


class TelegramOnMessageTriggerComponent(TelegramTriggerComponent):
    display_name = "Telegram: On Message"
    description = "Receive new text messages visible to your bot in explicitly allowed chats."
    name = "TelegramOnMessageTrigger"
    trigger_kind = "telegram.message"
    capability_ids = ("telegram.trigger.message.webhook", "telegram.trigger.message.poll")
    inputs = trigger_inputs("message")
