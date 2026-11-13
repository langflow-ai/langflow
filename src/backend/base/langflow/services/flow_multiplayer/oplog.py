"""SQL on the flow's operation log for multiplayer writes and reads.

Every statement is plain SQL through the caller's session, PostgreSQL only.
``Flow.data`` goes in and out as JSON text: reads select ``data::text`` and
writes pass the engine's ``to_json`` text through ``CAST(:data AS json)``.
A read for an engine (``read_flow_data(..., as_bytes=True)``) takes the text as
its UTF-8 bytes straight from the driver: both engines read bytes, so making a
``str`` and encoding it again would copy the whole graph twice for nothing.
"""

from __future__ import annotations

import functools
import hashlib
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

import orjson
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

LOCK_NAMESPACE = "flow_oplog:"
# The checkpoint claim: one checkpoint task per flow across processes. Not the flow's write lock.
CHECKPOINT_NAMESPACE = "flow_checkpoint:"
ENVELOPE_VERSION = 1

_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_HEAD = text("SELECT coalesce(max(end_revision), 0) FROM flow_operation WHERE flow_id = :flow_id")
# Head, retry lookup and the start of history in one round trip, after the lock.
_HEAD_AND_RETRY = text(
    """
    SELECT
      (SELECT coalesce(max(end_revision), 0) FROM flow_operation WHERE flow_id = :flow_id) AS head,
      (SELECT history_paused FROM flow WHERE id = :flow_id) AS paused,
      (SELECT latest_revision FROM flow WHERE id = :flow_id) AS latest,
      (SELECT EXISTS (
          SELECT 1 FROM flow_version
          WHERE flow_id = :flow_id AND operation_revision = 0 AND version_number IS NULL
            AND graph_hash IS NOT NULL AND view_only = false)) AS has_anchor,
      (SELECT json_agg(json_build_object('s', start_revision, 'e', end_revision, 'ops', ops)
                       ORDER BY start_revision)
         FROM flow_operation
        WHERE flow_id = :flow_id AND request_ids @> CAST(:request_ids AS jsonb)) AS retry_rows
    """
)
_FLOW_DATA_SQL = (
    "SELECT data::text, current_revision, latest_revision, history_paused, user_id, version_token "
    "FROM flow WHERE id = {flow_id}"
)
_FLOW_DATA = text(_FLOW_DATA_SQL.format(flow_id=":flow_id"))
_FLOW_DATA_PG = _FLOW_DATA_SQL.format(flow_id="%(flow_id)s")
_ROWS_AFTER = text(
    "SELECT start_revision, end_revision, ops::text FROM flow_operation "
    "WHERE flow_id = :flow_id AND end_revision > :after ORDER BY start_revision"
)
_ROWS_BETWEEN = text(
    "SELECT start_revision, end_revision, ops::text FROM flow_operation "
    "WHERE flow_id = :flow_id AND end_revision > :after AND start_revision <= :through ORDER BY start_revision"
)
_INSERT_ROW = text(
    "INSERT INTO flow_operation (id, flow_id, start_revision, end_revision, ops, actor_user_ids, request_ids, "
    "created_at) VALUES (:id, :flow_id, :start, :end, CAST(:ops AS json), CAST(:actors AS jsonb), "
    "CAST(:request_ids AS jsonb), now())"
)
_WRITE_FLOW = text(
    "UPDATE flow SET data = CAST(:data AS json), latest_revision = :revision, current_revision = :revision, "
    "version_token = :token, last_modified_by = :actor, history_paused = false, updated_at = now() "
    "WHERE id = :flow_id"
)
# Checkpoint: no advisory lock; only ever moves Flow.data forward.
_CHECKPOINT_FLOW = text(
    "UPDATE flow SET data = CAST(:data AS json), current_revision = :revision, "
    "latest_revision = greatest(latest_revision, :revision) "
    "WHERE id = :flow_id AND current_revision < :revision"
)
# A system checkpoint row, only when the log has rows, Flow.data is at or past it, and none is there yet.
# Compaction cuts only at system checkpoints, so this keeps every cut at or before Flow.current_revision.
_INSERT_CHECKPOINT_ROW = text(
    """
    INSERT INTO flow_version (id, flow_id, user_id, data, version_number, operation_revision, graph_hash,
                              retained, view_only, created_at)
    SELECT :id, f.id, f.user_id, CAST(:data AS json), NULL, :revision, :graph_hash, false, false, now()
      FROM flow f
     WHERE f.id = :flow_id AND f.current_revision >= :revision
       AND EXISTS (SELECT 1 FROM flow_operation WHERE flow_id = :flow_id)
       AND NOT EXISTS (SELECT 1 FROM flow_version v
                        WHERE v.flow_id = :flow_id AND v.operation_revision = :revision
                          AND v.version_number IS NULL AND v.graph_hash IS NOT NULL)
    """
)
# The anchor a flow's history starts from, written by its first recorded write.
_INSERT_ANCHOR = text(
    "INSERT INTO flow_version (id, flow_id, user_id, data, version_number, operation_revision, graph_hash, "
    "retained, view_only, created_at) "
    "VALUES (:id, :flow_id, :user_id, CAST(:data AS json), NULL, :revision, :graph_hash, false, false, now())"
)
_START_HISTORY = text(
    "UPDATE flow SET latest_revision = :revision, current_revision = :revision, history_paused = false "
    "WHERE id = :flow_id"
)
_LAST_CHECKPOINT = text(
    "SELECT max(operation_revision) FROM flow_version "
    "WHERE flow_id = :flow_id AND version_number IS NULL AND graph_hash IS NOT NULL"
)
_CLAIM_CHECKPOINT = text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))")
# Flow.current_revision and the newest system checkpoint, without the graph.
_CHECKPOINT_STATE = text(
    "SELECT f.current_revision, (SELECT max(v.operation_revision) FROM flow_version v "
    "WHERE v.flow_id = f.id AND v.version_number IS NULL AND v.graph_hash IS NOT NULL) "
    "FROM flow f WHERE f.id = :flow_id"
)
_FIRST_RETAINED = text("SELECT min(start_revision), max(end_revision) FROM flow_operation WHERE flow_id = :flow_id")


def lock_key(flow_id: UUID) -> str:
    return f"{LOCK_NAMESPACE}{flow_id}"


async def lock_flow(session: AsyncSession, flow_id: UUID) -> None:
    """Take the flow's operation-log advisory lock until the transaction ends (PostgreSQL)."""
    await session.execute(_LOCK, {"key": lock_key(flow_id)})


async def claim_checkpoint(session: AsyncSession, flow_id: UUID) -> bool:
    """Try to claim the flow's checkpoint until the transaction ends; False when another task holds it."""
    return bool((await session.execute(_CLAIM_CHECKPOINT, {"key": f"{CHECKPOINT_NAMESPACE}{flow_id}"})).scalar_one())


async def checkpoint_state(session: AsyncSession, flow_id: UUID) -> tuple[int, int | None] | None:
    """``(Flow.current_revision, newest system checkpoint revision)``, or None when the flow is gone."""
    row = (await session.execute(_CHECKPOINT_STATE, {"flow_id": flow_id})).first()
    if row is None:
        return None
    return int(row[0]), (None if row[1] is None else int(row[1]))


async def read_head(session: AsyncSession, flow_id: UUID) -> int:
    return int((await session.execute(_HEAD, {"flow_id": flow_id})).scalar_one())


@dataclass
class HeadRead:
    head: int
    has_anchor: bool
    retry_rows: list[dict[str, Any]] | None
    exists: bool
    paused: bool
    latest: int


async def read_head_and_retry(session: AsyncSession, flow_id: UUID, request_id: str) -> HeadRead:
    row = (
        await session.execute(_HEAD_AND_RETRY, {"flow_id": flow_id, "request_ids": orjson.dumps([request_id]).decode()})
    ).one()
    retry = row.retry_rows
    if isinstance(retry, (str, bytes)):
        retry = orjson.loads(retry)
    return HeadRead(
        head=int(row.head),
        has_anchor=bool(row.has_anchor),
        retry_rows=retry,
        exists=row.paused is not None,
        paused=bool(row.paused),
        latest=int(row.latest or 0),
    )


@dataclass
class FlowData:
    data: str | bytes | None
    current_revision: int
    latest_revision: int
    history_paused: bool
    user_id: UUID | None
    version_token: UUID | None


@functools.cache
def _text_as_bytes_loader() -> type:
    """A psycopg loader that loads a ``text`` value as its UTF-8 bytes, without making a ``str``.

    psycopg is an optional dependency (the ``postgresql`` extra), so it is imported only
    when the session's driver is psycopg.
    """
    from psycopg.adapt import Loader

    class TextAsBytes(Loader):
        def load(self, data: Any) -> bytes:
            return bytes(data)

    return TextAsBytes


async def read_flow_data(session: AsyncSession, flow_id: UUID, *, as_bytes: bool = False) -> FlowData | None:
    """``Flow.data`` as text and its revision, in one statement.

    With ``as_bytes``, ``data`` is the text's UTF-8 bytes, read without a ``str`` on psycopg.
    """
    if as_bytes:
        driver = await _psycopg_connection(session)
        if driver is not None:
            async with driver.cursor() as cursor:
                cursor.adapters.register_loader("text", _text_as_bytes_loader())
                await cursor.execute(_FLOW_DATA_PG, {"flow_id": flow_id})
                row = await cursor.fetchone()
        else:
            row = (await session.execute(_FLOW_DATA, {"flow_id": flow_id})).first()
            if row is not None and row[0] is not None:
                row = (row[0].encode(), *row[1:])
    else:
        row = (await session.execute(_FLOW_DATA, {"flow_id": flow_id})).first()
    if row is None:
        return None
    return FlowData(
        data=row[0],
        current_revision=int(row[1]),
        latest_revision=int(row[2]),
        history_paused=bool(row[3]),
        user_id=row[4],
        version_token=row[5],
    )


async def _psycopg_connection(session: AsyncSession) -> Any:
    """The session's psycopg connection, in the session's transaction; None on another driver."""
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    return driver if type(driver).__module__.startswith("psycopg") else None


@dataclass
class LogRow:
    start: int
    end: int
    ops: str


async def rows_after(session: AsyncSession, flow_id: UUID, after: int, through: int | None = None) -> list[LogRow]:
    if through is None:
        result = await session.execute(_ROWS_AFTER, {"flow_id": flow_id, "after": after})
    else:
        result = await session.execute(_ROWS_BETWEEN, {"flow_id": flow_id, "after": after, "through": through})
    return [LogRow(int(r[0]), int(r[1]), r[2]) for r in result.all()]


class LogGapError(Exception):
    """The log rows do not cover the revisions asked for: compacted, or a race with compaction."""


def _engine_operation(operation: Any) -> Any:
    """A stored operation as the engine reads it: each write without its ``secrets`` parts."""
    if not isinstance(operation, dict) or operation.get("type") != "update_nodes":
        return operation
    updates = operation.get("updates")
    if not isinstance(updates, list) or not any(isinstance(u, dict) and "secrets" in u for u in updates):
        return operation
    stripped = [{k: v for k, v in u.items() if k != "secrets"} if isinstance(u, dict) else u for u in updates]
    return {**operation, "updates": stripped}


def revisions_of(rows: list[LogRow], after: int, through: int | None = None) -> list[tuple[int, Any]]:
    """``(revision, operation)`` for every revision after ``after`` (through ``through``), in order.

    Raises ``LogGapError`` when the rows skip a revision.
    """
    out: list[tuple[int, Any]] = []
    expected = after + 1
    for row in rows:
        envelope = orjson.loads(row.ops)
        revision = row.start
        for batch in envelope["batches"]:
            for element in batch["operations"]:
                if revision > after and (through is None or revision <= through):
                    if revision != expected or element.get("revision") != revision:
                        raise LogGapError(expected)
                    out.append((revision, _engine_operation(element["operation"])))
                    expected += 1
                revision += 1
        if revision != row.end + 1:
            raise LogGapError(row.start)
    if through is not None and expected != through + 1:
        raise LogGapError(expected)
    return out


def body_hash(operations_json: bytes) -> str:
    return hashlib.sha256(operations_json).hexdigest()


@dataclass
class RetryMatch:
    body_sha256: str | None
    start_revision: int
    end_revision: int


def find_retry(retry_rows: list[dict[str, Any]] | None, request_id: str) -> RetryMatch | None:
    """The stored batch of ``request_id``, from the rows the GIN lookup returned."""
    if not retry_rows:
        return None
    start = end = None
    stored_hash = None
    for row in retry_rows:
        revision = row["s"]
        for batch in row["ops"]["batches"]:
            count = len(batch["operations"])
            if batch.get("request_id") == request_id:
                stored_hash = batch.get("body_sha256", stored_hash)
                if start is None:
                    start = revision
                end = revision + count - 1
            revision += count
    if start is None or end is None:
        return None
    return RetryMatch(body_sha256=stored_hash, start_revision=start, end_revision=end)


def pack_rows(
    forward: list[bytes], *, first_revision: int, ops_limit: int, bytes_limit: int
) -> list[tuple[int, int, list[bytes]]]:
    """Group consecutive operations into rows within both limits: ``(start, end, [operation JSON])``.

    ``forward`` holds each operation's JSON text, as the engine writes it (``forward_json``).
    An operation is never split, so one larger than the byte limit gets a row of its own.
    """
    rows: list[tuple[int, int, list[bytes]]] = []
    current: list[bytes] = []
    size = 0
    start = first_revision
    revision = first_revision
    for encoded in forward:
        added = len(encoded) + 32  # the revision wrapper
        if current and (len(current) >= ops_limit or size + added > bytes_limit):
            rows.append((start, revision - 1, current))
            current, size, start = [], 0, revision
        current.append(encoded)
        size += added
        revision += 1
    if current:
        rows.append((start, revision - 1, current))
    return rows


def envelope_text(
    operations: list[bytes], *, start: int, request_id: str, actor_id: UUID, operations_sha256: str
) -> str:
    """The stored envelope of one row: one batch for this request, with the body hash for retries."""
    elements = b",".join(
        b'{"revision":%d,"operation":%s}' % (start + i, encoded) for i, encoded in enumerate(operations)
    )
    head = orjson.dumps({"request_id": request_id, "actor_user_id": str(actor_id), "body_sha256": operations_sha256})[
        :-1
    ]
    return (b'{"version":%d,"batches":[%s,"operations":[%s]}]}' % (ENVELOPE_VERSION, head, elements)).decode()


async def append_rows(
    session: AsyncSession,
    flow_id: UUID,
    rows: list[tuple[int, int, list[bytes]]],
    *,
    request_id: str,
    actor_id: UUID,
    operations_sha256: str,
) -> None:
    actors = orjson.dumps([str(actor_id)]).decode()
    request_ids = orjson.dumps([request_id]).decode()
    params = [
        {
            "id": uuid.uuid4(),
            "flow_id": flow_id,
            "start": start,
            "end": end,
            "ops": envelope_text(
                encoded, start=start, request_id=request_id, actor_id=actor_id, operations_sha256=operations_sha256
            ),
            "actors": actors,
            "request_ids": request_ids,
        }
        for start, end, encoded in rows
    ]
    if len(params) == 1:
        await session.execute(_INSERT_ROW, params[0])
    else:
        await session.execute(_INSERT_ROW, params)


async def write_flow(
    session: AsyncSession, flow_id: UUID, data: str, *, revision: int, actor_id: UUID, token: UUID
) -> None:
    await session.execute(
        _WRITE_FLOW,
        {"data": data, "revision": revision, "flow_id": flow_id, "actor": actor_id, "token": token},
    )


async def checkpoint_flow(session: AsyncSession, flow_id: UUID, data: str, *, revision: int) -> bool:
    """Write ``Flow.data`` at ``revision`` only if that is newer than the stored revision."""
    result = await session.execute(_CHECKPOINT_FLOW, {"data": data, "revision": revision, "flow_id": flow_id})
    return result.rowcount == 1


async def insert_checkpoint_row(
    session: AsyncSession, flow_id: UUID, data: str, *, revision: int, graph_hash: str
) -> bool:
    result = await session.execute(
        _INSERT_CHECKPOINT_ROW,
        {"id": uuid.uuid4(), "flow_id": flow_id, "data": data, "revision": revision, "graph_hash": graph_hash},
    )
    return result.rowcount == 1


async def start_history(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID | None,
    data: str,
    *,
    revision: int,
    graph_hash: str,
    move_flow: bool,
) -> None:
    """Write the checkpoint a flow's history starts from (the flow's first recorded write)."""
    await session.execute(
        _INSERT_ANCHOR,
        {
            "id": uuid.uuid4(),
            "flow_id": flow_id,
            "user_id": user_id,
            "data": data,
            "revision": revision,
            "graph_hash": graph_hash,
        },
    )
    if move_flow:
        await session.execute(_START_HISTORY, {"revision": revision, "flow_id": flow_id})


async def last_checkpoint_revision(session: AsyncSession, flow_id: UUID) -> int | None:
    value = (await session.execute(_LAST_CHECKPOINT, {"flow_id": flow_id})).scalar_one()
    return None if value is None else int(value)


async def retained_range(session: AsyncSession, flow_id: UUID) -> tuple[int | None, int | None]:
    row = (await session.execute(_FIRST_RETAINED, {"flow_id": flow_id})).one()
    return (None if row[0] is None else int(row[0])), (None if row[1] is None else int(row[1]))


def wal_version_token(version_token: UUID | None, flow_id: UUID, head: int) -> UUID:
    """The ``If-Match`` token of a flow in WAL mode: it changes with every revision and every legacy save.

    WAL writers never touch the flow row, so the stored token alone cannot tell a reader
    that a multiplayer write came in between.
    """
    return uuid.uuid5(version_token or flow_id, f"revision:{head}")
