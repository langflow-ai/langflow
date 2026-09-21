"""From a verified delivery to a committed ledger row, and nothing further.

The whole of the request's job is: verify, deduplicate, commit, answer. No flow
runs here and nothing is fetched back from the provider - Graph basic
notifications carry ids only, and resolving them needs the owner's connection
and an outbound HTTP call that would blow every provider's acknowledgement
deadline (Slack's is three seconds, and it retries at zero, one, and five
minutes when it is missed). The dispatcher picks the row up afterwards and the
run does the fetching.

Existence privacy is the other half. An unauthenticated endpoint that answers
differently for "no such trigger" and "bad signature" is an oracle for which
trigger ids exist, so :func:`resolve_target` returns ``None`` rather than
raising, and the route renders every outcome the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerState, TriggerSubscriptionState
from langflow.services.triggers import ledger
from langflow.services.triggers.constants import (
    AUDIT_INGRESS_ACCEPT,
    AUDIT_INGRESS_REJECT,
    INGRESS_DEDUPE_PREFIX,
    KIND_INBOUND_WEBHOOK,
    PROVIDER_GOOGLE,
    PROVIDER_MICROSOFT,
    PROVIDER_SLACK,
    PROVIDER_WEBHOOK,
)
from langflow.services.triggers.ingress.verifiers import IngressSecrets

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import TriggerEvent

#: Trigger states that accept a delivery. A paused, expired, dead, or
#: needs-reconnect trigger is one somebody took out of service; its provider may
#: still be pushing, and those deliveries are dropped rather than queued to run
#: at a surprising moment later.
ACCEPTING_STATES = frozenset({TriggerState.ACTIVE.value, TriggerState.PENDING.value})

#: Provider to the trigger ``kind`` prefix it may deliver for. A Slack-signed
#: request must not be able to drive a trigger armed against Microsoft, even if
#: it somehow guessed the public id.
_PROVIDER_KINDS = {
    PROVIDER_WEBHOOK: (KIND_INBOUND_WEBHOOK,),
    PROVIDER_SLACK: ("slack.",),
    PROVIDER_MICROSOFT: ("microsoft.",),
    PROVIDER_GOOGLE: ("google.",),
}


@dataclass(frozen=True)
class IngressTarget:
    """A trigger a delivery may be about, with the secrets to prove it."""

    trigger_id: UUID
    owner_id: UUID
    flow_id: UUID
    kind: str
    accepting: bool
    secrets: IngressSecrets


def _kind_matches(provider: str, kind: str) -> bool:
    prefixes = _PROVIDER_KINDS.get(provider, ())
    return any(kind == prefix or kind.startswith(prefix) for prefix in prefixes)


async def _webhook_secret(row: Trigger) -> str | None:
    if not row.signing_secret_encrypted:
        return None
    from langflow.services.auth.utils import decrypt_api_key

    try:
        return decrypt_api_key(row.signing_secret_encrypted)
    except Exception:  # noqa: BLE001 - a secret encrypted under another key is simply unusable
        await logger.awarning("Trigger %s has an unreadable signing secret", row.id)
        return None


async def _slack_signing_secret(session: AsyncSession, row: Trigger) -> str | None:
    """The app-level signing secret of the registration behind the connection.

    Slack signs with a secret that belongs to the app, not to the user who
    installed it, so the path runs trigger -> connection -> OAuth row ->
    registration rather than reading anything off the trigger itself.
    """
    if row.connection_id is None:
        return None
    statement = select(ConnectionOAuth).where(ConnectionOAuth.connection_id == row.connection_id)
    oauth = (await session.exec(statement)).first()
    if oauth is None:
        return None
    from langflow.services.connection.oauth.config import OAuthError, get_oauth_settings

    try:
        registration = get_oauth_settings().registration(oauth.registration_id)
    except OAuthError:
        return None
    secret = registration.signing_secret
    return secret.get_secret_value() if secret is not None else None


async def _subscription_secrets(session: AsyncSession, row: Trigger) -> IngressSecrets:
    """The per-subscription secrets Microsoft and Google verify against."""
    statement = select(TriggerSubscription).where(
        TriggerSubscription.trigger_id == row.id,
        TriggerSubscription.state != TriggerSubscriptionState.ERROR.value,
    )
    subscription = (await session.exec(statement)).first()
    if subscription is None:
        return IngressSecrets()
    provider_state = subscription.provider_state or {}
    # One column, two provider names for the same thing: the secret Langflow
    # minted when it created the subscription and compares on every delivery.
    # Microsoft calls it ``clientState``, Google calls it the channel token.
    return IngressSecrets(
        client_state_digest=subscription.client_state_digest,
        channel_token_digest=subscription.client_state_digest,
        channel_id=provider_state.get("channel_id"),
    )


async def resolve_target(session: AsyncSession, *, provider: str, public_id: str) -> IngressTarget | None:
    """Find the trigger this delivery names, or None. Never raises for "unknown".

    The provider in the path must match the trigger's kind. Without that check a
    delivery signed by any provider Langflow trusts could drive a trigger armed
    against a different one, which is a confused-deputy hole the signature alone
    does not close.
    """
    statement = select(Trigger).where(Trigger.public_id == public_id)
    row = (await session.exec(statement)).first()
    if row is None or not _kind_matches(provider, row.kind):
        return None

    if provider == PROVIDER_WEBHOOK:
        secrets = IngressSecrets(signing_secret=await _webhook_secret(row))
    elif provider == PROVIDER_SLACK:
        secrets = IngressSecrets(signing_secret=await _slack_signing_secret(session, row))
    else:
        secrets = await _subscription_secrets(session, row)

    return IngressTarget(
        trigger_id=row.id,
        owner_id=row.user_id,
        flow_id=row.flow_id,
        kind=row.kind,
        accepting=row.state in ACCEPTING_STATES,
        secrets=secrets,
    )


def dedupe_key(*, provider: str, suffix: str | None, fallback: str) -> str:
    """The ledger key for one delivery.

    Derived from the provider's own event identity whenever it offers one -
    Slack's ``event_id``, Graph's subscription plus resource plus change type,
    Google's channel plus message number - because that identity is exactly what
    survives a redelivery. ``fallback`` is used only when a provider sends
    nothing stable, and it is a digest of the signed body, so two identical
    bodies still collapse into one run.
    """
    return f"{INGRESS_DEDUPE_PREFIX}:{provider}:{suffix or fallback}"[:255]


async def record_event(
    session: AsyncSession,
    *,
    target: IngressTarget,
    provider: str,
    payload: dict[str, Any],
    suffix: str | None,
    fallback: str,
) -> tuple[TriggerEvent, bool]:
    """Commit the ledger row. Returns ``(row, created)``.

    ``created`` is False for a redelivery, and the route answers 2xx either way:
    telling a provider "that was a duplicate" with an error status is how a
    provider is taught to retry forever.
    """
    key = dedupe_key(provider=provider, suffix=suffix, fallback=fallback)
    return await ledger.append_event(
        session,
        trigger_id=target.trigger_id,
        dedupe_key=key,
        payload={"provider": provider, "delivery": payload},
    )


async def audit_ingress(
    *,
    accepted: bool,
    provider: str,
    public_id: str,
    target: IngressTarget | None,
    reason: str | None = None,
    duplicate: bool = False,
) -> None:
    """Write the audit row for one ingress decision.

    Rejections are audited as deliberately as acceptances: on an endpoint with
    no authentication, refusals are the only signal an operator has that
    somebody is probing it, and "unknown id from one address, six hundred times"
    is a sentence an operator can act on.
    """
    from langflow.services.authorization.audit import audit_decision

    await audit_decision(
        user_id=target.owner_id if target is not None else None,
        action=AUDIT_INGRESS_ACCEPT if accepted else AUDIT_INGRESS_REJECT,
        obj=f"trigger:{target.trigger_id}" if target is not None else f"trigger_ingress:{provider}",
        result="allow" if accepted else "deny",
        details={
            "provider": provider,
            # The public id is the thing being probed, so it belongs in the audit
            # row; it is not a secret, it is an address.
            "public_id": public_id,
            "reason": reason,
            "duplicate": duplicate,
        },
    )
