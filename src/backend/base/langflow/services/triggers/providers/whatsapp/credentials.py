"""Verify system-user credentials before persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_whatsapp._client import WhatsAppClient

if TYPE_CHECKING:
    from langflow.services.database.models.connection.schemas import ConnectionCreate


async def validate_manual_credential(payload: ConnectionCreate, *, context: str) -> ConnectionCreate:
    if (
        context not in {"hosted", "self_managed"}
        or payload.provider_key != "whatsapp"
        or payload.ownership_mode.value != "user"
        or payload.executing_identity.identity != "service"
        or payload.credentials is None
        or payload.credentials.refresh_token is not None
        or payload.credentials.token_type != "Bearer"  # noqa: S105
    ):
        msg = "WhatsApp requires your own system-user token on a configured hosted or self-managed server."
        raise ValueError(msg)
    credentials = payload.credentials

    class Resolver:
        async def resolve(self, _request):
            return ResolvedCredential(access_token=credentials.access_token, provider="whatsapp", identity="service")

    lease = CredentialLease(
        Resolver(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="whatsapp", name=payload.name),
            principal=ExecutionPrincipal(
                kind="flow_owner", user_id="manual-check", actor_id="manual-check", interactive=True
            ),
        ),
    )
    async with WhatsAppClient(lease) as client:
        scopes, expires_at = await client.verify_account()
        account = ConnectionAccount(
            id=client.config.phone_id, display="WhatsApp business phone", tenant_id=client.config.tenant
        )
    return payload.model_copy(
        update={
            "executing_identity": payload.executing_identity.model_copy(update={"account": account}),
            "granted_scopes": sorted(scopes),
            "credentials": credentials.model_copy(update={"expires_at": expires_at}),
        }
    )
