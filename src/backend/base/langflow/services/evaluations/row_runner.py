"""Execute one dataset row against a pinned flow snapshot, isolated from the Playground."""

from __future__ import annotations

import copy
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lfx.graph.graph.base import Graph
from lfx.memory.flow_context import reset_evals_memory_isolated, set_evals_memory_isolated
from lfx.schema.schema import InputValueRequest
from lfx.services.model_provider_policy import (
    reset_current_model_provider_policy_context,
    set_current_model_provider_policy_context,
)

from langflow.api.utils.execution_principal import FAMILY_V1_RUN, execution_principal_for, stamp_execution_principal
from langflow.processing.process import run_graph_internal
from langflow.services.evaluations.pricing import cost_usd, model_identity
from langflow.services.model_provider_policy_scope import provider_policy_attributes_for_flow

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID

    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User

ERROR_MAX_CHARS = 2000
# A row's chat input goes to Chat Input and Text Input alike.
ROW_INPUT_TYPE = "any"


@dataclass(frozen=True)
class RowExecution:
    actual: str | None
    error: str | None
    duration_ms: int
    tokens: int | None
    cost: float | None
    trace_id: str


def row_session_id(run_id: UUID, position: int) -> str:
    return f"eval:{run_id}:{position}"


def output_text(graph: Graph, output_vertex_id: str) -> str | None:
    vertex = graph.get_vertex(output_vertex_id)
    result = getattr(vertex, "result", None) if vertex is not None else None
    values = list((getattr(result, "results", None) or {}).values())
    for value in values:
        text = getattr(value, "text", None)
        if isinstance(text, str):
            return text
        if isinstance(value, str):
            return value
    return None


def _vertex_model(vertex: Any) -> dict[str, Any] | None:
    template = ((vertex.data or {}).get("node") or {}).get("template") or {}
    model_field = template.get("model")
    return model_identity(model_field.get("value")) if isinstance(model_field, dict) else None


def flow_usage(graph: Graph) -> tuple[int | None, float | None]:
    """Sum token usage over the graph's own LLM vertices; cost is None unless every one is priced.

    Output vertices are skipped because Chat Output re-sums upstream usage into its message.
    """
    tokens = 0
    cost: float | None = 0.0
    seen = False
    for vertex in graph.vertices:
        usage = getattr(getattr(vertex, "custom_component", None), "_token_usage", None)
        if vertex.is_output or usage is None:
            continue
        seen = True
        input_tokens, output_tokens = usage.input_tokens or 0, usage.output_tokens or 0
        tokens += input_tokens + output_tokens
        vertex_cost = cost_usd(_vertex_model(vertex), input_tokens, output_tokens)
        cost = None if cost is None or vertex_cost is None else cost + vertex_cost
    if not seen:
        return None, None
    return tokens, cost


def _short_error(exc: BaseException) -> str:
    text = str(exc) or type(exc).__name__
    return text if len(text) <= ERROR_MAX_CHARS else text[:ERROR_MAX_CHARS] + "..."


def build_row_graph(graph_data: dict[str, Any], flow: Flow, user: User) -> Graph:
    graph = Graph.from_payload(
        copy.deepcopy(graph_data), flow_id=str(flow.id), user_id=str(user.id), flow_name=flow.name
    )
    stamp_execution_principal(graph, execution_principal_for(FAMILY_V1_RUN, user=user, flow_owner_id=flow.user_id))
    graph.persist_messages = False
    return graph


@contextmanager
def flow_policy_scope(flow: Flow, user: User) -> Iterator[None]:
    """The flow's model-provider policy scope; the judge is resolved inside it too."""
    token = set_current_model_provider_policy_context(
        user_id=user.id,
        attributes=provider_policy_attributes_for_flow(flow, is_superuser=bool(user.is_superuser), required=True),
    )
    try:
        yield
    finally:
        reset_current_model_provider_policy_context(token)


async def execute_row(
    *,
    graph_data: dict[str, Any],
    flow: Flow,
    user: User,
    run_id: UUID,
    position: int,
    input_text: str,
    output_vertex_id: str,
) -> RowExecution:
    trace_id = str(uuid4())
    started = time.perf_counter()
    isolation_token = set_evals_memory_isolated(True)
    graph: Graph | None = None
    try:
        graph = build_row_graph(graph_data, flow, user)
        graph.set_run_id(trace_id)
        await run_graph_internal(
            graph,
            str(flow.id),
            session_id=row_session_id(run_id, position),
            inputs=[InputValueRequest(components=[], input_value=input_text, type=ROW_INPUT_TYPE)],
            outputs=[output_vertex_id],
        )
        actual = output_text(graph, output_vertex_id)
        error = None if actual is not None else "The output component produced no text"
    except Exception as exc:  # noqa: BLE001 - any flow failure is recorded on the row, never fatal to the run
        actual, error = None, _short_error(exc)
    finally:
        reset_evals_memory_isolated(isolation_token)
    tokens, cost = flow_usage(graph) if graph is not None else (None, None)
    return RowExecution(
        actual=actual,
        error=error,
        duration_ms=int((time.perf_counter() - started) * 1000),
        tokens=tokens,
        cost=cost,
        trace_id=trace_id,
    )
