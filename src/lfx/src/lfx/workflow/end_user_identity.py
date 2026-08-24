"""Serving-plane end-user identity resolution and memory scoping.

The serving plane accepts requests with or without an end-user identity. When an
identity is present, per-user memory/state is scoped to it; when absent, the
request runs as an anonymous, ephemeral session with no persisted per-user
memory.

The identity travels in a trusted request header
(``LANGFLOW_SERVING_END_USER_HEADER``, e.g. ``X-End-User-Id``) whose value is an
opaque, deterministic per-user string minted and injected by the authenticated
gateway. Langflow does not parse or validate it (the gateway validates the
upstream JWT); it is used only as the per-user memory-scope key.

Trust is fail-closed. The header is honored ONLY when
``LANGFLOW_SERVING_TRUST_PROXY_HEADERS`` is True, because an unverified
client-supplied header would let any caller read another user's memory. Enabling
trust is an explicit opt-in that assumes the deployment guarantees:

1. the authenticated gateway injects/overwrites the header from a validated
   identity (so a client-supplied copy cannot survive), and
2. network policy makes that gateway the only caller able to reach the serving
   pods (so the gateway cannot be bypassed).

Scoping (see :func:`scope_session_for_identity`) follows the decision that memory
is keyed by ``(end-user id, session_id)`` so one user can run several parallel
conversations: for an identified request the end-user id is merged into the
effective ``session_id`` (idempotently, so a client echoing the returned key does
not get re-scoped); an anonymous request is moved into a reserved, per-request
random namespace and marked non-persisting, so it can neither accumulate memory
nor address an identified user's existing session key.

"No persisted per-user memory" covers what Langflow itself writes for a run: chat
messages, transaction rows, and vertex-build rows. It cannot cover stores outside
Langflow's own database — external tracing backends or memory services a flow
author explicitly wires in (e.g. an external chat-memory component) are the flow
author's responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable

# Separator between the end-user id and the caller's session id in a merged scope
# key. Chosen because it does not occur in a ``uuid`` or typical opaque gateway
# ids, keeping the two parts visually distinguishable.
#
# Cross-user isolation does NOT depend on this: the prefix is always the *authenticated*
# end-user id (the gateway mints it; a client cannot forge it), so one user can never
# reach another's namespace regardless of the session id they send. The separator only
# affects collisions WITHIN a single end-user, and the merge is injective as long as the
# end-user id does not itself contain the separator — e.g. ("a", "b::c") and ("a::b", "c")
# both render "a::b::c". Gateway-minted ids are expected to be separator-free (uuid /
# opaque token). If a gateway can mint ids containing "::", switch to a length-prefixed or
# percent-encoded join here. See the serving-plane end-user header contract.
SCOPE_SEPARATOR = "::"

# Reserved namespace for anonymous requests. The random per-request component makes
# the scope unguessable and collision-free even against a gateway that mints the
# literal end-user id "anon", so an anonymous caller can never address — and thus
# never read — any pre-existing session's memory.
ANONYMOUS_SESSION_PREFIX = f"anon{SCOPE_SEPARATOR}"


@dataclass(frozen=True)
class EndUserIdentity:
    """The resolved end-user identity for a serving request.

    ``id`` is the opaque per-user scope key, or ``None`` for an anonymous request.
    """

    id: str | None = None

    @property
    def is_anonymous(self) -> bool:
        return self.id is None


# Shared instance for the anonymous outcome — the common case, and cheap to reuse
# since the dataclass is frozen.
ANONYMOUS = EndUserIdentity(id=None)


@dataclass(frozen=True)
class ScopedSession:
    """Result of scoping a request's session to its end-user identity.

    ``session_id`` is the effective key the run should execute and persist under.
    ``persist`` is False for anonymous requests, which run ephemerally and must
    not write per-user memory. ``end_user_id`` is the raw end-user id the run should
    stamp onto ``graph.end_user_id`` (``None`` for an anonymous request), carried here
    so every serving entry point — v1 and v2 — reads it from the one shared helper.
    """

    session_id: str
    persist: bool
    end_user_id: str | None = None


class EndUserIdentityRequiredError(Exception):
    """A request carried no end-user identity while one was required.

    Route layers map this to a client error (HTTP 401). It is raised only when the
    feature is on (a header name is configured) and identity is required, so it
    never fires in the default fully-anonymous configuration.
    """


# Stable error code every serving entry point returns for a required-but-absent identity.
END_USER_IDENTITY_REQUIRED_CODE = "END_USER_IDENTITY_REQUIRED"


def end_user_required_detail(exc: EndUserIdentityRequiredError) -> dict[str, str]:
    """Transport-neutral error body for a required-but-absent identity (mapped to HTTP 401).

    Shared by every serving entry point (v2 router, v1 ``/run``, webhook, ...) so the
    ``code``/shape a client sees is identical no matter which door rejected the request.
    """
    return {
        "error": "End-user identity required",
        "code": END_USER_IDENTITY_REQUIRED_CODE,
        "message": str(exc),
    }


def resolve_end_user_identity(
    *,
    header_name: str | None,
    trust_proxy_headers: bool,
    require_identity: bool,
    get_header: Callable[[str], str | None],
) -> EndUserIdentity:
    """Resolve the end-user identity for one serving request.

    Args:
        header_name: Configured trusted-header name, or ``None``/empty when the
            feature is off.
        trust_proxy_headers: Whether the header is trusted at all (fail-closed
            opt-in). When False the header is ignored entirely.
        require_identity: Whether a request that resolves to anonymous is rejected.
        get_header: Case-insensitive header lookup returning the raw value or
            ``None`` (e.g. ``request.headers.get``).

    Returns:
        The resolved :class:`EndUserIdentity`; :data:`ANONYMOUS` when no trusted
        identity is present.

    Raises:
        EndUserIdentityRequiredError: When ``require_identity`` is set (and the
            feature is on) but no trusted identity could be resolved.
    """
    # Feature off: no header configured means fully anonymous. ``require_identity``
    # is moot here — the operator has not turned the feature on, so we never reject.
    if not header_name:
        return ANONYMOUS

    # Fail-closed trust gate: without an explicit opt-in the header is never read,
    # so a spoofed client-supplied header cannot leak into memory scoping. If the
    # operator also required identity, this combination rejects every request —
    # a loud, deliberate misconfiguration signal rather than a silent bypass.
    if not trust_proxy_headers:
        if require_identity:
            msg = (
                "End-user identity is required but LANGFLOW_SERVING_TRUST_PROXY_HEADERS is "
                "false, so the identity header is never trusted; no request can be identified."
            )
            raise EndUserIdentityRequiredError(msg)
        return ANONYMOUS

    # Anonymous requests omit the header entirely; treat empty/whitespace the same.
    raw = get_header(header_name)
    value = raw.strip() if raw else ""
    if not value:
        if require_identity:
            msg = f"End-user identity is required but the {header_name!r} header is missing."
            raise EndUserIdentityRequiredError(msg)
        return ANONYMOUS

    return EndUserIdentity(id=value)


def serving_end_user_enabled() -> bool:
    """Whether the serving-plane end-user identity feature is configured on.

    True iff an end-user header name is set (``LANGFLOW_SERVING_END_USER_HEADER``). This is
    the *deployment-level* switch, independent of whether any single request carries the
    header — so an anonymous serving request (no header) still reports the feature as on.

    Security gates use this to decide whether the shared service account (the SID, which is a
    superuser) must be subject to end-user scoping: on the serving plane the SID is the only
    principal, so its superuser bypass has to be suppressed whenever the feature is on, even
    for header-less requests. Off (the default) -> byte-for-byte pre-feature behavior.
    """
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    settings = settings_service.settings if settings_service is not None else None
    return bool(settings.serving_end_user_header) if settings is not None else False


def end_user_id_from_scoped_session(session_id: str | None) -> str | None:
    """The end-user id embedded in a serving-scoped session id, or ``None``.

    Serving scoping (:func:`scope_session_for_identity`) produces ``<end_user>::<base>``
    for an identified run and ``anon::<uuid>`` for an anonymous one. This recovers the
    end-user id from that already-scoped session id — the one value **every** ingestion
    path carries (live run, ``regenerate`` reconcile, manual trigger), unlike
    ``graph.end_user_id`` which only the live run path has.

    Memory Base ingestion stamps this onto each chunk and retrieval filters on it, so a
    query with ``filter_by_session`` off still stays within one end user instead of
    spanning the whole SID-owned store. Both sides key off this one helper, so a chunk's
    stamped owner and the query predicate are identical by construction.

    Returns ``None`` when the feature is off, the session is anonymous, or it carries no
    scope prefix — so feature-off / editor sessions stamp and filter nothing (byte-for-byte
    unchanged). The split is on the first separator, so an end-user id that itself contains
    ``::`` collapses to its leading segment; harmless because both sides derive identically
    (no leak, no relative recall loss) and gateway ids are opaque strings, typically UUIDs
    with no separator.
    """
    if not session_id or not serving_end_user_enabled():
        return None
    prefix, sep, _ = session_id.partition(SCOPE_SEPARATOR)
    if not sep or not prefix or f"{prefix}{SCOPE_SEPARATOR}" == ANONYMOUS_SESSION_PREFIX:
        return None
    return prefix


def resolve_serving_end_user_id(*, http_request: Any) -> str | None:
    """The raw trusted end-user id for a serving request, or ``None`` when off / anonymous.

    Mirrors :func:`resolve_serving_scope`'s identity resolution but returns just the raw
    end-user id (no session merge) — for callers that need the owner key to stamp / check a
    job (its ``job_metadata['end_user_id']``), not a scoped session. Returns ``None`` when the
    feature is off (no header configured), the header is untrusted, or the request is
    anonymous, so callers fall back to the executing (service-account) user and preserve
    pre-feature behavior.

    This is a *pure identifier* resolver, never a gate: it forces ``require_identity`` off so
    a status/stop/resume call can never raise here (the required-identity gate is a run-entry
    concern, already enforced by :func:`resolve_serving_scope` at the run door). ``http_request``
    only needs a case-insensitive ``headers.get(name)`` (duck-typed so lfx need not import the
    web framework).
    """
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    settings = settings_service.settings if settings_service is not None else None
    header_name = settings.serving_end_user_header if settings is not None else None
    if not header_name:
        return None

    identity = resolve_end_user_identity(
        header_name=header_name,
        trust_proxy_headers=bool(settings.serving_trust_proxy_headers),
        require_identity=False,
        get_header=http_request.headers.get,
    )
    return identity.id


def scope_session_for_identity(
    identity: EndUserIdentity,
    *,
    requested_session_id: str | None,
    default_session_id: str,
) -> ScopedSession:
    """Scope a request's session to its end-user identity.

    Memory is keyed by ``(end-user id, session_id)``. For an identified request
    the end-user id is prepended to the caller's session id (or the flow default
    when none was supplied), so two end-users sharing a session id — or both
    omitting it and falling back to the flow id — never collide. The merge is
    idempotent: a caller echoing back the effective key from a previous response
    (the normal Langflow contract) is not re-scoped into a fresh namespace.

    An anonymous request is moved into the reserved ``anon::<random>`` namespace
    and marked non-persisting. Its requested session id is deliberately ignored:
    session ids are read-scope keys, and honoring a client-supplied value would
    let an unauthenticated caller execute in — and read memory from — any
    identified user's session it can guess. An anonymous run persists nothing, so
    it has no legitimate use for a pre-existing session key.

    Args:
        identity: The resolved end-user identity.
        requested_session_id: The ``session_id`` from the request body, if any.
        default_session_id: The fallback when the request omits a session id
            (the flow id today, matching ``run_graph_internal``).

    Returns:
        A :class:`ScopedSession` with the effective session id and whether the
        run may persist per-user memory.
    """
    if identity.is_anonymous:
        return ScopedSession(session_id=f"{ANONYMOUS_SESSION_PREFIX}{uuid4()}", persist=False, end_user_id=None)
    prefix = f"{identity.id}{SCOPE_SEPARATOR}"
    base = requested_session_id or default_session_id
    # A key echoed from a previous response already carries this user's own prefix;
    # strip it once so the merge is idempotent. Another user's prefix never matches
    # (the gateway authenticated *this* id), so cross-user keys cannot be unwrapped.
    base = base.removeprefix(prefix)
    return ScopedSession(session_id=f"{prefix}{base}", persist=True, end_user_id=identity.id)


def resolve_serving_scope(
    *,
    http_request: Any,
    requested_session_id: str | None,
    default_session_id: str,
) -> ScopedSession | None:
    """Resolve the serving-plane session scope for one request, or ``None`` when off.

    Single source of the session-scoping decision for every serving entry point (the v2
    workflow router, v1 ``/run``, webhook, ...). Reads lfx serving settings, resolves the
    trusted end-user identity, and returns the :class:`ScopedSession` (effective
    ``session_id`` + ``persist``). ``None`` means the feature is off (no header
    configured), so the caller must leave the session and persistence untouched —
    byte-for-byte the pre-feature behavior, which is the default configuration.

    ``http_request`` only needs a case-insensitive ``headers.get(name)`` (e.g. a FastAPI
    ``Request``); it is duck-typed so lfx need not import the web framework. Callers map
    the raised error to their transport (HTTP 401).

    Raises:
        EndUserIdentityRequiredError: identity is required but absent (feature on).
    """
    # Imported lazily so this module stays import-light and free of a hard service-layer
    # dependency; the pure resolve/scope helpers above remain independently testable.
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    settings = settings_service.settings if settings_service is not None else None
    header_name = settings.serving_end_user_header if settings is not None else None
    if not header_name:
        return None

    identity = resolve_end_user_identity(
        header_name=header_name,
        trust_proxy_headers=bool(settings.serving_trust_proxy_headers),
        require_identity=bool(settings.serving_end_user_required),
        get_header=http_request.headers.get,
    )
    return scope_session_for_identity(
        identity,
        requested_session_id=requested_session_id,
        default_session_id=default_session_id,
    )
