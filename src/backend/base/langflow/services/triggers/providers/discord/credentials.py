"""Prove the bot and application identity before storing a token."""

from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_discord._client import DiscordClient


async def validate_manual_credential(payload, *, context: str):
    del context
    credentials = payload.credentials
    if (
        payload.provider_key != "discord"
        or payload.ownership_mode.value != "user"
        or payload.executing_identity.identity != "bot"
        or credentials is None
        or credentials.refresh_token is not None
        or credentials.expires_at is not None
    ):
        msg = "Discord requires your own nonexpiring bot token without OAuth refresh settings."
        raise ValueError(msg)

    class Resolver:
        async def resolve(self, _request):
            return ResolvedCredential(access_token=credentials.access_token, provider="discord", identity="bot")

    lease = CredentialLease(
        Resolver(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="discord", name=payload.name),
            principal=ExecutionPrincipal(
                kind="flow_owner", user_id="manual-check", actor_id="manual-check", interactive=True
            ),
        ),
    )
    async with DiscordClient(lease) as client:
        bot = await client.identity()
    identity = payload.executing_identity.model_copy(
        update={"account": ConnectionAccount(id=bot["id"], display=bot["name"])}
    )
    return payload.model_copy(update={"executing_identity": identity, "granted_scopes": []})
