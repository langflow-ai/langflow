"""Focused ordering tests for the OSS-to-plugin identity lifecycle seam."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.database.models.user.model import User
from lfx.services.authorization import AuthorizationMutationKind, AuthorizationMutationRejected

_RECOVERY_DETAIL = "At least one recovery administrator is required."


class _FirstResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


@pytest.fixture(autouse=True)
def isolate_user_route_from_team_lifecycle(monkeypatch):
    """These route-ordering tests isolate the separately tested team repair service."""
    from langflow.api.v1 import users
    from langflow.services.authorization.team_management import (
        UserTeamLifecycleLockContext,
        UserTeamLifecycleLockHint,
        UserTeamLifecycleResult,
    )
    from langflow.services.database.models.user.model import User
    from sqlmodel import select

    async def unchanged_team_state(*_args, **_kwargs):
        return UserTeamLifecycleResult((), (), (), ())

    async def user_only_lock_hint(_session, *, user_id):
        return UserTeamLifecycleLockHint((), (), (user_id,))

    async def acquire_user_only_lock_context(session, *, user_id, hint):  # noqa: ARG001
        result = await session.exec(select(User).where(User.id == user_id))
        target = result.first()
        return UserTeamLifecycleLockContext(
            users={user_id: target} if target is not None else {},
            teams={},
            members_by_team={},
        )

    monkeypatch.setattr(users, "apply_user_team_lifecycle", unchanged_team_state)
    monkeypatch.setattr(users, "prepare_user_team_lifecycle_lock_hint", user_only_lock_hint)
    monkeypatch.setattr(users, "acquire_user_team_lifecycle_locks", acquire_user_only_lock_context)


class _LifecycleService:
    def __init__(self, events: list[str], *, fail_stage: bool = False) -> None:
        self.events = events
        self.fail_stage = fail_stage
        self.validated = []
        self.staged = []
        self.committed = []
        self.lock_requests = []

    async def acquire_identity_mutation_lock(self, *, session, **request) -> None:  # noqa: ARG002
        self.events.append("lock")
        self.lock_requests.append(request)

    async def acquire_resource_mutation_lock(self, *, session) -> None:  # noqa: ARG002
        self.events.append("lock")

    async def validate_identity_mutation(self, *, session, mutation) -> None:  # noqa: ARG002
        self.events.append("validate")
        self.validated.append(mutation)

    async def stage_identity_mutation(self, *, session, event) -> None:  # noqa: ARG002
        self.events.append("stage")
        self.staged.append(event)
        if self.fail_stage:
            msg = "policy compilation failed"
            raise RuntimeError(msg)

    async def identity_mutation_committed(self, event) -> None:
        self.events.append("committed")
        self.committed.append(event)


@pytest.mark.asyncio
async def test_user_create_stages_default_folder_and_identity_in_one_transaction(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.database.models.user.model import UserCreate

    events: list[str] = []
    service = _LifecycleService(events)
    session = SimpleNamespace()
    session.add = Mock(side_effect=lambda _value: events.append("mutate"))
    session.flush = AsyncMock(side_effect=lambda: events.append("flush"))
    session.refresh = AsyncMock()
    session.commit = AsyncMock(side_effect=lambda: events.append("commit"))
    session.rollback = AsyncMock()

    async def create_default_folder(_session, _user_id):
        events.append("folder")
        return object()

    def stage_audit(**_kwargs):
        events.append("audit")
        return True

    auth_settings = SimpleNamespace(AUTO_LOGIN=False, ENABLE_SIGNUP=True, NEW_USER_IS_ACTIVE=True)
    monkeypatch.setattr(users, "get_settings_service", lambda: SimpleNamespace(auth_settings=auth_settings))
    monkeypatch.setattr(
        users,
        "get_auth_service",
        lambda: SimpleNamespace(get_password_hash=lambda _password: "hashed"),
    )
    monkeypatch.setattr(users, "get_or_create_default_folder", create_default_folder)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)
    monkeypatch.setattr(users, "stage_audit_decision", stage_audit)

    created = await users.add_user(
        user=UserCreate(username="new-user", password="not-a-real-password"),  # noqa: S106
        session=session,
        current_user=None,
    )

    assert events == ["lock", "mutate", "flush", "folder", "stage", "audit", "commit", "committed"]
    assert service.staged == service.committed
    mutation = service.staged[0]
    assert mutation.kind is AuthorizationMutationKind.USER_CREATED
    assert mutation.entity_id == created.id
    assert mutation.affected_user_ids == (created.id,)
    assert mutation.user_before is None
    assert mutation.user_after.is_active is True
    assert mutation.user_after.is_superuser is False


@pytest.mark.asyncio
async def test_failed_anonymous_signup_rolls_back_before_auditing_without_user_fk(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.authorization.audit import AUDIT_EVENT_ACCESS
    from langflow.services.database.models.user.model import UserCreate

    events: list[str] = []
    service = _LifecycleService(events)
    session = SimpleNamespace()
    added_users = []

    def add_user(value):
        added_users.append(value)
        events.append("mutate")

    session.add = Mock(side_effect=add_user)
    session.flush = AsyncMock(side_effect=lambda: events.append("flush"))
    session.refresh = AsyncMock()
    session.rollback = AsyncMock(side_effect=lambda: events.append("rollback"))
    session.commit = AsyncMock()
    audit_calls = []

    async def fail_default_folder(_session, _user_id):
        events.append("folder")

    async def audit(**kwargs):
        events.append("audit")
        audit_calls.append(kwargs)

    auth_settings = SimpleNamespace(AUTO_LOGIN=False, ENABLE_SIGNUP=True, NEW_USER_IS_ACTIVE=True)
    monkeypatch.setattr(users, "get_settings_service", lambda: SimpleNamespace(auth_settings=auth_settings))
    monkeypatch.setattr(
        users,
        "get_auth_service",
        lambda: SimpleNamespace(get_password_hash=lambda _password: "hashed"),
    )
    monkeypatch.setattr(users, "get_or_create_default_folder", fail_default_folder)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)
    monkeypatch.setattr(users, "audit_decision", audit)

    with pytest.raises(HTTPException, match="default project"):
        await users.add_user(
            user=UserCreate(username="new-user", password="not-a-real-password"),  # noqa: S106
            session=session,
            current_user=None,
        )

    assert events == ["lock", "mutate", "flush", "folder", "rollback", "audit"]
    assert audit_calls == [
        {
            "user_id": None,
            "action": "user:create",
            "obj": f"user:{added_users[0].id}",
            "result": "deny",
            "details": {
                "event": AUDIT_EVENT_ACCESS,
                "status_code": 500,
                "reason": "default_project_creation_failed",
            },
        }
    ]
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_disable_validates_and_stages_in_transaction_order(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.authorization.audit import AUDIT_EVENT_MUTATION
    from langflow.services.database.models.user.model import UserUpdate

    events: list[str] = []
    service = _LifecycleService(events)
    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=True,
        password="hashed",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=actor)

    async def update_user(_target, _update, _session):
        events.append("mutate")
        target.is_active = False
        return target

    async def commit():
        events.append("commit")

    async def read_user(_statement):
        events.append("read")
        return _FirstResult(target)

    audit_calls = []

    def stage_audit(**kwargs):
        events.append("audit")
        audit_calls.append(kwargs)
        return True

    session.commit.side_effect = commit
    session.get_bind = Mock(return_value=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    session.exec.side_effect = read_user
    monkeypatch.setattr(users, "update_user", update_user)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)
    monkeypatch.setattr(users, "stage_audit_decision", stage_audit)

    result = await users.patch_user(
        user_id=target.id,
        user_update=UserUpdate(is_active=False),
        user=actor,
        session=session,
    )

    assert result is target
    assert events == ["lock", "read", "validate", "mutate", "stage", "audit", "commit", "committed"]
    assert service.validated == service.staged == service.committed
    mutation = service.staged[0]
    assert mutation.kind is AuthorizationMutationKind.USER_DISABLED
    assert mutation.user_before.is_active is True
    assert mutation.user_after.is_active is False
    assert audit_calls == [
        {
            "session": session,
            "user_id": actor.id,
            "action": "user:update",
            "obj": f"user:{target.id}",
            "result": "allow",
            "details": {
                "event": AUDIT_EVENT_MUTATION,
                "fields_changed": ["is_active"],
                "lifecycle_kind": AuthorizationMutationKind.USER_DISABLED.value,
                "teams_deactivated": [],
            },
        }
    ]


@pytest.mark.asyncio
async def test_ordinary_user_patch_stages_audit_without_password_or_values(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.authorization.audit import AUDIT_EVENT_MUTATION
    from langflow.services.database.models.user.model import UserUpdate

    events: list[str] = []
    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        username="before",
        is_active=True,
        is_superuser=False,
        password="old-hash",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=actor)
    audit_calls = []

    async def read_user(_statement):
        events.append("read")
        return _FirstResult(target)

    async def update_user(_target, update, _session):
        events.append("mutate")
        target.username = update.username
        target.password = update.password
        return target

    async def commit():
        events.append("commit")

    def stage_audit(**kwargs):
        events.append("audit")
        audit_calls.append(kwargs)
        return True

    session.commit.side_effect = commit
    session.exec.side_effect = read_user
    monkeypatch.setattr(users, "update_user", update_user)
    monkeypatch.setattr(
        users,
        "get_auth_service",
        lambda: SimpleNamespace(get_password_hash=lambda _password: "new-hash"),
    )
    monkeypatch.setattr(users, "get_authorization_service", lambda: _LifecycleService(events))
    monkeypatch.setattr(users, "stage_audit_decision", stage_audit)

    await users.patch_user(
        user_id=target.id,
        user_update=UserUpdate(username="after", password="plaintext"),  # noqa: S106
        user=actor,
        session=session,
    )

    assert events == ["lock", "read", "mutate", "audit", "commit"]
    assert audit_calls == [
        {
            "session": session,
            "user_id": actor.id,
            "action": "user:update",
            "obj": f"user:{target.id}",
            "result": "allow",
            "details": {
                "event": AUDIT_EVENT_MUTATION,
                "fields_changed": ["username"],
                "lifecycle_kind": None,
                "teams_deactivated": [],
            },
        }
    ]
    assert "password" not in repr(audit_calls).lower()
    assert "plaintext" not in repr(audit_calls)
    assert "after" not in repr(audit_calls)


@pytest.mark.asyncio
async def test_user_patch_audit_stage_failure_rolls_back_before_commit(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.database.models.user.model import UserUpdate

    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        username="before",
        is_active=True,
        is_superuser=False,
        password="hashed",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=actor)

    async def update_user(_target, _update, _session):
        return target

    def fail_audit(**_kwargs):
        msg = "audit staging failed"
        raise RuntimeError(msg)

    session.exec.return_value = _FirstResult(target)
    monkeypatch.setattr(users, "update_user", update_user)
    monkeypatch.setattr(users, "get_authorization_service", lambda: _LifecycleService([]))
    monkeypatch.setattr(users, "stage_audit_decision", fail_audit)

    with pytest.raises(RuntimeError, match="audit staging failed"):
        await users.patch_user(
            user_id=target.id,
            user_update=UserUpdate(username="after"),
            user=actor,
            session=session,
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_patch_business_denial_emits_access_audit(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.authorization.audit import AUDIT_EVENT_ACCESS
    from langflow.services.database.models.user.model import UserUpdate

    actor = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=True)
    session = AsyncMock()
    audit_calls = []

    async def audit(**kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(users, "audit_decision", audit)

    with pytest.raises(HTTPException, match="deactivate"):
        await users.patch_user(
            user_id=actor.id,
            user_update=UserUpdate(is_active=False),
            user=actor,
            session=session,
        )

    assert audit_calls == [
        {
            "user_id": actor.id,
            "action": "user:update",
            "obj": f"user:{actor.id}",
            "result": "deny",
            "details": {
                "event": AUDIT_EVENT_ACCESS,
                "status_code": 403,
                "reason": "self_deactivation_forbidden",
            },
        }
    ]
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_superuser_delete_reaches_audited_gate(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.authorization.audit import AUDIT_EVENT_ACCESS

    actor = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    target_id = uuid4()
    session = AsyncMock()
    audit_calls = []

    async def audit(**kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(users, "audit_decision", audit)

    with pytest.raises(HTTPException, match="Permission denied") as exc_info:
        await users.delete_user(user_id=target_id, current_user=actor, session=session)

    assert exc_info.value.status_code == 403
    assert audit_calls == [
        {
            "user_id": actor.id,
            "action": "user:delete",
            "obj": f"user:{target_id}",
            "result": "deny",
            "details": {
                "event": AUDIT_EVENT_ACCESS,
                "status_code": 403,
                "reason": "superuser_required",
            },
        }
    ]
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_directory_platform_actions_honor_external_credential_ceiling(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.authorization.access_ceiling import (
        ExternalAccessContext,
        set_current_external_access_context,
    )
    from langflow.services.database.models.user.model import UserCreate, UserUpdate
    from langflow.services.deps import get_settings_service

    actor = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=True)
    target_id = uuid4()
    session = AsyncMock()
    monkeypatch.setattr(users, "audit_decision", AsyncMock())

    auth_settings = get_settings_service().auth_settings
    original_bypass = auth_settings.AUTHZ_SUPERUSER_BYPASS
    original_signup = auth_settings.ENABLE_SIGNUP
    original_auto_login = auth_settings.AUTO_LOGIN
    auth_settings.AUTHZ_SUPERUSER_BYPASS = True
    auth_settings.ENABLE_SIGNUP = False
    auth_settings.AUTO_LOGIN = False
    set_current_external_access_context(
        ExternalAccessContext(provider="test-idp", subject="platform-user", level="editor")
    )
    try:
        with pytest.raises(HTTPException) as exc_info:
            await users._get_current_platform_admin(actor)
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as exc_info:
            await users.add_user(
                user=UserCreate(username="blocked-admin-create", password="not-a-real-password"),  # noqa: S106
                session=session,
                current_user=actor,
            )
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as exc_info:
            await users.patch_user(
                user_id=target_id,
                user_update=UserUpdate(username="blocked-cross-user-update"),
                user=actor,
                session=session,
            )
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as exc_info:
            await users.delete_user(user_id=target_id, current_user=actor, session=session)
        assert exc_info.value.status_code == 403
    finally:
        set_current_external_access_context(None)
        auth_settings.AUTHZ_SUPERUSER_BYPASS = original_bypass
        auth_settings.ENABLE_SIGNUP = original_signup
        auth_settings.AUTO_LOGIN = original_auto_login

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_patch_lock_kind_is_advisory_before_state_read(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.database.models.user.model import UserUpdate

    events: list[str] = []
    service = _LifecycleService(events)
    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        is_active=False,
        is_superuser=True,
        password="hashed",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=actor)
    session.add = Mock()

    async def update_user(_target, _update, _session):
        events.append("mutate")
        target.is_superuser = False
        return target

    async def commit():
        events.append("commit")

    async def read_user(_statement):
        events.append("read")
        return _FirstResult(target)

    session.commit.side_effect = commit
    session.get_bind = Mock(return_value=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    session.exec.side_effect = read_user
    monkeypatch.setattr(users, "update_user", update_user)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)
    monkeypatch.setattr(users, "audit_decision", AsyncMock())

    result = await users.patch_user(
        user_id=target.id,
        user_update=UserUpdate(is_active=False, is_superuser=False),
        user=actor,
        session=session,
    )

    assert result is target
    assert events == ["lock", "read", "validate", "mutate", "stage", "commit", "committed"]
    assert service.lock_requests[0]["kind"] is AuthorizationMutationKind.USER_DISABLED
    assert service.staged[0].kind is AuthorizationMutationKind.USER_SUPERUSER_DEMOTED


@pytest.mark.asyncio
async def test_user_lifecycle_stage_failure_prevents_commit(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.database.models.user.model import UserUpdate

    events: list[str] = []
    service = _LifecycleService(events, fail_stage=True)
    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=False,
        password="hashed",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=actor)

    async def update_user(_target, _update, _session):
        events.append("mutate")
        return target

    session.get_bind = Mock(return_value=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    session.exec.return_value = _FirstResult(target)
    monkeypatch.setattr(users, "update_user", update_user)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)

    with pytest.raises(RuntimeError, match="policy compilation failed"):
        await users.patch_user(
            user_id=target.id,
            user_update=UserUpdate(is_active=False),
            user=actor,
            session=session,
        )

    assert events == ["lock", "validate", "mutate", "stage"]
    session.commit.assert_not_awaited()
    assert service.committed == []


@pytest.mark.asyncio
async def test_user_lifecycle_policy_rejection_is_409_without_mutation(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.database.models.user.model import UserUpdate

    events: list[str] = []
    service = _LifecycleService(events)
    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=True,
        password="hashed",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=actor)
    update = AsyncMock()
    audit = AsyncMock()

    async def reject(*, session, mutation):  # noqa: ARG001
        events.append("validate")
        raise AuthorizationMutationRejected(_RECOVERY_DETAIL)

    service.validate_identity_mutation = reject
    session.get_bind = Mock(return_value=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    session.exec.return_value = _FirstResult(target)
    monkeypatch.setattr(users, "update_user", update)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)
    monkeypatch.setattr(users, "audit_decision", audit)

    with pytest.raises(HTTPException) as exc_info:
        await users.patch_user(
            user_id=target.id,
            user_update=UserUpdate(is_active=False),
            user=actor,
            session=session,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == _RECOVERY_DETAIL
    assert events == ["lock", "validate"]
    update.assert_not_awaited()
    session.commit.assert_not_awaited()
    audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_api_key_delete_stages_revocation_then_audits_after_commit(monkeypatch):
    from langflow.api.v1 import api_key

    events: list[str] = []
    service = _LifecycleService(events)
    user = SimpleNamespace(id=uuid4())
    api_key_id = uuid4()
    session = AsyncMock()

    async def delete_key(_session, _key_id, _user_id):
        events.append("mutate")

    async def flush():
        events.append("flush")

    async def commit():
        events.append("commit")

    async def audit(**_kwargs):
        events.append("audit")

    session.flush.side_effect = flush
    session.commit.side_effect = commit
    monkeypatch.setattr(api_key, "delete_api_key", delete_key)
    monkeypatch.setattr(api_key, "get_authorization_service", lambda: service)
    monkeypatch.setattr(api_key, "audit_decision", audit)

    await api_key.delete_api_key_route(
        api_key_id=api_key_id,
        db=session,
        current_user=user,
    )

    assert events == ["mutate", "flush", "stage", "commit", "committed", "audit"]
    assert service.staged == service.committed
    assert service.staged[0].kind is AuthorizationMutationKind.API_KEY_DELETED


@pytest.mark.asyncio
async def test_api_key_create_stages_non_secret_event_before_commit(monkeypatch):
    from langflow.api.v1 import api_key

    events: list[str] = []
    service = _LifecycleService(events)
    user = SimpleNamespace(id=uuid4())
    created_key = SimpleNamespace(id=uuid4())
    session = AsyncMock()

    async def create_key(_session, _request, *, user_id):  # noqa: ARG001
        events.append("mutate")
        return created_key

    async def flush():
        events.append("flush")

    async def commit():
        events.append("commit")

    async def audit(**_kwargs):
        events.append("audit")

    session.flush.side_effect = flush
    session.commit.side_effect = commit
    monkeypatch.setattr(api_key, "create_api_key", create_key)
    monkeypatch.setattr(api_key, "get_authorization_service", lambda: service)
    monkeypatch.setattr(api_key, "audit_decision", audit)

    result = await api_key.create_api_key_route(
        req=SimpleNamespace(name="scoped-key"),
        db=session,
        current_user=user,
    )

    assert result is created_key
    assert events == ["mutate", "flush", "stage", "commit", "committed", "audit"]
    assert service.staged == service.committed
    mutation = service.staged[0]
    assert mutation.kind is AuthorizationMutationKind.API_KEY_CREATED
    assert mutation.entity_id == created_key.id
    assert mutation.affected_user_ids == (user.id,)
    assert set(mutation.policy_relevant_fields) == {"is_active", "expires_at"}


@pytest.mark.asyncio
async def test_api_key_create_stage_failure_rolls_back_without_exposing_plugin_detail(monkeypatch):
    from langflow.api.v1 import api_key

    events: list[str] = []
    service = _LifecycleService(events, fail_stage=True)
    user = SimpleNamespace(id=uuid4())
    created_key = SimpleNamespace(id=uuid4())
    session = AsyncMock()
    monkeypatch.setattr(api_key, "create_api_key", AsyncMock(return_value=created_key))
    monkeypatch.setattr(api_key, "get_authorization_service", lambda: service)

    with pytest.raises(HTTPException) as exc_info:
        await api_key.create_api_key_route(
            req=SimpleNamespace(name="scoped-key"),
            db=session,
            current_user=user,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to finalize API key creation."
    assert "policy compilation failed" not in exc_info.value.detail
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_assignment_delete_validates_live_row_before_mutation_and_stage(monkeypatch):
    from langflow.api.v1 import authz_role_assignments

    events: list[str] = []
    service = _LifecycleService(events)
    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    assignment = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        role_id=uuid4(),
        domain_type="global",
        domain_id=None,
    )
    session = SimpleNamespace()
    session.get = AsyncMock(side_effect=[actor, assignment])
    grant_result = SimpleNamespace(all=list)
    session.exec = AsyncMock(return_value=grant_result)
    session.delete = AsyncMock(side_effect=lambda _row: events.append("mutate"))
    session.flush = AsyncMock(side_effect=lambda: events.append("flush"))
    session.commit = AsyncMock(side_effect=lambda: events.append("commit"))

    async def audit(**_kwargs):
        events.append("audit")

    monkeypatch.setattr(authz_role_assignments, "get_authorization_service", lambda: service)
    monkeypatch.setattr(authz_role_assignments, "audit_decision", audit)

    await authz_role_assignments.delete_assignment(
        assignment_id=assignment.id,
        current_user=actor,
        session=session,
    )

    assert events == ["lock", "validate", "mutate", "flush", "stage", "commit", "committed", "audit"]
    assert service.validated == service.staged == service.committed
    assert len(service.staged) == 1
    assert len(service.lock_requests) == 1
    mutation = service.staged[0]
    assert mutation.kind is AuthorizationMutationKind.ROLE_ASSIGNMENT_DELETED
    assert mutation.entity_id == assignment.id
    assert mutation.affected_user_ids == (assignment.user_id,)
    assert mutation.domain_type == "global"
    assert mutation.domain_id is None


@pytest.mark.asyncio
async def test_assignment_delete_policy_rejection_is_409_without_mutation(monkeypatch):
    from langflow.api.v1 import authz_role_assignments

    events: list[str] = []
    service = _LifecycleService(events)
    actor = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    assignment = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        role_id=uuid4(),
        domain_type="global",
        domain_id=None,
    )
    session = SimpleNamespace()
    session.get = AsyncMock(side_effect=[actor, assignment])
    grant_result = SimpleNamespace(all=list)
    session.exec = AsyncMock(return_value=grant_result)
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def reject(*, session, mutation):  # noqa: ARG001
        events.append("validate")
        raise AuthorizationMutationRejected(_RECOVERY_DETAIL)

    service.validate_identity_mutation = reject
    monkeypatch.setattr(authz_role_assignments, "get_authorization_service", lambda: service)

    with pytest.raises(HTTPException) as exc_info:
        await authz_role_assignments.delete_assignment(
            assignment_id=assignment.id,
            current_user=actor,
            session=session,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == _RECOVERY_DETAIL
    assert events == ["lock", "validate"]
    session.delete.assert_not_awaited()
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()
