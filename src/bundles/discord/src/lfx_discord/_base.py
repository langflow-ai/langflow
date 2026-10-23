"""Connection-backed Discord actions."""

from __future__ import annotations

import hashlib
from typing import ClassVar
from uuid import uuid4

from lfx.custom import Component
from lfx.integrations.errors import ConnectionNotAuthorizedError, InvalidRequestError
from lfx.integrations.telemetry import integration_action
from lfx.io import ConnectionRefInput
from lfx.schema.data import Data

from lfx_discord._client import DiscordClient, snowflake


def connection_input(capability: str, *, required: bool = True):
    return ConnectionRefInput(
        name="connection",
        display_name="Discord Connection",
        provider="discord",
        auth_profile_id="discord-bot-token",
        identity_kind="instance",
        ownership_mode="user",
        required_scopes=[],
        capabilities=[capability],
        required=required,
        info="Your application bot token. Background triggers also require explicit consent.",
    )


MAX_MESSAGE_UNITS = 2000


class DiscordActionComponent(Component):
    icon = "MessageCircle"
    capability_id: ClassVar[str] = ""

    async def send(
        self,
        *,
        guild_id: str,
        channel_id: str,
        text: str,
        message_id: str | None = None,
        expected_bot: str | None = None,
    ) -> Data:
        guild_id, channel_id = snowflake(guild_id), snowflake(channel_id)
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-16-le")) // 2 > MAX_MESSAGE_UNITS:
            msg = "Discord message text must contain 1 to 2000 characters."
            raise InvalidRequestError(msg, provider="discord")
        if message_id is not None:
            message_id = snowflake(message_id)
        lease = self.resolve_connection("connection")
        credential = await lease.get_credential()
        async with (
            integration_action(
                self, provider="discord", capability=self.capability_id, owner_kind=credential.owner_kind
            ),
            DiscordClient(lease) as client,
        ):
            bot = await client.identity()
            if expected_bot is not None and bot["id"] != expected_bot:
                raise ConnectionNotAuthorizedError(
                    provider="discord", hint="Reply with the bot that received this event."
                )
            await client.channel(guild_id, channel_id)
            payload = {"content": text, "allowed_mentions": {"parse": [], "replied_user": False}}
            if message_id is not None:
                payload["message_reference"] = {
                    "message_id": message_id,
                    "channel_id": channel_id,
                    "guild_id": guild_id,
                    "fail_if_not_exists": True,
                }
            run_id = str(getattr(self.graph, "run_id", "")) if self.graph else ""
            if run_id:
                # Each invocation is a new send; its payload keeps one nonce during transport.
                payload["nonce"] = hashlib.sha256(
                    f"{run_id}:{self._id}:{channel_id}:{text}:{message_id}:{uuid4().hex}".encode()
                ).hexdigest()[:25]
                payload["enforce_nonce"] = True
            result = await client.request("POST", f"/channels/{channel_id}/messages", payload=payload)
            result_id = snowflake(result.get("id"))
            if result.get("channel_id") != channel_id:
                msg = "Discord returned a different message channel."
                raise InvalidRequestError(msg, provider="discord")
        self.status = "Discord message sent."
        return Data(
            data={
                "provider": "discord",
                "bot_id": bot["id"],
                "guild_id": guild_id,
                "channel_id": channel_id,
                "message_id": result_id,
                "text": result.get("content", ""),
                "session_key": f"discord:{bot['id']}:{guild_id}:{channel_id}",
            }
        )
