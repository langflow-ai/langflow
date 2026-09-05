"""The leased dispatcher: claim ledger rows, run one job each, account for them.

Guarantees, and where each one lives:

* **exactly one run per event across replicas** — every claim is a single
  conditional UPDATE guarded on ``state='pending'`` plus the row's own identity,
  so only one dispatcher sees ``rowcount == 1``. On Postgres the candidate scan
  additionally uses ``FOR UPDATE SKIP LOCKED`` so replicas do not queue behind
  each other; on SQLite the file-level write lock serializes the same statements
  across the several worker processes a single container runs.
* **no event dropped when a dispatcher dies** — a claimed row carries a lease.
  Once the lease expires, :func:`sweep_expired_claims` returns it to ``pending``
  with ``attempt`` incremented, or dead-letters it at the attempt limit.
* **no event doubled when a dispatcher dies after submitting** — the moment a
  job exists the row moves to ``dispatched`` and the lease is dropped: liveness
  for a running job belongs to the background execution service's own orphan
  sweep, not to this loop.
* **per-trigger concurrency** — claims are refused while a trigger already has
  ``concurrency_limit`` rows in flight.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from sqlmodel import col, func, select, update

from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.trigger.schemas import (
    IN_FLIGHT_EVENT_STATES,
    TriggerEventState,
    TriggerState,
)
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import leases
from langflow.services.triggers.binding import resolve_binding
from langflow.services.triggers.constants import (
    DISPATCHER_LEASE_NAME,
    FAMILY_TRIGGER_LISTENER,
    TRIGGER_EVENT_FIELD,
)
from langflow.services.triggers.correlation import derive_session_id
from langflow.services.triggers.errors import BindingUnsupportedError
from langflow.services.triggers.ledger import purge_events
from langflow.services.triggers.principal import connection_preflight

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

#: Trigger states whose events are executed. A paused, expired, or dead trigger
#: is one the owner (or the system) took out of service, so its queued events are
#: retired rather than run later at a surprising moment.
_DISPATCHABLE_TRIGGER_STATES = frozenset(
    {
        TriggerState.ACTIVE.value,
        TriggerState.PENDING.value,
        TriggerState.ERROR.value,
        TriggerState.NEEDS_RECONNECT.value,
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff, capped. ``attempt`` is the count already spent."""
    settings = get_settings_service().settings
    delay = settings.trigger_retry_backoff_base_s * (2 ** max(attempt - 1, 0))
    return min(delay, settings.trigger_retry_backoff_cap_s)


# --------------------------------------------------------------------------- #
# Claiming
# --------------------------------------------------------------------------- #


async def _due_trigger_ids(session: AsyncSession, *, limit: int) -> list[UUID]:
    """Triggers with at least one due pending event, longest-waiting first.

    The scan is per *trigger*, not per event, because the per-trigger
    concurrency cap is applied afterwards. A flat oldest-first event scan lets
    one busy trigger at its cap fill the whole candidate window: every candidate
    belongs to it, at most ``concurrency_limit`` of them are claimable, and a
    second trigger's single event never enters the window at all until the
    backlog drains. Choosing the triggers first and then taking each one's
    headroom is what makes the cap a cap rather than a queue head.
    """
    statement = (
        select(TriggerEvent.trigger_id)
        .where(
            TriggerEvent.state == TriggerEventState.PENDING.value,
            col(TriggerEvent.available_at) <= _now(),
        )
        .group_by(col(TriggerEvent.trigger_id))
        .order_by(func.min(col(TriggerEvent.available_at)))
        .limit(limit)
    )
    return list((await session.exec(statement)).all())


async def _candidate_ids(session: AsyncSession, *, trigger_id: UUID, limit: int) -> list[UUID]:
    """One trigger's due pending rows, oldest first, at most ``limit`` of them.

    On Postgres the scan takes row locks with ``SKIP LOCKED`` so concurrent
    dispatchers walk disjoint candidate sets instead of colliding on the same
    head-of-queue rows. SQLite has no such clause; correctness there comes from
    the guarded UPDATE below, which is what actually decides the winner on both
    engines.
    """
    statement = (
        select(TriggerEvent.id)
        .where(
            TriggerEvent.trigger_id == trigger_id,
            TriggerEvent.state == TriggerEventState.PENDING.value,
            col(TriggerEvent.available_at) <= _now(),
        )
        .order_by(col(TriggerEvent.available_at), col(TriggerEvent.created_at))
        .limit(limit)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    return list((await session.exec(statement)).all())


async def _in_flight_counts(session: AsyncSession) -> dict[UUID, int]:
    """How many rows each trigger currently has claimed or dispatched."""
    statement = select(TriggerEvent.trigger_id).where(col(TriggerEvent.state).in_(sorted(IN_FLIGHT_EVENT_STATES)))
    counts: dict[UUID, int] = {}
    for trigger_id in (await session.exec(statement)).all():
        counts[trigger_id] = counts.get(trigger_id, 0) + 1
    return counts


async def _claim_one(session: AsyncSession, *, event_id: UUID, owner: str, lease_ttl_s: float) -> bool:
    """Conditional UPDATE that decides the single winner for one row."""
    statement = (
        update(TriggerEvent)
        .where(TriggerEvent.id == event_id, TriggerEvent.state == TriggerEventState.PENDING.value)
        .values(
            state=TriggerEventState.CLAIMED.value,
            lease_owner=owner,
            lease_expires_at=_now() + timedelta(seconds=lease_ttl_s),
        )
    )
    result = await session.exec(statement)  # type: ignore[call-overload]
    await session.flush()
    return bool(result.rowcount == 1)


async def claim_batch(session: AsyncSession, *, owner: str, limit: int, lease_ttl_s: float) -> list[TriggerEvent]:
    """Claim up to ``limit`` due events for ``owner``, respecting concurrency caps.

    Triggers are visited round-robin (longest-waiting first) and each one may
    contribute only its remaining headroom, so a trigger at its cap costs the
    batch nothing and never crowds another trigger out of the window.
    """
    trigger_ids = await _due_trigger_ids(session, limit=limit)
    if not trigger_ids:
        return []
    in_flight = await _in_flight_counts(session)
    claimed: list[TriggerEvent] = []
    for trigger_id in trigger_ids:
        remaining = limit - len(claimed)
        if remaining <= 0:
            break
        trigger = await session.get(Trigger, trigger_id)
        if trigger is None:  # pragma: no cover - FK cascade makes this unreachable
            continue
        headroom = min(trigger.concurrency_limit - in_flight.get(trigger_id, 0), remaining)
        if headroom <= 0:
            continue
        for event_id in await _candidate_ids(session, trigger_id=trigger_id, limit=headroom):
            event = await session.get(TriggerEvent, event_id)
            if event is None or event.state != TriggerEventState.PENDING.value:
                continue
            if not await _claim_one(session, event_id=event_id, owner=owner, lease_ttl_s=lease_ttl_s):
                continue
            in_flight[trigger_id] = in_flight.get(trigger_id, 0) + 1
            await session.refresh(event)
            claimed.append(event)
    return claimed


# --------------------------------------------------------------------------- #
# Accounting
# --------------------------------------------------------------------------- #


async def _terminalize(
    session: AsyncSession,
    *,
    event: TriggerEvent,
    state: TriggerEventState,
    error: str | None = None,
) -> None:
    event.state = state.value
    event.error = error
    event.lease_owner = None
    event.lease_expires_at = None
    event.updated_at = _now()
    session.add(event)
    await session.flush()


async def _schedule_retry(session: AsyncSession, *, event: TriggerEvent, max_attempts: int, error: str) -> None:
    """Return a failed attempt to the queue, or dead-letter it at the limit."""
    attempt = event.attempt + 1
    if attempt >= max_attempts:
        event.attempt = attempt
        await _terminalize(session, event=event, state=TriggerEventState.DEAD, error=error)
        await logger.awarning("Trigger event %s dead-lettered after %s attempts", event.id, attempt)
        return
    event.attempt = attempt
    event.state = TriggerEventState.PENDING.value
    event.error = error
    event.lease_owner = None
    event.lease_expires_at = None
    event.available_at = _now() + timedelta(seconds=_backoff_seconds(attempt))
    event.updated_at = _now()
    session.add(event)
    await session.flush()


async def sweep_expired_claims(session: AsyncSession, *, limit: int = 100) -> int:
    """Reclaim rows whose holder died mid-claim. Returns the number reclaimed.

    Only ``claimed`` rows are swept. A ``dispatched`` row has a job, and the
    background execution service's own orphan sweep owns that job's liveness;
    re-dispatching it here is exactly the doubling this ledger exists to prevent.
    """
    statement = (
        select(TriggerEvent)
        .where(
            TriggerEvent.state == TriggerEventState.CLAIMED.value,
            col(TriggerEvent.lease_expires_at) < _now(),
        )
        .limit(limit)
    )
    reclaimed = 0
    for event in (await session.exec(statement)).all():
        trigger = await session.get(Trigger, event.trigger_id)
        max_attempts = trigger.max_attempts if trigger is not None else 1
        # Guarded on the exact lease we read, so two sweepers cannot both bump
        # the attempt counter for one row.
        guard = (
            update(TriggerEvent)
            .where(
                TriggerEvent.id == event.id,
                TriggerEvent.state == TriggerEventState.CLAIMED.value,
                TriggerEvent.lease_expires_at == event.lease_expires_at,
            )
            .values(state=TriggerEventState.PENDING.value, lease_owner=None, lease_expires_at=None)
        )
        result = await session.exec(guard)  # type: ignore[call-overload]
        await session.flush()
        if result.rowcount != 1:
            continue
        await session.refresh(event)
        await _schedule_retry(session, event=event, max_attempts=max_attempts, error="lease_expired")
        reclaimed += 1
    return reclaimed


async def reconcile_dispatched(session: AsyncSession, *, limit: int = 200) -> int:
    """Close out ledger rows whose job has reached a terminal state.

    Without this a ``dispatched`` row would never become purgeable and an
    operator could not tell a finished trigger run from a stuck one.
    """
    from langflow.services.database.models.jobs.model import Job, JobStatus

    terminal_success = {JobStatus.COMPLETED}
    terminal_failure = {JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT}
    statement = (
        select(TriggerEvent)
        .where(TriggerEvent.state == TriggerEventState.DISPATCHED.value, col(TriggerEvent.job_id).is_not(None))
        .limit(limit)
    )
    closed = 0
    for event in (await session.exec(statement)).all():
        job = await session.get(Job, event.job_id)
        if job is None or job.status not in (terminal_success | terminal_failure):
            continue
        if job.status in terminal_success:
            await _terminalize(session, event=event, state=TriggerEventState.COMPLETED)
        else:
            await _terminalize(session, event=event, state=TriggerEventState.FAILED, error=f"job_{job.status.value}")
        closed += 1
    return closed


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def _ensure_frame_source() -> None:
    """Install the background runner's build source if no route has yet.

    ``BackgroundExecutionService`` ships with ``frame_source_factory=None`` and
    only the v2 workflow routes install one, lazily, on their first POST. A
    dispatcher started from the API lifespan in a freshly booted process would
    otherwise reach ``None`` inside ``_enqueue`` and every trigger run would die
    on the first tick after a restart.

    Reaching from a service into ``langflow.api.v2.workflow`` is a layering
    inversion, and a deliberate one: the alternative is a second frame source
    that would have to reproduce the build loop, the memory-base hook and the
    telemetry drain the v2 factory already owns, and would drift from it. The
    import is local so the module graph stays acyclic, and the assignment is
    skipped whenever a route has already installed the same callable.
    """
    from langflow.api.v2.workflow import _default_frame_source_factory
    from langflow.services.deps import get_background_execution_service

    service = get_background_execution_service()
    if service._frame_source_factory is None:  # noqa: SLF001
        service._frame_source_factory = _default_frame_source_factory  # noqa: SLF001


def build_event_envelope(trigger: Trigger, event: TriggerEvent) -> dict[str, Any]:
    """What a trigger component sees as its ``Event`` output."""
    return {
        "trigger_id": str(trigger.id),
        "event_id": str(event.id),
        "kind": trigger.kind,
        "provider": trigger.provider,
        "dedupe_key": event.dedupe_key,
        "attempt": event.attempt,
        "payload": event.payload or {},
    }


def build_submit_request(
    *,
    trigger: Trigger,
    event: TriggerEvent,
    binding_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """The background-run request for one ledger row.

    Every key here is a field ``WorkflowRunRequest`` declares. That model is
    ``extra="forbid"`` and the worker re-parses this dict before it builds
    anything (``_parse_persisted_workflow_request``), so an invented key is not
    a harmless annotation — it fails the run after the job row is already
    committed, and the event retries its way to a dead letter. Two things that
    look like they belong on the body therefore do not:

    * the **execution family** travels as an argument, not a field (see
      ``EXECUTION_FAMILY_KWARG``);
    * the **firing event** rides ``tweaks``, keyed by the trigger's canvas node
      id, exactly as the Webhook component's payload does. ``tweaks`` survives
      the durable round trip in the authenticated override envelope, so a
      scaled-mode worker re-parsing the job row sees the same event.

    An API-created trigger with no ``node_id`` names no node to feed, so it
    sends no tweak and a trigger component in that flow reads an empty event.

    ``idempotency_key`` includes the attempt: the background execution service
    dedupes on that key *including completed jobs*, so a retry that reused the
    key would silently return the old job id and the event would never re-run.

    ``data`` carries a pinned version's canvas. It is the same override the v2
    route accepts from a flow writer; here it is server-generated from a version
    of the trigger's own flow, and the run executes as that flow's owner. It is
    sent only for a pinned trigger — an unpinned run builds from the saved flow,
    so copying the canvas onto every event would bloat each job row for nothing.
    """
    tweaks: dict[str, Any] = {}
    if trigger.node_id:
        tweaks[trigger.node_id] = {TRIGGER_EVENT_FIELD: json.dumps(build_event_envelope(trigger, event))}
    request: dict[str, Any] = {
        "flow_id": str(trigger.flow_id),
        "mode": "background",
        "input_value": "",
        "session_id": derive_session_id(trigger, event),
        "tweaks": tweaks,
        "idempotency_key": f"trg:{event.id}:{event.attempt}",
    }
    if binding_data is not None:
        request["data"] = binding_data
    return request


async def dispatch_event(session: AsyncSession, event: TriggerEvent, *, family: str = FAMILY_TRIGGER_LISTENER) -> None:
    """Turn one claimed ledger row into one background job, or account for why not."""
    from langflow.services.database.models.user.model import UserRead
    from langflow.services.deps import get_background_execution_service

    trigger = await session.get(Trigger, event.trigger_id)
    if trigger is None:  # pragma: no cover - FK cascade makes this unreachable
        await _terminalize(session, event=event, state=TriggerEventState.FAILED, error="trigger_missing")
        return

    if trigger.state not in _DISPATCHABLE_TRIGGER_STATES:
        await _terminalize(session, event=event, state=TriggerEventState.FAILED, error=f"trigger_{trigger.state}")
        return

    try:
        binding = await resolve_binding(session, trigger)
    except BindingUnsupportedError as exc:
        # Terminal on purpose: retrying cannot make an undispatchable binding
        # dispatchable, and a retry storm would bury the real message.
        await _terminalize(session, event=event, state=TriggerEventState.FAILED, error=str(exc))
        trigger.last_error = str(exc)
        session.add(trigger)
        await session.flush()
        return

    denial = await connection_preflight(session, trigger, family=family)
    if denial is not None:
        # Fail closed, and say so on the trigger: an unattended run must never
        # fall back to a weaker identity when its connection refuses one.
        await _terminalize(session, event=event, state=TriggerEventState.FAILED, error="connection_not_authorized")
        trigger.state = TriggerState.NEEDS_RECONNECT.value
        trigger.last_error = "connection_not_authorized"
        session.add(trigger)
        await session.flush()
        await logger.awarning(
            "Trigger %s cannot run unattended: its connection does not allow non-interactive use", trigger.id
        )
        return

    request = build_submit_request(trigger=trigger, event=event, binding_data=binding.data)
    session_id = request["session_id"]
    try:
        _ensure_frame_source()
        job_id = await get_background_execution_service().submit(
            flow_id=trigger.flow_id,
            request=request,
            user=UserRead.model_construct(id=trigger.user_id),
        )
    except Exception as exc:  # noqa: BLE001 — every submit failure is retryable work, not a crash
        await logger.awarning("Trigger %s failed to submit event %s: %s", trigger.id, event.id, type(exc).__name__)
        await _schedule_retry(
            session, event=event, max_attempts=trigger.max_attempts, error=f"submit_failed:{type(exc).__name__}"
        )
        return

    event.job_id = job_id
    event.session_id = session_id
    event.state = TriggerEventState.DISPATCHED.value
    event.error = None
    # The job now owns liveness; keeping a lease here would let the sweep
    # re-dispatch a run that is already going.
    event.lease_owner = None
    event.lease_expires_at = None
    event.updated_at = _now()
    session.add(event)
    trigger.last_fired_at = _now()
    session.add(trigger)
    await session.flush()


async def run_once(*, owner: str) -> int:
    """One dispatcher pass: sweep, reconcile, claim, dispatch. Returns rows dispatched."""
    settings = get_settings_service().settings
    async with session_scope() as session:
        await sweep_expired_claims(session)
        await reconcile_dispatched(session)
        claimed = await claim_batch(
            session,
            owner=owner,
            limit=settings.trigger_max_events_per_poll,
            lease_ttl_s=settings.trigger_lease_ttl_s,
        )
    dispatched = 0
    for event in claimed:
        # One transaction per event: a single poisonous row must not roll back
        # the whole batch's accounting.
        async with session_scope() as session:
            fresh = await session.get(TriggerEvent, event.id)
            if fresh is None or fresh.state != TriggerEventState.CLAIMED.value:
                continue
            await dispatch_event(session, fresh)
            if fresh.state == TriggerEventState.DISPATCHED.value:
                dispatched += 1
    return dispatched


class TriggerDispatcher:
    """The lifespan-owned loop that holds the dispatcher lease and drains the ledger.

    Every API replica may start one. The lease decides which of them is doing the
    work at any moment, and a replica that loses it keeps polling so a failover
    costs one TTL, not an operator page.
    """

    def __init__(self, *, owner: str | None = None) -> None:
        self.owner = owner or leases.new_owner_token("dispatcher")
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._last_purge_at: datetime | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        # Hand the lease back so another replica takes over immediately rather
        # than waiting out the TTL on a clean shutdown.
        with contextlib.suppress(Exception):
            async with session_scope() as session:
                await leases.release(session, name=DISPATCHER_LEASE_NAME, owner=self.owner)

    async def _loop(self) -> None:
        settings = get_settings_service().settings
        while not self._stopping.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — the loop must outlive one bad pass
                await logger.aerror("Trigger dispatcher pass failed: %s", type(exc).__name__)
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=settings.trigger_dispatcher_poll_interval_s)

    async def tick(self) -> int:
        """Produce due ticks, then drain the ledger. Returns rows dispatched.

        The schedule tick producer holds its OWN lease, so a replica may be
        producing ticks while another drains them — two independent singletons,
        not one bottleneck.
        """
        from langflow.services.triggers.scheduler import run_scheduler_pass

        await run_scheduler_pass(owner=self.owner)
        settings = get_settings_service().settings
        async with session_scope() as session:
            held = await leases.acquire(
                session,
                name=DISPATCHER_LEASE_NAME,
                owner=self.owner,
                ttl_s=settings.trigger_lease_ttl_s,
            )
        if not held:
            return 0
        dispatched = await run_once(owner=self.owner)
        await self._maybe_purge()
        return dispatched

    async def _maybe_purge(self) -> None:
        settings = get_settings_service().settings
        now = _now()
        if (
            self._last_purge_at is not None
            and (now - self._last_purge_at).total_seconds() < settings.trigger_purge_interval_s
        ):
            return
        self._last_purge_at = now
        async with session_scope() as session:
            removed = await purge_events(session, retention_days=settings.trigger_event_retention_days)
        if removed:
            await logger.adebug("Purged %s terminal trigger events", removed)


def start_dispatcher_if_enabled() -> TriggerDispatcher | None:
    """Start the lifespan-owned dispatcher, or return None when it is disabled.

    The API lifespan calls this once per worker. It is a function rather than
    four lines inline so the wiring itself — the setting is read, a dispatcher
    is created, it is started, and the caller gets something it can stop on
    shutdown — is testable; the lifespan body is not.

    Failures are swallowed on purpose: a trigger loop that cannot start must
    never stop the API from booting. The caller sees ``None`` and has nothing to
    stop.
    """
    if not get_settings_service().settings.trigger_dispatcher_enabled:
        return None
    try:
        dispatcher = TriggerDispatcher()
        dispatcher.start()
    except Exception as exc:  # noqa: BLE001 — boot must not depend on the trigger loop
        logger.warning("Trigger dispatcher did not start: %s", type(exc).__name__)
        return None
    return dispatcher
