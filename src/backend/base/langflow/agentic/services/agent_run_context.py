"""ContextVar carrying the request's LLM provider/model across a request.

The ``generate_component`` MCP tool runs the component-generation LLM flow
*mid agent loop*. It needs the same provider/model/api-key the request was
made with, but threading those through every tool argument would clutter
the tool surface the LLM sees. Same rationale and lifecycle as
``user_components_context``: asyncio-task-local, set at request entry,
reset in the ``finally`` block.
"""

from __future__ import annotations

import contextvars
from typing import TypedDict


class AgentRunModel(TypedDict):
    provider: str | None
    model_name: str | None
    api_key_var: str | None


_model_var: contextvars.ContextVar[AgentRunModel | None] = contextvars.ContextVar(
    "agentic_run_model", default=None
)


def set_agent_run_model(provider: str | None, model_name: str | None, api_key_var: str | None) -> None:
    """Bind the request's provider/model/api-key to the current context."""
    _model_var.set({"provider": provider, "model_name": model_name, "api_key_var": api_key_var})


def current_agent_run_model() -> AgentRunModel | None:
    """Return the bound provider/model (or ``None`` when unset)."""
    return _model_var.get()


def reset_agent_run_model() -> None:
    """Clear the binding. Idempotent; safe without a prior set."""
    _model_var.set(None)
