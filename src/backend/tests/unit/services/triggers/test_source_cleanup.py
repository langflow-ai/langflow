"""Cleanup credentials survive user cascades only as bounded revocation capabilities."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.service import _decrypt_credential_payload, _encrypt_credential_payload
from langflow.services.database.models.connection.model import Connection, ConnectionSecret
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers import source_cleanup, source_clients, source_subscription
from langflow.services.triggers.cleanup import delete_triggers
from lfx.integrations.errors import AuthExpiredError
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.erase_helpers import wait_for_erase

pytestmark = pytest.mark.no_blockbuster

_ACCESS_TOKEN = "cleanup-test-access"  # noqa: S105  # pragma: allowlist secret - synthetic test token
_MAILBOX_KEY = hashlib.sha256(b"cleanup@example.com").hexdigest()
_REFRESH_TOKEN = "must-not-retain-refresh"  # noqa: S105  # pragma: allowlist secret - synthetic test token


async def _connection(session, user_id, *, provider="microsoft", expires_at=None, status="ready"):
    row = Connection(
        provider_key=provider, name=f"source_{uuid4().hex}", display_name="Source", owner_id=user_id, status=status
    )
    session.add(row)
    await session.flush()
    session.add(
        ConnectionSecret(
            connection_id=row.id,
            encrypted_payload=_encrypt_credential_payload(
                json.dumps(
                    {
                        "version": 1,
                        "access_token": _ACCESS_TOKEN,
                        "refresh_token": _REFRESH_TOKEN,
                        "expires_at": expires_at.isoformat() if expires_at else None,
                        "oauth": {"registration_id": "must-not-retain-registration"},
                    }
                )
            ),
        )
    )
    await session.flush()
    return row.id


def _task(user_id, connection_id, *, provider="microsoft", kind="microsoft.calendar", expires_at=None):
    return TriggerCleanup(
        id=uuid4(),
        trigger_id=uuid4(),
        user_id=user_id,
        connection_id=connection_id,
        provider=provider,
        kind=kind,
        provider_subscription_id=f"watch-{uuid4().hex}",
        provider_state={"resource_id": "resource-1", "mailbox_key": _MAILBOX_KEY},
        expires_at=expires_at,
    )


@pytest.mark.parametrize(
    ("provider", "kind", "method", "path"),
    [
        ("microsoft", "microsoft.calendar", "DELETE", "/v1.0/subscriptions/"),
        ("google", "google.calendar", "POST", "/calendar/v3/channels/stop"),
        ("google", "google.drive", "POST", "/drive/v3/channels/stop"),
        ("google", "google.gmail", "POST", "/gmail/v1/users/me/stop"),
    ],
)
async def test_user_delete_preserves_new_and_previous_revocations(
    client, logged_in_headers_super_user, trigger_owner, make_trigger, monkeypatch, provider, kind, method, path
):
    token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    async with session_scope() as session:
        connection_id = await _connection(session, trigger_owner, provider=provider, expires_at=token_expiry)
        earlier = _task(trigger_owner, connection_id, provider=provider, kind=kind, expires_at=token_expiry)
        # This intent belongs to an already-deleted trigger and is in backoff.
        earlier.available_at = token_expiry
        session.add(earlier)
        earlier_id = earlier.id
    trigger_id = await make_trigger(kind=kind, provider=provider, connection_id=connection_id)
    async with session_scope() as session:
        subscription = TriggerSubscription(
            trigger_id=trigger_id,
            connection_id=connection_id,
            provider=provider,
            provider_subscription_id=f"watch-{uuid4().hex}",
            provider_state={"resource_id": "resource-1", "mailbox_key": _MAILBOX_KEY},
            expires_at=token_expiry,
        )
        session.add(subscription)
        await session.flush()
        subscription_id = subscription.id

    def no_resolver():
        pytest.fail("User deletion and retained cleanup must not resolve or refresh OAuth")

    monkeypatch.setattr(source_cleanup, "get_connection_resolver_service", no_resolver)
    response = await client.delete(f"/api/v1/users/{trigger_owner}", headers=logged_in_headers_super_user)
    assert response.status_code == 202, response.text
    await wait_for_erase(response.json()["request_id"])
    async with session_scope() as session:
        assert await session.get(User, trigger_owner) is None
        assert await session.get(Connection, connection_id) is None
        assert await session.get(ConnectionSecret, connection_id) is None
        assert await session.get(Trigger, trigger_id) is None
        for task_id in (earlier_id, subscription_id):
            task = await session.get(TriggerCleanup, task_id)
            retained = _decrypt_credential_payload(task.encrypted_credential)
            assert retained["access_token"] == _ACCESS_TOKEN
            assert "refresh_token" not in retained
            assert "oauth" not in retained
            assert "encrypted_credential" not in task.model_dump()
            assert task.encrypted_credential not in repr(task)
            assert source_cleanup._aware(task.credential_expires_at) <= token_expiry
            assert source_cleanup._aware(task.available_at) < token_expiry

    requests = []

    def reply(request):
        requests.append(request)
        assert request.headers["Authorization"] == f"Bearer {_ACCESS_TOKEN}"
        if request.url.path == "/gmail/v1/users/me/profile":
            return httpx.Response(200, json={"emailAddress": "cleanup@example.com"})
        return httpx.Response(204)

    monkeypatch.setattr(
        source_clients,
        "SourceHTTP",
        lambda lease, *, origin: source_clients_http(lease, origin=origin, transport=httpx.MockTransport(reply)),
    )
    monkeypatch.setattr(source_subscription, "SourceHTTP", source_clients.SourceHTTP)
    assert await source_cleanup.run_cleanup_pass() == 2
    assert len(requests) == (4 if kind == "google.gmail" else 2)
    revocations = [request for request in requests if request.method == method]
    assert len(revocations) == 2
    assert all(request.url.path.startswith(path) for request in revocations)
    async with session_scope() as session:
        assert await session.get(TriggerCleanup, earlier_id) is None
        assert await session.get(TriggerCleanup, subscription_id) is None


# Preserve the real transport class before individual tests monkeypatch it.
source_clients_http = source_clients.SourceHTTP


@pytest.fixture(params=[False, True], ids=["foreign-keys-off", "foreign-keys-on"])
async def cleanup_db(client, request):  # noqa: ARG001 - initialize the real encryption settings
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def set_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute(f"PRAGMA foreign_keys={'ON' if request.param else 'OFF'}")
        cursor.close()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
    finally:
        await engine.dispose()


async def test_retained_revocation_survives_owner_cascades_on_both_sqlite_modes(cleanup_db):
    session = cleanup_db
    owner = User(username=f"cleanup-{uuid4().hex}", password=str(uuid4()), is_active=True)
    session.add(owner)
    await session.flush()
    flow = Flow(name="Cleanup flow", user_id=owner.id)
    session.add(flow)
    await session.flush()
    connection_id = await _connection(session, owner.id)
    trigger = Trigger(
        flow_id=flow.id,
        user_id=owner.id,
        connection_id=connection_id,
        kind="microsoft.calendar",
        provider="microsoft",
        name="Cleanup",
    )
    session.add(trigger)
    await session.flush()
    subscription = TriggerSubscription(
        trigger_id=trigger.id,
        connection_id=connection_id,
        provider="microsoft",
        provider_subscription_id=f"watch-{uuid4().hex}",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.add(subscription)
    await session.commit()
    task_id = subscription.id
    await delete_triggers(session, trigger_ids=[trigger.id])
    await source_cleanup.preserve_user_cleanup_credentials(session, user_id=owner.id)
    await session.delete(owner)
    await session.commit()
    session.expunge_all()
    assert await session.get(User, owner.id) is None
    assert await session.get(Connection, connection_id) is None
    assert await session.get(ConnectionSecret, connection_id) is None
    task = await session.get(TriggerCleanup, task_id)
    assert await (await source_cleanup._cleanup_lease(task)).get_token() == _ACCESS_TOKEN


@pytest.mark.parametrize("deadline_kind", ["token", "watch", "fallback"])
async def test_snapshot_retention_uses_the_earliest_deadline(trigger_owner, deadline_kind):
    now = datetime.now(timezone.utc)
    token_expiry = now + timedelta(minutes=10) if deadline_kind == "token" else None
    watch_expiry = now + timedelta(minutes=5) if deadline_kind == "watch" else None
    async with session_scope() as session:
        connection_id = await _connection(session, trigger_owner, expires_at=token_expiry)
        task = _task(trigger_owner, connection_id, expires_at=watch_expiry)
        session.add(task)
        await source_cleanup.preserve_user_cleanup_credentials(session, user_id=trigger_owner)
        if token_expiry:
            assert task.credential_expires_at <= token_expiry
        if watch_expiry:
            assert task.credential_expires_at <= watch_expiry
        assert task.credential_expires_at <= datetime.now(timezone.utc) + timedelta(hours=1)


@pytest.mark.parametrize("unusable", ["expired-token", "revoked", "expired", "foreign-owner", "foreign-provider"])
async def test_unusable_or_foreign_credentials_are_never_retained(trigger_owner, unusable):
    expiry = datetime.now(timezone.utc) - timedelta(minutes=1) if unusable == "expired-token" else None
    async with session_scope() as session:
        owner_id = trigger_owner
        if unusable == "foreign-owner":
            foreign_owner = User(username=f"foreign-{uuid4().hex}", password=str(uuid4()), is_active=True)
            session.add(foreign_owner)
            await session.flush()
            owner_id = foreign_owner.id
        connection_id = await _connection(
            session, owner_id, expires_at=expiry, status=unusable if unusable in {"revoked", "expired"} else "ready"
        )
        task = _task(trigger_owner, connection_id, provider="google" if unusable == "foreign-provider" else "microsoft")
        session.add(task)
        await source_cleanup.preserve_user_cleanup_credentials(session, user_id=trigger_owner)
        assert task.encrypted_credential is None
        assert task.credential_expires_at is None


async def test_snapshot_cannot_authorize_a_different_watch_or_extend_its_deadline(trigger_owner):
    async with session_scope() as session:
        connection_id = await _connection(session, trigger_owner)
        task = _task(trigger_owner, connection_id)
        session.add(task)
        await source_cleanup.preserve_user_cleanup_credentials(session, user_id=trigger_owner)
        task.provider_subscription_id = "another-watch"
        with pytest.raises(AuthExpiredError):
            await (await source_cleanup._cleanup_lease(task)).get_token()

        retained = _decrypt_credential_payload(task.encrypted_credential)
        task.provider_subscription_id = retained["cleanup_binding"]["provider_subscription_id"]
        task.credential_expires_at += timedelta(hours=1)
        with pytest.raises(AuthExpiredError):
            await (await source_cleanup._cleanup_lease(task)).get_token()


async def test_expired_snapshot_is_purged_during_retry_backoff(trigger_owner, monkeypatch):
    async with session_scope() as session:
        connection_id = await _connection(session, trigger_owner)
        task = _task(trigger_owner, connection_id, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        session.add(task)
        await source_cleanup.preserve_user_cleanup_credentials(session, user_id=trigger_owner)
        task.credential_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        task.available_at = datetime.now(timezone.utc) + timedelta(hours=1)
        session.add(task)
        task_id = task.id

    async def no_revoke(_task):
        pytest.fail("Backoff intent must not attempt revocation")

    monkeypatch.setattr(source_cleanup, "_revoke", no_revoke)
    assert await source_cleanup.run_cleanup_pass() == 0
    async with session_scope() as session:
        task = await session.get(TriggerCleanup, task_id)
        assert task is not None
        assert task.encrypted_credential is None
        assert task.credential_expires_at is None


async def test_deleted_owner_cleanup_retries_transient_provider_failure(trigger_owner, monkeypatch):
    async with session_scope() as session:
        connection_id = await _connection(session, trigger_owner)
        task = _task(trigger_owner, connection_id, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        session.add(task)
        await source_cleanup.preserve_user_cleanup_credentials(session, user_id=trigger_owner)
        await session.delete(await session.get(User, trigger_owner))
        task_id = task.id

    requests = []

    def reply(request):
        requests.append(request)
        assert request.headers["Authorization"] == f"Bearer {_ACCESS_TOKEN}"
        return httpx.Response(503 if len(requests) == 1 else 204)

    monkeypatch.setattr(
        source_clients,
        "SourceHTTP",
        lambda lease, *, origin: source_clients_http(lease, origin=origin, transport=httpx.MockTransport(reply)),
    )
    assert await source_cleanup.run_cleanup_pass() == 0
    async with session_scope() as session:
        task = await session.get(TriggerCleanup, task_id)
        assert task.attempt == 1
        assert task.encrypted_credential is not None
        task.available_at = datetime.now(timezone.utc)
        session.add(task)
    assert await source_cleanup.run_cleanup_pass() == 1


async def test_snapshot_never_refreshes_a_rejected_token(trigger_owner, monkeypatch):
    async with session_scope() as session:
        connection_id = await _connection(session, trigger_owner)
        task = _task(trigger_owner, connection_id)
        session.add(task)
        await source_cleanup.preserve_user_cleanup_credentials(session, user_id=trigger_owner)

    calls = []

    def reply(request):
        calls.append(request)
        return httpx.Response(401)

    monkeypatch.setattr(
        source_clients,
        "SourceHTTP",
        lambda lease, *, origin: source_clients_http(lease, origin=origin, transport=httpx.MockTransport(reply)),
    )
    with pytest.raises(AuthExpiredError):
        await source_cleanup._revoke(task)
    assert len(calls) == 1


async def test_provider_policy_blocks_snapshot_before_decryption_or_http(trigger_owner, monkeypatch):
    from lfx.integrations.errors import IntegrationPolicyBlockedError

    async with session_scope() as session:
        connection_id = await _connection(session, trigger_owner)
        task = _task(trigger_owner, connection_id)
        session.add(task)
        await source_cleanup.preserve_user_cleanup_credentials(session, user_id=trigger_owner)

    async def blocked(provider, *, user_id):
        assert provider == task.provider
        assert user_id == str(trigger_owner)
        raise IntegrationPolicyBlockedError(provider=provider, policy_key="integration:microsoft")

    def no_decrypt(_encrypted):
        pytest.fail("Denied provider must not decrypt its cleanup credential")

    def no_http(*_args, **_kwargs):
        pytest.fail("Denied provider must not receive HTTP requests")

    monkeypatch.setattr(source_cleanup, "enforce_integration_policy_for_provider", blocked)
    monkeypatch.setattr(source_cleanup, "_decrypt_credential_payload", no_decrypt)
    monkeypatch.setattr(source_clients, "SourceHTTP", no_http)
    with pytest.raises(IntegrationPolicyBlockedError):
        await (await source_cleanup._cleanup_lease(task)).get_token()


async def test_deleted_gmail_owner_preserves_a_sibling_mailbox_watch(
    client, logged_in_headers_super_user, trigger_owner, make_trigger, monkeypatch
):
    expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    async with session_scope() as session:
        connection_id = await _connection(session, trigger_owner, provider="google", expires_at=expiry)
        sibling_owner = User(username=f"sibling-{uuid4().hex}", password=str(uuid4()), is_active=True)
        session.add(sibling_owner)
        await session.flush()
        sibling_owner_id = sibling_owner.id
        sibling_connection_id = await _connection(session, sibling_owner_id, provider="google", expires_at=expiry)
        sibling_flow = Flow(name="Sibling mailbox flow", user_id=sibling_owner_id)
        session.add(sibling_flow)
        await session.flush()
        sibling = Trigger(
            flow_id=sibling_flow.id,
            user_id=sibling_owner_id,
            connection_id=sibling_connection_id,
            name="Sibling mailbox",
            kind="google.gmail",
            provider="google",
            state="active",
        )
        session.add(sibling)
        await session.flush()
        sibling_subscription = TriggerSubscription(
            trigger_id=sibling.id,
            connection_id=sibling_connection_id,
            provider="google",
            provider_subscription_id=f"sibling-{uuid4().hex}",
            state="active",
            provider_state={"mailbox_key": _MAILBOX_KEY},
            expires_at=expiry,
        )
        session.add(sibling_subscription)
        await session.flush()
        sibling_subscription_id = sibling_subscription.id

    trigger_id = await make_trigger(kind="google.gmail", provider="google", connection_id=connection_id)
    async with session_scope() as session:
        session.add(
            TriggerSubscription(
                trigger_id=trigger_id,
                connection_id=connection_id,
                provider="google",
                provider_subscription_id=f"deleted-{uuid4().hex}",
                provider_state={"mailbox_key": _MAILBOX_KEY},
                expires_at=expiry,
            )
        )

    response = await client.delete(f"/api/v1/users/{trigger_owner}", headers=logged_in_headers_super_user)
    assert response.status_code == 202, response.text
    await wait_for_erase(response.json()["request_id"])
    requests = []

    def reply(request):
        requests.append(request)
        assert request.headers["Authorization"] == f"Bearer {_ACCESS_TOKEN}"
        assert request.method == "GET"
        assert request.url.path == "/gmail/v1/users/me/profile"
        return httpx.Response(200, json={"emailAddress": "cleanup@example.com"})

    def transport(lease, *, origin):
        return source_clients_http(lease, origin=origin, transport=httpx.MockTransport(reply))

    monkeypatch.setattr(source_clients, "SourceHTTP", transport)
    monkeypatch.setattr(source_subscription, "SourceHTTP", transport)
    assert await source_cleanup.run_cleanup_pass() == 1
    assert len(requests) == 1
    async with session_scope() as session:
        assert await session.get(User, trigger_owner) is None
        assert await session.get(Connection, connection_id) is None
        assert await session.get(User, sibling_owner_id) is not None
        assert (await session.get(TriggerSubscription, sibling_subscription_id)).state == "active"
