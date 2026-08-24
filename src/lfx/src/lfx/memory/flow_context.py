"""Ambient flow-scope for chat-memory retrieval (defense-in-depth for old saved flows).

Langflow executes the *frozen* component ``code`` embedded in each saved flow, not the installed
library version (see ``lfx.interface.initialize.loading.instantiate_class`` ->
``eval_custom_component_code``). A flow saved before PR #13087 therefore carries the old
``MemoryComponent.retrieve_messages`` that calls ``aget_messages`` WITHOUT ``flow_id`` and leaks
chat history across flows on a colliding ``session_id`` (issue #13059) — even on a patched server,
because the fix only updated the library default, not code already frozen into saved flows.

This ContextVar carries the executing graph's ``flow_id`` so ``aget_messages`` can default the
scope when a caller omits it. It is bound only for the duration of a component's execution
(``get_instance_results``) and reset afterward, so:

* callers that pass ``flow_id`` explicitly are unaffected (the default applies only when ``None``),
* callers outside a graph run see an unset ContextVar and thus identical, legacy behavior.

This is not new semantics — it is the PR #13087 flow-scoping contract, applied at the platform
function the frozen code calls instead of inside the (unchangeable) frozen code.
"""

from __future__ import annotations

import contextvars
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

# Fixed namespace for turning an opaque (non-UUID) serving-plane end-user id into a
# stable UUID for the UUID-typed ``message.user_id`` column. ``uuid5`` is a pure
# function of (namespace, name), so the same end-user string always maps to the same
# UUID — across processes and pods — which is what makes the derived owner id usable
# as a durable, cross-pod query key. Any consumer that queries ``message.user_id`` by
# a raw end-user id (e.g. the Monitor API filter) MUST derive it through
# :func:`derive_message_owner_uuid` so the query matches what the write stamped.
_END_USER_UUID_NAMESPACE = uuid5(NAMESPACE_DNS, "end-user.serving.langflow.ai")

_current_flow_id: contextvars.ContextVar[str | UUID | None] = contextvars.ContextVar(
    "lfx_current_flow_id",
    default=None,
)


def get_current_flow_id() -> str | UUID | None:
    """Return the ``flow_id`` of the graph currently executing, or ``None`` outside a graph run."""
    return _current_flow_id.get()


def set_current_flow_id(flow_id: str | UUID | None) -> contextvars.Token[str | UUID | None]:
    """Bind *flow_id* as the ambient flow scope for the current async task / thread."""
    return _current_flow_id.set(flow_id)


def reset_current_flow_id(token: contextvars.Token[str | UUID | None]) -> None:
    """Restore the previous ambient flow scope."""
    _current_flow_id.reset(token)


# Ambient "may this run persist chat memory?" flag. Bound per component execution
# (next to the flow-id scope) from ``graph.persist_messages`` so ``astore_message``
# can skip the DB write for anonymous serving requests, which must run ephemerally.
# Defaults True so every existing path — anything not opting out — persists exactly
# as before.
_messages_persist: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "lfx_messages_persist",
    default=True,
)


def should_persist_messages() -> bool:
    """Return whether the current run may persist chat memory (True outside a run)."""
    return _messages_persist.get()


def set_messages_persist(persist: bool) -> contextvars.Token[bool]:  # noqa: FBT001
    """Bind the message-persistence flag for the current async task / thread."""
    return _messages_persist.set(persist)


def reset_messages_persist(token: contextvars.Token[bool]) -> None:
    """Restore the previous message-persistence flag."""
    _messages_persist.reset(token)


def _clean_identity(value: Any) -> str | UUID | None:
    """Return *value* unless it is missing or a placeholder ("None"/"null"/empty).

    ``PlaceholderGraph`` stringifies a missing user as ``"None"``, so a missing owner
    must read as *no owner*, not as a user literally named "None" (which would either
    over-filter retrieval to zero rows or mint a spurious namespace).
    """
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() in {"none", "null"}:
        return None
    return value


def _identity_candidates(graph: Any) -> list[str | UUID]:
    """The graph's user ids in preference order: end user first, then executing user.

    ``graph.end_user_id`` is the serving-plane end-user identity (present only when a
    serving entry point set it); ``graph.user_id`` is the executing user — the service
    account on the serving plane, the human on the editor plane. Placeholder/empty
    values are dropped. Values are returned with their original type.
    """
    candidates: list[str | UUID] = []
    for attr in ("end_user_id", "user_id"):
        value = _clean_identity(getattr(graph, attr, None))
        if value is not None:
            candidates.append(value)
    return candidates


def resolve_effective_user_id(graph: Any) -> str | UUID | None:
    """The user id this run scopes non-DB per-user state to (e.g. agent file writes).

    Prefers the serving-plane end-user id, else the executing user id. Returns the raw
    value (an opaque header string need not be a UUID), or ``None`` when neither is a
    real id. Use :func:`resolve_message_owner_id` instead for the UUID-typed
    ``message.user_id`` column.
    """
    candidates = _identity_candidates(graph)
    return candidates[0] if candidates else None


def derive_message_owner_uuid(end_user_id: str | UUID) -> UUID:
    """The UUID a serving-plane end-user id maps to in ``message.user_id``.

    A UUID-shaped id is used directly (the gateway contract says the id is a UUID); an
    opaque non-UUID id is turned into a *stable* UUID via ``uuid5`` so per-user rows
    stay separated in the UUID-typed column even when a gateway sends a non-UUID id.
    The mapping is deterministic across processes and pods, so any consumer querying
    ``message.user_id`` by a raw end-user id (e.g. the Monitor API filter) must resolve
    it through this same function for the predicate to match the stored owner.
    """
    coerced = coerce_flow_id(end_user_id)
    return coerced if coerced is not None else uuid5(_END_USER_UUID_NAMESPACE, str(end_user_id))


def resolve_message_owner_id(graph: Any) -> UUID | None:
    """The UUID to stamp on / query ``message.user_id`` for this run (write == read).

    ``message.user_id`` is UUID-typed. The serving-plane end-user id wins when present:
    it is mapped to a stable UUID via :func:`derive_message_owner_uuid` (direct when
    UUID-shaped, deterministically derived otherwise) so per-user separation survives a
    non-UUID gateway id and never crashes the write or raises on retrieval. With no end
    user, the executing (service-account / human) user id is used — it is already a
    UUID, so it is coerced only, never derived (a non-UUID there means no real owner and
    yields ``None`` → unscoped, as before). Both the write path
    (``Component._store_message``) and the read path (``_safe_graph_user_id``) resolve
    through this one function so the stored owner and the retrieval predicate agree.
    """
    end_user = _clean_identity(getattr(graph, "end_user_id", None))
    if end_user is not None:
        return derive_message_owner_uuid(end_user)
    executing = _clean_identity(getattr(graph, "user_id", None))
    if executing is not None:
        return coerce_flow_id(executing)
    return None


def coerce_flow_id(flow_id: str | UUID | None) -> UUID | None:
    """Coerce an ambient ``flow_id`` (usually ``graph.flow_id``, a ``str``) to ``UUID``.

    Returns ``None`` when the value is missing or not a valid UUID (synthetic/test graph ids),
    so retrieval degrades to the previous unscoped behavior rather than crashing.
    """
    if flow_id is None or flow_id == "":
        return None
    if isinstance(flow_id, UUID):
        return flow_id
    try:
        return UUID(str(flow_id))
    except (ValueError, TypeError, AttributeError):
        return None
