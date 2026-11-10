"""Reserve one durable receiver per verified Telegram bot account."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lfx_telegram._client import TelegramClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import TriggerCleanup, TriggerSubscription
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
from langflow.services.triggers.ingress.verifiers import IngressSecrets
from langflow.services.triggers.source_clients import source_lease
from langflow.services.triggers.source_errors import SourceConfigurationError
from langflow.services.triggers.source_subscription import source_ingress_url

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger


async def _claim(session: AsyncSession, trigger: Trigger, *, bot: dict, address: str | None) -> TriggerSubscription:
    bot_key = f"bot:{bot['id']}"
    pending = (
        await session.exec(
            select(TriggerCleanup.id).where(
                TriggerCleanup.provider == "telegram",
                TriggerCleanup.provider_subscription_id == bot_key,
            )
        )
    ).first()
    if pending is not None:
        msg = "Telegram receiver cleanup is pending. Retry after it finishes."
        raise SourceConfigurationError(msg)
    row = (
        await session.exec(
            select(TriggerSubscription)
            .where(
                TriggerSubscription.provider == "telegram",
                TriggerSubscription.provider_subscription_id == bot_key,
            )
            .with_for_update()
        )
    ).first()
    if row is not None and row.state != "expired":
        if row.trigger_id != trigger.id:
            msg = "This Telegram bot already has an active trigger. Use a different bot."
            raise SourceConfigurationError(msg)
        if (
            row.provider_state.get("transport") != trigger.config.get("mechanism_id")
            or row.connection_id != trigger.connection_id
        ):
            msg = "Disable this Telegram trigger and finish cleanup before changing its transport or connection."
            raise SourceConfigurationError(msg)
        return row
    siblings = (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.trigger_id == trigger.id,
                TriggerSubscription.state != "expired",
            )
        )
    ).all()
    if siblings:
        msg = "Disable the previous Telegram receiver before changing the connected bot."
        raise SourceConfigurationError(msg)
    try:
        async with session.begin_nested():
            if row is not None:
                await session.delete(row)
                await session.flush()
            row = TriggerSubscription(
                trigger_id=trigger.id,
                connection_id=trigger.connection_id,
                provider="telegram",
                provider_subscription_id=bot_key,
                state="pending" if address else "active",
                provider_state={
                    "bot_id": bot["id"],
                    "bot_username": bot["username"],
                    "transport": trigger.config.get("mechanism_id"),
                    "callback_url": address,
                },
            )
            session.add(row)
            await session.flush()
            # A concurrent trigger deletion may have removed the old unique
            # claim after the first cleanup read but before this insert won.
            pending = (
                await session.exec(
                    select(TriggerCleanup.id).where(
                        TriggerCleanup.provider == "telegram",
                        TriggerCleanup.provider_subscription_id == bot_key,
                    )
                )
            ).first()
            if pending is not None:
                msg = "Telegram receiver cleanup is pending. Retry after it finishes."
                raise SourceConfigurationError(msg)
    except IntegrityError:
        msg = "This Telegram bot already has a receiver. Retry with a different bot."
        raise SourceConfigurationError(msg) from None
    return row


async def prepare(session: AsyncSession, trigger: Trigger) -> None:
    """Admission and the unique claim share the trigger enable transaction."""
    if not trigger.config.get("allowed_chats"):
        msg = "Add at least one allowed Telegram chat before enabling this trigger."
        raise SourceConfigurationError(msg)
    mechanism = trigger.config.get("mechanism_id")
    if mechanism not in {"telegram.webhook", "telegram.get_updates"}:
        msg = "Unsupported Telegram receiver mechanism."
        raise SourceConfigurationError(msg)
    push = mechanism == "telegram.webhook"
    address = await source_ingress_url(session, trigger) if push else None
    connection = await session.get(Connection, trigger.connection_id) if trigger.connection_id else None
    identity = connection.executing_identity if connection is not None else {}
    account = identity.get("account")
    if (
        connection is None
        or connection.provider_key != "telegram"
        or identity.get("identity") != "bot"
        or not isinstance(account, dict)
        or not re.fullmatch(r"[1-9][0-9]{0,15}", str(account.get("id", "")))
        or not re.fullmatch(r"[A-Za-z0-9_]{5,32}", str(account.get("display", "")))
    ):
        msg = "Reconnect Telegram to verify the bot identity before enabling a trigger."
        raise SourceConfigurationError(msg)
    # Connection creation verifies getMe before storing this account metadata.
    # Resolving a credential here would open a second SQLite writer while
    # enable already holds the trigger writer. Network checks run in the
    # subsequent provisioning or collection phase instead.
    bot = {"id": account["id"], "username": account["display"]}
    await _claim(session, trigger, bot=bot, address=address)
    trigger.provider_state = {**(trigger.provider_state or {}), "bot_id": bot["id"], "bot_username": bot["username"]}
    session.add(trigger)
    await session.flush()


async def provision(session: AsyncSession, trigger: Trigger) -> TriggerSubscription:
    """Set only the webhook already reserved by this trigger's durable claim."""
    bot_id = trigger.provider_state.get("bot_id")
    row = (
        await session.exec(
            select(TriggerSubscription)
            .where(
                TriggerSubscription.provider == "telegram",
                TriggerSubscription.provider_subscription_id == f"bot:{bot_id}",
                TriggerSubscription.trigger_id == trigger.id,
            )
            .with_for_update()
        )
    ).first()
    if (
        row is None
        or row.state not in {"pending", "active"}
        or row.provider_state.get("transport") != "telegram.webhook"
    ):
        msg = "The Telegram receiver is not reserved by this trigger."
        raise SourceConfigurationError(msg)
    address = await source_ingress_url(session, trigger)
    if address != row.provider_state.get("callback_url") or not trigger.signing_secret_encrypted:
        msg = "The Telegram callback changed. Disable and re-enable this trigger."
        raise SourceConfigurationError(msg)
    secret = decrypt_api_key(trigger.signing_secret_encrypted)
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    async with TelegramClient(lease) as client:
        bot = await client.identity()
        if bot["id"] != bot_id:
            msg = "The Telegram bot changed. Reconnect the original bot before enabling."
            raise SourceConfigurationError(msg)
        info = await client.call("getWebhookInfo")
        if not isinstance(info, dict) or info.get("url") not in {"", address}:
            msg = "This Telegram bot now has another receiver. Its webhook was left unchanged."
            raise SourceConfigurationError(msg)
        accepted = await client.call(
            "setWebhook",
            url=address,
            secret_token=secret,
            allowed_updates=["message"],
            drop_pending_updates=False,
            max_connections=1,
        )
        if accepted is not True:
            msg = "Telegram did not accept the webhook."
            raise SourceConfigurationError(msg)
    row.provider_state = {**row.provider_state, "bot_username": bot["username"]}
    trigger.provider_state = {**trigger.provider_state, "bot_username": bot["username"]}
    session.add(trigger)
    row.state = "active"
    row.renew_after = None
    row.expires_at = None
    session.add(row)
    await session.flush()
    return row


async def ingress_secrets(session: AsyncSession, trigger: Trigger) -> IngressSecrets:
    row = (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.provider == "telegram",
                TriggerSubscription.trigger_id == trigger.id,
                TriggerSubscription.state == "active",
            )
        )
    ).first()
    if row is None or row.provider_state.get("transport") != "telegram.webhook" or not trigger.signing_secret_encrypted:
        return IngressSecrets()
    # Internal resource and channel slots carry the verified bot identity.
    # Keep target_config identical to the persisted commit precondition.
    return IngressSecrets(
        signing_secret=decrypt_api_key(trigger.signing_secret_encrypted),
        target_kind=trigger.kind,
        target_config=dict(trigger.config),
        resource_id=row.provider_state["bot_id"],
        channel_id=row.provider_state["bot_username"],
    )


async def revoke(task: TriggerCleanup, lease: CredentialLease) -> None:
    """Never delete a webhook that no longer points to this receiver's URL."""
    state = task.provider_state or {}
    if state.get("transport") == "telegram.get_updates":
        return
    address = state.get("callback_url")
    bot_id = state.get("bot_id")
    if (
        not isinstance(address, str)
        or not address.startswith("https://")
        or not bot_id
        or task.provider_subscription_id != f"bot:{bot_id}"
    ):
        msg = "The original Telegram receiver cannot be identified for cleanup."
        raise SourceConfigurationError(msg)
    async with TelegramClient(lease) as client:
        bot = await client.identity()
        if bot["id"] != bot_id:
            msg = "The original Telegram bot cannot be verified for cleanup."
            raise SourceConfigurationError(msg)
        info = await client.call("getWebhookInfo")
        if not isinstance(info, dict) or not isinstance(info.get("url"), str):
            msg = "Telegram returned invalid receiver information."
            raise SourceConfigurationError(msg)
        if info["url"] != address:
            return
        accepted = await client.call("deleteWebhook", drop_pending_updates=False)
        if accepted is not True:
            msg = "Telegram did not confirm receiver cleanup."
            raise SourceConfigurationError(msg)
