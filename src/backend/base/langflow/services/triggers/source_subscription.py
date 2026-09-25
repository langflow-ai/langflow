"""Provider subscription lifecycle for Microsoft and Google source triggers."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit
from uuid import uuid4

from lfx.log.logger import logger
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
from langflow.services.triggers.subscriptions import upsert_subscription

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def source_ingress_url(session: AsyncSession, trigger: Trigger) -> str:
    if not trigger.connection_id or not trigger.public_id:
        msg = "A push source requires a connection and a public ingress address."
        raise ValueError(msg)
    binding = await session.get(ConnectionOAuth, trigger.connection_id)
    if binding is None:
        msg = "A push source requires an OAuth connection with a configured public callback."
        raise ValueError(msg)
    registration = get_oauth_settings().registration(binding.registration_id)
    uri = urlsplit(registration.redirect_uri)
    if uri.scheme != "https" or not uri.netloc:
        msg = "Provider push requires a public HTTPS OAuth callback on this instance."
        raise ValueError(msg)
    return f"{uri.scheme}://{uri.netloc}/api/v1/triggers/ingress/{trigger.provider}/{trigger.public_id}"


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
        from langflow.services.triggers.source_poll import poll_source

        if not (trigger.provider_state or {}).get("page_token"):
            await poll_source(session, trigger, family=FAMILY_TRIGGER_PUSH)
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
            provider_subscription_id=f"gmail-watch:{trigger.id}",
            client_state_digest=None,
            expires_at=_expiry(response.get("expiration")),
            provider_state={
                "kind": "gmail",
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
        subscription.provider_subscription_id = channel_id
        subscription.client_state_digest = state_digest(token)
        subscription.provider_state = state
        session.add(subscription)
        from langflow.services.triggers.source_poll import poll_source

        await poll_source(session, trigger, family=FAMILY_TRIGGER_PUSH)
        if old_resource:
            try:
                origin = GOOGLE_CALENDAR_ORIGIN if trigger.kind == "google.calendar" else GOOGLE_DRIVE_ORIGIN
                path = "calendar/v3/channels/stop" if trigger.kind == "google.calendar" else "drive/v3/channels/stop"
                async with SourceHTTP(lease, origin=origin) as client:
                    await client.request("POST", path, body={"id": old_channel, "resourceId": old_resource})
            except Exception:  # noqa: BLE001 - the old channel expires while the new one serves
                # The old channel expires soon; the new verified channel is
                # already live and local deduplication spans them.
                await logger.awarning("Old Google channel %s could not be stopped", old_channel)
        return expiry
    if trigger.kind == "google.gmail":
        async with SourceHTTP(lease, origin=GOOGLE_GMAIL_ORIGIN) as client:
            response = await client.request(
                "POST",
                "gmail/v1/users/me/watch",
                body={"topicName": (trigger.config or {})["pubsub_topic"], "labelIds": ["INBOX"]},
            )
        return _expiry(response.get("expiration"))
    msg = "Unsupported source subscription renewal."
    raise ValueError(msg)


async def revoke_source(session: AsyncSession, subscription: TriggerSubscription) -> None:
    trigger = await session.get(Trigger, subscription.trigger_id)
    if trigger is None:
        return
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    if subscription.provider == PROVIDER_MICROSOFT:
        async with SourceHTTP(lease, origin=GRAPH_ORIGIN) as client:
            await client.request("DELETE", f"v1.0/subscriptions/{subscription.provider_subscription_id}")
    elif trigger.kind == "google.gmail":
        async with SourceHTTP(lease, origin=GOOGLE_GMAIL_ORIGIN) as client:
            await client.request("POST", "gmail/v1/users/me/stop")
    else:
        resource_id = (subscription.provider_state or {}).get("resource_id")
        if resource_id:
            origin = GOOGLE_CALENDAR_ORIGIN if trigger.kind == "google.calendar" else GOOGLE_DRIVE_ORIGIN
            path = "calendar/v3/channels/stop" if trigger.kind == "google.calendar" else "drive/v3/channels/stop"
            async with SourceHTTP(lease, origin=origin) as client:
                await client.request(
                    "POST",
                    path,
                    body={"id": subscription.provider_subscription_id, "resourceId": resource_id},
                )
