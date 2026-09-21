"""Per-provider verification of an unauthenticated delivery.

This is the only unauthenticated write path triggers have, so everything here
is written to fail closed. A verifier answers one question - "did the provider
this trigger is armed against actually send this body?" - and answers it from
the raw bytes, never from a parsed model, because a signature covers bytes and
any re-serialization breaks it.

Four verifiers, one per wave-1 mechanism:

``slack``
    ``v0=`` HMAC-SHA256 over ``v0:{timestamp}:{body}`` with the registration's
    app-level signing secret, plus a staleness window so a captured request
    cannot be replayed tomorrow. Slack's ``url_verification`` handshake is
    answered here too, because it arrives signed and must be echoed inside the
    same three-second budget.
``microsoft``
    Two shapes. The subscription handshake arrives as a ``validationToken``
    query parameter that must be echoed as ``text/plain``; notifications carry
    ``clientState``, a secret Langflow minted at subscribe time, which is
    compared against the stored digest.
``google``
    ``X-Goog-Channel-Token``, the secret Langflow set when it created the
    channel, compared against the stored digest, together with the channel id
    so a token from one channel cannot drive another.
``webhook``
    The generic signed endpoint: ``X-Langflow-Signature: v1=<hex>`` over
    ``v1:{timestamp}:{body}`` with the trigger's own rotatable secret.

Every comparison uses :func:`hmac.compare_digest`. Every failure returns the
same shaped rejection with a machine-readable reason, and the route turns all of
them into one status code, so the endpoint is not an oracle for which check
failed or whether a trigger exists.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from langflow.services.triggers.constants import (
    PROVIDER_GOOGLE,
    PROVIDER_MICROSOFT,
    PROVIDER_SLACK,
    PROVIDER_WEBHOOK,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Rejection reasons. They are audit vocabulary, not response bodies: the route
#: answers every one of them with the same status and an empty detail.
REASON_BAD_SIGNATURE = "bad_signature"
REASON_STALE_TIMESTAMP = "stale_timestamp"
REASON_MISSING_SIGNATURE = "missing_signature"
REASON_MISSING_SECRET = "missing_secret"  # noqa: S105 - an audit reason word, not a credential  # pragma: allowlist secret
REASON_BAD_STATE = "bad_client_state"
REASON_BAD_PAYLOAD = "bad_payload"
REASON_UNKNOWN_PROVIDER = "unknown_provider"
REASON_BODY_TOO_LARGE = "body_too_large"
REASON_UNKNOWN_TRIGGER = "unknown_trigger"
REASON_TRIGGER_NOT_ACCEPTING = "trigger_not_accepting"
REASON_RATE_LIMITED = "rate_limited"
REASON_SCHEMA_MISMATCH = "schema_mismatch"
#: Not a refusal: the audit word for a subscription handshake, which is
#: answered without a trigger and therefore has no target to name.
REASON_HANDSHAKE = "handshake"

_SLACK_SIGNATURE_VERSION = "v0"
_WEBHOOK_SIGNATURE_VERSION = "v1"


class IngressRejected(Exception):  # noqa: N818 - a decision, not an error condition
    """A delivery that did not verify. The reason is audited, never returned."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class IngressRequest:
    """The raw delivery, as the verifiers need to see it."""

    provider: str
    body: bytes
    headers: Mapping[str, str]
    query: Mapping[str, str]

    def header(self, name: str) -> str | None:
        """Case-insensitive header lookup.

        Starlette's header mapping is already case-insensitive, but a verifier
        may be handed a plain dict by a test or by the renewal job, and a
        signature check that silently reads ``None`` because of header casing
        is a check that never fails and therefore never protects anything.
        """
        value = self.headers.get(name)
        if value is not None:
            return value
        lowered = name.lower()
        for key, candidate in self.headers.items():
            if key.lower() == lowered:
                return candidate
        return None


@dataclass(frozen=True)
class IngressSecrets:
    """Whatever this trigger's provider needs to verify a delivery.

    Resolved by the route before the verifier runs, so a verifier never touches
    the database and stays a pure function of bytes plus secrets - which is what
    makes it testable against recorded provider payloads.

    Microsoft's ``clientState`` and Google's channel token are held as SHA-256
    digests rather than as the values themselves. Langflow mints both and never
    has to replay either, so a comparison against a digest is all that is ever
    needed - and a database read that cannot yield the secret is one fewer place
    to leak it.
    """

    signing_secret: str | None = None
    client_state_digest: str | None = None
    channel_token_digest: str | None = None
    channel_id: str | None = None


def state_digest(value: str) -> str:
    """The stored form of a secret Langflow minted and only ever compares."""
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Verified:
    """A delivery that verified, and what the route should do with it.

    ``handshake`` short-circuits the ledger: a Graph ``validationToken`` echo or
    a Slack ``url_verification`` challenge is a subscription-lifecycle exchange,
    not an event, and writing one to the ledger would fire the flow with a
    payload that means nothing.
    """

    payload: dict[str, Any] = field(default_factory=dict)
    dedupe_suffix: str | None = None
    handshake: str | None = None
    handshake_media_type: str = "text/plain"
    #: ``(subscription_id, lifecycle_event)`` pairs. Graph sends these *instead*
    #: of the notification you were expecting, so a trigger whose subscription
    #: needs re-authorization looks perfectly healthy until they are acted on.
    #: They are not events: nothing is written to the ledger for one.
    lifecycle: tuple[tuple[str, str], ...] = ()


#: Graph's validationToken is a short opaque string it expects echoed verbatim.
#: Bounded and charset-checked because this is echoed to an anonymous caller
#: before any trigger is looked up: an unbounded echo is a reflection primitive.
_MAX_VALIDATION_TOKEN = 2048
_VALIDATION_TOKEN_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~+/= :")


def validation_token(provider: str, query: Mapping[str, str]) -> str | None:
    """The Graph subscription handshake token, if this request is one.

    Answered by the route *before* the trigger is resolved, so that the one
    exchange on this endpoint which carries no provider proof cannot also
    reveal whether a public id exists. Returning None means "not a handshake";
    a malformed token is treated the same way, so it falls through to the
    ordinary verification path and gets the ordinary refusal.
    """
    if provider != PROVIDER_MICROSOFT:
        return None
    token = query.get("validationToken")
    if not token or len(token) > _MAX_VALIDATION_TOKEN:
        return None
    if not set(token) <= _VALIDATION_TOKEN_ALLOWED:
        return None
    return token


def _json_body(body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(body or b"{}")
    except ValueError as exc:
        raise IngressRejected(REASON_BAD_PAYLOAD) from exc
    if not isinstance(parsed, dict):
        raise IngressRejected(REASON_BAD_PAYLOAD)
    return parsed


def _check_timestamp(raw: str | None, *, tolerance_s: int) -> int:
    if not raw:
        raise IngressRejected(REASON_MISSING_SIGNATURE)
    try:
        timestamp = int(float(raw))
    except (TypeError, ValueError) as exc:
        raise IngressRejected(REASON_STALE_TIMESTAMP) from exc
    # Both directions: a far-future timestamp is as much a replay tool as an old
    # one, because it would stay "fresh" for as long as the attacker likes.
    if abs(time.time() - timestamp) > tolerance_s:
        raise IngressRejected(REASON_STALE_TIMESTAMP)
    return timestamp


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def _require(secret: str | None, reason: str = REASON_MISSING_SECRET) -> str:
    if not secret:
        raise IngressRejected(reason)
    return secret


def verify_slack(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:
    """Slack request signing, plus the URL-verification handshake."""
    signature = request.header("X-Slack-Signature")
    if not signature:
        raise IngressRejected(REASON_MISSING_SIGNATURE)
    timestamp = _check_timestamp(request.header("X-Slack-Request-Timestamp"), tolerance_s=tolerance_s)
    secret = _require(secrets.signing_secret)
    basestring = f"{_SLACK_SIGNATURE_VERSION}:{timestamp}:".encode() + request.body
    expected = f"{_SLACK_SIGNATURE_VERSION}={_hmac_hex(secret, basestring)}"
    if not hmac.compare_digest(expected, signature):
        raise IngressRejected(REASON_BAD_SIGNATURE)

    payload = _json_body(request.body)
    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        if not isinstance(challenge, str):
            raise IngressRejected(REASON_BAD_PAYLOAD)
        return Verified(handshake=challenge)

    # Slack's retries at 0, 1, and 5 minutes carry the same event_id. Keying the
    # ledger on it is what turns three deliveries into one run.
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    suffix = payload.get("event_id") or event.get("event_ts") or event.get("ts")
    return Verified(payload=payload, dedupe_suffix=str(suffix) if suffix else None)


def verify_microsoft(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:  # noqa: ARG001
    """``clientState`` on every notification in the batch.

    The subscription handshake is *not* handled here. It carries no proof, so
    the route answers it with :func:`validation_token` before a trigger is
    resolved - one answer, in one place, that cannot depend on whether a public
    id exists. A handshake that somehow reached this function has no body and is
    refused as a malformed payload, which is the correct fallback.
    """
    payload = _json_body(request.body)
    notifications = payload.get("value")
    if not isinstance(notifications, list) or not notifications:
        raise IngressRejected(REASON_BAD_PAYLOAD)
    expected = _require(secrets.client_state_digest)
    for notification in notifications:
        if not isinstance(notification, dict):
            raise IngressRejected(REASON_BAD_PAYLOAD)
        supplied = notification.get("clientState")
        if not isinstance(supplied, str) or not hmac.compare_digest(state_digest(supplied), expected):
            raise IngressRejected(REASON_BAD_STATE)

    lifecycle = tuple(
        (str(notification.get("subscriptionId") or ""), str(notification["lifecycleEvent"]))
        for notification in notifications
        if notification.get("lifecycleEvent")
    )
    if lifecycle:
        return Verified(payload=payload, lifecycle=lifecycle)

    first = notifications[0]
    suffix = first.get("subscriptionId")
    resource_data = first.get("resourceData") if isinstance(first.get("resourceData"), dict) else {}
    resource_id = resource_data.get("id") or first.get("resource")
    # Graph basic notifications carry ids only; the run fetches the resource back
    # with the owner's connection. Nothing is fetched in this request.
    parts = [str(part) for part in (suffix, resource_id, first.get("changeType")) if part]
    return Verified(payload=payload, dedupe_suffix=":".join(parts) or None)


def verify_google(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:  # noqa: ARG001
    """The Google push channel token, bound to the channel it was minted for."""
    token = request.header("X-Goog-Channel-Token")
    if not token:
        raise IngressRejected(REASON_MISSING_SIGNATURE)
    if not hmac.compare_digest(state_digest(token), _require(secrets.channel_token_digest)):
        raise IngressRejected(REASON_BAD_SIGNATURE)
    channel_id = request.header("X-Goog-Channel-ID")
    if secrets.channel_id and not hmac.compare_digest(channel_id or "", secrets.channel_id):
        # A token is per channel. Accepting it for another channel would let one
        # watched resource drive a trigger armed against a different one.
        raise IngressRejected(REASON_BAD_STATE)

    message_number = request.header("X-Goog-Message-Number")
    resource_id = request.header("X-Goog-Resource-ID")
    resource_state = request.header("X-Goog-Resource-State")
    payload: dict[str, Any] = {
        "channel_id": channel_id,
        "resource_id": resource_id,
        "resource_state": resource_state,
        "resource_uri": request.header("X-Goog-Resource-URI"),
        "message_number": message_number,
    }
    if request.body:
        # Gmail's Pub/Sub push carries a body; Calendar and Drive channels do not.
        payload["body"] = _json_body(request.body)
    parts = [str(part) for part in (channel_id, message_number or resource_state) if part]
    return Verified(payload=payload, dedupe_suffix=":".join(parts) or None)


def verify_webhook(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:
    """The generic signed inbound webhook, with the trigger's own secret."""
    signature = request.header("X-Langflow-Signature")
    if not signature:
        raise IngressRejected(REASON_MISSING_SIGNATURE)
    timestamp = _check_timestamp(request.header("X-Langflow-Timestamp"), tolerance_s=tolerance_s)
    secret = _require(secrets.signing_secret)
    basestring = f"{_WEBHOOK_SIGNATURE_VERSION}:{timestamp}:".encode() + request.body
    expected = f"{_WEBHOOK_SIGNATURE_VERSION}={_hmac_hex(secret, basestring)}"
    if not hmac.compare_digest(expected, signature):
        raise IngressRejected(REASON_BAD_SIGNATURE)

    payload = _json_body(request.body)
    # The signature covers the body, so the body's own identity is a sound
    # dedupe key: a retried delivery of the same bytes at the same timestamp is
    # the same event, and a caller that wants two runs sends two bodies.
    digest = hashlib.sha256(f"{timestamp}:".encode() + request.body).hexdigest()[:32]
    return Verified(payload=payload, dedupe_suffix=digest)


_VERIFIERS = {
    PROVIDER_SLACK: verify_slack,
    PROVIDER_MICROSOFT: verify_microsoft,
    PROVIDER_GOOGLE: verify_google,
    PROVIDER_WEBHOOK: verify_webhook,
}


def verify(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:
    """Dispatch to the provider's verifier. Unknown providers are rejected."""
    verifier = _VERIFIERS.get(request.provider)
    if verifier is None:
        raise IngressRejected(REASON_UNKNOWN_PROVIDER)
    return verifier(request, secrets, tolerance_s=tolerance_s)


def sign_webhook_payload(secret: str, *, timestamp: int, body: bytes) -> str:
    """Produce the header a caller sends. Used by the test action and by docs.

    Shipping the signer next to the verifier is deliberate: a webhook whose
    documentation describes a signature nobody has computed with the same code
    is a webhook that rejects every real caller.
    """
    basestring = f"{_WEBHOOK_SIGNATURE_VERSION}:{timestamp}:".encode() + body
    return f"{_WEBHOOK_SIGNATURE_VERSION}={_hmac_hex(secret, basestring)}"
