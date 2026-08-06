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
from uuid import UUID

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
