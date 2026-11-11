"""Read retained job evidence from old Editor and Serving schemas without starting services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import UUID

import sqlalchemy as sa

from langflow.upgrade_check.reader import SourceDatabaseError, read_only_connection
from langflow.upgrade_check.source import identity_for_source
from langflow.upgrade_check.usage import JobUsage, UsageCoverage
from langflow.upgrade_check.usage_timestamps import normalize_usage_timestamp

if TYPE_CHECKING:
    from langflow.upgrade_check.source import SourceIdentity

# SUSPENDED is written only after an executing graph pauses for human input.
# A cancellation can occur before execution, so it provides no start evidence.
_EXECUTED_STATUSES = frozenset({"in_progress", "completed", "failed", "timed_out", "suspended"})
_ERROR_STATUSES = frozenset({"failed", "timed_out"})
_REQUIRED_COLUMNS = frozenset({"flow_id", "type", "status", "created_timestamp"})
_HISTORY_LIMITATIONS = (
    "retained_jobs_only",
    "retention_policy_unknown",
    "executions_without_job_records_untracked",
    "run_time_is_job_created_at",
)


@dataclass(frozen=True)
class JobUsageSnapshot:
    """One short aggregate read, reused for every checked flow and saved version."""

    by_flow: dict[str, JobUsage]
    default: JobUsage
    serving: bool = False

    def for_flow(self, editor_flow_id: str) -> JobUsage:
        usage = self.by_flow.get(editor_flow_id, self.default)
        if self.serving and usage.history == "no_retained_records":
            return usage.model_copy(
                update={"limitations": [*usage.limitations, "preserved_editor_flow_id_not_observed"]}
            )
        return usage


@dataclass
class _Counts:
    records: int = 0
    runs: int = 0
    errors: int = 0
    oldest: str | None = None
    newest: str | None = None
    last_run: str | None = None
    invalid_run_time: bool = False
    unclassified_type: bool = False
    limitations: set[str] = field(default_factory=set)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def unavailable_usage(
    reason: str, *, observed_at: str | None = None, identity: SourceIdentity | None = None
) -> JobUsageSnapshot:
    """Return explicit unknown evidence without copying a connection exception or URL."""
    usage = JobUsage(
        history="unavailable",
        coverage=UsageCoverage(observed_at=observed_at or _now()),
        limitations=[reason],
        source_identity=identity,
    )
    return JobUsageSnapshot({}, usage)


def read_serving_usage(database_url: str | None) -> JobUsageSnapshot:
    """Use the existing Serving job table and preserved Editor IDs, with no new API dependency."""
    if not database_url:
        return unavailable_usage("serving_not_configured")
    try:
        with read_only_connection(database_url) as connection:
            identity = identity_for_source(database_url, connection)
            snapshot = read_job_usage(connection, identity=identity)
    except (sa.exc.SQLAlchemyError, OSError, ValueError, ImportError, SourceDatabaseError):
        return unavailable_usage("serving_source_unreadable")
    return JobUsageSnapshot(snapshot.by_flow, snapshot.default, serving=True)


def read_job_usage(connection: sa.Connection, *, identity: SourceIdentity | None = None) -> JobUsageSnapshot:
    """Aggregate only known workflow execution states without loading job payloads.

    The source models are deliberately not imported because an old database may lack
    their columns. Null or absent job types cannot establish workflow execution.
    """
    observed_at = _now()
    try:
        inspector = sa.inspect(connection)
        if "job" not in inspector.get_table_names():
            return unavailable_usage("job_table_missing", observed_at=observed_at, identity=identity)
        columns = {column["name"] for column in inspector.get_columns("job")}
        missing = sorted(_REQUIRED_COLUMNS - columns)
        if missing:
            result = unavailable_usage(f"job_column_missing:{missing[0]}", observed_at=observed_at, identity=identity)
            return JobUsageSnapshot(
                {},
                result.default.model_copy(update={"limitations": [f"job_column_missing:{name}" for name in missing]}),
            )
        connection.rollback()
        rows = _job_groups(connection)
    except sa.exc.SQLAlchemyError:
        return unavailable_usage("job_history_unreadable", observed_at=observed_at, identity=identity)
    finally:
        connection.rollback()

    counts: dict[str, _Counts] = {}
    invalid_ids = False
    for row in rows:
        try:
            flow_id = str(UUID(str(row.flow_id)))
        except (ValueError, TypeError, AttributeError):
            invalid_ids = True
            continue
        current = counts.setdefault(flow_id, _Counts())
        if row.job_type != "workflow":
            current.unclassified_type = True
            current.limitations.add("unclassified_job_type_excluded")
            continue
        _add_group(current, row)

    default = _usage(_Counts(), observed_at, identity, invalid_ids=invalid_ids)
    return JobUsageSnapshot(
        {flow_id: _usage(count, observed_at, identity, invalid_ids=invalid_ids) for flow_id, count in counts.items()},
        default,
    )


def _job_groups(connection: sa.Connection):
    job = sa.table("job", *(sa.column(name) for name in sorted(_REQUIRED_COLUMNS)))
    job_type = sa.func.lower(sa.cast(job.c.type, sa.String))
    status = sa.func.lower(sa.cast(job.c.status, sa.String))
    timestamp = job.c.created_timestamp
    if connection.dialect.name == "sqlite":
        # Validate original components before SQLite can repair an invalid date.
        connection.connection.driver_connection.create_function(
            "langflow_upgrade_job_timestamp", 1, normalize_usage_timestamp, deterministic=True
        )
        timestamp = sa.func.langflow_upgrade_job_timestamp(timestamp)

    query = (
        sa.select(
            job.c.flow_id,
            job_type.label("job_type"),
            status.label("status"),
            sa.func.count().label("records"),
            sa.func.min(timestamp).label("oldest"),
            sa.func.max(timestamp).label("newest"),
            sa.func.count(timestamp).label("dated_records"),
        )
        .where(sa.or_(job_type.is_(None), job_type.not_in(("ingestion", "evaluation"))))
        .group_by(job.c.flow_id, job_type, status)
    )
    return connection.execute(query).all()


def _timestamp(value: object) -> str | None:
    normalized = normalize_usage_timestamp(value)
    if normalized is not None and normalized.endswith(".000000Z"):
        return f"{normalized.removesuffix('.000000Z')}Z"
    return normalized


def _timestamp_key(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _add_group(count: _Counts, row) -> None:
    count.records += row.records
    oldest, newest = _timestamp(row.oldest), _timestamp(row.newest)
    if oldest is not None:
        count.oldest = min(filter(None, (count.oldest, oldest)), key=_timestamp_key)
    if newest is not None:
        count.newest = max(filter(None, (count.newest, newest)), key=_timestamp_key)
    if row.dated_records != row.records:
        count.limitations.add("job_timestamps_invalid")
    if row.status in _EXECUTED_STATUSES:
        count.runs += row.records
        if row.status in _ERROR_STATUSES:
            count.errors += row.records
        if newest is not None:
            count.last_run = max(filter(None, (count.last_run, newest)), key=_timestamp_key)
        count.invalid_run_time |= row.dated_records != row.records
    elif row.status == "cancelled":
        count.limitations.add("cancelled_start_unknown")
    elif row.status != "queued":
        count.limitations.add("unknown_job_status_excluded")


def _usage(count: _Counts, observed_at: str, identity: SourceIdentity | None, *, invalid_ids: bool) -> JobUsage:
    limitations = {*_HISTORY_LIMITATIONS, *count.limitations}
    if invalid_ids:
        limitations.add("job_flow_id_invalid")
    history: Literal["retained_records", "no_retained_records"] = (
        "retained_records" if count.records else "no_retained_records"
    )
    unavailable = not count.records and count.unclassified_type
    return JobUsage(
        runs=None if unavailable else count.runs,
        errors=None if unavailable else count.errors,
        last_run_at=None if count.invalid_run_time else count.last_run,
        history="unavailable" if unavailable else history,
        coverage=UsageCoverage(
            oldest_retained_at=count.oldest, newest_retained_at=count.newest, observed_at=observed_at
        ),
        limitations=sorted(limitations),
        source_identity=identity,
    )
