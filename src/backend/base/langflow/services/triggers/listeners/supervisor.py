"""The supervisor: which connections this replica holds, and what to do when one breaks.

The shape comes from ``decisions/process-model.md``. One reconcile loop compares
the triggers in the database with the connections this process is holding and
moves one step toward agreement. There is no broker and no push: the poll *is*
how a listener learns that a trigger was armed, paused, or deleted.

Three invariants hold the design together.

**One replica per connection.** A ``trigger_listener_lease`` row is claimed
before an adapter starts and renewed on a heartbeat. Losing the lease cancels
the adapter immediately; a replica that cannot renew must assume another one has
already taken over.

**One connection per adapter, not one per trigger.** Several triggers on several
flows may share one Slack workspace connection. Opening a socket per trigger
would blow the provider's connection budget (Slack allows ten per app), so the
supervisor fans the trigger list into one adapter and the adapter emits per
trigger.

**Failure is the supervisor's problem.** An adapter raises; the supervisor backs
off with jitter, keeps the lease so the connection does not thrash between
replicas, surfaces the error on the triggers once it is persistent, and - for
the one failure a retry can never fix, a revoked or expired credential - moves
the triggers to ``needs_reconnect`` and stops. A failure this process could fix
by being configured correctly is not that failure: it backs off like any other.

A fourth rule follows from the first. Leases spread connections armed while
several replicas are running, but a lease is invisible until it is held, so on
its own it never *moves* one. Every pass therefore announces this replica in
``replicas``, counts the live ones, and releases whatever it holds above
``ceil(total / replicas)`` - which is what makes adding a replica to a loaded
deployment do something.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionUnresolvedError,
    ScopeMissingError,
)
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.log.logger import logger
from pydantic import ValidationError
from sqlmodel import col, select, update

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.deps import get_connection_resolver_service, get_settings_service, session_scope
from langflow.services.triggers import ledger
from langflow.services.triggers.constants import FAMILY_TRIGGER_LISTENER
from langflow.services.triggers.listeners import connection_leases, replicas
from langflow.services.triggers.listeners.adapters import (
    ListenerContext,
    ListenerTrigger,
    build_adapter,
    is_listener_kind,
)
from langflow.services.triggers.ownership import UNUSABLE_CONNECTION_STATUSES, owned_by_trigger_owner
from langflow.services.triggers.principal import trigger_execution_principal

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.triggers.listeners.adapters import ListenerAdapter

#: Connection statuses that no amount of retrying fixes. The owner has to
#: re-consent, so the triggers say so and the listener stops dialling.
_UNUSABLE_CONNECTION_STATUSES = UNUSABLE_CONNECTION_STATUSES

#: Adapter failures that mean the same thing.
_NEEDS_RECONNECT_ERRORS = (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionUnresolvedError,
    ScopeMissingError,
)

#: ...except when the failure is this process's own configuration. A listener
#: started with a different ``LANGFLOW_SECRET_KEY`` than the API cannot decrypt
#: a credential, and one started without the API's
#: ``LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS`` cannot refresh a token - in both
#: cases without a single request reaching the provider. The consent is intact,
#: so asking the owner to reconnect is wrong twice over: it blames the user for
#: an operator's misconfiguration, and ``needs_reconnect`` is a state the
#: listener never polls, so correcting the configuration would not bring the
#: trigger back. These back off and retry like any other failure, and recover on
#: their own the moment the process is configured correctly.
_LOCAL_CONFIGURATION_REASONS = frozenset({"credential-undecryptable", "registration-unavailable"})


def is_local_configuration_failure(exc: BaseException) -> bool:
    """True when this process, not the credential, is what is broken."""
    return isinstance(exc, ConnectionUnresolvedError) and exc.reason in _LOCAL_CONFIGURATION_REASONS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_holder_token() -> str:
    """A process-unique holder token for this replica's leases."""
    from langflow.services.triggers.leases import new_owner_token

    return new_owner_token("listener")


def _snapshot(row: Trigger) -> ListenerTrigger:
    config = row.config or {}
    return ListenerTrigger(
        id=row.id,
        flow_id=row.flow_id,
        user_id=row.user_id,
        kind=row.kind,
        provider=row.provider,
        mechanism_id=config.get("mechanism_id"),
        config=dict(config),
        provider_state=dict(row.provider_state or {}),
    )


async def load_desired_state(session: AsyncSession) -> dict[UUID, list[ListenerTrigger]]:
    """Every armed Track B trigger, grouped by the connection it holds.

    Only ``active`` triggers are listened to. ``paused`` is the owner's off
    switch, ``needs_reconnect`` is waiting on a human, and ``error`` and
    ``dead`` have already stopped; none of them should hold a socket open.
    """
    statement = (
        select(Trigger)
        # Only through a connection the trigger's owner owns: a row that names a
        # colleague's or an instance connection is never dialled, however it was
        # written (``ownership.py``).
        .join(Connection, col(Connection.id) == col(Trigger.connection_id))
        .where(
            Trigger.state == TriggerState.ACTIVE.value,
            owned_by_trigger_owner(),
        )
        # Ordered so the *first* trigger on a connection is the same row on
        # every pass: it is the one ``build_adapter`` is given, so an unordered
        # query would let a reconcile silently rebuild an adapter from a
        # different trigger's configuration.
        .order_by(col(Trigger.id))
    )
    desired: dict[UUID, list[ListenerTrigger]] = {}
    for row in (await session.exec(statement)).all():
        snapshot = _snapshot(row)
        if not is_listener_kind(snapshot):
            # A schedule or a TRG-4 push trigger. Not ours.
            continue
        assert row.connection_id is not None  # noqa: S101 - narrowed by the query
        desired.setdefault(row.connection_id, []).append(snapshot)
    return desired


async def unusable_connection_ids(session: AsyncSession, connection_ids: list[UUID]) -> set[UUID]:
    """Connections whose credential the owner has to re-grant."""
    if not connection_ids:
        return set()
    statement = select(Connection).where(col(Connection.id).in_(connection_ids))
    rows = (await session.exec(statement)).all()
    found = {row.id for row in rows}
    unusable = {row.id for row in rows if row.status in _UNUSABLE_CONNECTION_STATUSES}
    # A connection row that vanished is unusable too: ``ON DELETE SET NULL``
    # clears the trigger's reference, but until reconciliation notices, the
    # listener would otherwise dial a connection that no longer exists.
    return unusable | (set(connection_ids) - found)


async def mark_needs_reconnect(session: AsyncSession, *, trigger_ids: list[UUID], reason: str) -> None:
    """Move triggers to ``needs_reconnect`` and stop listening for them."""
    if not trigger_ids:
        return
    for row in (await session.exec(select(Trigger).where(col(Trigger.id).in_(trigger_ids)))).all():
        if row.state == TriggerState.NEEDS_RECONNECT.value:
            continue
        row.state = TriggerState.NEEDS_RECONNECT.value
        row.last_error = reason
        row.updated_at = _now()
        session.add(row)
    await session.flush()


async def record_listener_error(session: AsyncSession, *, trigger_ids: list[UUID], message: str) -> None:
    """Surface a persistent connection failure on the triggers it affects.

    The state is deliberately left alone. A flapping provider is not an owner
    configuration error, and moving the trigger out of ``active`` would stop the
    listener retrying - which is the opposite of what a transient outage needs.
    """
    if not trigger_ids:
        return
    for row in (await session.exec(select(Trigger).where(col(Trigger.id).in_(trigger_ids)))).all():
        row.last_error = message
        row.updated_at = _now()
        session.add(row)
    await session.flush()


async def clear_listener_error(session: AsyncSession, *, trigger_ids: list[UUID]) -> None:
    """Clear an error a later success disproved."""
    if not trigger_ids:
        return
    statement = select(Trigger).where(col(Trigger.id).in_(trigger_ids), col(Trigger.last_error).is_not(None))
    for row in (await session.exec(statement)).all():
        row.last_error = None
        row.updated_at = _now()
        session.add(row)
    await session.flush()


def _adapter_spec(trigger: ListenerTrigger) -> tuple[str, str | None, str]:
    """What ``build_adapter`` reads off a trigger, as a comparable value.

    An adapter is constructed once from the connection's first trigger, so a
    later edit to that trigger - a new mechanism, a new poll interval - cannot
    reach a socket that is already open. Comparing this spec is how the
    supervisor notices and rebuilds instead of running yesterday's config
    forever.
    """
    return (trigger.kind, trigger.mechanism_id, json.dumps(trigger.config or {}, sort_keys=True, default=str))


@dataclass
class ConnectionWorker:
    """One held connection: its adapter, its task, and its failure history."""

    connection_id: UUID
    triggers: list[ListenerTrigger]
    adapter: ListenerAdapter
    stopping: asyncio.Event
    adapter_spec: tuple[str, str | None, str] | None = None
    #: ``trigger_listener_lease.acquired_at`` for the period of ownership this
    #: adapter is running under. Fences writes that outlive a handover.
    lease_generation: datetime | None = None
    task: asyncio.Task | None = None
    consecutive_failures: int = 0
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    last_renewed_at: datetime = field(default_factory=_now)
    succeeded_since_failure: bool = False

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def resting(self, *, now: datetime | None = None) -> bool:
        """True while the worker is inside its backoff window."""
        return self.next_attempt_at is not None and self.next_attempt_at > (now or _now())

    def healthy(self) -> bool:
        return self.running and self.adapter.healthy()


class ListenerSupervisor:
    """Reconciles held connections against the trigger table, forever."""

    def __init__(self, *, holder: str | None = None) -> None:
        self.holder = holder or new_holder_token()
        self.workers: dict[UUID, ConnectionWorker] = {}
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self.last_reconcile_at: datetime | None = None
        self.last_reconcile_error: str | None = None
        self.last_renew_failure_at: datetime | None = None
        self.started_at = _now()
        #: Replicas announcing themselves on the last pass, including this one.
        #: One until the first reconcile proves otherwise, so a supervisor that
        #: has not reconciled yet never behaves as if it were sharing.
        self.live_replicas = 1
        #: This replica's share of the armed connections on the last pass.
        self.fair_share = 0
        #: Connections handed back to the fleet, and the moment this replica may
        #: claim one again. Without the pause, the replica that just released a
        #: connection would race its peers for it on the very next pass - and
        #: being the one already connected to that database, usually win.
        self._handed_back: dict[UUID, datetime] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop every adapter and hand back every lease.

        Leases are released rather than left to expire so a rolling restart
        moves connections in seconds instead of a TTL, and so a Desktop user
        closing the app leaves nothing behind that looks alive.
        """
        self._stopping.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        for worker in list(self.workers.values()):
            await self._stop_worker(worker)
        self.workers.clear()
        with contextlib.suppress(Exception):
            async with session_scope() as session:
                await connection_leases.release_all(session, holder=self.holder)
                await replicas.withdraw(session, holder=self.holder)

    async def _loop(self) -> None:
        settings = get_settings_service().settings
        while not self._stopping.is_set():
            try:
                await self.reconcile()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - one bad pass must not end the process
                # The class name alone is what ``/healthz`` publishes, because
                # that port is unauthenticated by design and an exception
                # message can carry a DSN or a query. The full exception and its
                # traceback go to the log, which is where an operator debugging
                # a red readiness probe can actually read them.
                self.last_reconcile_error = type(exc).__name__
                await logger.aexception("Listener reconcile failed: %s", exc)
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=settings.listener_reconcile_interval_s)

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    async def reconcile(self) -> None:
        """One pass toward agreement between the table and the held set."""
        settings = get_settings_service().settings
        async with session_scope() as session:
            desired = await load_desired_state(session)
            unusable = await unusable_connection_ids(session, list(desired))
            for connection_id in unusable:
                await mark_needs_reconnect(
                    session,
                    trigger_ids=[trigger.id for trigger in desired[connection_id]],
                    reason="The connection was revoked or expired. Reconnect it to resume this trigger.",
                )
                desired.pop(connection_id, None)
            # Announced before it is counted, so this replica is always in its
            # own total: a pass that failed to announce would otherwise read
            # zero peers and conclude it is sharing with nobody.
            await replicas.announce(session, holder=self.holder, ttl_s=settings.listener_lease_ttl_s)
            self.live_replicas = await replicas.live_replicas(
                session, reap_after_s=max(settings.listener_lease_ttl_s * 10, 300.0)
            )

        # Connections we hold but no longer want.
        for connection_id in [cid for cid in self.workers if cid not in desired]:
            await self._drop(connection_id)

        self.fair_share = replicas.fair_share(total=len(desired), replicas=self.live_replicas)
        await self._hand_back_excess()

        for connection_id, triggers in desired.items():
            # The cap applies to new claims only. Holding at the share and
            # renewing is the steady state; refusing to renew there would drop a
            # connection this replica is the rightful holder of.
            if connection_id not in self.workers and len(self.workers) >= self.fair_share:
                continue
            await self._ensure(connection_id, triggers, ttl_s=settings.listener_lease_ttl_s)

        self.last_reconcile_at = _now()
        self.last_reconcile_error = None

    async def _hand_back_excess(self) -> None:
        """Release whatever this replica holds above its fair share.

        The newest holdings go first, because a handover costs a reconnect and
        a bounded overlap: an adapter that has held a socket for hours is the
        one worth disturbing last. The connection id breaks ties so a pass is
        deterministic rather than dependent on dictionary order.

        Nothing is *assigned* to a peer. A released lease is simply free, and
        the peers take it through the same race that spreads a connection armed
        while several replicas were already running.
        """
        now = _now()
        self._handed_back = {cid: until for cid, until in self._handed_back.items() if until > now}
        excess = len(self.workers) - self.fair_share
        if excess <= 0:
            return
        ordered = sorted(
            self.workers.values(),
            key=lambda worker: (worker.lease_generation or self.started_at, str(worker.connection_id)),
            reverse=True,
        )
        pause = max(get_settings_service().settings.listener_reconcile_interval_s * 2, 1.0)
        for worker in ordered[:excess]:
            await logger.ainfo(
                "Listener handing connection %s back to the fleet: holding %s of a %s share across %s replicas",
                worker.connection_id,
                len(self.workers),
                self.fair_share,
                self.live_replicas,
            )
            self._handed_back[worker.connection_id] = now + timedelta(seconds=pause)
            await self._drop(worker.connection_id)

    async def _ensure(self, connection_id: UUID, triggers: list[ListenerTrigger], *, ttl_s: float) -> None:
        worker = self.workers.get(connection_id)
        settings = get_settings_service().settings

        if worker is None:
            resume_at = self._handed_back.get(connection_id)
            if resume_at is not None and resume_at > _now():
                # Handed back on a recent pass. Let a peer have it.
                return
            async with session_scope() as session:
                generation = await connection_leases.claim_generation(
                    session, connection_id=connection_id, holder=self.holder, ttl_s=ttl_s
                )
            if generation is None:
                return
            adapter = build_adapter(triggers[0])
            if adapter is None:  # pragma: no cover - filtered by is_listener_kind
                async with session_scope() as session:
                    await connection_leases.release(session, connection_id=connection_id, holder=self.holder)
                return
            worker = ConnectionWorker(
                connection_id=connection_id,
                triggers=list(triggers),
                adapter=adapter,
                stopping=asyncio.Event(),
                adapter_spec=_adapter_spec(triggers[0]),
                lease_generation=generation,
            )
            self.workers[connection_id] = worker
            self._spawn(worker)
            return

        # Renew before anything else: an adapter running without a lease is the
        # one state this design must not have.
        if (_now() - worker.last_renewed_at).total_seconds() >= settings.listener_heartbeat_interval_s:
            async with session_scope() as session:
                generation = await connection_leases.claim_generation(
                    session, connection_id=connection_id, holder=self.holder, ttl_s=ttl_s
                )
            if generation is None:
                self.last_renew_failure_at = _now()
                await logger.awarning("Listener lost the lease on connection %s; stopping its adapter", connection_id)
                await self._drop(connection_id, release_lease=False)
                return
            # A renewal keeps the generation; re-taking a lapsed lease starts a
            # new one, and the fence has to follow it or every later cursor
            # write would be discarded.
            worker.lease_generation = generation
            worker.last_renewed_at = _now()

        # In place, not a rebind: ``_context`` handed this exact list object to
        # the running adapter, and an adapter that has held a socket for hours
        # would otherwise iterate the snapshot it was born with - never seeing a
        # newly armed trigger, and still emitting for one the owner paused.
        worker.triggers[:] = triggers

        spec = _adapter_spec(triggers[0])
        if spec != worker.adapter_spec:
            await self._rebuild_adapter(worker, spec)
            return

        if not worker.running and not worker.resting():
            self._spawn(worker)

    async def _rebuild_adapter(self, worker: ConnectionWorker, spec: tuple[str, str | None, str]) -> None:
        """Swap in an adapter built from the edited configuration, keeping the lease.

        Dropping the connection instead would hand it to another replica for a
        configuration change the owner made in this one.
        """
        await logger.ainfo(
            "Listener rebuilding the adapter on connection %s after a configuration change", worker.connection_id
        )
        await self._stop_worker(worker)
        adapter = build_adapter(worker.triggers[0])
        if adapter is None:  # pragma: no cover - filtered by is_listener_kind
            await self._drop(worker.connection_id)
            return
        worker.adapter = adapter
        worker.adapter_spec = spec
        worker.consecutive_failures = 0
        worker.next_attempt_at = None
        self._spawn(worker)

    async def _drop(self, connection_id: UUID, *, release_lease: bool = True) -> None:
        worker = self.workers.pop(connection_id, None)
        if worker is None:
            return
        await self._stop_worker(worker)
        if release_lease:
            with contextlib.suppress(Exception):
                async with session_scope() as session:
                    await connection_leases.release(session, connection_id=connection_id, holder=self.holder)

    async def _stop_worker(self, worker: ConnectionWorker) -> None:
        worker.stopping.set()
        task, worker.task = worker.task, None
        # ``_needs_reconnect`` runs *inside* ``worker.task``, so this is reached
        # with ``task is asyncio.current_task()``. Cancelling there schedules a
        # CancelledError into this very coroutine, which would then fire at the
        # next await - cutting the adapter shutdown and the lease release below
        # in half. The stopping event is already set, which is what actually
        # ends the adapter; the task is returning anyway.
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        with contextlib.suppress(Exception):
            await worker.adapter.stop()

    # ------------------------------------------------------------------ #
    # One connection's task
    # ------------------------------------------------------------------ #

    def _spawn(self, worker: ConnectionWorker) -> None:
        worker.stopping = asyncio.Event()
        worker.next_attempt_at = None
        worker.task = asyncio.create_task(self._run_worker(worker))

    async def _run_worker(self, worker: ConnectionWorker) -> None:
        ctx = self._context(worker)
        try:
            await worker.adapter.start(ctx)
        except asyncio.CancelledError:
            raise
        except _NEEDS_RECONNECT_ERRORS as exc:
            if is_local_configuration_failure(exc):
                await self._failed(worker, exc)
            else:
                await self._needs_reconnect(worker, exc)
        except Exception as exc:  # noqa: BLE001 - every adapter failure is a backoff, not a crash
            await self._failed(worker, exc)

    def _context(self, worker: ConnectionWorker) -> ListenerContext:
        async def emit(*, trigger_id: UUID, dedupe_key: str, payload: dict[str, Any]) -> bool:
            """Commit one ledger row. Returns True when it was new.

            The write happens in its own transaction and is committed before the
            caller regains control, so an adapter that acknowledges a provider
            immediately afterwards is acknowledging something durable. That is
            the whole of the listener's delivery responsibility: it never runs a
            flow, and the dispatcher picks the row up from the ledger.
            """
            async with session_scope() as session:
                _row, created = await ledger.append_event(
                    session, trigger_id=trigger_id, dedupe_key=dedupe_key, payload=payload
                )
            # A completed round trip is the proof the connection works; what
            # the ledger did with the row is a dedupe outcome, not a health
            # signal. Requiring ``created`` would leave the error banner up
            # through an entire replay window after an outage - hours, on a
            # quiet source - even though the adapter is demonstrably back.
            if not worker.succeeded_since_failure:
                await self._succeeded(worker)
            return created

        async def save_cursor(*, trigger_id: UUID, provider_state: dict[str, Any]) -> None:
            """Persist a provider cursor (``deltaLink``, ``historyId``, ...).

            Written to ``trigger.provider_state``, never to ``config``, so a
            canvas save cannot clobber a cursor and replay the world.

            Fenced on the lease generation this adapter started under, in the
            same statement as the write. Lease expiry says the previous holder
            stopped heartbeating, not that it stopped running: without the
            fence, an adapter that was slow to notice a handover could land an
            older cursor on top of its successor's and replay or skip a window
            of provider events. With it, the stale write matches no rows.
            """
            async with session_scope() as session:
                result = await session.exec(  # type: ignore[call-overload]
                    update(Trigger)
                    .where(
                        col(Trigger.id) == trigger_id,
                        connection_leases.held_clause(
                            connection_id=worker.connection_id,
                            holder=self.holder,
                            generation=worker.lease_generation,
                        ),
                    )
                    .values(provider_state=dict(provider_state), updated_at=_now())
                )
                if result.rowcount:
                    return
                if await session.get(Trigger, trigger_id) is None:
                    # The owner deleted the trigger mid-poll. Routine, not a fence.
                    return
            await logger.awarning(
                "Listener discarded a stale cursor for trigger %s: the lease on connection %s moved on",
                trigger_id,
                worker.connection_id,
            )

        async def resolve_credential(trigger_id: UUID | None = None) -> Any:
            """Resolve this connection through the registered resolver.

            In this process, not over HTTP: the whole reason the listener is a
            separate process rather than a second API replica is that it holds
            connections itself (``decisions/process-model.md``, and the 1.13
            boundary obligation on INT-2). Refresh goes through the same
            cross-process coordinator the API uses, so two processes refreshing
            one token still mint one.
            """
            target = next((t for t in worker.triggers if trigger_id is None or t.id == trigger_id), None)
            if target is None:
                # A trigger id that is not armed on this connection (or none at
                # all). Typed, so the supervisor classifies it rather than
                # treating a programming slip as a transient failure.
                handle = f"connection:{worker.connection_id}"
                raise ConnectionUnresolvedError(handle)
            async with session_scope() as session:
                row = await session.get(Connection, worker.connection_id)
                trigger_row = await session.get(Trigger, target.id)
            if row is None or trigger_row is None:
                handle = f"connection:{worker.connection_id}"
                raise ConnectionUnresolvedError(handle)
            try:
                request = ConnectionResolutionRequest(
                    ref=ConnectionRef(provider=row.provider_key, name=row.name),
                    principal=trigger_execution_principal(trigger_row, family=FAMILY_TRIGGER_LISTENER),
                    required_scopes=frozenset(),
                )
            except ValidationError as exc:
                # A row whose handle does not parse cannot be resolved. Raise the
                # typed error so the supervisor classifies it as "needs
                # reconnect" instead of retrying a row that can never work -
                # the same treatment ``principal.connection_preflight`` gives it
                # on the dispatch side.
                handle = f"{row.provider_key}/{row.name}"
                raise ConnectionUnresolvedError(handle, provider=row.provider_key) from exc
            return await get_connection_resolver_service().resolve(request)

        return ListenerContext(
            connection_id=worker.connection_id,
            triggers=worker.triggers,
            emit=emit,
            save_cursor=save_cursor,
            resolve_credential=resolve_credential,
            stopping=worker.stopping,
        )

    # ------------------------------------------------------------------ #
    # Failure accounting
    # ------------------------------------------------------------------ #

    async def _succeeded(self, worker: ConnectionWorker) -> None:
        """A delivery landed: forget the failure history and the error banner."""
        had_failures = worker.consecutive_failures >= get_settings_service().settings.listener_failure_threshold
        worker.consecutive_failures = 0
        worker.next_attempt_at = None
        worker.last_error = None
        worker.succeeded_since_failure = True
        if had_failures:
            with contextlib.suppress(Exception):
                async with session_scope() as session:
                    await clear_listener_error(session, trigger_ids=[t.id for t in worker.triggers])

    async def _failed(self, worker: ConnectionWorker, exc: Exception) -> None:
        settings = get_settings_service().settings
        local_configuration = is_local_configuration_failure(exc)
        worker.consecutive_failures += 1
        worker.succeeded_since_failure = False
        # The typed reason is this project's own vocabulary, so it is as safe to
        # show an owner as the class name and says far more: "the listener is
        # configured wrong" rather than "something was unresolved".
        worker.last_error = str(exc.reason) if local_configuration else type(exc).__name__  # type: ignore[attr-defined]
        delay = min(
            settings.listener_backoff_base_s * (2 ** (worker.consecutive_failures - 1)),
            settings.listener_backoff_cap_s,
        )
        delay *= random.uniform(0.85, 1.15)  # noqa: S311 - jitter, not crypto
        worker.next_attempt_at = _now() + timedelta(seconds=delay)
        # A flapping provider is a warning, not an error - backing off and
        # retrying is the designed response, and a traceback per hiccup would
        # bury the reconcile-loop failures that really do need one.
        # ``worker.last_error`` stays the class name because it reaches the
        # owner's trigger banner, where a provider library's raw message is
        # noise at best; the message goes to the log, where it is useful.
        await logger.awarning(
            "Listener connection %s failed (%s consecutive); retrying in %.1fs: %s: %s",
            worker.connection_id,
            worker.consecutive_failures,
            delay,
            type(exc).__name__,
            exc,
        )
        if worker.consecutive_failures >= settings.listener_failure_threshold:
            # Persistent enough that the owner should see it on the trigger,
            # not only in a log the owner cannot read.
            message = (
                # Named precisely, because this one is fixed by an operator
                # editing the listener's environment and by nothing the owner
                # of the trigger can do.
                "The listener cannot read this connection with its own configuration "
                f"({worker.last_error}). It must run with the same LANGFLOW_SECRET_KEY and "
                "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS as the Langflow API. The trigger stays armed and "
                "resumes on its own once it does."
                if local_configuration
                else (
                    f"The listener could not hold this connection after {worker.consecutive_failures} "
                    f"attempts ({worker.last_error}). Retrying."
                )
            )
            with contextlib.suppress(Exception):
                async with session_scope() as session:
                    await record_listener_error(session, trigger_ids=[t.id for t in worker.triggers], message=message)

    async def _needs_reconnect(self, worker: ConnectionWorker, exc: Exception) -> None:
        """Stop retrying: only a human re-granting consent fixes this."""
        await logger.awarning(
            "Listener connection %s needs reconnect (%s): %s", worker.connection_id, type(exc).__name__, exc
        )
        with contextlib.suppress(Exception):
            async with session_scope() as session:
                await mark_needs_reconnect(
                    session,
                    trigger_ids=[t.id for t in worker.triggers],
                    reason="The connection is no longer authorized. Reconnect it to resume this trigger.",
                )
        await self._drop(worker.connection_id)

    # ------------------------------------------------------------------ #
    # Health
    # ------------------------------------------------------------------ #

    def snapshot(self) -> dict[str, Any]:
        """What ``/healthz`` reports. Cheap: no database access."""
        return {
            "holder": self.holder,
            "running": self.running,
            "connections": len(self.workers),
            "healthy_connections": sum(1 for worker in self.workers.values() if worker.healthy()),
            "resting_connections": sum(1 for worker in self.workers.values() if worker.resting()),
            # What an operator needs to answer "did adding a replica help?"
            # without a database session: how many replicas this one can see,
            # and how many connections that entitles it to.
            "replicas": self.live_replicas,
            "fair_share": self.fair_share,
            "last_reconcile_at": self.last_reconcile_at.isoformat() if self.last_reconcile_at else None,
            "last_reconcile_error": self.last_reconcile_error,
            "last_renew_failure_at": (self.last_renew_failure_at.isoformat() if self.last_renew_failure_at else None),
            "started_at": self.started_at.isoformat(),
        }
