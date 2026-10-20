"""The one place a flow's graph is written.

Every path that replaces ``Flow.data`` — PATCH, PUT and import, restoring a
version, the assistant — calls ``write_flow_graph``. It records the change as
ordered, attributed operations and stores them, the new graph and the
revision counters in the caller's transaction, so they commit or roll back
together. A write that is refused records nothing.

The caller must hold the flow's row lock (``lock_flow_for_update``) before it
reads or changes the flow, and keep it until commit: the lock is what makes
the revision head safe to extend across workers.

1. Multi-edit safety's ``If-Match`` check runs against the locked flow: a
   stale token is refused with a conflict, unless the submitted graph already
   equals the stored one, which loses nothing and writes nothing. That is
   also what makes a retried save safe: its graph is already stored.
2. The stored graph must be the graph its revision replays to. Otherwise the
   write is refused, or with ``repair_revision_mismatch`` the stored graph is
   reset to the latest recorded revision first.
3. Both graphs must follow the flow graph rules, and every table value the
   write adds or changes must give its rows ids and positions. Otherwise the
   write is refused, or with ``repair_invalid_graph`` they are repaired,
   keeping the stored original as a view-only version.
4. The change is derived as operations, verified by exact replay, numbered
   from the flow's latest revision, and stored in rows that respect the
   configured size limits. Each write is stored with the parts of its value
   that the secret scrubbing of a flow read changes in the graph the write
   stores, so a history read can strip them.
5. The version token rotates, naming the writer, whenever the write changed
   the graph the history holds: operations were recorded, or a repair
   rewrote the stored graph. A save that only changes view state does not
   rotate it, so it never makes other open editors stale.

With flow history off (``flow_history_enabled``, the default), a graph write
behaves as before history existed and records nothing. It marks a flow whose
history had started (``history_paused``), and that flow's next recorded write
starts its history again from a new checkpoint, one past the revisions
recorded before, which stay readable.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from lfx.services.flow_operations import (
    AddEdgesOp,
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodesOp,
    FlowDataValidationError,
    FlowOperation,
    FlowOperationError,
    GraphFix,
    UpdateNodesOp,
    dump_flow_operation,
    find_graph_violations,
    graph_hash,
    graphs_equal,
    repair_flow_data,
)
from lfx.services.flow_operations.limits import check_graph_limits
from sqlmodel import select

from langflow.services.database.models.flow_operation import FlowOperation as FlowOperationRow
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_flow_operation_service, get_settings_service, get_variable_service
from langflow.services.flow_history.envelope import (
    RecordedOperation,
    batch_header,
    distinct_actor_ids,
    encode_envelope,
    request_ids_in_order,
    stored_operation,
)
from langflow.services.flow_history.errors import (
    FlowGraphInvalidError,
    FlowHistoryCorruptionError,
    FlowHistoryError,
    FlowRevisionMismatchError,
    FlowVersionConflictError,
)
from langflow.services.flow_history.replay import reconstruct_graph, replay_from
from langflow.services.flow_history.secrets import SecretFinder
from langflow.services.flow_history.store import has_anchor, latest_anchor_at_or_before

if TYPE_CHECKING:
    from lfx.services.flow_operations import GraphViolation
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow, FlowGraphWriteOptions
    from langflow.services.flow_history.secrets import OperationSecrets, WriteSecrets

REPAIRED_ORIGINAL_DESCRIPTION = "Original before automatic repair"


@dataclass
class GraphWriteResult:
    """What a graph write recorded, for the response."""

    latest_revision: int
    current_revision: int
    start_revision: int | None = None
    end_revision: int | None = None
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


def flow_history_enabled() -> bool:
    """Whether graph writes are recorded in the flow's history."""
    return get_settings_service().settings.flow_history_enabled


async def write_flow_graph(
    session: AsyncSession,
    flow: Flow,
    target: Any,
    *,
    actor_id: UUID,
    options: FlowGraphWriteOptions | None = None,
    expected_version_token: UUID | None = None,
) -> GraphWriteResult:
    """Replace ``flow.data`` with ``target``, recording the change in the flow's history.

    ``expected_version_token`` is the request's ``If-Match``; None writes unconditionally.
    """
    # Names this write's batch in the stored envelope. A whole-flow save needs
    # no retry check: a retry carries the graph already stored, so it records nothing.
    request_id = uuid4()
    repair_mismatch = bool(options and options.repair_revision_mismatch)
    repair_invalid = bool(options and options.repair_invalid_graph)
    result = GraphWriteResult(
        latest_revision=flow.latest_revision,
        current_revision=flow.current_revision,
    )

    # Starter projects have no owner and are refreshed by delete and re-insert,
    # never edited, so they keep no history.
    if flow.user_id is None:
        flow.data = normalize_absent_graph(target)
        return result

    if not flow_history_enabled():
        await _write_without_history(
            session, flow, target, actor_id=actor_id, expected_version_token=expected_version_token
        )
        return result

    if (
        expected_version_token is not None
        and flow.version_token is not None
        and flow.version_token != expected_version_token
    ):
        if graphs_equal(normalize_absent_graph(target), normalize_absent_graph(flow.data)):
            return result
        raise FlowVersionConflictError(
            flow.id,
            expected=expected_version_token,
            current=flow.version_token,
            author_id=flow.last_modified_by,
            author_name=await _username(session, flow.last_modified_by),
            modified_at=flow.updated_at,
        )

    stored_repaired = False
    # A paused flow's stored graph was written without history, so its history
    # starts again as if it had none, and its stored graph is checked like one.
    resuming = flow.history_paused
    started = not resuming and (flow.latest_revision > 0 or await has_anchor(session, flow.id))
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
        violations = _graph_violations(base, graph="stored")
        if violations:
            if not repair_invalid:
                raise FlowGraphInvalidError(violations, graph="stored")
            await _keep_repaired_original(session, flow, actor_id)
            repaired = repair_flow_data(base)
            base = repaired.flow_data
            stored_repaired = True
            result.graph_repairs.extend(_fix_entry("stored", fix) for fix in repaired.fixes)

    target = normalize_absent_graph(target)
    # Against the stored graph, so the table rules apply to the tables this
    # write adds or changes, while a table it leaves alone is accepted as stored.
    violations = _graph_violations(target, graph="submitted", base=base)
    if violations:
        if not repair_invalid:
            raise FlowGraphInvalidError(violations, graph="submitted")
        try:
            repaired = repair_flow_data(target, base=base)
        except FlowDataValidationError as exc:
            # What repair leaves needs the person's intent, so the client fixes it.
            raise FlowGraphInvalidError(exc.violations, graph="submitted") from exc
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
    if derived.operations or result.flow_repaired or stored_repaired:
        flow.version_token = uuid4()
        flow.last_modified_by = actor_id
    if not derived.operations:
        return result

    if not started:
        # Revision 0, or one past the revisions recorded before history paused.
        anchor = flow.latest_revision + 1 if resuming else 0
        session.add(checkpoint_system(flow, base, revision=anchor))
        flow.latest_revision = flow.current_revision = anchor
        flow.history_paused = False

    recorded = _sequence(
        derived.operations,
        flow=flow,
        secret_finder=SecretFinder(target, await _owner_variable_names(session, flow, derived.operations)),
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

    # Imported here: maintenance builds on this module.
    from langflow.services.flow_history.maintenance import needs_maintenance, request_maintenance

    if await needs_maintenance(session, flow):
        request_maintenance(session, flow.id)
    return result


def _graph_violations(
    flow_data: Any, *, graph: Literal["stored", "submitted"], base: Any = None
) -> list[GraphViolation]:
    """Return the rules a graph breaks, refusing a graph the engine cannot read.

    A graph that breaks the JSON limits (a lone surrogate, or nesting deeper
    than 127 levels) is refused before any rule is checked, so it is refused
    with no violations, and repair cannot fix it.
    """
    try:
        return find_graph_violations(flow_data, base=base)
    except FlowDataValidationError as exc:
        raise FlowGraphInvalidError(exc.violations, graph=graph, reason=str(exc)) from exc


def refuse_unreadable_graph(flow_data: Any) -> None:
    """Refuse a submitted graph that breaks the JSON limits, as a save refuses it.

    Writes that record no history, such as creating a flow, store graphs that
    every later save must read, so they check the limits too.
    """
    try:
        check_graph_limits(flow_data)
    except FlowDataValidationError as exc:
        raise FlowGraphInvalidError([], graph="submitted", reason=str(exc)) from exc


async def _write_without_history(
    session: AsyncSession,
    flow: Flow,
    target: Any,
    *,
    actor_id: UUID,
    expected_version_token: UUID | None,
) -> None:
    """Write the graph as Langflow did before flow history: nothing is recorded or checked against it.

    As in multi-edit safety, only a graph that changed takes the writer's
    turn: its ``If-Match`` must name the current token, and the token rotates.
    Only the JSON limits are checked, as when a flow is created, so a graph
    that history could never read is not stored while history is off.
    """
    if target == flow.data:
        return
    refuse_unreadable_graph(target)
    if (
        expected_version_token is not None
        and flow.version_token is not None
        and flow.version_token != expected_version_token
    ):
        raise FlowVersionConflictError(
            flow.id,
            expected=expected_version_token,
            current=flow.version_token,
            author_id=flow.last_modified_by,
            author_name=await _username(session, flow.last_modified_by),
            modified_at=flow.updated_at,
        )
    if not flow.history_paused and (flow.latest_revision > 0 or await has_anchor(session, flow.id)):
        flow.history_paused = True
    flow.data = target
    flow.version_token = uuid4()
    flow.last_modified_by = actor_id


async def _username(session: AsyncSession, user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    return (await session.exec(select(User.username).where(User.id == user_id))).first()


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
    if (
        flow.user_id is None
        or not flow_history_enabled()
        or flow.history_paused
        or not (flow.latest_revision > 0 or await has_anchor(session, flow.id))
    ):
        return {}
    try:
        if not await projection_matches(session, flow):
            return {}
        return {"operation_revision": flow.current_revision, "graph_hash": graph_hash(flow.data)}
    except (FlowHistoryError, FlowOperationError):
        return {}


def checkpoint_system(flow: Flow, flow_data: dict[str, Any], *, revision: int) -> FlowVersion:
    """Build a system checkpoint: no version number, never listed or pruned."""
    return FlowVersion(
        flow_id=flow.id,
        user_id=flow.user_id,
        data=copy.deepcopy(flow_data),
        version_number=None,
        operation_revision=revision,
        graph_hash=graph_hash(flow_data),
    )


async def _keep_repaired_original(session: AsyncSession, flow: Flow, actor_id: UUID) -> None:
    await create_flow_version_entry(
        session,
        flow_id=flow.id,
        user_id=flow.user_id,
        data=copy.deepcopy(flow.data),
        description=REPAIRED_ORIGINAL_DESCRIPTION,
        view_only=True,
        saved_by_user_id=actor_id,
    )


def _fix_entry(graph: str, fix: GraphFix) -> dict[str, Any]:
    return {"graph": graph, **fix.to_dict()}


# --- Numbering and storing operations -------------------------------------------------


def _json_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8", "surrogatepass"))


_ENVELOPE_OVERHEAD = _json_size(encode_envelope([]))
# Request and actor ids are UUIDs, so every batch header has the same size.
_BATCH_OVERHEAD = _json_size(batch_header(UUID(int=0), UUID(int=0))) + 1


def _sequence(
    operations: list[FlowOperation],
    *,
    flow: Flow,
    secret_finder: SecretFinder,
    actor_id: UUID,
    request_id: UUID,
    cause: str | None = None,
) -> list[RecordedOperation]:
    """Find secret parts, split to fit the row size limit, and number operations from the flow's head."""
    bytes_limit = get_settings_service().settings.flow_op_log_row_bytes_limit

    recorded: list[RecordedOperation] = []
    revision = flow.latest_revision
    for operation in operations:
        try:
            secrets = secret_finder.secrets_of(operation)
        except ValueError as exc:
            # Only a defect gets here. As for a failed diff, the write is refused.
            msg = f"Could not find the secret parts of the change to flow {flow.id}"
            raise FlowHistoryError(msg) from exc
        for part, part_secrets in _split_to_fit(operation, secrets, bytes_limit - _ENVELOPE_OVERHEAD - _BATCH_OVERHEAD):
            revision += 1
            recorded.append(
                RecordedOperation(
                    revision=revision,
                    actor_user_id=actor_id,
                    request_id=request_id,
                    operation=part,
                    cause=cause,
                    secrets=part_secrets,
                )
            )
    return recorded


def _pack_rows(operations: list[RecordedOperation]) -> list[list[RecordedOperation]]:
    """Group consecutive operations into rows within both configured limits.

    A partly filled row is never reopened; each write starts new rows. An
    operation that starts a request's batch in the row also pays for the
    batch header.
    """
    settings = get_settings_service().settings
    ops_limit = settings.flow_op_log_row_ops_limit
    bytes_limit = settings.flow_op_log_row_bytes_limit

    rows: list[list[RecordedOperation]] = []
    current: list[RecordedOperation] = []
    size = _ENVELOPE_OVERHEAD
    for operation in operations:
        element_size = _json_size(operation.to_json()) + 1
        starts_batch = not current or current[-1].request_id != operation.request_id
        added = element_size + (_BATCH_OVERHEAD if starts_batch else 0)
        if current and (len(current) >= ops_limit or size + added > bytes_limit):
            rows.append(current)
            current, size = [], _ENVELOPE_OVERHEAD
            added = element_size + _BATCH_OVERHEAD
        current.append(operation)
        size += added
    if current:
        rows.append(current)
    return rows


def _split_to_fit(
    operation: FlowOperation, secrets: OperationSecrets, budget: int
) -> list[tuple[FlowOperation, OperationSecrets]]:
    """Split a list-valued operation into same-type operations that each fit ``budget`` as stored.

    Each part keeps the secret parts of its own writes. Items are never
    split, so an item larger than the budget becomes an operation of its own
    that exceeds it.
    """
    if _json_size(stored_operation(operation, secrets)) <= budget:
        return [(operation, secrets)]
    items, rebuild = _items(operation)
    if len(items) <= 1:
        return [(operation, secrets)]
    # Only an update_nodes has secret parts, one entry per write.
    item_secrets: OperationSecrets = secrets or ((),) * len(items)

    def part(entries: list[tuple[Any, WriteSecrets]]) -> tuple[FlowOperation, OperationSecrets]:
        part_secrets = tuple(write_secrets for _, write_secrets in entries) if secrets else ()
        return rebuild([item for item, _ in entries]), part_secrets

    empty_size = _json_size(dump_flow_operation(rebuild([])))
    parts: list[tuple[FlowOperation, OperationSecrets]] = []
    chunk: list[tuple[Any, WriteSecrets]] = []
    size = empty_size
    for item, write_secrets in zip(items, item_secrets, strict=True):
        item_size = _json_size(_stored_item(item, write_secrets)) + 1
        if chunk and size + item_size > budget:
            parts.append(part(chunk))
            chunk, size = [], empty_size
        chunk.append((item, write_secrets))
        size += item_size
    parts.append(part(chunk))
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
    return [], lambda _chunk: operation


def _stored_item(item: Any, write_secrets: WriteSecrets) -> Any:
    """Return one item of a list-valued operation as the row stores it."""
    if not hasattr(item, "model_dump"):
        return item
    stored = item.model_dump(mode="json")
    if write_secrets:
        stored["secrets"] = [part.to_json() for part in write_secrets]
    return stored


async def _owner_variable_names(session: AsyncSession, flow: Flow, operations: list[FlowOperation]) -> frozenset[str]:
    """Return the names of the flow owner's global variables, which a scrubbed write may keep.

    Only a ``set_field`` can have secret parts, so the names are loaded only
    when the batch has one.
    """
    if not any(
        isinstance(operation, UpdateNodesOp) and any(update.op == "set_field" for update in operation.updates)
        for operation in operations
    ):
        return frozenset()
    names = await get_variable_service().list_variables(user_id=flow.user_id, session=session)
    return frozenset(name for name in names if name)
