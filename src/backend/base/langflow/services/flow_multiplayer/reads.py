"""Multiplayer reads. None takes a lock.

- ``revisions_body``: the revisions after R, straight from the log rows.
- ``join_body``: the cached graph caught up to the head when the flow is
  cached; otherwise ``Flow.data`` and its revision in one statement (in
  ``wal`` that is the last checkpoint, and the client catches up through the
  revisions).
- ``current_flow``: the current graph for the v1 read: ``Flow.data``
  (``nocache``: always the head), or the cached graph caught up to the head,
  built from ``Flow.data`` plus the rows after it when it is not cached.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import orjson
from starlette.responses import Response

from langflow.services.flow_multiplayer import bench, config, oplog
from langflow.services.flow_multiplayer.cache import CACHE, EntryGoneError, SerializedGraph, entry_at_head
from langflow.services.flow_multiplayer.serialization_response import SerializedGraphResponse, hold_for_response

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

EMPTY_GRAPH = '{"nodes":[],"edges":[]}'


async def revisions_body(session: AsyncSession, flow_id: UUID, after: int, fallback_head: int) -> bytes:
    """``{"latest_revision", "retention_gap", "revisions": [{"revision", "operations"}]}``.

    ``retention_gap`` is true when revision ``after + 1`` is no longer in the log;
    the client then joins again. ``fallback_head`` is the flow's latest revision,
    used only when the log has no rows at all (after a purge).
    """
    with bench.timed("rows_db"):
        rows = await oplog.rows_after(session, flow_id, after)
    if not rows:
        _first, last = await oplog.retained_range(session, flow_id)
        head = last if last is not None else fallback_head
        gap = last is None and after < head
        return b'{"latest_revision":%d,"retention_gap":%s,"revisions":[]}' % (head, b"true" if gap else b"false")
    head = rows[-1].end
    try:
        if rows[0].start > after + 1:
            raise oplog.LogGapError(after + 1)
        revisions = oplog.revisions_of(rows, after)
    except oplog.LogGapError:
        return b'{"latest_revision":%d,"retention_gap":true,"revisions":[]}' % head
    with bench.timed("encode_part"):
        parts = [b'{"revision":%d,"operations":[%s]}' % (revision, orjson.dumps(op)) for revision, op in revisions]
    bench.put("revisions_n", len(parts))
    return b'{"latest_revision":%d,"retention_gap":false,"revisions":[%s]}' % (head, b",".join(parts))


@dataclass
class CurrentGraph:
    revision: int
    text: str
    lease: SerializedGraph | None = None

    def close(self) -> None:
        """Release a service-level lease not managed by the outer HTTP scope."""
        if self.lease is not None:
            self.lease.close()
            self.lease = None

    def response(self, body: bytes) -> Response:
        """Transfer a router-only lease to the response which sends these bytes."""
        if self.lease is None:
            return Response(body, media_type="application/json")
        response = SerializedGraphResponse(body, lease=self.lease, media_type="application/json")
        self.lease = None
        return response


async def join_graph(session: AsyncSession, flow_id: UUID) -> CurrentGraph | None:
    if config.uses_cache() and CACHE.get(flow_id) is not None:
        return await _cached_at_head(session, flow_id)
    data = await oplog.read_flow_data(session, flow_id)
    if data is None:
        return None
    return CurrentGraph(data.current_revision, data.data or EMPTY_GRAPH)


async def current_graph(session: AsyncSession, flow_id: UUID) -> CurrentGraph | None:
    """The graph at the head, for the v1 read."""
    if config.uses_cache():
        return await _cached_at_head(session, flow_id)
    data = await oplog.read_flow_data(session, flow_id)
    if data is None:
        return None
    return CurrentGraph(data.current_revision, data.data or EMPTY_GRAPH)


async def _cached_at_head(session: AsyncSession, flow_id: UUID) -> CurrentGraph | None:
    for _attempt in range(3):
        with bench.timed("head"):
            head = await oplog.read_head(session, flow_id)
        entry = await entry_at_head(session, flow_id, head)
        if entry is None:
            return None
        try:
            serialized = await entry.serialized()
        except EntryGoneError:
            continue
        try:
            managed = hold_for_response(serialized)
            return CurrentGraph(serialized.revision, serialized.text, None if managed else serialized)
        except BaseException:
            serialized.close()
            raise
    msg = f"could not read flow {flow_id}"
    raise RuntimeError(msg)


def join_body(graph: CurrentGraph) -> bytes:
    return b'{"revision":%d,"data":%s}' % (graph.revision, graph.text.encode())
