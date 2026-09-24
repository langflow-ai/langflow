"""Which Slack transport a trigger runs on, decided from its connection.

A Slack trigger node names a connection by its portable handle
(``slack/<name>``) and nothing else, so one flow JSON runs on hosted Langflow,
a self-managed instance and Desktop. The transport follows from what that name
resolves to on *this* instance, for *this* flow owner:

* an **OAuth bot installation** of a Slack registration that carries a signing
  secret receives the **Events API** (``slack.events_api``), through the app's
  Request URL;
* an **app-level token connection** (``xapp-``, marked server-side) holds a
  **Socket Mode** socket (``slack.socket_mode``) in the listener process.

Everything else is a typed, owner-readable reason the trigger cannot be armed -
recorded on the trigger when the flow is saved, and re-checked when it is
enabled. The two deployment rules the matrices set are enforced here too: hosted
has no Socket Mode (a Marketplace app cannot use it) and Desktop has no Events
API (Slack has nowhere to deliver to).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.integrations.models import ConnectionRef
from sqlmodel import select

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.database.models.connection.schemas import ConnectionOwnershipMode
from langflow.services.triggers.constants import (
    KIND_SLACK_MESSAGE,
    MECHANISM_SLACK_EVENTS_API,
    MECHANISM_SLACK_SOCKET_MODE,
    PROVIDER_SLACK,
    SLACK_PROVIDER_STATE_APP_ID,
)
from langflow.services.triggers.ownership import UNUSABLE_CONNECTION_STATUSES

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger

#: The node field holding the connection handle.
CONNECTION_FIELD = "connection"

#: Bot scopes each Events API subscription needs (Slack's event reference).
_MESSAGE_SCOPES = {
    "channel": "channels:history",
    "group": "groups:history",
    "im": "im:history",
    "mpim": "mpim:history",
}
_MENTION_SCOPE = "app_mentions:read"
_REACTION_SCOPE = "reactions:read"


class SlackTriggerArmingError(ValueError):
    """A Slack trigger that cannot be armed on the connection it names."""


@dataclass(frozen=True)
class SlackArming:
    """How a Slack trigger is armed: its connection and its transport."""

    connection_id: UUID
    mechanism_id: str


async def resolve_arming(
    session: AsyncSession,
    *,
    owner_id: UUID,
    config: dict[str, Any],
    context: str,
) -> SlackArming:
    """Resolve the node's connection handle and derive the transport, or raise.

    Reads connection *metadata* only; nothing is decrypted, so this is safe on
    every flow save.
    """
    handle = config.get(CONNECTION_FIELD)
    if not handle:
        msg = "Choose a Slack connection for this trigger; it cannot be armed without one."
        raise SlackTriggerArmingError(msg)
    try:
        ref = ConnectionRef.parse(handle)
    except ValueError as exc:
        msg = f"{handle!r} is not a Slack connection."
        raise SlackTriggerArmingError(msg) from exc
    if ref.provider != PROVIDER_SLACK:
        msg = f"{handle!r} is not a Slack connection."
        raise SlackTriggerArmingError(msg)

    row = await _owned_connection(session, owner_id=owner_id, ref=ref)
    if row is None:
        msg = (
            f"The flow owner has no Slack connection named {ref.name!r}. A trigger listens through one of its "
            "owner's own connections; shared and instance connections cannot back a trigger."
        )
        raise SlackTriggerArmingError(msg)

    from langflow.services.connection.slack_credentials import is_app_token_connection

    if is_app_token_connection(row):
        if context == "hosted":
            msg = (
                "Hosted Langflow receives Slack events through the Events API; Socket Mode is not available "
                "because a Slack Marketplace app cannot use it. Choose a Slack app installation instead of an "
                "app-level token connection."
            )
            raise SlackTriggerArmingError(msg)
        return SlackArming(connection_id=row.id, mechanism_id=MECHANISM_SLACK_SOCKET_MODE)

    if context == "desktop":
        msg = (
            "Langflow Desktop receives Slack events over Socket Mode: Slack cannot deliver Events API requests to "
            "a computer without a public address. Create an app-level token connection for your Slack app "
            "(Basic Information > App-Level Tokens, with the connections:write scope) and choose it here."
        )
        raise SlackTriggerArmingError(msg)
    return SlackArming(connection_id=row.id, mechanism_id=await _events_api_mechanism(session, row))


async def _owned_connection(session: AsyncSession, *, owner_id: UUID, ref: ConnectionRef) -> Connection | None:
    statement = select(Connection).where(
        Connection.ownership_mode == ConnectionOwnershipMode.USER.value,
        Connection.owner_id == owner_id,
        Connection.provider_key == ref.provider,
        Connection.name == ref.name,
    )
    return (await session.exec(statement)).first()


async def _events_api_mechanism(session: AsyncSession, row: Connection) -> str:
    """An installation receives the Events API only through a registration that can verify it."""
    binding = await session.get(ConnectionOAuth, row.id)
    if binding is None:
        msg = (
            "This Slack connection cannot receive events. Use a Slack app installation (events arrive through "
            "the Events API) or an app-level token connection (events arrive over Socket Mode)."
        )
        raise SlackTriggerArmingError(msg)

    from langflow.services.connection.oauth.config import OAuthError, get_oauth_settings

    try:
        registration = get_oauth_settings().registration(binding.registration_id)
    except OAuthError as exc:
        msg = (
            f"The Slack app this connection was installed from ({binding.registration_id!r}) is not configured on "
            "this instance, so its events cannot be received."
        )
        raise SlackTriggerArmingError(msg) from exc
    if registration.profile != "bot":
        msg = (
            "A Slack user connection cannot receive events. Install the Slack app to the workspace (a bot "
            "installation) and choose that connection."
        )
        raise SlackTriggerArmingError(msg)
    if registration.signing_secret is None:
        msg = (
            f"The Slack app registration {binding.registration_id!r} has no signing secret, so Slack's event "
            "deliveries could not be verified. Add the app's signing secret to the registration."
        )
        raise SlackTriggerArmingError(msg)
    if _installation_team_id(row) is None:
        # Deliveries are routed by the workspace they were delivered for, and an
        # org-wide Enterprise Grid install records none (``oauth.v2.access``
        # returns no ``team``). Armed anyway, it would sit active and never fire.
        msg = (
            "This Slack installation has no workspace, so no event delivery could ever be matched to it. "
            "Org-wide Enterprise Grid installations are not supported for triggers; install the app to a "
            "workspace and choose that connection."
        )
        raise SlackTriggerArmingError(msg)
    return MECHANISM_SLACK_EVENTS_API


def _installation_team_id(row: Connection) -> str | None:
    """The workspace an installation belongs to, as the Events API fan-out matches it."""
    account = (row.executing_identity or {}).get("account")
    team_id = account.get("tenant_id") if isinstance(account, dict) else None
    return team_id if isinstance(team_id, str) and team_id else None


def bind_connection(row: Trigger, connection_id: UUID | None) -> bool:
    """Point a Slack trigger at ``connection_id``. Returns whether it moved.

    The Slack app a Socket Mode socket proved (``provider_state.slack_app_id``)
    is a fact about the *old* connection. Kept across a move, other people's
    sockets for that app would go on writing its events into this trigger until
    the new connection's socket says hello - and for good if it never does, say
    because the new token was refused. The new connection's socket records its
    own app when it opens.
    """
    if row.connection_id == connection_id:
        return False
    row.connection_id = connection_id
    state = row.provider_state or {}
    if SLACK_PROVIDER_STATE_APP_ID in state:
        row.provider_state = {key: value for key, value in state.items() if key != SLACK_PROVIDER_STATE_APP_ID}
    return True


def required_event_scopes(kind: str, config: dict[str, Any]) -> set[str]:
    """The bot scopes an Events API installation needs for this trigger's subscriptions."""
    if kind != KIND_SLACK_MESSAGE:
        return {_REACTION_SCOPE}
    if config.get("mentions_only"):
        return {_MENTION_SCOPE}
    types = config.get("conversation_types") or list(_MESSAGE_SCOPES)
    return {_MESSAGE_SCOPES[value] for value in types if value in _MESSAGE_SCOPES}


async def check_ready_to_arm(session: AsyncSession, *, kind: str, config: dict[str, Any], arming: SlackArming) -> None:
    """What enabling additionally requires: a usable connection that consents to background runs.

    Checked at enable rather than on every save, because these are properties
    of the connection that change without the flow changing - and each one has
    its own remedy, none of which is "reconnect".
    """
    row = await session.get(Connection, arming.connection_id)
    if row is None or row.status in UNUSABLE_CONNECTION_STATUSES:
        msg = "The Slack connection this trigger uses is revoked or expired. Reconnect it, then enable the trigger."
        raise SlackTriggerArmingError(msg)
    if not row.allow_non_interactive:
        msg = (
            "Turn on 'Allow background runs' for the Slack connection this trigger uses: a trigger runs its flow "
            "with no one signed in, and the connection's owner has not allowed that yet."
        )
        raise SlackTriggerArmingError(msg)
    if arming.mechanism_id == MECHANISM_SLACK_EVENTS_API:
        missing = sorted(required_event_scopes(kind, config) - set(row.granted_scopes or []))
        if missing:
            msg = (
                f"The Slack installation behind this connection is missing {', '.join(missing)}, which this "
                "trigger's events need. Add the scopes to the Slack app and reinstall it, then reconnect."
            )
            raise SlackTriggerArmingError(msg)
