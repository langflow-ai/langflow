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
effective ``session_id``; an anonymous request keeps its requested session but is
marked non-persisting so nothing accumulates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Separator between the end-user id and the caller's session id in a merged scope
# key. A pipe is not produced by ``uuid`` / typical opaque ids, so it keeps the
# two parts visually and programmatically distinguishable.
SCOPE_SEPARATOR = "::"


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
    not write per-user memory.
    """

    session_id: str
    persist: bool


class EndUserIdentityRequiredError(Exception):
    """A request carried no end-user identity while one was required.

    Route layers map this to a client error (HTTP 401). It is raised only when the
    feature is on (a header name is configured) and identity is required, so it
    never fires in the default fully-anonymous configuration.
    """


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
    omitting it and falling back to the flow id — never collide. For an anonymous
    request the session is left as requested but marked non-persisting.

    Args:
        identity: The resolved end-user identity.
        requested_session_id: The ``session_id`` from the request body, if any.
        default_session_id: The fallback when the request omits a session id
            (the flow id today, matching ``run_graph_internal``).

    Returns:
        A :class:`ScopedSession` with the effective session id and whether the
        run may persist per-user memory.
    """
    base = requested_session_id or default_session_id
    if identity.is_anonymous:
        return ScopedSession(session_id=base, persist=False)
    return ScopedSession(session_id=f"{identity.id}{SCOPE_SEPARATOR}{base}", persist=True)
