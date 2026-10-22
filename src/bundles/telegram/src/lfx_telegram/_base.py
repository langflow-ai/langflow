"""Connection and action execution shared by Telegram components."""

from __future__ import annotations

from typing import ClassVar

from lfx.custom import Component
from lfx.integrations.telemetry import integration_action
from lfx.io import ConnectionRefInput
from lfx.schema.data import Data

from lfx_telegram._client import TelegramClient, redact

AUTH_PROFILE = "telegram-bot-token"


def connection_input(*, capabilities: list[str], required: bool = True) -> ConnectionRefInput:
    """Request only the bot connection owned by this flow's user."""
    return ConnectionRefInput(
        name="connection",
        display_name="Telegram Connection",
        provider="telegram",
        auth_profile_id=AUTH_PROFILE,
        identity_kind="instance",
        ownership_mode="user",
        required_scopes=[],
        capabilities=capabilities,
        required=required,
        info="A BotFather bot token stored in your connection. Triggers also require background-run consent.",
    )


class TelegramActionComponent(Component):
    """Resolve and govern each action through the common connection service."""

    icon = "Send"
    capability_id: ClassVar[str] = ""

    async def send(self, payload: dict, *, expected_bot_id: str | None = None) -> Data:
        lease = self.resolve_connection("connection")
        credential = await lease.get_credential()
        async with (
            integration_action(
                self, provider="telegram", capability=self.capability_id, owner_kind=credential.owner_kind
            ),
            TelegramClient(lease) as client,
        ):
            bot = await client.identity()
            if expected_bot_id is not None and expected_bot_id != bot["id"]:
                from lfx.integrations.errors import ConnectionNotAuthorizedError

                raise ConnectionNotAuthorizedError(
                    provider="telegram", hint="Reply with the bot that received this event."
                )
            result = await client.call("sendMessage", **payload)
        if not isinstance(result, dict) or type(result.get("message_id")) is not int:
            from lfx.integrations.errors import ProviderUnavailableError

            raise ProviderUnavailableError(provider="telegram")
        self.status = "Telegram message sent."
        return Data(
            data=redact(
                {
                    "provider": "telegram",
                    "bot_id": bot["id"],
                    "chat_id": payload["chat_id"],
                    "message_id": result["message_id"],
                    "thread_id": result.get("message_thread_id"),
                    "text": result.get("text", ""),
                }
            )
        )
