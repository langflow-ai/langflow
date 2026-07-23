"""Focused ordering tests for the OSS-to-plugin identity lifecycle seam."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from lfx.services.authorization import AuthorizationMutationKind, AuthorizationMutationRejected

_RECOVERY_DETAIL = "At least one recovery administrator is required."


class _LifecycleService:
    def __init__(self, events: list[str], *, fail_stage: bool = False) -> None:
        self.events = events
        self.fail_stage = fail_stage
        self.validated = []
        self.staged = []
        self.committed = []

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

    async def audit(**_kwargs):
        events.append("audit")

    auth_settings = SimpleNamespace(AUTO_LOGIN=False, ENABLE_SIGNUP=True, NEW_USER_IS_ACTIVE=True)
    monkeypatch.setattr(users, "get_settings_service", lambda: SimpleNamespace(auth_settings=auth_settings))
    monkeypatch.setattr(
        users,
        "get_auth_service",
        lambda: SimpleNamespace(get_password_hash=lambda _password: "hashed"),
    )
    monkeypatch.setattr(users, "get_or_create_default_folder", create_default_folder)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)
    monkeypatch.setattr(users, "audit_decision", audit)

    created = await users.add_user(
        user=UserCreate(username="new-user", password="not-a-real-password"),  # noqa: S106
        session=session,
        current_user=None,
    )

    assert events == ["mutate", "flush", "folder", "stage", "commit", "committed", "audit"]
    assert service.staged == service.committed
    mutation = service.staged[0]
    assert mutation.kind is AuthorizationMutationKind.USER_CREATED
    assert mutation.entity_id == created.id
    assert mutation.affected_user_ids == (created.id,)
    assert mutation.user_before is None
    assert mutation.user_after.is_active is True
    assert mutation.user_after.is_superuser is False


@pytest.mark.asyncio
async def test_user_disable_validates_and_stages_in_transaction_order(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.database.models.user.model import UserUpdate

    events: list[str] = []
    service = _LifecycleService(events)
    actor = SimpleNamespace(id=uuid4(), is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=True,
        password="hashed",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()

    async def update_user(_target, _update, _session):
        events.append("mutate")
        target.is_active = False
        return target

    async def commit():
        events.append("commit")

    session.commit.side_effect = commit
    monkeypatch.setattr(users, "get_user_by_id", AsyncMock(return_value=target))
    monkeypatch.setattr(users, "update_user", update_user)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)
    monkeypatch.setattr(users, "audit_decision", AsyncMock())

    result = await users.patch_user(
        user_id=target.id,
        user_update=UserUpdate(is_active=False),
        user=actor,
        session=session,
    )

    assert result is target
    assert events == ["validate", "mutate", "stage", "commit", "committed"]
    assert service.validated == service.staged == service.committed
    mutation = service.staged[0]
    assert mutation.kind is AuthorizationMutationKind.USER_DISABLED
    assert mutation.user_before.is_active is True
    assert mutation.user_after.is_active is False


@pytest.mark.asyncio
async def test_user_lifecycle_stage_failure_prevents_commit(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.database.models.user.model import UserUpdate

    events: list[str] = []
    service = _LifecycleService(events, fail_stage=True)
    actor = SimpleNamespace(id=uuid4(), is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=False,
        password="hashed",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()

    async def update_user(_target, _update, _session):
        events.append("mutate")
        return target

    monkeypatch.setattr(users, "get_user_by_id", AsyncMock(return_value=target))
    monkeypatch.setattr(users, "update_user", update_user)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)

    with pytest.raises(RuntimeError, match="policy compilation failed"):
        await users.patch_user(
            user_id=target.id,
            user_update=UserUpdate(is_active=False),
            user=actor,
            session=session,
        )

    assert events == ["validate", "mutate", "stage"]
    session.commit.assert_not_awaited()
    assert service.committed == []


@pytest.mark.asyncio
async def test_user_lifecycle_policy_rejection_is_409_without_mutation(monkeypatch):
    from langflow.api.v1 import users
    from langflow.services.database.models.user.model import UserUpdate

    events: list[str] = []
    service = _LifecycleService(events)
    actor = SimpleNamespace(id=uuid4(), is_superuser=True)
    target = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=True,
        password="hashed",  # noqa: S106  # pragma: allowlist secret
    )
    session = AsyncMock()
    update = AsyncMock()

    async def reject(*, session, mutation):  # noqa: ARG001
        events.append("validate")
        raise AuthorizationMutationRejected(_RECOVERY_DETAIL)

    service.validate_identity_mutation = reject
    monkeypatch.setattr(users, "get_user_by_id", AsyncMock(return_value=target))
    monkeypatch.setattr(users, "update_user", update)
    monkeypatch.setattr(users, "get_authorization_service", lambda: service)

    with pytest.raises(HTTPException) as exc_info:
        await users.patch_user(
            user_id=target.id,
            user_update=UserUpdate(is_active=False),
            user=actor,
            session=session,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == _RECOVERY_DETAIL
    assert events == ["validate"]
    update.assert_not_awaited()
    session.commit.assert_not_awaited()


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
    actor = SimpleNamespace(id=uuid4(), is_superuser=True)
    assignment = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        role_id=uuid4(),
        domain_type="global",
        domain_id=None,
    )
    session = SimpleNamespace()
    session.get = AsyncMock(return_value=assignment)
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

    assert events == ["validate", "mutate", "flush", "stage", "commit", "committed", "audit"]
    assert service.validated == service.staged == service.committed
    mutation = service.validated[0]
    assert mutation.kind is AuthorizationMutationKind.ROLE_ASSIGNMENT_DELETED
    assert mutation.domain_type == "global"
    assert mutation.domain_id is None


@pytest.mark.asyncio
async def test_assignment_delete_policy_rejection_is_409_without_mutation(monkeypatch):
    from langflow.api.v1 import authz_role_assignments

    events: list[str] = []
    service = _LifecycleService(events)
    actor = SimpleNamespace(id=uuid4(), is_superuser=True)
    assignment = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        role_id=uuid4(),
        domain_type="global",
        domain_id=None,
    )
    session = SimpleNamespace()
    session.get = AsyncMock(return_value=assignment)
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
    assert events == ["validate"]
    session.delete.assert_not_awaited()
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()
