"""Provider subscription lifecycle for Microsoft and Google source triggers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlmodel import select

from langflow.services.connection.oauth.config import get_oauth_settings
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerSubscriptionState
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH, PROVIDER_GOOGLE, PROVIDER_MICROSOFT
from langflow.services.triggers.ingress.verifiers import state_digest
from langflow.services.triggers.source_clients import (
    GOOGLE_CALENDAR_ORIGIN,
    GOOGLE_DRIVE_ORIGIN,
    GOOGLE_GMAIL_ORIGIN,
    GRAPH_ORIGIN,
    SourceHTTP,
    source_lease,
)
from langflow.services.triggers.source_errors import SourceConfigurationError
from langflow.services.triggers.subscriptions import revoke_for_trigger, upsert_subscription

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def source_ingress_url(session: AsyncSession, trigger: Trigger) -> str:
    if not trigger.connection_id or not trigger.public_id:
        msg = "A push source requires a connection and a public ingress address."
        raise SourceConfigurationError(msg)
    binding = await session.get(ConnectionOAuth, trigger.connection_id)
    if binding is None:
        msg = "A push source requires an OAuth connection with a configured public callback."
        raise SourceConfigurationError(msg)
    registration = get_oauth_settings().registration(binding.registration_id)
    from langflow.services.triggers.source_arming import public_ingress_origin

    origin = public_ingress_origin(registration.redirect_uri)
    if origin is None:
        msg = "Provider push requires a public HTTPS OAuth callback on this instance."
        raise SourceConfigurationError(msg)
    return f"{origin}/api/v1/triggers/ingress/{trigger.provider}/{trigger.public_id}"


def _expiry(value: Any) -> datetime:
    if isinstance(value, str):
        if value.isdecimal():
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, int | float):
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    msg = "Provider watch response contained no expiration."
    raise ValueError(msg)


def _graph_resource(trigger: Trigger) -> str:
    if trigger.kind == "microsoft.mail":
        return "me/mailFolders('Inbox')/messages"
    if trigger.kind == "microsoft.calendar":
        return "me/events"
    if trigger.kind == "microsoft.file":
        return "me/drive/root"
    msg = f"Unsupported Graph subscription kind: {trigger.kind}"
    raise ValueError(msg)


async def _graph_create(session: AsyncSession, trigger: Trigger, address: str) -> TriggerSubscription:
    secret = secrets.token_urlsafe(32)
    expiry = _now() + timedelta(hours=24)
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    async with SourceHTTP(lease, origin=GRAPH_ORIGIN) as client:
        resource = _graph_resource(trigger)
        site_id = (trigger.config or {}).get("site_id") if trigger.kind == "microsoft.file" else None
        if site_id:
            from langflow.services.triggers.source_poll import _graph_start

            _graph_start(trigger)  # Validates the site identifier before it enters a URL.
            site_drive = await client.request("GET", f"v1.0/sites/{site_id}/drive")
            drive_id = site_drive.get("id")
            if not isinstance(drive_id, str) or not drive_id:
                msg = "Graph did not return a drive for this SharePoint site."
                raise ValueError(msg)
            resource = f"drives/{drive_id}/root"
        response = await client.request(
            "POST",
            "v1.0/subscriptions",
            body={
                "changeType": "updated" if trigger.kind == "microsoft.file" else "created,updated,deleted",
                "notificationUrl": address,
                "lifecycleNotificationUrl": address,
                "resource": resource,
                "expirationDateTime": expiry.isoformat(),
                "clientState": secret,
            },
        )
    subscription_id = response.get("id")
    if not isinstance(subscription_id, str) or not subscription_id:
        msg = "Graph did not return a subscription id."
        raise ValueError(msg)
    return await upsert_subscription(
        session,
        trigger_id=trigger.id,
        connection_id=trigger.connection_id,
        provider=PROVIDER_MICROSOFT,
        provider_subscription_id=subscription_id,
        client_state_digest=state_digest(secret),
        expires_at=_expiry(response.get("expirationDateTime")),
        provider_state={"resource": resource},
    )


async def _google_watch(
    session: AsyncSession, trigger: Trigger, address: str
) -> tuple[str, str, dict[str, Any], datetime]:
    token = secrets.token_urlsafe(32)
    channel_id = str(uuid4())
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    if trigger.kind == "google.calendar":
        from urllib.parse import quote

        calendar_id = str((trigger.config or {}).get("calendar_id") or "primary")
        path = f"calendar/v3/calendars/{quote(calendar_id, safe='')}/events/watch"
        origin = GOOGLE_CALENDAR_ORIGIN
        params = None
    elif trigger.kind == "google.drive":
        # The change-feed token is established before the channel, so a
        # change between those two calls is still visible on the next scan.

        if not (trigger.provider_state or {}).get("page_token"):
            msg = "Initialize the Drive cursor before creating a watch."
            raise SourceConfigurationError(msg)
        path = "drive/v3/changes/watch"
        origin = GOOGLE_DRIVE_ORIGIN
        params = {"pageToken": (trigger.provider_state or {})["page_token"]}
    else:
        msg = f"Unsupported Google channel kind: {trigger.kind}"
        raise ValueError(msg)
    body = {"id": channel_id, "type": "web_hook", "address": address, "token": token}
    async with SourceHTTP(lease, origin=origin) as client:
        response = await client.request("POST", path, params=params, body=body)
    resource_id = response.get("resourceId")
    if not isinstance(resource_id, str) or not resource_id:
        msg = "Google did not return a watched resource id."
        raise ValueError(msg)
    return (
        channel_id,
        token,
        {"channel_id": channel_id, "resource_id": resource_id},
        _expiry(response.get("expiration")),
    )


async def gmail_mailbox_key(lease) -> str:
    """Use the provider's canonical mailbox identity across OAuth connections."""
    async with SourceHTTP(lease, origin=GOOGLE_GMAIL_ORIGIN) as client:
        profile = await client.request("GET", "gmail/v1/users/me/profile")
    address = profile.get("emailAddress")
    if not isinstance(address, str) or not address:
        msg = "Gmail did not return a mailbox identity."
        raise ValueError(msg)
    return hashlib.sha256(address.casefold().encode()).hexdigest()


async def provision_source(session: AsyncSession, trigger: Trigger) -> TriggerSubscription:
    """Create a watch once, or return the live one on an idempotent enable."""
    existing = (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.trigger_id == trigger.id,
                TriggerSubscription.state == TriggerSubscriptionState.ACTIVE.value,
            )
        )
    ).first()
    if existing is not None and existing.connection_id == trigger.connection_id:
        return existing
    if existing is not None:
        await revoke_for_trigger(session, trigger_id=trigger.id)
    address = await source_ingress_url(session, trigger)
    if trigger.provider == PROVIDER_MICROSOFT:
        return await _graph_create(session, trigger, address)
    if trigger.kind in {"google.calendar", "google.drive"}:
        channel_id, token, state, expiry = await _google_watch(session, trigger, address)
        return await upsert_subscription(
            session,
            trigger_id=trigger.id,
            connection_id=trigger.connection_id,
            provider=PROVIDER_GOOGLE,
            provider_subscription_id=channel_id,
            client_state_digest=state_digest(token),
            expires_at=expiry,
            provider_state=state,
        )
    if trigger.kind == "google.gmail":
        config = trigger.config or {}
        lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
        mailbox_key = session.info.get("gmail_mailbox_key") or await gmail_mailbox_key(lease)
        siblings = (
            await session.exec(
                select(TriggerSubscription).where(
                    TriggerSubscription.provider == PROVIDER_GOOGLE,
                    TriggerSubscription.state == TriggerSubscriptionState.ACTIVE.value,
                )
            )
        ).all()
        for sibling in siblings:
            state = sibling.provider_state or {}
            if state.get("kind") == "gmail" and not state.get("mailbox_key"):
                msg = "Disable and re-enable existing Gmail triggers before adding another mailbox watch."
                raise SourceConfigurationError(msg)
            if state.get("mailbox_key") == mailbox_key and state.get("pubsub_topic") != config["pubsub_topic"]:
                msg = "All Gmail triggers for one mailbox must use the same Pub/Sub topic."
                raise SourceConfigurationError(msg)
        async with SourceHTTP(lease, origin=GOOGLE_GMAIL_ORIGIN) as client:
            response = await client.request(
                "POST",
                "gmail/v1/users/me/watch",
                body={"topicName": config["pubsub_topic"], "labelIds": ["INBOX"]},
            )
        row = await upsert_subscription(
            session,
            trigger_id=trigger.id,
            connection_id=trigger.connection_id,
            provider=PROVIDER_GOOGLE,
            provider_subscription_id=f"gmail-watch:{trigger.id}:{uuid4()}",
            client_state_digest=None,
            expires_at=_expiry(response.get("expiration")),
            provider_state={
                "kind": "gmail",
                "mailbox_key": mailbox_key,
                "pubsub_topic": config["pubsub_topic"],
                "audience": address,
                "pubsub_service_account": config["pubsub_service_account"],
            },
        )
        row.renew_after = _now() + timedelta(days=1)
        session.add(row)
        await session.flush()
        return row
    msg = "Unsupported source subscription kind."
    raise ValueError(msg)


async def renew_source(session: AsyncSession, subscription: TriggerSubscription) -> datetime:
    trigger = await session.get(Trigger, subscription.trigger_id)
    if trigger is None:
        msg = "The trigger behind this subscription no longer exists."
        raise ValueError(msg)
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    if subscription.provider == PROVIDER_MICROSOFT:
        expiry = _now() + timedelta(hours=24)
        async with SourceHTTP(lease, origin=GRAPH_ORIGIN) as client:
            response = await client.request(
                "PATCH",
                f"v1.0/subscriptions/{subscription.provider_subscription_id}",
                body={"expirationDateTime": expiry.isoformat()},
            )
        return _expiry(response.get("expirationDateTime"))
    if trigger.kind in {"google.calendar", "google.drive"}:
        address = await source_ingress_url(session, trigger)
        old_channel = subscription.provider_subscription_id
        old_resource = (subscription.provider_state or {}).get("resource_id")
        channel_id, token, state, expiry = await _google_watch(session, trigger, address)
        from langflow.services.triggers.source_cleanup import enqueue_cleanup

        if old_resource:
            old_watch = TriggerSubscription(**subscription.model_dump())
            old_watch.id = uuid4()
            old_watch.provider_subscription_id = old_channel
            await enqueue_cleanup(session, old_watch)
        subscription.provider_subscription_id = channel_id
        subscription.client_state_digest = state_digest(token)
        subscription.provider_state = state
        session.add(subscription)
        return expiry
    if trigger.kind == "google.gmail":
        from langflow.services.triggers.source_cleanup import with_mailbox_lease

        key = await gmail_mailbox_key(lease)
        if key != (subscription.provider_state or {}).get("mailbox_key"):
            msg = "The Gmail mailbox identity changed. Enable the trigger again."
            raise ValueError(msg)

        async def renew_watch():
            await session.refresh(subscription)
            if subscription.state != TriggerSubscriptionState.ACTIVE.value:
                msg = "The Gmail watch was retired during renewal."
                raise ValueError(msg)
            async with SourceHTTP(lease, origin=GOOGLE_GMAIL_ORIGIN) as client:
                response = await client.request(
                    "POST",
                    "gmail/v1/users/me/watch",
                    body={"topicName": (subscription.provider_state or {})["pubsub_topic"], "labelIds": ["INBOX"]},
                )
            return _expiry(response.get("expiration"))

        return await with_mailbox_lease(key, renew_watch)
    msg = "Unsupported source subscription renewal."
    raise ValueError(msg)


async def revoke_source(session: AsyncSession, subscription: TriggerSubscription) -> None:
    """Queue revocation; lifecycle transactions must not hold writes during I/O."""
    from langflow.services.triggers.source_cleanup import enqueue_cleanup

    await enqueue_cleanup(session, subscription)
