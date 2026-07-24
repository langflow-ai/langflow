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
from typing import TYPE_CHECKING, Any

from lfx.graph.flow_builder.builder import load_local_registry
from lfx.graph.flow_builder.flow import empty_flow
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable


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


_flow_events_var: ContextVar[deque[dict[str, Any]]] = ContextVar("_flow_events_var")
_working_flow_var: ContextVar[dict | None] = ContextVar("_working_flow_var", default=None)
_current_flow_id_var: ContextVar[str | None] = ContextVar("_current_flow_id_var", default=None)
# Canvas component IDs at the START of the turn (set by init_working_flow) so a
# pre-existing component (EDIT target) is distinguishable from one added this turn.
_initial_node_ids_var: ContextVar[frozenset[str]] = ContextVar("_initial_node_ids_var", default=frozenset())
# When True, configure_component on a PRE-EXISTING component becomes a reviewable
# edit_field proposal (pure-edit turns); default False keeps every other path live.
_propose_existing_edits_var: ContextVar[bool] = ContextVar("_propose_existing_edits_var", default=False)
# Headless MCP has no UI to apply a reviewable proposal, so the propose tools
# apply live and narrate it as done. Default False keeps UI review cards.
_apply_edits_live_var: ContextVar[bool] = ContextVar("_apply_edits_live_var", default=False)
# Live "tool started" callback installed by the streaming executor; None means
# no consumer (headless MCP, nested runs) and emits are silent no-ops.
_tool_start_listener_var: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar(
    "_tool_start_listener_var", default=None
)


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


def set_apply_edits_live(*, enabled: bool) -> None:
    """Enable/disable applying proposed edits live (headless callers with no review UI)."""
    _apply_edits_live_var.set(enabled)


def should_apply_edits_live() -> bool:
    """Whether proposed edits should be applied live instead of surfaced for review."""
    return _apply_edits_live_var.get(False)


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
    _apply_edits_live_var.set(False)
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
    _apply_edits_live_var.set(False)
    _tool_start_listener_var.set(None)


def _emit(action: str, **data: Any) -> None:
    """Push a flow_update event."""
    _get_flow_events().append({"action": action, **data})


def set_tool_start_listener(listener: Callable[[dict[str, Any]], None] | None) -> None:
    """Install (or clear) the per-context live tool-start callback.

    The streaming executor installs a listener that forwards payloads onto its
    event queue so the SSE consumer sees "tool started" WHILE the tool runs —
    unlike ``_emit``, whose deque is only drained between LLM tokens.
    """
    _tool_start_listener_var.set(listener)


def emit_tool_start(tool: str, **data: Any) -> None:
    """Announce that a canvas-mutating tool began executing.

    Silent no-op when no listener is installed (headless MCP, nested runs).
    Listener failures are swallowed: a UI indicator must never break the tool.
    """
    listener = _tool_start_listener_var.get()
    if listener is None:
        return
    try:
        listener({"tool": tool, **data})
    except Exception:  # noqa: BLE001
        logger.debug("tool_start listener failed for tool=%s", tool)


def _ensure_working_flow() -> dict:
    """Get or create the working flow."""
    flow = _working_flow_var.get(None)
    if flow is None:
        flow = empty_flow()
        _working_flow_var.set(flow)
    return flow


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
    # Collapse real control chars AND their two-char escape sequences ("\\n" etc.)
    # — LLMs emit either, and the card must never show a literal backslash-n.
    for esc in ("\\n", "\\r", "\\t"):
        text = text.replace(esc, " ")
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text
