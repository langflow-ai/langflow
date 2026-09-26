"""Resolve canvas source connections and choose a supported delivery track."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.integrations.models import ConnectionRef
from sqlmodel import select

from langflow.services.connection.oauth.config import deployment_context, get_oauth_settings
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.database.models.connection.schemas import ConnectionOwnershipMode
from langflow.services.deps import get_settings_service
from langflow.services.triggers.constants import (
    GOOGLE_SOURCE_KINDS,
    MECHANISM_GRAPH_DELTA,
    MECHANISM_GRAPH_NOTIFICATIONS,
    MICROSOFT_SOURCE_KINDS,
)
from langflow.services.triggers.ownership import UNUSABLE_CONNECTION_STATUSES

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


_SCOPES = {
    "microsoft.mail": {"Mail.Read"},
    "microsoft.calendar": {"Calendars.Read"},
    "microsoft.file": {"Files.Read"},
    "google.calendar": {"https://www.googleapis.com/auth/calendar.events.readonly"},
    "google.drive": {"https://www.googleapis.com/auth/drive.file"},
    "google.gmail": {"https://www.googleapis.com/auth/gmail.readonly"},
}
_SCOPE_ALTERNATIVES = {
    "Calendars.Read": {"Calendars.ReadWrite"},
    "https://www.googleapis.com/auth/calendar.events.readonly": {"https://www.googleapis.com/auth/calendar.events"},
}
_PUBSUB_TOPIC = re.compile(r"^projects/[A-Za-z0-9_.~+%-]+/topics/[A-Za-z0-9_.~+%-]+$")
_SERVICE_ACCOUNT = re.compile(r"^[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com$")


@dataclass(frozen=True)
class SourceArming:
    connection_id: UUID
    mechanism_id: str


def normalize_source_config(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    if kind not in MICROSOFT_SOURCE_KINDS | GOOGLE_SOURCE_KINDS:
        msg = f"Unsupported source kind: {kind}"
        raise ValueError(msg)
    config = {
        key: raw.get(key)
        for key in ("connection", "calendar_id", "site_id", "pubsub_topic", "pubsub_service_account")
        if raw.get(key)
    }
    config["share_session"] = bool(raw.get("share_session"))
    return config


async def resolve_arming(session: AsyncSession, *, kind: str, owner_id: UUID, config: dict[str, Any]) -> SourceArming:
    handle = config.get("connection")
    if not isinstance(handle, str) or not handle:
        msg = "Choose a connection owned by the flow owner for this source."
        raise ValueError(msg)
    try:
        ref = ConnectionRef.parse(handle)
    except ValueError as exc:
        msg = "The source connection handle is invalid."
        raise ValueError(msg) from exc
    provider = kind.split(".", 1)[0]
    if ref.provider != provider:
        msg = f"Choose a {provider} connection for this source."
        raise ValueError(msg)
    row = (
        await session.exec(
            select(Connection).where(
                Connection.ownership_mode == ConnectionOwnershipMode.USER.value,
                Connection.owner_id == owner_id,
                Connection.provider_key == ref.provider,
                Connection.name == ref.name,
            )
        )
    ).first()
    if row is None:
        msg = "The flow owner does not own this connection. Shared and instance connections cannot back a source."
        raise ValueError(msg)
    context = deployment_context()
    if kind == "google.gmail":
        if context == "hosted":
            msg = "Gmail triggers are unavailable on hosted Langflow pending restricted-scope verification."
            raise ValueError(msg)
        binding = await session.get(ConnectionOAuth, row.id)
        if binding is None:
            msg = "Gmail requires a customer-owned OAuth registration."
            raise ValueError(msg)
        registration = get_oauth_settings().registration(binding.registration_id)
        if registration.owner != "customer":
            msg = "Gmail triggers require a customer-owned OAuth registration."
            raise ValueError(msg)
        if not config.get("pubsub_topic"):
            msg = "Configure a customer Pub/Sub topic before enabling a Gmail trigger."
            raise ValueError(msg)
        if not config.get("pubsub_service_account"):
            msg = "Configure the authenticated Pub/Sub push service account for this Gmail trigger."
            raise ValueError(msg)
        if not _PUBSUB_TOPIC.fullmatch(str(config["pubsub_topic"])):
            msg = "Use a fully qualified customer Pub/Sub topic name."
            raise ValueError(msg)
        if not _SERVICE_ACCOUNT.fullmatch(str(config["pubsub_service_account"])):
            msg = "Use the customer service account email configured for authenticated Pub/Sub push."
            raise ValueError(msg)
    ingress = get_settings_service().settings.trigger_ingress_enabled and context != "desktop"
    if kind in MICROSOFT_SOURCE_KINDS:
        mechanism = MECHANISM_GRAPH_NOTIFICATIONS if ingress else MECHANISM_GRAPH_DELTA
    elif kind == "google.calendar":
        mechanism = "google.calendar_push" if ingress else "google.calendar_sync_poll"
    elif kind == "google.drive":
        mechanism = "google.drive_push" if ingress else "google.drive_changes_poll"
    else:
        if not ingress:
            msg = "Gmail Pub/Sub push requires a public HTTPS ingress on this deployment."
            raise ValueError(msg)
        mechanism = "google.gmail_watch_pubsub_push"
    if context == "hosted" and not ingress:
        msg = "Hosted source triggers require provider ingress to be enabled."
        raise ValueError(msg)
    return SourceArming(connection_id=row.id, mechanism_id=mechanism)


async def check_ready(
    session: AsyncSession, *, kind: str, arming: SourceArming, config: dict[str, Any] | None = None
) -> None:
    row = await session.get(Connection, arming.connection_id)
    if row is None or row.status in UNUSABLE_CONNECTION_STATUSES:
        msg = "This source connection was revoked or expired. Reconnect it before enabling the trigger."
        raise ValueError(msg)
    if not row.allow_non_interactive:
        msg = "Turn on Allow background runs for this source connection."
        raise ValueError(msg)
    needed = set(_SCOPES[kind])
    if kind == "microsoft.file" and (config or {}).get("site_id"):
        needed.update({"Files.Read.All", "Sites.Read.All"})
    granted = set(row.granted_scopes or [])
    if kind in MICROSOFT_SOURCE_KINDS:
        granted |= {scope.removeprefix("https://graph.microsoft.com/") for scope in granted}
    missing = {
        scope for scope in needed if scope not in granted and not (_SCOPE_ALTERNATIVES.get(scope, set()) & granted)
    }
    if missing:
        msg = f"The source connection is missing required scopes: {', '.join(sorted(missing))}."
        raise ValueError(msg)
