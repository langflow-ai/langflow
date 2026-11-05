"""Validate a bounded guild receiver without credential-bearing settings."""

from lfx.integrations.models import ConnectionRef
from lfx_discord._client import snowflake

MAX_CHANNELS = 100

FIELDS = ("connection", "guild_id", "channel_ids", "session_scope", "delivery_mode")


def normalize_config(kind: str, config: dict) -> dict:
    if kind not in {"discord.message", "discord.mention"} or set(config) - set(FIELDS):
        msg = "Unsupported Discord trigger configuration."
        raise ValueError(msg)
    ref = ConnectionRef.parse(config.get("connection"))
    if ref.provider != "discord":
        msg = "Choose a Discord connection."
        raise ValueError(msg)
    channels = config.get("channel_ids")
    if not isinstance(channels, list) or not 1 <= len(channels) <= MAX_CHANNELS:
        msg = "Choose between 1 and 100 explicit Discord channel or thread IDs."
        raise ValueError(msg)
    channels = sorted({snowflake(value) for value in channels})
    scope = config.get("session_scope") or "channel"
    if scope not in {"channel", "sender"} or (config.get("delivery_mode") or "auto") != "auto":
        msg = "Discord supports the supervised Gateway transport and channel or sender sessions."
        raise ValueError(msg)
    return {
        "connection": str(ref),
        "guild_id": snowflake(config.get("guild_id")),
        "channel_ids": channels,
        "session_scope": scope,
        "delivery_mode": "auto",
    }
