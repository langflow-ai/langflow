"""Per-request state for the flow-builder tool surface.

Owns the asyncio-task-local working flow + flow id + event queue, plus the
``_emit`` push that mutating tools use to surface ``flow_update`` events to
the assistant service. Each async request gets its own values via
``ContextVar`` — safe under concurrency.

Also exposes the small node-shape utilities ``_find_node`` and
``_readable_preview`` that every tool layer needs; co-located here so no
"generic helpers" file is required.
"""

from __future__ import annotations

from collections import deque
from contextvars import ContextVar
from typing import Any

from lfx.graph.flow_builder.builder import load_local_registry
from lfx.graph.flow_builder.flow import empty_flow

# ---------------------------------------------------------------------------
# Registry loader (user-overlay aware)
# ---------------------------------------------------------------------------


def _load_registry_user_aware() -> dict[str, dict]:
    """Return the base registry merged with the calling user's overlay.

    Tries the langflow-side overlay (which reads the current_user_id
    ContextVar and walks ``<sandbox>/.components/*.py`` for that user).
    Falls back to the bare base registry when:
        - the langflow package isn't installed alongside lfx (e.g., the
          MCP server is running standalone),
        - no user is bound to the context.

    Keeps the lfx package free of a hard dependency on the langflow
    code path while letting the agent's tools see user-registered
    Components when both packages are co-installed.
    """
    try:
        from langflow.agentic.services.user_components_overlay import (
            load_registry_for_current_user,
        )
    except ImportError:
        return load_local_registry()
    return load_registry_for_current_user()


# ---------------------------------------------------------------------------
# Per-request state using contextvars. Each async request gets its own
# working flow, flow ID, and event queue -- safe under concurrency.
# ---------------------------------------------------------------------------

_flow_events_var: ContextVar[deque[dict[str, Any]]] = ContextVar("_flow_events_var")
_working_flow_var: ContextVar[dict | None] = ContextVar("_working_flow_var", default=None)
_current_flow_id_var: ContextVar[str | None] = ContextVar("_current_flow_id_var", default=None)


def _get_flow_events() -> deque[dict[str, Any]]:
    """Get the per-request event queue, creating one if needed."""
    try:
        return _flow_events_var.get()
    except LookupError:
        q: deque[dict[str, Any]] = deque()
        _flow_events_var.set(q)
        return q


def drain_flow_events() -> list[dict[str, Any]]:
    """Return and clear all pending flow update events."""
    q = _get_flow_events()
    events = list(q)
    q.clear()
    return events


def get_working_flow() -> dict | None:
    """Return the current working flow (for the assistant service)."""
    return _working_flow_var.get(None)


def init_working_flow(flow_data: dict, flow_id: str | None = None) -> None:
    """Initialize working flow from actual canvas data."""
    _working_flow_var.set(flow_data)
    _current_flow_id_var.set(flow_id)
    _get_flow_events().clear()


def reset_working_flow() -> None:
    """Reset the working flow state between requests."""
    _working_flow_var.set(None)
    _current_flow_id_var.set(None)
    _get_flow_events().clear()


def isolate_flow_run_context() -> None:
    """Rebind the per-run flow ContextVars to FRESH values.

    For a NESTED pipeline run (``GenerateComponent`` re-entering
    ``execute_flow_with_validation`` mid agent-loop), the parent loop's
    canvas/events must be invisible and untouchable. Unlike
    ``reset_working_flow()`` — which ``.clear()``s the event deque that a
    child context inherited *by reference* from the parent — this installs
    a brand-new deque, so the nested run can neither drain the parent's
    queued events nor wipe the parent's working flow.
    """
    _flow_events_var.set(deque())
    _working_flow_var.set(None)
    _current_flow_id_var.set(None)


def _emit(action: str, **data: Any) -> None:
    """Push a flow_update event."""
    _get_flow_events().append({"action": action, **data})


def _ensure_working_flow() -> dict:
    """Get or create the working flow."""
    flow = _working_flow_var.get(None)
    if flow is None:
        flow = empty_flow()
        _working_flow_var.set(flow)
    return flow


# ---------------------------------------------------------------------------
# Small node-shape utilities (used by every tool layer)
# ---------------------------------------------------------------------------


def _find_node(flow: dict, component_id: str) -> dict | None:
    """Find a node in the flow by component ID."""
    for node in flow.get("data", {}).get("nodes", []):
        nid = node.get("data", {}).get("id", node.get("id", ""))
        if nid == component_id:
            return node
    return None


def _readable_preview(value: Any, limit: int = 120) -> str:
    r"""One-line, human-readable rendering of a field value for a summary.

    The full value is carried separately (``new_value``/the patch) for the
    diff body — this is only the short headline. Uses ``repr()``-free
    formatting (no surrounding quotes, no escaped ``\n``) and collapses all
    whitespace so a multi-line system prompt doesn't blow up the card.
    """
    text = value if isinstance(value, str) else str(value)
    # Collapse BOTH real control chars and their two-char escape sequences
    # ("\\n"/"\\r"/"\\t") — LLMs emit either, and the card must never show
    # a literal backslash-n.
    for esc in ("\\n", "\\r", "\\t"):
        text = text.replace(esc, " ")
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text
