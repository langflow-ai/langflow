"""ContextVar that carries the calling user's id across a single request.

The MCP tools (``SearchComponentTypes``, ``DescribeComponentType``,
``AddComponent``, ``BuildFlowFromSpec``) need to know which user is on
the other end of the request so they can resolve the user's component
overlay. Threading ``user_id`` through every tool argument would clutter
the tool surface the LLM sees and require schema work; threading it
through a hook chain would couple modules that have no other relationship.

A ``ContextVar`` is the right primitive here for the same reasons it's
the right primitive for ``_working_flow_var`` and ``_flow_events_var``:
asyncio-task-local, no module globals, automatic isolation between
concurrent requests.

``assistant_service`` sets the value at request entry and resets in the
``finally`` block. Consumers call ``current_user_id()`` to read it.
"""

from __future__ import annotations

import contextvars

_user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("agentic_current_user_id", default=None)


def set_current_user_id(user_id: str | None) -> None:
    """Bind ``user_id`` to the current async-task context.

    Pass ``None`` to clear. ``reset_current_user_id`` is the named
    alias the request handler should call in its ``finally`` block.
    """
    _user_id_var.set(user_id)


def current_user_id() -> str | None:
    """Return the user_id bound to the current context (or ``None``)."""
    return _user_id_var.get()


def reset_current_user_id() -> None:
    """Clear the bound user_id. Idempotent; safe to call without a prior set."""
    _user_id_var.set(None)
