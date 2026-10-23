"""Validate the WhatsApp receiver's public configuration."""

from lfx.integrations.models import ConnectionRef
from lfx_whatsapp._components import recipient

MAX_SENDERS = 1000


def normalize_config(kind: str, config: dict) -> dict:
    if kind != "whatsapp.event" or set(config) - {
        "connection",
        "allowed_senders",
        "receive_messages",
        "receive_statuses",
        "delivery_mode",
    }:
        msg = "Unsupported WhatsApp trigger configuration."
        raise ValueError(msg)
    connection = config.get("connection")
    if connection:
        ref = ConnectionRef.parse(connection)
        if ref.provider != "whatsapp":
            msg = "Use a WhatsApp connection."
            raise ValueError(msg)
        connection = ref.to_handle()
    senders = config.get("allowed_senders") or []
    if not isinstance(senders, list) or len(senders) > MAX_SENDERS:
        msg = "Provide at most 1000 allowed WhatsApp senders."
        raise ValueError(msg)
    senders = sorted({recipient(value) for value in senders})
    messages = config.get("receive_messages", True)
    statuses = config.get("receive_statuses", True)
    if (
        type(messages) is not bool
        or type(statuses) is not bool
        or not (messages or statuses)
        or config.get("delivery_mode") not in {None, "auto", "push"}
    ):
        msg = "Select at least one WhatsApp event type and push delivery."
        raise ValueError(msg)
    return {
        "connection": connection,
        "allowed_senders": senders,
        "receive_messages": messages,
        "receive_statuses": statuses,
        "delivery_mode": "push",
    }
