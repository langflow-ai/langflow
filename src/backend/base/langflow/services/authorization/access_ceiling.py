"""Request-scoped action ceiling (deny-only) enforced by authorization guards.

This is an authorization primitive: a coarse, deny-only cap on which actions a
request may perform, stored in a context variable for the lifetime of the
request/task. The authentication layer derives the ceiling from a trusted
external identity (see
``langflow.services.auth.external.access_context_from_identity``) and installs
it via :func:`set_current_external_access_context`; the guards in this package
consult it. Keeping the primitive here lets authorization enforce the ceiling
without importing the authentication layer, preserving the auth/authz split
documented in AGENTS.md.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

EXTERNAL_ACCESS_VIEWER = "viewer"
EXTERNAL_ACCESS_EDITOR = "editor"
EXTERNAL_ACCESS_ADMIN = "admin"
EXTERNAL_ACCESS_LEVELS = frozenset(
    {
        EXTERNAL_ACCESS_VIEWER,
        EXTERNAL_ACCESS_EDITOR,
        EXTERNAL_ACCESS_ADMIN,
    }
)
_VIEWER_ALLOWED_ACTIONS = frozenset({"read"})
_EDITOR_ALLOWED_ACTIONS = frozenset({"read", "write", "create", "execute", "ingest"})


@dataclass(frozen=True)
class ExternalAccessContext:
    """Request-local access ceiling derived from an external identity claim."""

    provider: str
    subject: str
    level: str
    claim_name: str | None = None
    claim_value: str | None = None


_current_external_access: ContextVar[ExternalAccessContext | None] = ContextVar(
    "langflow_external_access",
    default=None,
)


def set_current_external_access_context(context: ExternalAccessContext | None) -> None:
    """Store the external access ceiling for the current request/task."""
    _current_external_access.set(context)


def clear_current_external_access_context() -> None:
    """Clear any external access ceiling from the current request/task."""
    _current_external_access.set(None)


def get_current_external_access_context() -> ExternalAccessContext | None:
    """Return the external access ceiling for the current request/task, if any."""
    return _current_external_access.get()


def external_access_allows(action: str, context: ExternalAccessContext | None = None) -> bool:
    """Return whether the external access ceiling allows this action.

    This is deliberately action-level and deny-only. It does not grant access to
    resources; normal ownership, route guards, and enterprise authz plugins still
    decide whether an otherwise allowed action may proceed.
    """
    context = context if context is not None else get_current_external_access_context()
    if context is None:
        return True

    normalized_action = action.strip().lower()
    if context.level == EXTERNAL_ACCESS_ADMIN:
        return True
    if context.level == EXTERNAL_ACCESS_EDITOR:
        return normalized_action in _EDITOR_ALLOWED_ACTIONS
    return normalized_action in _VIEWER_ALLOWED_ACTIONS


def filter_actions_by_external_access_ceiling(actions: list[str] | tuple[str, ...]) -> list[str]:
    """Filter an action list through the current external access ceiling."""
    context = get_current_external_access_context()
    if context is None:
        return list(actions)
    return [action for action in actions if external_access_allows(action, context)]
