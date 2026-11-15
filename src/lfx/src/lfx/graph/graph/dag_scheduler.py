"""Opt-in static DAG eligibility, without constructing or executing components."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.template.field.base import UNDEFINED

if TYPE_CHECKING:
    from collections.abc import Mapping

    from lfx.graph.graph.base import Graph


@dataclass(frozen=True)
class DagCandidate:
    ids: tuple[str, ...]
    predecessors: Mapping[str, tuple[str, ...]]
    successors: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class DagSelection(DagCandidate):
    pass


def validate_dag_max_concurrency(value: int | None) -> int | None:
    if value is not None and (type(value) is not int or value <= 0):
        msg = "dag_max_concurrency must be a positive integer or None"
        raise ValueError(msg)
    return value


def inspect_dag_candidate(graph: Graph) -> DagCandidate | str:
    from lfx.custom.custom_component.component import Component
    from lfx.graph.graph.base import Graph

    if type(graph) is not Graph:
        return "custom graph"
    if any(
        (
            graph.checkpointing_enabled,
            graph.resumed_from_checkpoint,
            graph.pause_requested,
            graph.pause_probe is not None,
            graph.pause_info is not None,
            bool(graph.checkpoint_restored_built_ids),
            bool(graph.checkpoint_opaque_dropped_ids),
            bool(graph.inactivated_vertices),
            bool(graph.inactive_vertices),
            bool(graph.activated_vertices),
            bool(graph.branch_inactivation_sources),
            bool(graph.conditionally_excluded_vertices),
            bool(graph.conditional_exclusion_sources),
            bool(graph.conditional_exclusion_outputs),
            graph.stop_vertex is not None,
        )
    ):
        return "dynamic or checkpoint state"
    ids = tuple(vertex.id for vertex in graph.vertices)
    if len(set(ids)) != len(ids):
        return "duplicate vertex"
    if set(graph.vertex_map) != set(ids) or any(graph.vertex_map[vertex.id] is not vertex for vertex in graph.vertices):
        return "inconsistent vertex lookup"
    predecessors: dict[str, list[str]] = {key: [] for key in ids}
    successors: dict[str, list[str]] = {key: [] for key in ids}
    seen_edges: set[tuple[str, str]] = set()
    for edge in graph.edges:
        pair = (edge.source_id, edge.target_id)
        if pair[0] not in predecessors or pair[1] not in predecessors:
            return "missing edge endpoint"
        if pair[0] == pair[1] or pair in seen_edges:
            return "self or duplicate dependency"
        seen_edges.add(pair)
        predecessors[pair[1]].append(pair[0])
        successors[pair[0]].append(pair[1])
    counts = {key: len(value) for key, value in predecessors.items()}
    ready = [key for key in ids if not counts[key]]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for successor in successors[key]:
            counts[successor] -= 1
            if not counts[successor]:
                ready.append(successor)
    if visited != len(ids):
        return "cyclic graph"
    for vertex in graph.vertices:
        component = vertex.custom_component
        if (
            not isinstance(component, Component)
            or type(component).__dict__.get("supports_dependency_ready_scheduling") is not True
        ):
            return "component has no concrete static scheduling promise"
        if vertex.built or vertex.result is not None:
            return "previously built vertex"
        if any(output.value is not UNDEFINED for output in component._outputs_map.values()):  # noqa: SLF001
            return "populated output cache"
        node = vertex.data.get("node", {})
        if (
            vertex.is_state
            or vertex._is_loop  # noqa: SLF001 - inspect cached flag without evaluating a property
            or any(output.get("allows_loop") for output in vertex.outputs)
            or vertex.frozen
            or node.get("tool_mode")
        ):
            return "state, loop, frozen or tool vertex"
        if vertex.will_stream or any(
            params.get(key)
            for params in (vertex.params, component._attributes)  # noqa: SLF001 - existing instance inputs
            for key in ("stream", "streaming")
        ):
            return "streaming vertex"
    return DagCandidate(
        ids,
        MappingProxyType({key: tuple(value) for key, value in predecessors.items()}),
        MappingProxyType({key: tuple(value) for key, value in successors.items()}),
    )


def select_dag_candidate(graph: Graph, candidate: DagCandidate, first_layer: list[str]) -> DagSelection | str:
    current = inspect_dag_candidate(graph)
    if isinstance(current, str):
        return current
    if current != candidate:
        return "topology changed during selection"
    selected = graph.vertices_to_run
    if not selected <= set(candidate.ids):
        return "unknown selected vertex"
    if any(parent not in selected for key in selected for parent in candidate.predecessors[key]):
        return "unsatisfied external predecessor"
    frontier = {key for key in selected if not candidate.predecessors[key]}
    if set(first_layer) != frontier or len(first_layer) != len(frontier):
        return "inconsistent selected frontier"
    ids = tuple(key for key in candidate.ids if key in selected)
    return DagSelection(
        ids,
        MappingProxyType({key: candidate.predecessors[key] for key in ids}),
        MappingProxyType(
            {key: tuple(value for value in candidate.successors[key] if value in selected) for key in ids}
        ),
    )


@dataclass
class DagRunContext:
    eligible: bool = False
    initialization_attempted: bool = False
    owned_tasks: set = field(default_factory=set)
    primary: BaseException | None = None
    finalized: bool = False

    def latch(self, error: BaseException) -> None:
        if self.primary is None:
            self.primary = error


async def _await_owned(future, context: DagRunContext):
    """Outer cancellation stops admission, never the work this invocation owns."""
    while True:
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError as exc:
            context.latch(exc)
            if future.done():
                return future.result()


async def drain_admitted(context: DagRunContext) -> None:
    if context.owned_tasks:
        await _await_owned(asyncio.gather(*context.owned_tasks, return_exceptions=True), context)


async def finalize_dag_run(graph: Graph, context: DagRunContext) -> None:
    if context.finalized or not context.eligible or not context.initialization_attempted:
        return
    context.finalized = True
    if graph._is_subgraph:  # noqa: SLF001 - parent owns native trace lifetime
        return
    # Create in the owner context, before its flow span is detached.
    task = asyncio.create_task(graph.end_all_traces(error=context.primary))
    try:
        await _await_owned(task, context)
    except BaseException as exc:  # noqa: BLE001 - preserve primary outcome while draining
        if context.primary is None:
            context.latch(exc)
        else:
            logger.debug("Secondary DAG finalization failure: {}", type(exc).__name__)


async def execute_dependency_ready(
    graph: Graph, selection: DagSelection, *, max_concurrency: int, build_kwargs: dict, context: DagRunContext
) -> None:
    from lfx.graph.graph.schema import VertexBuildResult

    build_kwargs = dict(build_kwargs)
    has_webhook_component = build_kwargs.pop("has_webhook_component", False)
    index = {key: i for i, key in enumerate(selection.ids)}
    counts = {key: len(value) for key, value in selection.predecessors.items()}
    ready = [key for key in selection.ids if not counts[key]]
    pending: dict[asyncio.Task, str] = {}
    completed: set[str] = set()
    scheduled: set[str] = set()
    manager = graph.run_manager
    # The legacy manager shallow-copies lists; install fresh arrays for this run.
    manager.run_predecessors = {key: list(value) for key, value in selection.predecessors.items()}
    manager.run_map = {key: list(value) for key, value in selection.successors.items()}
    manager.vertices_to_run = set(selection.ids)
    manager.vertices_being_run = set()
    manager.ran_at_least_once = set()
    try:
        while ready or pending:
            # Handlers below may await while admitted siblings finish. Harvest
            # every already-finished group before allowing another admission wave.
            # In particular, a queued child cannot overtake a sibling failure.
            done = {task for task in pending if task.done()}
            if not done:
                while ready and len(pending) < max_concurrency:
                    vertex_id = ready.pop(0)
                    if vertex_id in scheduled:
                        msg = "Dependency-ready vertex was admitted twice"
                        raise RuntimeError(msg)
                    scheduled.add(vertex_id)
                    task = asyncio.create_task(
                        graph.build_vertex(vertex_id=vertex_id, **build_kwargs), name=f"{vertex_id} DAG"
                    )
                    pending[task] = vertex_id
                    context.owned_tasks.add(task)
                done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            ordered = sorted(done, key=lambda task: index[pending[task]])
            # Select failures before applying any result in this observed group.
            for task in ordered:
                if task.cancelled():
                    raise asyncio.CancelledError
                error = task.exception()
                if error is not None:
                    context.latch(error)
                    if has_webhook_component and isinstance(error, Exception):
                        await graph._log_vertex_build_from_exception(pending[task], error)  # noqa: SLF001
                    raise error
            for task in ordered:
                vertex_id = pending.pop(task)
                result = task.result()
                if not isinstance(result, VertexBuildResult) or result.vertex.id != vertex_id:
                    msg = f"Invalid result from DAG task {vertex_id}"
                    raise TypeError(msg)
                component = result.vertex.custom_component
                for output in component._outputs_map.values():  # noqa: SLF001
                    value = output.value
                    # Check only direct output values and the documented Message.text
                    # slot, never recursively walk or close arbitrary user inputs.
                    from lfx.schema.message import Message

                    stream_value = value.text if isinstance(value, Message) else value
                    if isinstance(stream_value, (Iterator, AsyncIterator)) or inspect.isawaitable(stream_value):
                        msg = "Dependency-ready components must return materialized outputs"
                        raise TypeError(msg)
                await graph._record_vertex_build_result(result)  # noqa: SLF001
                manager.remove_vertex_from_runnables(vertex_id)
                manager.ran_at_least_once.add(vertex_id)
                completed.add(vertex_id)
                newly_ready = []
                for successor in selection.successors[vertex_id]:
                    counts[successor] -= 1
                    if not counts[successor]:
                        newly_ready.append(successor)
                newly_ready.sort(key=index.__getitem__)
                await graph._emit_vertex_build_result(result, newly_ready)  # noqa: SLF001
                ready.extend(newly_ready)
            ready.sort(key=index.__getitem__)
        if len(completed) != len(selection.ids):
            msg = "Dependency-ready execution stalled with unfinished vertices"
            raise RuntimeError(msg)
    except BaseException as exc:  # noqa: BLE001 - preserve primary outcome while draining
        context.latch(exc)
    finally:
        await drain_admitted(context)
    if context.primary is not None:
        raise context.primary
