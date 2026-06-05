"""DB-derived metric queries for background execution observability.

Pure, read-only aggregates over the durable job model. Each function takes a
session and (where time matters) an injected ``now`` so the math is
deterministic in tests and the loop owns the clock. No side effects, no gauge
writes — Task 7 wires these into the OTel gauges.

``now`` is timezone-aware UTC. ``created_timestamp`` is stored as a
timezone-aware column, but SQLite hands it back naive; we normalize to aware
UTC before subtracting so the math is valid on both SQLite and Postgres.

The "alive" worker definition reuses ``JobService.is_lease_stale`` semantics so
it matches the watchdog exactly: a heartbeat is FRESH while its age is within
the lease window (``age <= lease_window``), stale once older.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import col, func, select

from langflow.services.database.models.jobs.model import Job, JobStatus

# Non-terminal statuses: a job in one of these is still occupying the system.
# QUEUED/IN_PROGRESS are the only non-terminal states; COMPLETED / FAILED /
# TIMED_OUT / CANCELLED are terminal.
NONTERMINAL_STATUSES = (JobStatus.QUEUED, JobStatus.IN_PROGRESS)


async def count_nonterminal_jobs(session) -> dict[str, int]:
    """Return counts of non-terminal jobs keyed by status string.

    ``{"queued": 3, "in_progress": 1}`` via a ``GROUP BY status`` aggregate
    filtered to the non-terminal set. Statuses with zero rows are omitted (the
    collector loop fills in the canonical set with 0 when it sets gauges).
    """
    stmt = select(Job.status, func.count()).where(col(Job.status).in_(NONTERMINAL_STATUSES)).group_by(Job.status)
    result = await session.exec(stmt)
    counts: dict[str, int] = {}
    for status, count in result.all():
        # ``status`` is a JobStatus enum; ``.value`` is the wire string.
        key = status.value if isinstance(status, JobStatus) else str(status)
        counts[key] = int(count)
    return counts


async def oldest_queued_seconds(session, now: datetime) -> float:
    """Age in seconds of the oldest QUEUED job: ``now - min(created_timestamp)``.

    Returns ``0.0`` when nothing is queued. ``now`` is injected (aware UTC) for
    determinism.
    """
    stmt = select(func.min(Job.created_timestamp)).where(Job.status == JobStatus.QUEUED)
    result = await session.exec(stmt)
    oldest = result.first()
    if oldest is None:
        return 0.0
    # SQLite returns a naive datetime for a timezone-aware column; treat it as
    # UTC (matching how is_lease_stale normalizes naive heartbeats).
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    age = (now - oldest).total_seconds()
    # A clock skew where now precedes the row should never report a negative age.
    return max(age, 0.0)


async def alive_worker_count(session, now: datetime, lease_window: float) -> int:
    """Count distinct heartbeat owners whose lease is still fresh.

    Fresh means ``heartbeat_at >= now - lease_window`` — the exact inverse of
    ``JobService.is_lease_stale`` (stale once ``age > lease_window``), so a
    worker counted "alive" here is one the watchdog would NOT reconcile. The
    heartbeat lease lives in ``job_metadata`` (``owner`` + ``heartbeat_at`` ISO
    string), stamped only on IN_PROGRESS rows by ``JobService.heartbeat``.

    Parsing the ISO ``heartbeat_at`` in Python (rather than a cross-dialect
    JSON-string SQL comparison) keeps the boundary identical to is_lease_stale
    on both SQLite and Postgres.
    """
    stmt = select(Job.job_metadata).where(Job.status == JobStatus.IN_PROGRESS)
    result = await session.exec(stmt)
    alive_owners: set[str] = set()
    for row in result.all():
        meta = row or {}
        owner = meta.get("owner")
        raw = meta.get("heartbeat_at")
        if not owner or not raw:
            continue
        try:
            hb = datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            continue
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        age = (now - hb).total_seconds()
        if age <= lease_window:
            alive_owners.add(owner)
    return len(alive_owners)
