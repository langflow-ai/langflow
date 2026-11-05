"""Reserve one app/WABA callback and clean up only that exact override."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from lfx.integrations.errors import ConnectionNotAuthorizedError
from lfx.integrations.models import ConnectionAccount
from lfx_whatsapp._client import WhatsAppClient, settings
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import TriggerCleanup, TriggerSubscription
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
from langflow.services.triggers.ingress.verifiers import IngressSecrets, state_digest
from langflow.services.triggers.source_clients import source_lease
from langflow.services.triggers.source_errors import SourceConfigurationError
from langflow.services.triggers.source_subscription import source_ingress_url

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease, ResolvedCredential
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger


MAX_CALLBACK = 200


async def prepare(session: AsyncSession, trigger: Trigger) -> None:
    config = settings()
    key = f"waba:{config.tenant}"
    connection = await session.get(Connection, trigger.connection_id) if trigger.connection_id else None
    identity = connection.executing_identity if connection else {}
    account = identity.get("account")
    if (
        connection is None
        or connection.provider_key != "whatsapp"
        or identity.get("identity") != "service"
        or not isinstance(account, dict)
        or account.get("id") != config.phone_id
        or account.get("tenant_id") != config.tenant
    ):
        msg = "Reconnect WhatsApp to verify the configured app, WABA and phone."
        raise SourceConfigurationError(msg)
    address = await source_ingress_url(session, trigger)
    if len(address) > MAX_CALLBACK:
        msg = "WhatsApp callback URLs must contain at most 200 characters."
        raise SourceConfigurationError(msg)
    pending_statement = select(TriggerCleanup.id).where(
        TriggerCleanup.provider == "whatsapp", TriggerCleanup.provider_subscription_id == key
    )
    if (await session.exec(pending_statement)).first() is not None:
        msg = "WhatsApp receiver cleanup is pending. Retry after it finishes."
        raise SourceConfigurationError(msg)
    row = (
        await session.exec(
            select(TriggerSubscription)
            .where(TriggerSubscription.provider == "whatsapp", TriggerSubscription.provider_subscription_id == key)
            .with_for_update()
        )
    ).first()
    if row is not None and row.state != "expired":
        if row.trigger_id != trigger.id:
            msg = "This app/WABA already has a receiver. One WhatsApp trigger may own it."
            raise SourceConfigurationError(msg)
        if (
            row.connection_id != trigger.connection_id
            or row.provider_state.get("callback_url") != address
            or row.provider_state.get("phone_id") != config.phone_id
        ):
            msg = "Disable the receiver and finish cleanup before changing its connection or phone."
            raise SourceConfigurationError(msg)
        return
    siblings = (
        await session.exec(
            select(TriggerSubscription.id).where(
                TriggerSubscription.trigger_id == trigger.id, TriggerSubscription.state != "expired"
            )
        )
    ).first()
    if siblings is not None:
        msg = "Finish cleanup of the previous WhatsApp receiver before changing accounts."
        raise SourceConfigurationError(msg)
    try:
        async with session.begin_nested():
            if row is not None:
                await session.delete(row)
                await session.flush()
            row = TriggerSubscription(
                trigger_id=trigger.id,
                connection_id=trigger.connection_id,
                provider="whatsapp",
                provider_subscription_id=key,
                state="pending",
                provider_state={
                    "app_id": config.app_id,
                    "waba_id": config.waba_id,
                    "phone_id": config.phone_id,
                    "callback_url": address,
                },
            )
            session.add(row)
            await session.flush()
            if (await session.exec(pending_statement)).first() is not None:
                msg = "WhatsApp receiver cleanup is pending. Retry after it finishes."
                raise SourceConfigurationError(msg)
    except IntegrityError:
        msg = "This app/WABA already has a WhatsApp receiver."
        raise SourceConfigurationError(msg) from None


async def subscription(session: AsyncSession, trigger: Trigger, *, lock: bool = True) -> TriggerSubscription | None:
    statement = select(TriggerSubscription).where(
        TriggerSubscription.provider == "whatsapp",
        TriggerSubscription.trigger_id == trigger.id,
        TriggerSubscription.state.in_(["pending", "active"]),
    )
    if lock:
        statement = statement.with_for_update()
    return (await session.exec(statement)).first()


async def current_override(client: WhatsAppClient, *, require_app: bool = True) -> str | None:
    result = await client.request("GET", f"{client.config.waba_id}/subscribed_apps")
    rows = result.get("data")
    paging = result.get("paging", {})
    if not isinstance(rows, list) or not isinstance(paging, dict) or paging.get("next"):
        msg = "WhatsApp returned incomplete app subscription information."
        raise SourceConfigurationError(msg)
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("whatsapp_business_api_data"), dict)
        and row["whatsapp_business_api_data"].get("id") == client.config.app_id
    ]
    if not matches and not require_app:
        return None
    if len(matches) != 1:
        msg = "Subscribe this customer-owned app to the WABA before enabling the trigger."
        raise SourceConfigurationError(msg)
    address = matches[0].get("override_callback_uri")
    if address is not None and not isinstance(address, str):
        msg = "WhatsApp returned invalid callback information."
        raise SourceConfigurationError(msg)
    return address or None


async def provision(session: AsyncSession, trigger: Trigger) -> TriggerSubscription:
    row = await subscription(session, trigger)
    config = settings()
    address = await source_ingress_url(session, trigger)
    if (
        row is None
        or row.connection_id != trigger.connection_id
        or row.provider_subscription_id != f"waba:{config.tenant}"
        or row.provider_state.get("callback_url") != address
        or row.provider_state.get("phone_id") != config.phone_id
        or not trigger.signing_secret_encrypted
    ):
        msg = "The WhatsApp receiver reservation changed. Disable it and finish cleanup."
        raise SourceConfigurationError(msg)
    secret = decrypt_api_key(trigger.signing_secret_encrypted)
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    async with WhatsAppClient(lease) as client:
        await client.verify_account()
        previous = await current_override(client)
        if previous not in {None, address}:
            msg = "This app/WABA has another callback override. It was left unchanged."
            raise SourceConfigurationError(msg)
        result = await client.request(
            "POST", f"{config.waba_id}/subscribed_apps", body={"override_callback_uri": address, "verify_token": secret}
        )
        if result.get("success") is not True:
            msg = "WhatsApp did not confirm the callback override."
            raise SourceConfigurationError(msg)
    row.state = "active"
    row.expires_at = None
    row.renew_after = None
    session.add(row)
    await session.flush()
    return row


async def ingress_secrets(session: AsyncSession, trigger: Trigger) -> IngressSecrets:
    # Meta verifies the callback while provisioning still holds the mutation
    # lock. Reading the committed reservation must not wait for that POST.
    row = await subscription(session, trigger, lock=False)
    config = settings()
    if (
        row is None
        or row.provider_subscription_id != f"waba:{config.tenant}"
        or row.provider_state.get("phone_id") != config.phone_id
        or not trigger.signing_secret_encrypted
    ):
        return IngressSecrets()
    return IngressSecrets(
        signing_secret=config.app_secret,
        verification_token_digest=state_digest(decrypt_api_key(trigger.signing_secret_encrypted)),
        resource_id=config.waba_id,
        channel_id=config.phone_id,
        target_kind=trigger.kind,
        target_config=dict(trigger.config),
    )


class _RetainedCleanupLease:
    """Add sealed account metadata after the original lease resolves authority."""

    def __init__(self, lease: CredentialLease, account: ConnectionAccount) -> None:
        self._lease = lease
        self._account = account

    async def get_credential(self) -> ResolvedCredential:
        credential = await self._lease.get_credential()
        if credential.provider != "whatsapp":
            raise ConnectionNotAuthorizedError(provider="whatsapp")
        return replace(credential, identity="service", account=self._account)


async def revoke(task: TriggerCleanup, lease: CredentialLease) -> None:
    config = settings()
    state = task.provider_state or {}
    address = state.get("callback_url")
    if (
        task.provider_subscription_id != f"waba:{config.tenant}"
        or state.get("app_id") != config.app_id
        or state.get("waba_id") != config.waba_id
        or state.get("phone_id") != config.phone_id
        or not isinstance(address, str)
        or not address.startswith("https://")
    ):
        msg = "The original WhatsApp receiver cannot be verified for cleanup."
        raise SourceConfigurationError(msg)
    cleanup_lease = (
        _RetainedCleanupLease(
            lease, ConnectionAccount(id=state["phone_id"], tenant_id=f"{state['app_id']}:{state['waba_id']}")
        )
        if task.encrypted_credential is not None
        else lease
    )
    async with WhatsAppClient(cleanup_lease) as client:
        await client.verify_account()
        if await current_override(client, require_app=False) != address:
            return
        result = await client.request("POST", f"{config.waba_id}/subscribed_apps", body={})
        if result.get("success") is not True:
            msg = "WhatsApp did not confirm callback cleanup."
            raise SourceConfigurationError(msg)
