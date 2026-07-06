"""Interactive human-in-the-loop driver for CLI runs (CLI HITL).

``lfx run`` streams via ``Graph.async_start``, which does not honor the pause seam
(``check_and_handle_pause`` runs only inside ``Graph.process``). When a flow contains
a pausing node (e.g. HumanInput) and the CLI is interactive, this driver runs the
graph via ``process()`` in a loop: each pause surfaces the request to a decision
provider (a terminal prompt on the CLI, a scripted callable in tests), injects the
chosen decision into the resumed graph, and continues until the run completes.

Checkpoints stay in-process (``InMemoryCheckpointStore``): the CLI has no durable job
store, so a paused CLI run lives only as long as the process. The restore + inject +
un-build sequence mirrors what ``build.py``'s background resume branch performs.
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.graph.checkpoint.store import CheckpointStore, InMemoryCheckpointStore
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.schema import VertexBuildResult

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph

DecisionProvider = Callable[[dict[str, Any]], "dict[str, Any] | Awaitable[dict[str, Any]]"]

# A provider that never resolves a pause would loop forever; bound it.
_MAX_PAUSES = 100

# Sentinel action for a late answer when no fallback is configured: it matches no
# branch, so ``HumanInput.route_branch`` stops every branch and the flow takes no path.
EXPIRED_ACTION = "__expired__"


def reroute_decision_on_timeout(pending: dict | None, decision: dict) -> dict:
    """Reroute a late HITL decision once the pause timed out.

    Lazy timeout (no background watchdog): when the human responds we compare now against
    ``paused_at + timeout_seconds``. If it elapsed, the late answer must not take the path
    the human picked: it is rerouted to the fallback branch when the node defined one, or
    to an expired sentinel (no branch taken) otherwise. A timely answer is kept unchanged.
    """
    pending = pending or {}
    timeout_s = pending.get("timeout_seconds") or 0
    fallback = pending.get("fallback_action")
    paused_at = pending.get("paused_at")
    if not (timeout_s and paused_at):
        return decision
    try:
        paused_dt = datetime.fromisoformat(paused_at)
    except (TypeError, ValueError):
        return decision
    if (datetime.now(timezone.utc) - paused_dt).total_seconds() > timeout_s:
        return {**(decision or {}), "action_id": fallback or EXPIRED_ACTION}
    return decision


async def run_graph_with_human_input(
    graph: Graph,
    *,
    decision_provider: DecisionProvider,
    input_value: str | None = None,
    event_manager: Any = None,
    fallback_to_env_vars: bool = False,
    store: CheckpointStore | None = None,
    start_component_id: str | None = None,
) -> list[VertexBuildResult]:
    """Drive a graph through pauses, asking ``decision_provider`` at each one.

    Returns the per-vertex results of the completed run (same shape ``async_start``
    yields) so the existing CLI output extractors work unchanged.
    """
    from lfx.graph.graph.base import Graph as LfxGraph
    from lfx.schema.schema import INPUT_FIELD_NAME

    store = store or InMemoryCheckpointStore()
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    # process() (used so resume honors restored state) takes no inputs argument, so
    # apply the chat input to the input vertices up front, as Graph.arun does.
    if input_value is not None:
        graph._set_inputs([], {INPUT_FIELD_NAME: input_value}, "chat")  # noqa: SLF001

    pauses = 0
    while True:
        try:
            await graph.process(
                fallback_to_env_vars=fallback_to_env_vars,
                event_manager=event_manager,
                start_component_id=start_component_id,
            )
        except GraphPausedException as exc:
            pauses += 1
            if pauses > _MAX_PAUSES:
                raise
            request = exc.data or {}
            decision = decision_provider(request)
            if inspect.isawaitable(decision):
                decision = await decision
            checkpoint = await store.load(exc.checkpoint_id) or await store.load_by_run_id(graph.run_id)
            if checkpoint is None:
                msg = "Paused run has no recoverable checkpoint; cannot resume."
                raise RuntimeError(msg) from exc
            graph = LfxGraph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
            graph.checkpointing_enabled = True
            graph.checkpoint_store = store
            request_id = request.get("request_id")
            decision = reroute_decision_on_timeout(request, decision)
            graph.human_input_decisions = {
                **(getattr(graph, "human_input_decisions", {}) or {}),
                request_id: decision,
            }
            for vertex in graph.vertices:
                if f"{vertex.id}:{graph.run_id}" == request_id:
                    vertex.built = False
            continue
        break

    return _collect_results(graph)


def terminal_decision_provider(request: dict[str, Any]) -> dict[str, Any]:
    """Interactive CLI provider: print the prompt + options, read the human's pick.

    Prints to stderr (stdout is captured for the structured result) and reads a 1-based
    option number from stdin. Returns ``{"action_id", "values": {}}``. An empty/invalid
    entry defaults to the first option.
    """
    prompt = request.get("prompt") or "Human input required"
    options = request.get("options") or []
    sys.stderr.write(f"\n⏸  {prompt}\n")
    for index, option in enumerate(options, start=1):
        label = option.get("label") or option.get("action_id")
        sys.stderr.write(f"  {index}. {label}\n")
    sys.stderr.write("Choose an option [1]: ")
    sys.stderr.flush()
    raw = sys.stdin.readline().strip()
    choice = 0
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        choice = int(raw) - 1
    action_id = options[choice].get("action_id") if options else raw
    return {"action_id": action_id, "values": {}}


def flow_has_pausing_node(graph: Graph) -> bool:
    """True when the graph contains a node that can request a human-input pause."""
    pausing_types = {"HumanInput"}
    return any((getattr(vertex, "data", None) or {}).get("type") in pausing_types for vertex in graph.vertices)


NESTED_HITL_UNSUPPORTED = (
    "This flow uses Human-in-the-Loop (a Human Input node or a tool that requires approval) and cannot "
    "run as a nested flow (Run Flow / Sub Flow / flow-as-tool), because a nested run cannot pause for "
    "a decision. Move the approval to the parent flow."
)


class NestedHITLUnsupportedError(ValueError):
    """Deliberate user guidance — wrappers must surface it verbatim, not genericize it."""


def flow_has_blocking_pausing_node(graph: Graph) -> bool:
    """True when a non-pausable run of this graph would need to pause.

    Mirrors the v1 API guard's two HITL shapes: a Human Input wired to a downstream consumer
    (an isolated one skips at runtime, so it is not blocking), or an agent tool carrying a
    non-empty ``approval_actions``.
    """
    for vertex in graph.vertices:
        data = getattr(vertex, "data", None) or {}
        if data.get("type") == "HumanInput" and graph.successor_map.get(vertex.id):
            return True
        template = ((data.get("node") or {}).get("template")) or {}
        rows = (template.get("tools_metadata") or {}).get("value")
        if isinstance(rows, list) and any(isinstance(row, dict) and row.get("approval_actions") for row in rows):
            return True
    return False


def raise_if_nested_hitl_unsupported(graph: Graph) -> None:
    """Reject a nested run of a pausing flow with a clear error instead of a silent non-pause."""
    if flow_has_blocking_pausing_node(graph):
        raise NestedHITLUnsupportedError(NESTED_HITL_UNSUPPORTED)


def _collect_results(graph: Graph) -> list[VertexBuildResult]:
    """Rebuild the per-vertex result list from a processed graph's built vertices."""
    results: list[VertexBuildResult] = []
    for vertex in graph.vertices:
        if not vertex.built or vertex.result is None:
            continue
        results.append(
            VertexBuildResult(
                result_dict=vertex.result,
                params="",
                valid=True,
                artifacts=vertex.artifacts,
                vertex=vertex,
            )
        )
    return results
