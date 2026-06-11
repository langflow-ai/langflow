"""Helpers shared by transport components.

Transports need the per-session ``WebSocket`` (and any other per-call values
like ``stream_sid`` / ``call_sid`` for telephony). These are not known at
canvas-design time — they exist only when an actual connection is open.

The Langflow API layer (Phase 7) injects a session dict into the graph's
context via ``Graph.from_payload(session_context=...)`` (Phase 6). Components
call ``get_session()`` below to read it.
"""

from typing import Any


def get_session(component: Any) -> dict:
    """Return the session-context dict injected by the API layer.

    Raises a clear ``RuntimeError`` if the graph wasn't loaded with a
    ``session_context``. That happens when:
      - the component is built outside a live WebSocket session (e.g. canvas
        validation, a unit test), or
      - the Phase 6 loader change hasn't shipped yet.
    """
    graph = getattr(component, "graph", None)
    if graph is None:
        msg = (
            f"{type(component).__name__} requires a live session but has no "
            "graph attached. This component can only run inside a Voice Pipeline "
            "loaded via the /voice WebSocket endpoint."
        )
        raise RuntimeError(msg)
    context = getattr(graph, "context", {}) or {}
    session = context.get("session") if isinstance(context, dict) else None
    if not session:
        msg = (
            f"{type(component).__name__} requires a session context. "
            "The Langflow API layer must call Graph.from_payload(session_context=...) "
            "with at least a 'websocket' entry."
        )
        raise RuntimeError(msg)
    return session


def get_websocket(component: Any) -> Any:
    """Return the live WebSocket object from the session context."""
    session = get_session(component)
    websocket = session.get("websocket")
    if websocket is None:
        msg = f"{type(component).__name__}: session context missing 'websocket'."
        raise RuntimeError(msg)
    return websocket
