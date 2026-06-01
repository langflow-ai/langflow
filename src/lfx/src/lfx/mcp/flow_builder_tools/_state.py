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
# Snapshot of the component IDs present on the canvas at the START of the turn
# (captured by init_working_flow). Used to tell a pre-existing component (an
# EDIT target) apart from one added during this turn (part of a BUILD).
_initial_node_ids_var: ContextVar[frozenset[str]] = ContextVar("_initial_node_ids_var", default=frozenset())
# When True, a ``configure_component`` on a PRE-EXISTING component is converted
# into a reviewable ``edit_field`` proposal for its text-content fields instead
# of being auto-applied. The assistant service sets this for PURE-edit turns
# (no run requested), guaranteeing "improve the prompt"-style edits ALWAYS show
# the diff card regardless of which tool the LLM chose. Default False so every
# other path (fresh build, build+run, run, continuation) keeps applying live.
_propose_existing_edits_var: ContextVar[bool] = ContextVar("_propose_existing_edits_var", default=False)


def _collect_node_ids(flow_data: dict | None) -> frozenset[str]:
    """Return the set of component IDs in a flow dict (data.id or top-level id)."""
    nodes = ((flow_data or {}).get("data") or {}).get("nodes") or []
    ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = (node.get("data") or {}).get("id") or node.get("id")
        if isinstance(nid, str) and nid:
            ids.add(nid)
    return frozenset(ids)


def node_existed_at_start(component_id: str) -> bool:
    """True if the component was already on the canvas when the turn began."""
    return component_id in _initial_node_ids_var.get(frozenset())


def set_propose_existing_edits(*, enabled: bool) -> None:
    """Enable/disable converting configure→propose for pre-existing components."""
    _propose_existing_edits_var.set(enabled)


def should_propose_existing_edits() -> bool:
    """Whether edits to pre-existing components should surface as review cards."""
    return _propose_existing_edits_var.get(False)


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
    # Snapshot which components already existed so edits to them can later be
    # told apart from components added during this turn.
    _initial_node_ids_var.set(_collect_node_ids(flow_data))
    _get_flow_events().clear()


def reset_working_flow() -> None:
    """Reset the working flow state between requests."""
    _working_flow_var.set(None)
    _current_flow_id_var.set(None)
    _initial_node_ids_var.set(frozenset())
    _propose_existing_edits_var.set(False)
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
    # A nested pipeline run must not inherit the parent turn's edit-review mode
    # nor its initial-node snapshot — those belong to the parent canvas only.
    _initial_node_ids_var.set(frozenset())
    _propose_existing_edits_var.set(False)


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
