"""Validate a manually installed BotFather token before persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.integrations.models import ConnectionAccount, ConnectionRef, CredentialLease, ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_telegram._client import TelegramClient

if TYPE_CHECKING:
    from langflow.services.database.models.connection.schemas import ConnectionCreate


async def validate_manual_credential(payload: ConnectionCreate, *, context: str) -> ConnectionCreate:
    del context
    credentials = payload.credentials
    if (
        payload.provider_key != "telegram"
        or payload.ownership_mode.value != "user"
        or payload.executing_identity.identity != "bot"
        or credentials is None
        or credentials.refresh_token is not None
        or credentials.expires_at is not None
    ):
        msg = "Telegram requires your own bot connection with a BotFather token and no OAuth refresh settings."
        raise ValueError(msg)

    class Resolver:
        async def resolve(self, _request):
            return ResolvedCredential(access_token=credentials.access_token, provider="telegram", identity="bot")

    from lfx.integrations.models import ConnectionResolutionRequest

    lease = CredentialLease(
        Resolver(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="telegram", name=payload.name),
            principal=ExecutionPrincipal(
                kind="flow_owner", user_id="manual-check", actor_id="manual-check", interactive=True
            ),
        ),
    )
    async with TelegramClient(lease) as client:
        bot = await client.identity()
    identity = payload.executing_identity.model_copy(
        update={"account": ConnectionAccount(id=bot["id"], display=bot["username"])}
    )
    return payload.model_copy(update={"executing_identity": identity, "granted_scopes": []})
