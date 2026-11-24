"""Tests for the batched audit pipeline (``audit_decision`` + writer)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.auth.context import (
    AUTH_METHOD_API_KEY,
    AUTH_METHOD_JWT,
    AuthCredentialContext,
    clear_current_auth_context,
    set_current_auth_context,
)
from langflow.services.authorization import audit as authz_audit
from lfx.services.authorization import base as authz_base
from lfx.services.settings.auth import AuthSettings

from ._common import (
    install_audit_recorder,
    install_settings,
)


@pytest.fixture
def patched_audit_flush(monkeypatch):
    """Replace ``_flush_audit_batch`` with a recorder so we exercise the writer without touching the DB."""
    flushed: list[list[object]] = []

    async def _record(batch):
        flushed.append(list(batch))

    monkeypatch.setattr(authz_audit, "_flush_audit_batch", _record)
    return flushed


@pytest.fixture(autouse=True)
def reset_auth_context():
    """Prevent request-local credential metadata from leaking between tests."""
    clear_current_auth_context()
    yield
    clear_current_auth_context()


async def _reset_audit_pipeline() -> None:
    """Best-effort teardown so each test starts with a clean audit pipeline."""
    await authz_audit.drain_pending_audit_writes(timeout=0.5)
    authz_audit._audit_queue = None
    authz_audit._audit_queue_loop = None
    authz_audit._audit_writer_task = None
    authz_audit._audit_inflight = ()
    authz_audit._audit_accepting = True
    authz_audit._audit_capacity_waiters.clear()
    authz_audit._audit_dropped_count = 0
    authz_audit._audit_last_drop_warn = 0.0
    authz_audit._audit_submitted_count = 0
    authz_audit._audit_persisted_count = 0
    authz_audit._audit_failed_count = 0
    authz_audit._audit_last_failure_code = None
    authz_audit._pending_audit_tasks.clear()


def test_durable_audit_mode_is_explicitly_disabled_by_default(tmp_path) -> None:
    assert AuthSettings(CONFIG_DIR=str(tmp_path)).AUTHZ_AUDIT_DURABLE is False


@pytest.mark.anyio
async def test_durable_audit_call_returns_only_after_its_batch_is_persisted(monkeypatch):
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )
    flush_started = asyncio.Event()
    release_flush = asyncio.Event()
    flushed: list[object] = []

    async def controlled_flush(batch):
        flush_started.set()
        await release_flush.wait()
        flushed.extend(batch)

    monkeypatch.setattr(authz_audit, "_flush_audit_batch", controlled_flush)
    call = asyncio.create_task(
        authz_audit.audit_decision(
            user_id=uuid4(),
            action="flow:read",
            obj="flow:*",
            result="allow",
        )
    )
    await asyncio.wait_for(flush_started.wait(), timeout=1.0)
    try:
        assert not call.done(), "durable audit returned before its database batch completed"
    finally:
        release_flush.set()
        await call

    health = authz_audit.get_audit_producer_health()
    assert len(flushed) == 1
    assert health == {
        "enabled": True,
        "durable": True,
        "active": True,
        "healthy": True,
        "queue_depth": 0,
        "queue_capacity": authz_audit._AUDIT_QUEUE_MAX,
        "submitted_count": 1,
        "persisted_count": 1,
        "failed_count": 0,
        "dropped_count": 0,
        "last_failure_code": None,
    }


@pytest.mark.anyio
async def test_durable_audit_backpressures_at_capacity_instead_of_dropping(monkeypatch):
    monkeypatch.setattr(authz_audit, "_AUDIT_QUEUE_MAX", 1)
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )
    flush_started = asyncio.Event()
    release_flush = asyncio.Event()
    persisted: list[object] = []

    async def blocked_first_flush(batch):
        flush_started.set()
        await release_flush.wait()
        persisted.extend(batch)

    monkeypatch.setattr(authz_audit, "_flush_audit_batch", blocked_first_flush)

    def submit(index: int) -> asyncio.Task[None]:
        return asyncio.create_task(
            authz_audit.audit_decision(
                user_id=uuid4(),
                action=f"flow:read:{index}",
                obj="flow:*",
                result="allow",
            )
        )

    first = submit(1)
    await asyncio.wait_for(flush_started.wait(), timeout=1.0)
    second = submit(2)
    await asyncio.sleep(0)
    third = submit(3)
    await asyncio.sleep(0)
    try:
        assert not third.done(), "a full durable queue must backpressure the caller"
        assert authz_audit.get_audit_producer_health()["dropped_count"] == 0
    finally:
        release_flush.set()
        await asyncio.gather(first, second, third)

    health = authz_audit.get_audit_producer_health()
    assert len(persisted) == 3
    assert health["submitted_count"] == 3
    assert health["persisted_count"] == 3
    assert health["dropped_count"] == 0


@pytest.mark.anyio
async def test_durable_audit_failure_is_sanitized_and_propagated_to_the_caller(monkeypatch):
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )

    sensitive_error = "postgres://user:secret@db/audit"  # pragma: allowlist secret

    async def failed_flush(_batch):
        raise RuntimeError(sensitive_error)

    monkeypatch.setattr(authz_audit, "_flush_audit_batch", failed_flush)
    with pytest.raises(authz_audit.AuditPersistenceError, match="Durable authorization audit persistence failed"):
        await authz_audit.audit_decision(
            user_id=uuid4(),
            action="flow:read",
            obj="flow:*",
            result="allow",
        )

    health = authz_audit.get_audit_producer_health()
    assert health["healthy"] is False
    assert health["submitted_count"] == 1
    assert health["persisted_count"] == 0
    assert health["failed_count"] == 1
    assert health["last_failure_code"] == "RuntimeError"
    assert "secret" not in str(health)


@pytest.mark.anyio
async def test_durable_caller_timeout_does_not_cancel_an_accepted_persistence(monkeypatch):
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )
    flush_started = asyncio.Event()
    release_flush = asyncio.Event()

    async def delayed_flush(_batch):
        flush_started.set()
        await release_flush.wait()

    monkeypatch.setattr(authz_audit, "_flush_audit_batch", delayed_flush)
    call = asyncio.create_task(
        asyncio.wait_for(
            authz_audit.audit_decision(
                user_id=uuid4(),
                action="flow:read",
                obj="flow:*",
                result="allow",
            ),
            timeout=0.01,
        )
    )
    await asyncio.wait_for(flush_started.wait(), timeout=1.0)
    with pytest.raises(asyncio.TimeoutError):
        await call

    release_flush.set()
    assert authz_audit._audit_queue is not None
    await asyncio.wait_for(authz_audit._audit_queue.join(), timeout=1.0)
    health = authz_audit.get_audit_producer_health()
    assert health["submitted_count"] == 1
    assert health["persisted_count"] == 1
    assert health["failed_count"] == 0
    assert health["dropped_count"] == 0


@pytest.mark.anyio
async def test_durable_shutdown_gives_inflight_and_queued_entries_terminal_failures(monkeypatch):
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )
    flush_started = asyncio.Event()

    async def never_finishes(_batch):
        flush_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(authz_audit, "_flush_audit_batch", never_finishes)

    def submit(index: int) -> asyncio.Task[None]:
        return asyncio.create_task(
            authz_audit.audit_decision(
                user_id=uuid4(),
                action=f"flow:read:{index}",
                obj="flow:*",
                result="allow",
            )
        )

    inflight = submit(1)
    await asyncio.wait_for(flush_started.wait(), timeout=1.0)
    queued = submit(2)
    await asyncio.sleep(0)
    await authz_audit.drain_pending_audit_writes(timeout=0.2)
    results = await asyncio.wait_for(
        asyncio.gather(inflight, queued, return_exceptions=True),
        timeout=1.0,
    )

    assert all(isinstance(result, authz_audit.AuditPersistenceError) for result in results)
    health = authz_audit.get_audit_producer_health()
    assert health["queue_depth"] == 0
    assert health["submitted_count"] == 2
    assert health["persisted_count"] == 0
    assert health["failed_count"] == 2
    assert health["last_failure_code"] == "writer_stopped"


@pytest.mark.anyio
async def test_durable_shutdown_rejects_a_producer_blocked_on_full_capacity(monkeypatch):
    """Closing admission must wake a producer that has not reached the queue yet."""
    monkeypatch.setattr(authz_audit, "_AUDIT_QUEUE_MAX", 1)
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )
    flush_started = asyncio.Event()

    async def never_finishes(_batch):
        flush_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(authz_audit, "_flush_audit_batch", never_finishes)

    def submit(index: int) -> asyncio.Task[None]:
        return asyncio.create_task(
            authz_audit.audit_decision(
                user_id=uuid4(),
                action=f"flow:read:{index}",
                obj="flow:*",
                result="allow",
            )
        )

    inflight = submit(1)
    await asyncio.wait_for(flush_started.wait(), timeout=1.0)
    queued = submit(2)
    await asyncio.sleep(0)
    blocked = submit(3)
    await asyncio.sleep(0)
    assert authz_audit.get_audit_producer_health()["queue_depth"] == 1
    assert not blocked.done()

    await authz_audit.drain_pending_audit_writes(timeout=0.2)
    results = await asyncio.wait_for(
        asyncio.gather(inflight, queued, blocked, return_exceptions=True),
        timeout=1.0,
    )

    assert all(isinstance(result, authz_audit.AuditPersistenceError) for result in results)
    assert authz_audit._audit_writer_task is None
    assert authz_audit.get_audit_producer_health()["queue_depth"] == 0


@pytest.mark.anyio
async def test_durable_post_drain_rejection_does_not_restart_writer(monkeypatch, patched_audit_flush):
    """A stopped same-loop durable pipeline stays stopped until a new loop owns it."""
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )

    await authz_audit.audit_decision(
        user_id=uuid4(),
        action="flow:read",
        obj="flow:*",
        result="allow",
    )
    await authz_audit.drain_pending_audit_writes(timeout=1.0)
    assert len(patched_audit_flush) == 1
    assert authz_audit._audit_writer_task is None

    with pytest.raises(authz_audit.AuditPersistenceError):
        await authz_audit.audit_decision(
            user_id=uuid4(),
            action="flow:read",
            obj="flow:*",
            result="allow",
        )

    assert authz_audit._audit_writer_task is None
    assert authz_audit.get_audit_producer_health()["active"] is False


@pytest.mark.anyio
async def test_cancelled_capacity_waiter_is_never_admitted(monkeypatch):
    """Cancellation before queue admission remains a normal caller cancellation."""
    monkeypatch.setattr(authz_audit, "_AUDIT_QUEUE_MAX", 1)
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )
    flush_started = asyncio.Event()
    release_flush = asyncio.Event()

    async def delayed_flush(_batch):
        flush_started.set()
        await release_flush.wait()

    monkeypatch.setattr(authz_audit, "_flush_audit_batch", delayed_flush)

    def submit(index: int) -> asyncio.Task[None]:
        return asyncio.create_task(
            authz_audit.audit_decision(
                user_id=uuid4(),
                action=f"flow:read:{index}",
                obj="flow:*",
                result="allow",
            )
        )

    inflight = submit(1)
    await asyncio.wait_for(flush_started.wait(), timeout=1.0)
    queued = submit(2)
    await asyncio.sleep(0)
    blocked = submit(3)
    await asyncio.sleep(0)
    blocked.cancel()
    with pytest.raises(asyncio.CancelledError):
        await blocked

    release_flush.set()
    await asyncio.gather(inflight, queued)
    await authz_audit.drain_pending_audit_writes(timeout=1.0)
    health = authz_audit.get_audit_producer_health()
    assert health["submitted_count"] == 2
    assert health["persisted_count"] == 2
    assert health["queue_depth"] == 0


@pytest.mark.anyio
async def test_audit_decision_runs_when_authz_disabled_but_audit_on(monkeypatch, patched_audit_flush):
    """Audit is independent of enforcement.

    Previously ``audit_decision`` short-circuited when ``AUTHZ_ENABLED=False``,
    which meant share CRUD writes left no audit trail on default installs. The
    new contract gates only on ``AUTHZ_AUDIT_ENABLED`` so operators can
    observe traffic before flipping enforcement on.
    """
    await _reset_audit_pipeline()
    install_settings(monkeypatch, authz_enabled=False, audit_enabled=True)

    await authz_audit.audit_decision(user_id=uuid4(), action="flow:read", obj="flow:x", result="allow")
    await authz_audit.drain_pending_audit_writes(timeout=1.0)

    assert sum(len(b) for b in patched_audit_flush) == 1


@pytest.mark.anyio
async def test_audit_decision_noop_when_audit_disabled(monkeypatch, patched_audit_flush):
    """AUTHZ_AUDIT_ENABLED=False suppresses audit writes."""
    await _reset_audit_pipeline()
    install_settings(monkeypatch, authz_enabled=True, audit_enabled=False)

    await authz_audit.audit_decision(user_id=uuid4(), action="flow:read", obj="flow:x", result="allow")
    await authz_audit.drain_pending_audit_writes(timeout=0.5)

    assert patched_audit_flush == []


@pytest.mark.anyio
async def test_audit_decision_enqueues_when_enabled(monkeypatch, patched_audit_flush):
    """When both flags are on, ``audit_decision`` enqueues an entry the background writer flushes."""
    await _reset_audit_pipeline()
    install_settings(monkeypatch, authz_enabled=True, audit_enabled=True)

    user_id = uuid4()
    await authz_audit.audit_decision(user_id=user_id, action="flow:read", obj="flow:abc", result="allow")
    # Drain forces the writer to flush before we inspect.
    await authz_audit.drain_pending_audit_writes(timeout=1.0)

    assert len(patched_audit_flush) == 1
    batch = patched_audit_flush[0]
    assert len(batch) == 1
    entry = batch[0]
    assert entry.user_id == user_id
    assert entry.action == "flow:read"
    assert entry.obj == "flow:abc"
    assert entry.result == "allow"


@pytest.mark.anyio
async def test_api_key_actor_is_captured_centrally_and_preserves_owner(monkeypatch, patched_audit_flush):
    """Audit attribution reads request-local credentials without relying on a guard caller."""
    await _reset_audit_pipeline()
    install_settings(monkeypatch, authz_enabled=True, audit_enabled=True)
    owner_id = uuid4()
    api_key_id = uuid4()
    set_current_auth_context(
        AuthCredentialContext(
            method=AUTH_METHOD_API_KEY,
            api_key_id=api_key_id,
            api_key_source="db",  # pragma: allowlist secret
        )
    )

    await authz_audit.audit_decision(
        user_id=owner_id,
        action="flow:read",
        obj=f"flow:{uuid4()}",
        result="allow",
        details={"domain": "*", "actor_type": "user", "actor_id": str(uuid4())},
    )
    await authz_audit.drain_pending_audit_writes(timeout=1.0)

    entry = patched_audit_flush[0][0]
    assert entry.user_id == owner_id
    assert entry.actor_type == "api_key"
    assert entry.actor_id == api_key_id
    assert entry.details == {
        "domain": "*",
        "auth_method": "api_key",
        "api_key_id": str(api_key_id),
        "api_key_source": "db",  # pragma: allowlist secret
    }


@pytest.mark.anyio
async def test_jwt_and_system_actor_identity_are_derived_per_queued_entry(monkeypatch, patched_audit_flush):
    """Actor fields are captured at enqueue time so a mixed batch cannot inherit later context."""
    await _reset_audit_pipeline()
    install_settings(monkeypatch, authz_enabled=True, audit_enabled=True)
    user_id = uuid4()

    set_current_auth_context(AuthCredentialContext(method=AUTH_METHOD_JWT))
    await authz_audit.audit_decision(
        user_id=user_id,
        action="flow:read",
        obj="flow:*",
        result="allow",
    )
    lingering_api_key_id = uuid4()
    set_current_auth_context(
        AuthCredentialContext(
            method=AUTH_METHOD_API_KEY,
            api_key_id=lingering_api_key_id,
            api_key_source="db",  # pragma: allowlist secret
        )
    )
    await authz_audit.audit_decision(
        user_id=None,
        action="system:sync",
        obj="system:*",
        result="allow",
        details={"job": "policy-sync"},
    )
    await authz_audit.drain_pending_audit_writes(timeout=1.0)

    entries = [entry for batch in patched_audit_flush for entry in batch]
    assert [(entry.actor_type, entry.actor_id) for entry in entries] == [
        ("user", user_id),
        ("unknown", None),
    ]
    assert entries[0].details == {"auth_method": "jwt"}
    assert entries[1].details == {"job": "policy-sync"}


@pytest.mark.anyio
async def test_public_principal_uses_stable_non_user_audit_actor(monkeypatch, patched_audit_flush):
    """Anonymous decisions populate actor columns without inventing a user foreign key."""
    await _reset_audit_pipeline()
    install_settings(monkeypatch, authz_enabled=False, audit_enabled=True)
    principal_type = getattr(authz_base, "AuthorizationPrincipal", None)
    assert principal_type is not None
    principal = principal_type.public_anonymous()

    await authz_audit.audit_decision(
        user_id=None,
        principal=principal,
        action="flow:execute",
        obj=f"flow:{uuid4()}",
        result="allow",
    )
    await authz_audit.drain_pending_audit_writes(timeout=1.0)

    entry = patched_audit_flush[0][0]
    assert entry.user_id is None
    assert entry.actor_type == "anonymous_public"
    assert entry.actor_id == principal.actor_id


@pytest.mark.anyio
async def test_invalid_api_key_actor_uuid_is_safely_dropped(monkeypatch, patched_audit_flush):
    """Malformed request metadata must not crash or poison the background DB batch."""
    await _reset_audit_pipeline()
    install_settings(monkeypatch, authz_enabled=True, audit_enabled=True)
    set_current_auth_context(
        AuthCredentialContext(
            method=AUTH_METHOD_API_KEY,
            api_key_id="not-a-uuid",  # type: ignore[arg-type]
            api_key_source="plugin",  # pragma: allowlist secret
        )
    )

    await authz_audit.audit_decision(user_id=uuid4(), action="flow:read", obj="flow:*", result="deny")
    await authz_audit.drain_pending_audit_writes(timeout=1.0)

    entry = patched_audit_flush[0][0]
    assert entry.actor_type == "api_key"
    assert entry.actor_id is None
    assert entry.details["api_key_id"] == "not-a-uuid"


@pytest.mark.anyio
async def test_flush_batch_maps_actor_fields_to_model(monkeypatch):
    """The batched DB projection must retain actor fields captured at enqueue time."""
    from langflow.services import deps

    rows = []

    class _Session:
        def add(self, row):
            rows.append(row)

    @asynccontextmanager
    async def _scope():
        yield _Session()

    monkeypatch.setattr(deps, "session_scope", _scope)
    actor_id = uuid4()
    user_id = uuid4()
    entry = authz_audit._AuditEntry(
        user_id=user_id,
        actor_type="api_key",
        actor_id=actor_id,
        action="flow:read",
        obj=f"flow:{uuid4()}",
        result="allow",
        details={"api_key_source": "db"},  # pragma: allowlist secret
    )

    await authz_audit._flush_audit_batch([entry])

    assert len(rows) == 1
    assert rows[0].user_id == user_id
    assert rows[0].actor_type == "api_key"
    assert rows[0].actor_id == actor_id
    assert rows[0].details == {"api_key_source": "db"}  # pragma: allowlist secret
    assert rows[0].id == entry.event_id
    assert rows[0].timestamp == entry.occurred_at


@pytest.mark.anyio
async def test_flush_batch_stages_plugin_events_in_same_transaction(monkeypatch):
    """Plugins receive stable event identity on the audit row's open session."""
    from langflow.services import deps

    rows = []
    staged = []

    class _Session:
        def add(self, row):
            rows.append(row)

    class _AuthorizationService:
        def stage_audit_events(self, *, session, events):
            staged.append((session, tuple(events)))

    session = _Session()

    @asynccontextmanager
    async def _scope():
        yield session

    monkeypatch.setattr(deps, "session_scope", _scope)
    monkeypatch.setattr(deps, "get_authorization_service", lambda: _AuthorizationService())
    entry = authz_audit._AuditEntry(
        user_id=uuid4(),
        actor_type="user",
        actor_id=uuid4(),
        action="flow:read",
        obj=f"flow:{uuid4()}",
        result="allow",
        details={"secret": "must-not-cross-plugin-seam"},  # pragma: allowlist secret
    )

    await authz_audit._flush_audit_batch([entry])

    assert len(rows) == 1
    assert len(staged) == 1
    staged_session, events = staged[0]
    assert staged_session is session
    assert len(events) == 1
    assert events[0].event_id == entry.event_id
    assert events[0].occurred_at == entry.occurred_at
    assert not hasattr(events[0], "details")


def test_stage_audit_decision_uses_caller_transaction(monkeypatch):
    """Mutation audit rows and plugin events are staged without a separate commit."""
    from langflow.services import deps

    install_settings(monkeypatch, authz_enabled=True, audit_enabled=True, audit_durable=True)
    rows = []
    staged = []

    class _Session:
        def add(self, row):
            rows.append(row)

    class _AuthorizationService:
        def stage_audit_events(self, *, session, events):
            staged.append((session, tuple(events)))

    session = _Session()
    user_id = uuid4()
    resource_id = uuid4()
    monkeypatch.setattr(deps, "get_authorization_service", lambda: _AuthorizationService())

    staged_in_transaction = authz_audit.stage_audit_decision(
        session=session,
        user_id=user_id,
        action="user:update",
        obj=f"user:{resource_id}",
        result="allow",
        details={"event": authz_audit.AUDIT_EVENT_MUTATION},
    )

    assert len(rows) == 1
    assert rows[0].user_id == user_id
    assert rows[0].resource_type == "user"
    assert rows[0].resource_id == resource_id
    assert rows[0].details == {"event": authz_audit.AUDIT_EVENT_MUTATION}
    assert len(staged) == 1
    assert staged[0][0] is session
    assert staged[0][1][0].event_id == rows[0].id
    assert staged_in_transaction is True


def test_stage_audit_decision_preserves_best_effort_pipeline(monkeypatch):
    """Best-effort mutation audits remain asynchronous after commit."""
    install_settings(monkeypatch, authz_enabled=True, audit_enabled=True, audit_durable=False)

    class _Session:
        def add(self, _row):
            pytest.fail("best-effort audit must not join the mutation transaction")

    staged_in_transaction = authz_audit.stage_audit_decision(
        session=_Session(),
        user_id=uuid4(),
        action="user:update",
        obj=f"user:{uuid4()}",
        result="allow",
        details={"event": authz_audit.AUDIT_EVENT_MUTATION},
    )

    assert staged_in_transaction is False


@pytest.mark.anyio
async def test_audit_decision_batches_multiple_entries(monkeypatch, patched_audit_flush):
    """Multiple concurrent ``audit_decision`` calls coalesce into a single DB batch.

    This is the contract we want — the writer should pull every entry already
    in the queue when it wakes up, so we make N decisions before yielding and
    expect ONE batch of N rows, not N separate ``session_scope`` opens.
    """
    await _reset_audit_pipeline()
    install_settings(monkeypatch, authz_enabled=True, audit_enabled=True)

    for _ in range(5):
        await authz_audit.audit_decision(user_id=uuid4(), action="flow:read", obj="flow:x", result="allow")

    await authz_audit.drain_pending_audit_writes(timeout=1.0)

    total_rows = sum(len(batch) for batch in patched_audit_flush)
    assert total_rows == 5
    # All entries are emitted before the first await, so they should land in a single batch.
    assert len(patched_audit_flush) == 1, (
        f"Expected 1 batch of 5 rows, got {len(patched_audit_flush)} batches "
        f"with sizes {[len(b) for b in patched_audit_flush]}"
    )


@pytest.mark.anyio
async def test_idle_drain_keeps_durable_admission_terminal(monkeypatch, patched_audit_flush):
    """A same-loop durable submit cannot reopen a never-started drained pipeline."""
    await _reset_audit_pipeline()
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )

    await authz_audit.drain_pending_audit_writes(timeout=0.1)

    try:
        with pytest.raises(authz_audit.AuditPersistenceError):
            await authz_audit.audit_decision(
                user_id=uuid4(),
                action="flow:read",
                obj="flow:*",
                result="allow",
            )

        assert authz_audit._audit_accepting is False
        assert authz_audit._audit_queue is None
        assert authz_audit._audit_writer_task is None
        assert patched_audit_flush == []
    finally:
        await authz_audit.drain_pending_audit_writes(timeout=0.1)


def test_new_loop_replaces_idle_drained_pipeline(monkeypatch, patched_audit_flush):
    """A closed owner loop does not make durable shutdown process-global."""
    install_settings(
        monkeypatch,
        authz_enabled=True,
        audit_enabled=True,
        audit_durable=True,
    )

    async def stop_idle_pipeline() -> None:
        await _reset_audit_pipeline()
        await authz_audit.drain_pending_audit_writes(timeout=0.1)

    async def submit_on_replacement_loop() -> None:
        await authz_audit.audit_decision(
            user_id=uuid4(),
            action="flow:read",
            obj="flow:*",
            result="allow",
        )
        await authz_audit.drain_pending_audit_writes(timeout=0.1)

    asyncio.run(stop_idle_pipeline())
    asyncio.run(submit_on_replacement_loop())

    assert sum(len(batch) for batch in patched_audit_flush) == 1


@pytest.mark.anyio
async def test_ensure_permission_fails_closed_on_plugin_exception(monkeypatch, fake_user):
    """If the authz plugin raises, ``ensure_permission`` must deny (403), not bubble 500."""
    from langflow.services.authorization import guards as authz_guards

    install_settings(monkeypatch, authz_enabled=True, audit_enabled=False)

    class _BrokenPlugin:
        async def enforce(self, **_kwargs):
            msg = "policy store down"
            raise RuntimeError(msg)

        async def batch_enforce(self, **_kwargs):
            return []

    monkeypatch.setattr(authz_guards, "get_authorization_service", lambda: _BrokenPlugin())
    captured = install_audit_recorder(monkeypatch)

    with pytest.raises(HTTPException) as excinfo:
        await authz_guards.ensure_permission(fake_user, domain="*", obj="flow:abc", act="read")

    assert excinfo.value.status_code == 403, "Plugin exceptions must fail closed (deny), not 500"
    # The deny path must still emit an audit row so the operator can see the failure.
    assert captured, "Plugin exception must still produce an audit row"
    assert captured[0]["result"] == "deny"
    assert "error" in captured[0]["details"]
