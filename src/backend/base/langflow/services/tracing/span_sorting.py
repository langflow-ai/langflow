"""Span pre-insertion utilities for the native tracer.

Provides UUID resolution and topological sorting so that parent spans are
always inserted before their children — a requirement for PostgreSQL's
immediate foreign-key enforcement on ``span.parent_span_id → span.id``.
"""

from __future__ import annotations

from collections import defaultdict
from heapq import heappop, heappush
from typing import Any
from uuid import UUID, uuid5

from lfx.log.logger import logger

# Deterministic namespace for generating span UUIDs from non-UUID string IDs.
LANGFLOW_SPAN_NAMESPACE = UUID("a3e1c2d4-5b6f-7890-abcd-ef1234567890")


def resolve_span_uuids(
    completed_spans: list[dict[str, Any]],
    trace_id: UUID,
) -> list[tuple[dict[str, Any], UUID, UUID | None]]:
    """Pre-compute DB UUIDs for each span and its parent.

    Returns a list of (span_data, span_uuid, parent_uuid) tuples that can
    be topologically sorted before insertion.

    Args:
        completed_spans: List of completed span dicts.
        trace_id: The trace UUID used as part of the deterministic namespace
            when generating UUIDs from non-UUID string IDs.
    """
    resolved: list[tuple[dict[str, Any], UUID, UUID | None]] = []
    for span_data in completed_spans:
        try:
            span_uuid = UUID(span_data["id"])
        except (ValueError, TypeError):
            span_uuid = uuid5(LANGFLOW_SPAN_NAMESPACE, f"{trace_id}-{span_data['id']}")

        parent_uuid: UUID | None = None
        if span_data.get("parent_span_id"):
            parent_id = span_data["parent_span_id"]
            if isinstance(parent_id, UUID):
                parent_uuid = parent_id
            else:
                try:
                    parent_uuid = UUID(str(parent_id))
                except (ValueError, TypeError):
                    parent_uuid = uuid5(LANGFLOW_SPAN_NAMESPACE, f"{trace_id}-{parent_id}")

        resolved.append((span_data, span_uuid, parent_uuid))
    return resolved


def topological_sort_spans(
    resolved: list[tuple[dict[str, Any], UUID, UUID | None]],
) -> list[tuple[dict[str, Any], UUID, UUID | None]]:
    """Sort spans so parents appear before children.

    PostgreSQL enforces foreign-key constraints at INSERT time, so a child
    span referencing ``parent_span_id`` will fail if the parent row hasn't
    been written yet.  This performs a Kahn's-algorithm-style topological
    sort over the batch so that every parent is inserted first.

    Spans whose ``parent_span_id`` points outside the current batch are
    detached from that missing parent. Native tracing persists a trace's
    spans in a single batch, so retaining the reference would violate the
    immediate foreign-key constraint.
    """
    batch_ids = {span_uuid for _, span_uuid, _ in resolved}
    sorted_spans: list[tuple[dict[str, Any], UUID, UUID | None]] = []
    deferred: list[tuple[dict[str, Any], UUID, UUID | None]] = []
    inserted: set[UUID] = set()
    missing_parent_count = 0

    for item in resolved:
        span_data, span_uuid, parent_uuid = item
        if parent_uuid is not None and parent_uuid not in batch_ids:
            sorted_spans.append((span_data, span_uuid, None))
            missing_parent_count += 1
        elif parent_uuid is not None and parent_uuid not in inserted:
            deferred.append(item)
            continue
        else:
            sorted_spans.append(item)
        inserted.add(span_uuid)

    if missing_parent_count:
        logger.warning(
            "Detached %d tracing spans from missing parents to preserve database integrity.",
            missing_parent_count,
        )
    if not deferred:
        return sorted_spans

    # (scan round, input position) reproduces the order of successive left-to-right scans.
    ready: list[tuple[int, int]] = []
    waiting: dict[UUID, list[int]] = defaultdict(list)
    for position, (_, _, parent_uuid) in enumerate(deferred):
        if parent_uuid is not None and parent_uuid not in inserted:
            waiting[parent_uuid].append(position)
        else:
            ready.append((0, position))

    # Initial positions are already ordered. Releasing each parent ID once avoids
    # scheduling its children twice when multiple spans share the same ID.
    while ready:
        scan_round, position = heappop(ready)
        item = deferred[position]
        sorted_spans.append(item)
        for child in waiting.pop(item[1], []):
            child_round = scan_round + (child < position)
            heappush(ready, (child_round, child))

    if waiting:
        logger.warning(
            "Detected cycle or unresolvable span dependencies in tracing batch; "
            "breaking parent relationships for %d spans to preserve DB integrity.",
            len(resolved) - len(sorted_spans),
        )
        sorted_spans.extend((data, span_id, None) for data, span_id, parent in deferred if parent in waiting)

    return sorted_spans
