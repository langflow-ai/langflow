"""Normalize only human message creates in explicit guild channels."""

from lfx_discord._client import snowflake

# Nitro messages can exceed the separate outbound bot limit.
MAX_MESSAGE_UNITS = 4000


def normalize(data: dict, *, bot_id: str, kind: str, config: dict) -> dict | None:
    if (
        not isinstance(data, dict)
        or data.get("guild_id") != config["guild_id"]
        or data.get("channel_id") not in config["channel_ids"]
    ):
        return None
    author = data.get("author")
    if not isinstance(author, dict) or author.get("bot") or data.get("webhook_id") or data.get("type") not in {0, 19}:
        return None
    author_id = snowflake(author.get("id"))
    if author_id == bot_id:
        return None
    mentions = data.get("mentions", [])
    if kind == "discord.mention" and (
        not isinstance(mentions, list)
        or not any(isinstance(user, dict) and user.get("id") == bot_id for user in mentions)
    ):
        return None
    text = data.get("content")
    if not isinstance(text, str) or len(text.encode("utf-16-le")) // 2 > MAX_MESSAGE_UNITS:
        return None
    message_id = snowflake(data.get("id"))
    channel_id = data["channel_id"]
    key = f"discord:{bot_id}:{config['guild_id']}:{channel_id}"
    if config.get("session_scope") == "sender":
        key += f":{author_id}"
    return {
        "provider": "discord",
        "bot_id": bot_id,
        "guild_id": config["guild_id"],
        "channel_id": channel_id,
        "message_id": message_id,
        "sender_id": author_id,
        "text": text,
        "session_key": key,
    }
