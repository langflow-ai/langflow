"""Verify system-user credentials before persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.integrations.errors import ConnectionNotAuthorizedError, InvalidRequestError
from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_whatsapp._client import (
    PHONE_MEMBERSHIP_HINT,
    SERVER_CONFIGURATION_HINT,
    SYSTEM_USER_HINT,
    WhatsAppClient,
)

from langflow.services.connection.slack_credentials import ManualCredentialError

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
        raise ManualCredentialError(msg)
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
    try:
        async with WhatsAppClient(lease) as client:
            scopes, expires_at = await client.verify_account()
            account = ConnectionAccount(
                id=client.config.phone_id, display="WhatsApp business phone", tenant_id=client.config.tenant
            )
    except ConnectionNotAuthorizedError as exc:
        if exc.hint in {SYSTEM_USER_HINT, PHONE_MEMBERSHIP_HINT}:
            raise ManualCredentialError(exc.hint) from None
        raise
    except InvalidRequestError as exc:
        if exc.safe_message == SERVER_CONFIGURATION_HINT:
            raise ManualCredentialError(SERVER_CONFIGURATION_HINT) from None
        raise
    return payload.model_copy(
        update={
            "executing_identity": payload.executing_identity.model_copy(update={"account": account}),
            "granted_scopes": sorted(scopes),
            "credentials": credentials.model_copy(update={"expires_at": expires_at}),
        }
    )
