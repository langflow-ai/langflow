"""The one place a flow's graph is written.

Every path that replaces ``Flow.data`` — PATCH, PUT and import, restoring a
version, the assistant — calls ``write_flow_graph``. It records the change as
ordered, attributed operations and stores them, the new graph and the
revision counters in the caller's transaction, so they commit or roll back
together. A write that is refused records nothing.

The caller must hold the flow's row lock (``lock_flow_for_update``) before it
reads or changes the flow, and keep it until commit: the lock is what makes
the revision head safe to extend across workers.

1. A retry of a request already recorded returns that request's revisions and
   writes nothing.
2. The stored graph must be the graph its revision replays to. Otherwise the
   write is refused, or with ``repair_revision_mismatch`` the stored graph is
   reset to the latest recorded revision first.
3. Both graphs must follow the flow graph rules, and every table value the
   write adds or changes must give its rows ids and positions. Otherwise the
   write is refused, or with ``repair_invalid_graph`` they are repaired,
   keeping the stored original as a view-only version.
4. The change is derived as operations, verified by exact replay, numbered
   from the flow's latest revision, and stored in rows that respect the
   configured size limits.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from lfx.services.flow_operations import (
    AddEdgesOp,
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodesOp,
    FlowOperation,
    FlowOperationError,
    GraphFix,
    UpdateEdgesOp,
    UpdateMetadataOp,
    UpdateNodesOp,
    dump_flow_operation,
    find_graph_violations,
    graph_hash,
    graphs_equal,
    repair_flow_data,
)

from langflow.services.database.models.flow_operation import FlowOperation as FlowOperationRow
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import get_flow_operation_service, get_settings_service
from langflow.services.flow_history.envelope import (
    RecordedOperation,
    decode_row,
    distinct_actor_ids,
    encode_envelope,
    request_ids_in_order,
)
from langflow.services.flow_history.errors import (
    FlowGraphInvalidError,
    FlowHistoryCorruptionError,
    FlowHistoryError,
    FlowRevisionMismatchError,
)
from langflow.services.flow_history.replay import reconstruct_graph, replay_from
from langflow.services.flow_history.store import has_anchor, latest_anchor_at_or_before, rows_with_request

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow, FlowGraphWriteOptions

REPAIRED_ORIGINAL_DESCRIPTION = "Original before automatic repair"


@dataclass
class GraphWriteResult:
    """What a graph write recorded, for the response."""

    request_id: UUID
    latest_revision: int
    current_revision: int
    start_revision: int | None = None
    end_revision: int | None = None
    deduplicated: bool = False
    flow_repaired: bool = False
    graph_repairs: list[dict[str, Any]] = field(default_factory=list)


def normalize_absent_graph(flow_data: Any) -> Any:
    """Fill in a graph that is missing entirely or lacks its collections.

    A flow created without data, or data without ``nodes`` or ``edges``, is an
    empty graph rather than a broken one, and saying so loses nothing, so it
    needs no repair request. Anything else that breaks the rules is left for
    validation to report.
    """
    if flow_data is None:
        return {"nodes": [], "edges": []}
    if isinstance(flow_data, dict) and (flow_data.get("nodes") is None or flow_data.get("edges") is None):
        return {
            **flow_data,
            "nodes": flow_data["nodes"] if flow_data.get("nodes") is not None else [],
            "edges": flow_data["edges"] if flow_data.get("edges") is not None else [],
        }
    return flow_data


async def write_flow_graph(
    session: AsyncSession,
    flow: Flow,
    target: Any,
    *,
    actor_id: UUID,
    options: FlowGraphWriteOptions | None = None,
) -> GraphWriteResult:
    """Replace ``flow.data`` with ``target``, recording the change in the flow's history."""
    request_id = (options.request_id if options else None) or uuid4()
    repair_mismatch = bool(options and options.repair_revision_mismatch)
    repair_invalid = bool(options and options.repair_invalid_graph)
    result = GraphWriteResult(
        request_id=request_id,
        latest_revision=flow.latest_revision,
        current_revision=flow.current_revision,
    )

    # Starter projects have no owner and are refreshed by delete and re-insert,
    # never edited, so they keep no history.
    if flow.user_id is None:
        flow.data = normalize_absent_graph(target)
        return result

    if options is not None and options.request_id is not None:
        original = await _recorded_request(session, flow, options.request_id)
        if original is not None:
            original.latest_revision = flow.latest_revision
            original.current_revision = flow.current_revision
            return original

    started = flow.latest_revision > 0 or await has_anchor(session, flow.id)
    if started:
        if not await projection_matches(session, flow):
            if not repair_mismatch:
                raise FlowRevisionMismatchError(
                    flow.id, current_revision=flow.current_revision, latest_revision=flow.latest_revision
                )
            flow.data = copy.deepcopy(
                await reconstruct_graph(session, flow.id, flow.latest_revision, latest_revision=flow.latest_revision)
            )
            flow.current_revision = flow.latest_revision
            result.flow_repaired = True
            result.current_revision = flow.current_revision
        base = flow.data
    else:
        base = normalize_absent_graph(flow.data)
        violations = find_graph_violations(base)
        if violations:
            if not repair_invalid:
                raise FlowGraphInvalidError(violations, graph="stored")
            await _keep_repaired_original(session, flow)
            repaired = repair_flow_data(base)
            base = repaired.flow_data
            result.graph_repairs.extend(_fix_entry("stored", fix) for fix in repaired.fixes)

    target = normalize_absent_graph(target)
    # Against the stored graph, so the table rules apply to the tables this
    # write adds or changes, while a table it leaves alone is accepted as stored.
    violations = find_graph_violations(target, base=base)
    if violations:
        if not repair_invalid:
            raise FlowGraphInvalidError(violations, graph="submitted")
        repaired = repair_flow_data(target, base=base)
        target = repaired.flow_data
        result.graph_repairs.extend(_fix_entry("submitted", fix) for fix in repaired.fixes)

    try:
        derived = get_flow_operation_service().derive(base, target)
    except FlowOperationError as exc:
        # Both graphs follow the rules, so this is a defect in the diff or the
        # engine. Refusing the write keeps the history complete.
        msg = f"Could not record the change to flow {flow.id} as operations"
        raise FlowHistoryError(msg) from exc

    flow.data = target
    if not derived.operations:
        return result

    if not started:
        session.add(_checkpoint(flow, base, revision=0))

    recorded = _sequence(
        derived.operations,
        flow=flow,
        actor_id=actor_id,
        request_id=request_id,
        cause=options.cause if options else None,
    )
    for row_operations in _pack_rows(recorded):
        session.add(
            FlowOperationRow(
                flow_id=flow.id,
                start_revision=row_operations[0].revision,
                end_revision=row_operations[-1].revision,
                ops=encode_envelope(row_operations),
                actor_user_ids=distinct_actor_ids(row_operations),
                request_ids=request_ids_in_order(row_operations),
            )
        )

    flow.latest_revision = recorded[-1].revision
    flow.current_revision = recorded[-1].revision
    result.start_revision = recorded[0].revision
    result.end_revision = recorded[-1].revision
    result.latest_revision = flow.latest_revision
    result.current_revision = flow.current_revision
    return result


async def projection_matches(session: AsyncSession, flow: Flow) -> bool:
    """Return whether ``flow.data`` is the graph its ``current_revision`` replays to."""
    anchor = await latest_anchor_at_or_before(session, flow.id, flow.current_revision)
    if anchor is None:
        raise FlowHistoryCorruptionError(flow.id, "no checkpoint to replay from", revision=flow.current_revision)
    try:
        if anchor.operation_revision == flow.current_revision:
            return graph_hash(flow.data) == anchor.graph_hash
        return graphs_equal(await replay_from(session, flow.id, anchor, flow.current_revision), flow.data)
    except FlowOperationError:
        # Stored data that cannot even be canonicalized is not the recorded graph.
        return False


async def checkpoint_fields(session: AsyncSession, flow: Flow) -> dict[str, Any]:
    """Return what makes a version saved from ``flow.data`` a replay checkpoint.

    A version is an anchor only when the stored graph is exactly the graph at
    the flow's current revision; otherwise, or before history starts, it is a
    plain snapshot and replay never starts from it.
    """
    if flow.user_id is None or not (flow.latest_revision > 0 or await has_anchor(session, flow.id)):
        return {}
    try:
        if not await projection_matches(session, flow):
            return {}
        return {"operation_revision": flow.current_revision, "graph_hash": graph_hash(flow.data)}
    except (FlowHistoryError, FlowOperationError):
        return {}


def _checkpoint(flow: Flow, flow_data: dict[str, Any], *, revision: int) -> FlowVersion:
    """Build a system checkpoint: no version number, never listed or pruned."""
    return FlowVersion(
        flow_id=flow.id,
        user_id=flow.user_id,
        data=copy.deepcopy(flow_data),
        version_number=None,
        operation_revision=revision,
        graph_hash=graph_hash(flow_data),
    )


async def _keep_repaired_original(session: AsyncSession, flow: Flow) -> None:
    await create_flow_version_entry(
        session,
        flow_id=flow.id,
        user_id=flow.user_id,
        data=copy.deepcopy(flow.data),
        description=REPAIRED_ORIGINAL_DESCRIPTION,
        view_only=True,
    )


def _fix_entry(graph: str, fix: GraphFix) -> dict[str, Any]:
    return {"graph": graph, **fix.to_dict()}


async def _recorded_request(session: AsyncSession, flow: Flow, request_id: UUID) -> GraphWriteResult | None:
    revisions = [
        recorded.revision
        for row in await rows_with_request(session, flow.id, request_id)
        for recorded in decode_row(row)
        if recorded.request_id == request_id
    ]
    if not revisions:
        return None
    return GraphWriteResult(
        request_id=request_id,
        latest_revision=flow.latest_revision,
        current_revision=flow.current_revision,
        start_revision=min(revisions),
        end_revision=max(revisions),
        deduplicated=True,
    )


# --- Numbering and storing operations -------------------------------------------------


def _json_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8", "surrogatepass"))


_ENVELOPE_OVERHEAD = _json_size(encode_envelope([]))


def _sequence(
    operations: list[FlowOperation],
    *,
    flow: Flow,
    actor_id: UUID,
    request_id: UUID,
    cause: str | None = None,
) -> list[RecordedOperation]:
    """Split operations to fit the row size limit and number them from the flow's head."""
    bytes_limit = get_settings_service().settings.flow_op_log_row_bytes_limit

    recorded: list[RecordedOperation] = []
    revision = flow.latest_revision
    for operation in operations:
        for part in _split_to_fit(operation, bytes_limit - _ENVELOPE_OVERHEAD):
            revision += 1
            recorded.append(
                RecordedOperation(
                    revision=revision,
                    actor_user_id=actor_id,
                    request_id=request_id,
                    operation=part,
                    cause=cause,
                )
            )
    return recorded


def _pack_rows(operations: list[RecordedOperation]) -> list[list[RecordedOperation]]:
    """Group consecutive operations into rows within both configured limits.

    A partly filled row is never reopened; each write starts new rows.
    """
    settings = get_settings_service().settings
    ops_limit = settings.flow_op_log_row_ops_limit
    bytes_limit = settings.flow_op_log_row_bytes_limit

    rows: list[list[RecordedOperation]] = []
    current: list[RecordedOperation] = []
    size = _ENVELOPE_OVERHEAD
    for operation in operations:
        element_size = _json_size(operation.to_json()) + 1
        if current and (len(current) >= ops_limit or size + element_size > bytes_limit):
            rows.append(current)
            current, size = [], _ENVELOPE_OVERHEAD
        current.append(operation)
        size += element_size
    if current:
        rows.append(current)
    return rows


def _split_to_fit(operation: FlowOperation, budget: int) -> list[FlowOperation]:
    """Split a list-valued operation into same-type operations that each fit ``budget``.

    Items are never split, so an item larger than the budget becomes an
    operation of its own that exceeds it.
    """
    if _json_size(dump_flow_operation(operation)) <= budget:
        return [operation]
    items, rebuild = _items(operation)
    if len(items) <= 1:
        return [operation]

    empty_size = _json_size(dump_flow_operation(rebuild([])))
    parts: list[FlowOperation] = []
    chunk: list[Any] = []
    size = empty_size
    for item, item_size in ((item, _json_size(_dump_item(item)) + 1) for item in items):
        if chunk and size + item_size > budget:
            parts.append(rebuild(chunk))
            chunk, size = [], empty_size
        chunk.append(item)
        size += item_size
    parts.append(rebuild(chunk))
    return parts


def _items(operation: FlowOperation):
    if isinstance(operation, AddNodesOp):
        return operation.nodes, lambda chunk: AddNodesOp(type="add_nodes", nodes=chunk)
    if isinstance(operation, AddEdgesOp):
        return operation.edges, lambda chunk: AddEdgesOp(type="add_edges", edges=chunk)
    if isinstance(operation, DeleteNodesOp):
        return operation.ids, lambda chunk: DeleteNodesOp(type="delete_nodes", ids=chunk)
    if isinstance(operation, DeleteEdgesOp):
        return operation.ids, lambda chunk: DeleteEdgesOp(type="delete_edges", ids=chunk)
    if isinstance(operation, UpdateNodesOp):
        return operation.updates, lambda chunk: UpdateNodesOp(type="update_nodes", updates=chunk)
    if isinstance(operation, UpdateEdgesOp):
        return operation.updates, lambda chunk: UpdateEdgesOp(type="update_edges", updates=chunk)
    if isinstance(operation, UpdateMetadataOp):
        entries = [("set", key, value) for key, value in operation.fields.items()]
        entries += [("delete", key, None) for key in operation.delete_keys]
        return entries, lambda chunk: UpdateMetadataOp(
            type="update_metadata",
            fields={key: value for kind, key, value in chunk if kind == "set"},
            delete_keys=[key for kind, key, _ in chunk if kind == "delete"],
        )
    return [], lambda _chunk: operation


def _dump_item(item: Any) -> Any:
    return item.model_dump(mode="json", exclude_defaults=True) if hasattr(item, "model_dump") else item
