"""Pause and resume for a flow that runs inside another flow's component (Run Flow).

A child run that pauses stores its checkpoint in the parent's ``child_checkpoints`` and pauses the
parent under a nested request id (``lfx.run.hitl.nested_request_prefix`` plus the child's own id). The
parent's checkpoint is the only durable copy. On resume, the nested id un-builds the component, which
builds its child graph again and runs it here: the saved state goes back onto that graph, with the
decision, so the child picks up where it paused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from lfx.base.tools.constants import TOOL_OUTPUT_NAME
from lfx.graph.checkpoint.resume import apply_checkpoint, inject_decision
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.graph.exceptions import GraphPausedException

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from lfx.custom import Component
    from lfx.graph.checkpoint.schema import GraphCheckpoint
    from lfx.graph.graph.base import Graph

T = TypeVar("T")


class NestedRunPaused(Exception):  # noqa: N818
    """The child paused: its checkpoint is stored on the parent and the parent's pause is requested."""


class NestedFlowChangedError(ValueError):
    """The child flow changed while the run waited, so its saved state no longer fits. User guidance."""


def _pausable_parent(component: Component) -> Graph | None:
    """The graph a pause of ``component``'s child suspends, or None when the child must not pause."""
    vertex = component._vertex  # noqa: SLF001
    parent = vertex.graph if vertex is not None else None
    if parent is None or not parent.checkpointing_enabled:
        return None
    # Restore cannot look a child up in a harness candidate's definitions yet.
    if parent.runtime_candidate is not None:
        return None
    # A tool call cannot pause: the Agent would get an empty result and never see the decision.
    if component._current_output == TOOL_OUTPUT_NAME:  # noqa: SLF001
        return None
    return parent


def _restore(graph: Graph, saved: GraphCheckpoint, decision: dict, store: InMemoryCheckpointStore) -> None:
    payload = dict(graph.raw_graph_data)
    if payload != saved.flow_payload:
        msg = (
            f"The flow '{graph.flow_name or graph.flow_id}' changed while this run waited for a decision, "
            "so the run cannot continue. Start a new run."
        )
        raise NestedFlowChangedError(msg)
    apply_checkpoint(graph, saved, store=store)
    inject_decision(graph, saved.pause_context["data"]["request_id"], decision)


async def run_nested(component: Component, graph: Graph, run: Callable[[], Awaitable[T]]) -> T:
    """Run ``graph``, the child of ``component``, with ``run``, and pause the parent when the child pauses.

    Raises NestedRunPaused once the child's checkpoint is stored on the parent. When the parent cannot
    pause, the child runs with checkpointing off, so ``run_flow`` refuses a flow that would need to
    (NestedHITLUnsupportedError).
    """
    from lfx.run.hitl import nested_request_prefix

    parent = _pausable_parent(component)
    if parent is None:
        return await run()
    prefix = nested_request_prefix(component.get_id(), parent.run_id)
    # A private capture store: the parent's checkpoint, not this one, is what gets persisted.
    store = InMemoryCheckpointStore()
    if (saved := parent.child_checkpoints.get(prefix)) is not None:
        decision = parent.human_input_decisions[prefix + saved.pause_context["data"]["request_id"]]
        _restore(graph, saved, decision, store)
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    graph.job_id = parent.job_id
    try:
        result = await run()
    except GraphPausedException as exc:
        parent.request_pause(reason=exc.reason, data={**exc.data, "request_id": prefix + exc.data["request_id"]})
        parent.child_checkpoints[prefix] = await store.load(exc.checkpoint_id)
        raise NestedRunPaused from None
    parent.child_checkpoints.pop(prefix, None)
    return result
