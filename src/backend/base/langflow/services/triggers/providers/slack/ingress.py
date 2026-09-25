"""Track A: one Slack app's Request URL, fanned out to the triggers it feeds.

Slack gives an app exactly one Request URL, and a distributed (hosted) app is
installed in many workspaces, so a delivery names an *app* and a *workspace* -
never a trigger. The route resolves the app from the path (its OAuth
registration, whose signing secret proves the delivery), then this module finds
every armed trigger that delivery should reach:

* ``active`` Slack triggers armed on the Events API mechanism,
* whose connection is an installation of *this* registration,
* in the workspace the event was delivered for,
* on a connection the trigger's owner owns and has not lost,

and writes one ledger row per trigger whose filters match. Nothing runs here and
nothing is fetched back; the dispatcher runs each flow afterwards as its owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.triggers import ledger
from langflow.services.triggers.constants import (
    AUDIT_INGRESS_ACCEPT,
    AUDIT_INGRESS_REJECT,
    MECHANISM_SLACK_EVENTS_API,
    PROVIDER_SLACK,
    SLACK_TRIGGER_KINDS,
)
from langflow.services.triggers.ownership import UNUSABLE_CONNECTION_STATUSES, owned_by_trigger_owner
from langflow.services.triggers.providers.slack.filters import matches

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.triggers.providers.slack.events import SlackEvent

#: Audit reasons specific to the app route. The shared ones (bad signature,
#: stale timestamp, body too large, rate limited) come from the verifiers.
REASON_UNKNOWN_APP = "unknown_app"
REASON_IGNORED = "ignored"
REASON_APP_RATE_LIMITED = "slack_app_rate_limited"

#: How many trigger ids an audit row lists. The count is always exact; the list
#: is for an operator following one delivery, not a complete index.
_AUDITED_TRIGGER_IDS = 20


@dataclass(frozen=True)
class SlackApp:
    """A Slack app registration that can receive Events API deliveries."""

    registration_id: str
    signing_secret: str


@dataclass(frozen=True)
class FanOut:
    """What one verified delivery did."""

    matched: tuple[UUID, ...]
    created: int


def resolve_app(registration_id: str) -> SlackApp | None:
    """The registration behind a Request URL, if it can receive events here.

    ``None`` for an unknown id, a non-Slack or non-bot registration, one without
    a signing secret, or one that belongs to another deployment context - the
    route answers all of them identically.
    """
    from langflow.services.connection.oauth.config import OAuthError, get_oauth_settings

    try:
        registration = get_oauth_settings().registration(registration_id)
    except OAuthError:
        return None
    if registration.provider != PROVIDER_SLACK or registration.profile != "bot" or registration.signing_secret is None:
        return None
    return SlackApp(registration_id=registration_id, signing_secret=registration.signing_secret.get_secret_value())


async def fan_out(session: AsyncSession, *, registration_id: str, event: SlackEvent) -> FanOut:
    """Append ``event`` to the ledger of every trigger it should fire.

    Runs inside the request's session; the caller commits once for the whole
    delivery, so a delivery is durable for every trigger or for none, and the
    acknowledgement is only sent after that commit.
    """
    matched: list[UUID] = []
    created = 0
    for trigger in await _candidates(session, registration_id=registration_id, team_ids=event.team_ids):
        if not matches(trigger.kind, trigger.config or {}, event):
            continue
        _row, was_created = await ledger.append_event(
            session, trigger_id=trigger.id, dedupe_key=event.dedupe_key, payload=event.payload
        )
        matched.append(trigger.id)
        created += int(was_created)
    return FanOut(matched=tuple(matched), created=created)


async def _candidates(session: AsyncSession, *, registration_id: str, team_ids: frozenset[str]) -> list[Trigger]:
    """Armed Events API triggers on installations of this app in these workspaces."""
    if not team_ids:
        return []
    tenant = col(Connection.executing_identity)["account"]["tenant_id"].as_string()
    mechanism = col(Trigger.config)["mechanism_id"].as_string()
    statement = (
        select(Trigger)
        .join(Connection, col(Connection.id) == col(Trigger.connection_id))
        .join(ConnectionOAuth, col(ConnectionOAuth.connection_id) == col(Connection.id))
        .where(
            Trigger.state == TriggerState.ACTIVE.value,
            col(Trigger.kind).in_(SLACK_TRIGGER_KINDS),
            mechanism == MECHANISM_SLACK_EVENTS_API,
            ConnectionOAuth.registration_id == registration_id,
            owned_by_trigger_owner(),
            col(Connection.status).not_in(UNUSABLE_CONNECTION_STATUSES),
            tenant.in_(sorted(team_ids)),
        )
        .order_by(col(Trigger.id))
    )
    return list((await session.exec(statement)).all())


async def audit_delivery(
    *,
    accepted: bool,
    registration_id: str,
    reason: str | None = None,
    event: SlackEvent | None = None,
    team_id: str | None = None,
    fanout: FanOut | None = None,
    retry_num: str | None = None,
    retry_reason: str | None = None,
) -> None:
    """One audit row per delivery to an app's Request URL.

    Slack's retry headers are recorded here and only here. They differ between
    the three deliveries of one event and do not exist on the Socket Mode
    track, so they must never reach the flow-facing payload - but "Slack is
    retrying us" is exactly what an operator chasing a slow instance needs.
    """
    from langflow.services.authorization.audit import audit_decision

    details = {
        "provider": PROVIDER_SLACK,
        "registration_id": registration_id,
        "reason": reason,
        "team_id": team_id or (event.payload["team_id"] if event is not None else None),
        "slack_event_id": event.event_id if event is not None else None,
        "retry_num": retry_num,
        "retry_reason": retry_reason,
    }
    if fanout is not None:
        details.update(
            {
                "matched": len(fanout.matched),
                "created": fanout.created,
                "trigger_ids": [str(trigger_id) for trigger_id in fanout.matched[:_AUDITED_TRIGGER_IDS]],
            }
        )
    try:
        await audit_decision(
            user_id=None,
            action=AUDIT_INGRESS_ACCEPT if accepted else AUDIT_INGRESS_REJECT,
            obj=f"trigger_ingress:slack_app:{registration_id}",
            result="allow" if accepted else "deny",
            details=details,
        )
    except Exception:  # noqa: BLE001 - an audit failure must not turn a durable delivery into a retry
        await logger.aexception("Could not audit a Slack delivery for registration %s", registration_id)
