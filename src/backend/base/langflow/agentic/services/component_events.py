"""Per-request event queue for component-generation failures.

The ``GenerateComponent`` tool runs inside the single agent loop that powers a
compound request ("create a component AND build a flow with it"). When the
generation sub-task fails validation, the tool used to hand the agent only an
error string — which the agent could bury in prose or paper over by
substituting a generic component, leaving the user with no clear signal that
the component they asked for was never built.

This queue lets the tool push a structured failure payload that
``assistant_service`` drains between LLM tokens and forwards to the SSE client
as a ``validation_failed`` progress event — surfaced honestly regardless of
what the agent decides to say.

Mirrors ``langflow.agentic.services.file_events`` and
``lfx.mcp.flow_builder_tools._flow_events_var``: a per-request ContextVar so
concurrent SSE sessions stay isolated, with the deque shared by reference into
child tasks spawned within the same request.
"""

from __future__ import annotations

import contextvars
from collections import deque
from typing import Any

# Per-request queue; default=None so each context lazily gets its own deque
# (a context created by ``copy_context().run(...)`` must not share the parent's
# object unless the parent pre-allocated it via ``reset_component_events``).
_component_events_var: contextvars.ContextVar[deque[dict[str, Any]] | None] = contextvars.ContextVar(
    "_component_events_var",
    default=None,
)


def _get_component_events() -> deque[dict[str, Any]]:
    queue = _component_events_var.get()
    if queue is None:
        queue = deque()
        _component_events_var.set(queue)
    return queue


def emit_component_generation_failed(
    *,
    error: str,
    class_name: str | None = None,
    component_code: str | None = None,
) -> None:
    """Push a component-generation failure onto the per-request queue.

    Args:
        error: Compact, user-safe reason the component could not be generated.
        class_name: The class name the generator was attempting, when known.
        component_code: The last (invalid) code, when available — lets the
            frontend offer it for inspection instead of discarding it silently.
    """
    if not error:
        msg = "emit_component_generation_failed: error must be non-empty"
        raise ValueError(msg)
    payload: dict[str, Any] = {"error": error}
    if class_name:
        payload["class_name"] = class_name
    if component_code:
        payload["component_code"] = component_code
    _get_component_events().append(payload)


def drain_component_events() -> list[dict[str, Any]]:
    """Return and clear all pending component events for the current context.

    Does NOT lazily allocate: a drain in the parent context must not write a
    shared deque into the ContextVar that child tasks would then inherit and
    mutate in lockstep (mirrors ``drain_file_events``).
    """
    queue = _component_events_var.get()
    if queue is None:
        return []
    drained = list(queue)
    queue.clear()
    return drained


def reset_component_events() -> None:
    """Allocate a fresh queue in the current context for this request.

    Pre-allocates a new empty deque so child tasks spawned by this request
    (the agent's LLM call and its wrapped tool invocations) inherit the same
    deque by reference and their emits become visible to the drain calls back
    in the parent. Cross-request isolation comes from each HTTP request getting
    its own task context.
    """
    _component_events_var.set(deque())
