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
    UpdateNodesOp,
    dump_flow_operation,
    parse_flow_operation,
)
from lfx.services.flow_operations.limits import check_graph_limits
from sqlalchemy import JSON, Text, bindparam, cast
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.types import TypeDecorator
from sqlmodel import func, select

from langflow.services.database.models.flow_operation import FlowOperation as FlowOperationRow
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, get_variable_service
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
from langflow.services.flow_multiplayer import config as multiplayer

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow, FlowGraphWriteOptions
    from langflow.services.flow_history.secrets import OperationSecrets, WriteSecrets

REPAIRED_ORIGINAL_DESCRIPTION = "Original before automatic repair"


async def _engine(name: str, *args: Any, **kwargs: Any) -> Any:
    """Run one function of the process's flow engine (``LANGFLOW_FLOW_ENGINE``) on whole graphs.

    Every call here reads or builds a whole flow, so it runs in a worker thread, as the
    multiplayer path runs its large calls (both engines alike): the event loop serves other
    requests meanwhile. Each call is measured (``eng_<function>`` wall and CPU) when the
    request is measured.
    """
    from langflow.services.flow_multiplayer.cache import whole_flow

    return await whole_flow(name, *args, **kwargs)


@dataclass(frozen=True)
class EngineViolation:
    """A graph rule violation as the engine object reports it (a dict), with the ``to_dict`` errors expect."""

    value: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.value)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.value[name]
        except KeyError:
            raise AttributeError(name) from None


async def log_head(session: AsyncSession, flow_id: UUID) -> int:
    """The flow's head revision, read from its operation log (0 when it has no rows)."""
    head = (
        await session.exec(select(func.max(FlowOperationRow.end_revision)).where(FlowOperationRow.flow_id == flow_id))
    ).one()
    return int(head or 0)


def _multiplayer_cached(session: AsyncSession) -> bool:
    """Whether the head graph comes from the multiplayer cache (modes cache and wal, PostgreSQL)."""
    return session.get_bind().dialect.name == "postgresql" and multiplayer.uses_cache()


def _wal(session: AsyncSession) -> bool:
    return session.get_bind().dialect.name == "postgresql" and multiplayer.write_mode() == "wal"


def current_version_token(session: AsyncSession, flow: Flow, head: int) -> UUID | None:
    """The token ``If-Match`` names: in WAL mode it also changes with every revision of the log."""
    if _wal(session) and flow.user_id is not None and flow_history_enabled():
        from langflow.services.flow_multiplayer.oplog import wal_version_token

        return wal_version_token(flow.version_token, flow.id, head)
    return flow.version_token


async def response_version_token(session: AsyncSession, flow: Flow) -> UUID | None:
    """The token a write's response carries: in WAL mode, the token of the log's head."""
    if not _wal(session):
        return flow.version_token
    return current_version_token(session, flow, await log_head(session, flow.id))


async def graph_at_head(session: AsyncSession, flow_id: UUID, head: int) -> bytes:
    """The graph at ``head`` as JSON text, from the multiplayer cache caught up from the log."""
    from langflow.services.flow_multiplayer.cache import EntryGoneError, entry_at_head

    for _attempt in range(3):
        entry = await entry_at_head(session, flow_id, head)
        if entry is None:
            break
        try:
            async with await entry.serialized() as serialized:
                if serialized.revision == head:
                    return serialized.text.encode()
        except EntryGoneError:
            continue
    msg = f"Could not read flow {flow_id} at revision {head}"
    raise FlowHistoryError(msg)


def _wal_reads_log(session: AsyncSession, flow: Flow) -> bool:
    """Whether the flow's current graph is the log's head and not ``Flow.data`` (WAL, as the v1 read)."""
    return _wal(session) and flow.user_id is not None and flow_history_enabled()


async def refresh_after_write(session: AsyncSession, flow: Flow) -> None:
    """Refresh ``flow`` after a v1 write, with the current graph on it for the answer and follow-up work.

    A legacy save that records a change writes ``Flow.data`` at the new head in every mode.
    In WAL mode a write that records nothing (no graph in the request, or an unchanged graph)
    can leave ``Flow.data`` at an older revision, since multiplayer writers do not touch the
    row. Then the flow gets the graph at the log's head, as the v1 read answers, from the
    cached graph's coalesced serialization, parsed in a worker thread. Never writes ``Flow.data``.
    """
    await session.refresh(flow)
    if not _wal_reads_log(session, flow):
        return
    head = await log_head(session, flow.id)
    if flow.current_revision >= head:
        return
    import anyio
    import orjson

    text = await graph_at_head(session, flow.id, head)
    set_committed_value(flow, "data", await anyio.to_thread.run_sync(orjson.loads, text))
    set_committed_value(flow, "latest_revision", max(head, flow.latest_revision))
    set_committed_value(flow, "current_revision", head)


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

    # The head comes from the log: a multiplayer writer in WAL mode records
    # revisions without touching the flow row. The caller holds the flow's write lock.
    head = await log_head(session, flow.id)
    if head > flow.latest_revision:
        # Only WAL writers leave the row behind the log; the row catches up with this write.
        flow.latest_revision = head
        result.latest_revision = head
    from_cache = _multiplayer_cached(session)
    head_graph: bytes | None = None

    current_token = current_version_token(session, flow, head)
    if expected_version_token is not None and current_token is not None and current_token != expected_version_token:
        if from_cache and flow.latest_revision > 0 and not flow.history_paused:
            head_graph = await graph_at_head(session, flow.id, head)
            unchanged = await _engine("graphs_equal", normalize_absent_graph(target), head_graph)
        else:
            unchanged = await _engine("graphs_equal", normalize_absent_graph(target), normalize_absent_graph(flow.data))
        if unchanged:
            return result
        raise FlowVersionConflictError(
            flow.id,
            expected=expected_version_token,
            current=current_token,
            author_id=flow.last_modified_by,
            author_name=await _username(session, flow.last_modified_by),
            modified_at=flow.updated_at,
        )

    stored_repaired = False
    # A paused flow's stored graph was written without history, so its history
    # starts again as if it had none, and its stored graph is checked like one.
    resuming = flow.history_paused
    started = not resuming and (flow.latest_revision > 0 or await has_anchor(session, flow.id))
    if started and from_cache:
        # The graph at the log's head, not Flow.data (which is only a checkpoint in WAL mode).
        base = head_graph if head_graph is not None else await graph_at_head(session, flow.id, head)
    elif started:
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
        violations = await _graph_violations(base, graph="stored")
        if violations:
            if not repair_invalid:
                raise FlowGraphInvalidError(violations, graph="stored")
            await _keep_repaired_original(session, flow, actor_id)
            repaired = await _engine("repair", base)
            base = repaired["flow_data"]
            stored_repaired = True
            result.graph_repairs.extend(_fix_entry("stored", fix) for fix in repaired["fixes"])

    target = normalize_absent_graph(target)
    # Against the stored graph, so the table rules apply to the tables this
    # write adds or changes, while a table it leaves alone is accepted as stored.
    violations = await _graph_violations(target, graph="submitted", base=base)
    if violations:
        if not repair_invalid:
            raise FlowGraphInvalidError(violations, graph="submitted")
        try:
            repaired = await _engine("repair", target, base)
        except FlowDataValidationError as exc:
            # What repair leaves needs the person's intent, so the client fixes it.
            raise FlowGraphInvalidError(exc.violations, graph="submitted") from exc
        target = repaired["flow_data"]
        result.graph_repairs.extend(_fix_entry("submitted", fix) for fix in repaired["fixes"])

    try:
        derived_operations = [parse_flow_operation(operation) for operation in await _engine("ops_diff", base, target)]
    except FlowOperationError as exc:
        # Both graphs follow the rules, so this is a defect in the diff or the
        # engine. Refusing the write keeps the history complete.
        msg = f"Could not record the change to flow {flow.id} as operations"
        raise FlowHistoryError(msg) from exc

    # Every mode, WAL included: the stored graph becomes the graph at the new head, under the
    # flow's advisory lock. The checkpoint moves Flow.data only to a newer revision, so it
    # cannot put an older graph back over this one.
    flow.data = target
    if started and from_cache and flow.current_revision != head:
        # The stored graph becomes the graph at the head (WAL mode: a checkpoint for free).
        flow.latest_revision = flow.current_revision = head
        result.current_revision = head
    if derived_operations or result.flow_repaired or stored_repaired:
        flow.version_token = uuid4()
        flow.last_modified_by = actor_id
    if not derived_operations:
        return result

    if not started:
        # Revision 0, or one past the revisions recorded before history paused.
        anchor = flow.latest_revision + 1 if resuming else 0
        await checkpoint_system(session, flow, base, revision=anchor)
        flow.latest_revision = flow.current_revision = anchor
        flow.history_paused = False

    recorded = _sequence(
        derived_operations,
        flow=flow,
        secret_finder=SecretFinder(target, await _owner_variable_names(session, flow, derived_operations)),
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
    result.latest_revision = recorded[-1].revision
    result.current_revision = flow.current_revision

    if from_cache:
        # Modes cache and wal: the multiplayer checkpoint task checkpoints and compacts after the
        # commit, as for a multiplayer write, with the lock held only for its deletes. Legacy
        # maintenance would read and hash whole large graphs under the lock.
        from langflow.services.flow_multiplayer.checkpoint import request_after_commit

        request_after_commit(session, flow.id, recorded[-1].revision)
        return result

    # Imported here: maintenance builds on this module.
    from langflow.services.flow_history.maintenance import needs_maintenance, request_maintenance

    if await needs_maintenance(session, flow):
        request_maintenance(session, flow.id)
    return result


async def _graph_violations(
    flow_data: Any, *, graph: Literal["stored", "submitted"], base: Any = None
) -> list[EngineViolation]:
    """Return the rules a graph breaks, refusing a graph the engine cannot read.

    A graph that breaks the JSON limits (a lone surrogate, or nesting deeper
    than 127 levels) is refused before any rule is checked, so it is refused
    with no violations, and repair cannot fix it.
    """
    try:
        return [EngineViolation(violation) for violation in await _engine("validate", flow_data, base)]
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
    """Return whether ``flow.data`` is the graph its ``current_revision`` replays to.

    At a checkpoint's revision, the stored text of ``Flow.data`` that hashes to the
    checkpoint's hash is the checkpoint's text, so it matches without the engine. Other
    text can still be the same graph (a save that changed only view state, or the same
    graph written by another serializer), so the engine compares the graphs then.
    """
    anchor = await latest_anchor_at_or_before(session, flow.id, flow.current_revision)
    if anchor is None:
        raise FlowHistoryCorruptionError(flow.id, "no checkpoint to replay from", revision=flow.current_revision)
    try:
        if anchor.operation_revision == flow.current_revision:
            from langflow.services.database.models.flow.model import Flow
            from langflow.services.flow_multiplayer.cache import call, text_hash

            stored = (await session.exec(select(cast(Flow.data, Text)).where(Flow.id == flow.id))).first()
            if stored is not None and await call(text_hash, stored, large=True, name="hash") == anchor.graph_hash:
                return True
            return await _engine("graphs_equal", anchor.data, flow.data)
        return await _engine(
            "graphs_equal", await replay_from(session, flow.id, anchor, flow.current_revision), flow.data
        )
    except FlowOperationError:
        # Stored data that cannot even be canonicalized is not the recorded graph.
        return False


async def checkpoint_fields(session: AsyncSession, flow: Flow) -> dict[str, Any]:
    """Return what makes a version saved from ``flow.data`` a replay checkpoint.

    A version is an anchor only when the stored graph is exactly the graph at
    the flow's current revision; otherwise, or before history starts, it is a
    plain snapshot and replay never starts from it. The caller stores a copy of
    ``flow.data`` as a dict, which SQLAlchemy serializes with ``json.dumps`` and its
    defaults (SQLite and psycopg alike), so the hash is of that same text.
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
    except (FlowHistoryError, FlowOperationError):
        return {}
    from langflow.services.flow_multiplayer.cache import call

    _, graph_hash = await call(_dump_and_hash, flow.data, large=True, name="hash")
    return {"operation_revision": flow.current_revision, "graph_hash": graph_hash}


class _JsonText(TypeDecorator):
    """A JSON column's value that is JSON text already: bound as it is, never serialized again.

    PostgreSQL's ``json`` keeps its input text byte for byte; SQLite stores the string.
    """

    impl = JSON
    cache_ok = True

    def bind_processor(self, dialect: Any) -> None:  # noqa: ARG002
        return None


async def checkpoint_system(
    session: AsyncSession, flow: Flow, flow_data: dict[str, Any], *, revision: int, text: str | None = None
) -> FlowVersion:
    """Add a system checkpoint (no version number, never listed or pruned) and flush it.

    ``text`` is ``flow_data`` already serialized (``Flow.data``'s stored text); without
    it ``flow_data`` is serialized here, once. The row stores that text as it is and its
    hash is the SHA-256 of that text. ``data`` is expired after the flush: a query loads it.
    """
    from langflow.services.flow_multiplayer.cache import call, text_hash

    if text is None:
        text, graph_hash = await call(_dump_and_hash, flow_data, large=True, name="hash")
    else:
        graph_hash = await call(text_hash, text, large=True, name="hash")
    checkpoint = FlowVersion(
        flow_id=flow.id,
        user_id=flow.user_id,
        version_number=None,
        operation_revision=revision,
        graph_hash=graph_hash,
    )
    checkpoint.data = bindparam(None, text, type_=_JsonText())
    session.add(checkpoint)
    await session.flush()
    session.expire(checkpoint, ["data"])
    return checkpoint


def _dump_and_hash(graph: Any) -> tuple[str, str]:
    """The JSON text SQLAlchemy stores for ``graph`` (``json.dumps``, defaults) and its SHA-256."""
    from langflow.services.flow_multiplayer.cache import text_hash

    text = json.dumps(graph)
    return text, text_hash(text)


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


def _fix_entry(graph: str, fix: dict[str, Any]) -> dict[str, Any]:
    return {"graph": graph, **fix}


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
