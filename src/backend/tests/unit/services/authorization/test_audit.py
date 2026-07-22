"""Tests for the batched audit pipeline (``audit_decision`` + writer)."""

from __future__ import annotations

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
    authz_audit._audit_dropped_count = 0
    authz_audit._audit_last_drop_warn = 0.0
    authz_audit._pending_audit_tasks.clear()


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
async def test_drain_pending_audit_writes_is_safe_when_idle():
    """``drain_pending_audit_writes`` is a no-op when no audit traffic has run."""
    await _reset_audit_pipeline()
    # Must not raise.
    await authz_audit.drain_pending_audit_writes(timeout=0.1)


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
