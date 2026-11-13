"""Read-only success measures over a bounded, retained trigger cohort.

Only the Prometheus-owning API process collects these gauges, through the
existing background metric collector. No event payloads or resource identifiers
become metric labels. Retries and replica failover reuse durable rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_
from sqlmodel import col, select

from langflow.services.database.models.jobs.model import JobEvent
from langflow.services.database.models.trigger.model import TriggerEvent, TriggerRenewalObservation, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerEventState, TriggerSubscriptionState
from langflow.services.triggers.constants import REPLAY_DEDUPE_PREFIX, TEST_DEDUPE_PREFIX
from langflow.services.triggers.source_delivery import SOURCE_HINT_FIELD

ORIGINS = ("source", "replay", "test")


@dataclass
class TriggerMetricSnapshot:
    event_counts: dict[tuple[str, str], int] = field(default_factory=dict)
    dispatch_latencies: list[float] = field(default_factory=list)
    missing_first_starts: int = 0
    oldest_pending_seconds: float = 0
    renewal_counts: dict[str, int] = field(default_factory=dict)
    renewals_with_gap: int = 0
    renewal_gap_seconds: float = 0
    expired_subscriptions: int = 0


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def query_trigger_metrics(session, *, now: datetime, window_seconds: float = 300) -> TriggerMetricSnapshot:
    """Collect one window of retained data; missing first-start evidence stays explicit."""
    snapshot = TriggerMetricSnapshot()
    cutoff = now - timedelta(seconds=window_seconds)
    if session.get_bind().dialect.name != "postgresql":
        cutoff = cutoff.replace(tzinfo=None)
    replay = or_(
        col(TriggerEvent.replay_of_event_id).is_not(None),
        col(TriggerEvent.dedupe_key).startswith(f"{REPLAY_DEDUPE_PREFIX}:"),
    )
    origin = case(
        (replay, "replay"),
        (col(TriggerEvent.dedupe_key).startswith(f"{TEST_DEDUPE_PREFIX}:"), "test"),
        else_="source",
    )
    # Hint rows wake provider reconciliation; they are not accepted canonical
    # events and do not represent a flow run. Filtered deliveries remain
    # visible as skipped and are excluded from the dashboard's eligible cohort.
    canonical = func.coalesce(TriggerEvent.payload[SOURCE_HINT_FIELD].as_boolean(), False).is_(False)
    cohort = [col(TriggerEvent.created_at) >= cutoff, canonical]
    # Provider eligibility checks can terminalize a delivery without creating a
    # job. Such ledger completions mean filtered work, never a successful run.
    outcome = case(
        (
            (TriggerEvent.state == TriggerEventState.COMPLETED.value) & col(TriggerEvent.job_id).is_(None),
            TriggerEventState.SKIPPED.value,
        ),
        else_=TriggerEvent.state,
    )
    counts = await session.exec(select(origin, outcome, func.count()).where(*cohort).group_by(origin, outcome))
    snapshot.event_counts = {(source, state): int(count) for source, state, count in counts.all()}
    # A correlated lookup uses the job-id index for each bounded-cohort row;
    # it never groups all retained job events just to find a recent first start.
    first_started = (
        select(func.min(JobEvent.created_at))
        .where(JobEvent.job_id == TriggerEvent.job_id, col(JobEvent.event_type).in_(("build_start", "RUN_STARTED")))
        .correlate(TriggerEvent)
        .scalar_subquery()
    )
    rows = await session.exec(
        select(TriggerEvent.created_at, first_started).where(
            *cohort, origin == "source", col(TriggerEvent.job_id).is_not(None)
        )
    )
    for accepted, started in rows.all():
        if started is None:
            snapshot.missing_first_starts += 1
        else:
            snapshot.dispatch_latencies.append(max((_aware(started) - _aware(accepted)).total_seconds(), 0))
    snapshot.dispatch_latencies.sort()
    oldest = (
        await session.exec(
            select(func.min(TriggerEvent.created_at)).where(
                canonical,
                origin == "source",
                col(TriggerEvent.state).in_([TriggerEventState.PENDING.value, TriggerEventState.CLAIMED.value]),
            )
        )
    ).first()
    if oldest is not None:
        snapshot.oldest_pending_seconds = max((_aware(now) - _aware(oldest)).total_seconds(), 0)
    renewals = (
        await session.exec(
            select(TriggerRenewalObservation.outcome, func.count())
            .where(TriggerRenewalObservation.observed_at >= cutoff)
            .group_by(TriggerRenewalObservation.outcome)
        )
    ).all()
    snapshot.renewal_counts = {outcome: int(count) for outcome, count in renewals}
    count, gap = (
        await session.exec(
            select(func.count(), func.coalesce(func.sum(TriggerRenewalObservation.gap_seconds), 0)).where(
                TriggerRenewalObservation.observed_at >= cutoff,
                TriggerRenewalObservation.outcome == "renewed",
                TriggerRenewalObservation.gap_seconds > 0,
            )
        )
    ).one()
    snapshot.renewals_with_gap = int(count)
    snapshot.renewal_gap_seconds = float(gap)
    sql_now = now if session.get_bind().dialect.name == "postgresql" else now.replace(tzinfo=None)
    snapshot.expired_subscriptions = int(
        (
            await session.exec(
                select(func.count())
                .select_from(TriggerSubscription)
                .where(
                    col(TriggerSubscription.state).in_(
                        [TriggerSubscriptionState.ACTIVE.value, TriggerSubscriptionState.ERROR.value]
                    ),
                    TriggerSubscription.expires_at <= sql_now,
                )
            )
        ).one()
    )
    return snapshot


def publish_trigger_metrics(ot, snapshot: TriggerMetricSnapshot, *, backend: str, window_seconds: float) -> None:
    """Zero-fill bounded label sets so a disappearing cohort does not stay stale."""
    from langflow.services.background_execution.metrics_collector import _nearest_rank

    labels = {"backend": backend}
    ot.update_gauge("langflow_trigger_metrics_window_seconds", window_seconds, labels)
    for origin in ORIGINS:
        for state in TriggerEventState:
            ot.update_gauge(
                "langflow_trigger_events",
                snapshot.event_counts.get((origin, state.value), 0),
                {**labels, "origin": origin, "state": state.value},
            )
    for percentile in (50, 95):
        value = _nearest_rank(snapshot.dispatch_latencies, percentile) if snapshot.dispatch_latencies else 0
        ot.update_gauge(f"langflow_trigger_dispatch_latency_p{percentile}_seconds", value, labels)
    ot.update_gauge("langflow_trigger_dispatch_latency_samples", len(snapshot.dispatch_latencies), labels)
    ot.update_gauge("langflow_trigger_missing_first_starts", snapshot.missing_first_starts, labels)
    ot.update_gauge("langflow_trigger_oldest_pending_seconds", snapshot.oldest_pending_seconds, labels)
    for outcome in ("renewed", "failed"):
        ot.update_gauge(
            "langflow_trigger_renewals", snapshot.renewal_counts.get(outcome, 0), {**labels, "outcome": outcome}
        )
    ot.update_gauge("langflow_trigger_renewals_with_gap", snapshot.renewals_with_gap, labels)
    ot.update_gauge("langflow_trigger_renewal_gap_seconds", snapshot.renewal_gap_seconds, labels)
    ot.update_gauge("langflow_trigger_expired_subscriptions", snapshot.expired_subscriptions, labels)
