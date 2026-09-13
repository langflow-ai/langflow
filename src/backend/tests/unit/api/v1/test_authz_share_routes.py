"""Route-level tests for the OSS share-administration owner floor."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Response
from langflow.api.v1 import authz_shares as shares_module
from langflow.api.v1.schemas.authz_shares import ShareCreate, ShareUpdate
from langflow.services.authorization.repository import ResourceRecord, ShareManagementScopes
from langflow.services.authorization.share_management import (
    ShareDeletionResult,
    ShareManagementError,
    ShareMutationResult,
)
from langflow.services.database.models.auth import AuthzShare, SharePermissionLevel, ShareScope
from lfx.services.authorization import BaseAuthorizationService, ShareRuleSnapshot
from lfx.services.authorization.service import AuthorizationService as LfxAuthorizationService

pytestmark = pytest.mark.no_blockbuster

_TEST_USERS: dict[UUID, SimpleNamespace] = {}


@pytest.fixture(autouse=True)
def native_collaboration_contract(monkeypatch):
    """Keep route tests focused while real service tests own DB invariants."""
    from langflow.services.authorization import fetch, guards
    from langflow.services.authorization.share_management import _validate_value_contract
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.file.model import File
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
    from langflow.services.database.models.memory_base.model import MemoryBase
    from langflow.services.database.models.variable.model import Variable

    _TEST_USERS.clear()
    for module in (fetch, guards):
        monkeypatch.setattr(module, "get_authorization_service", lambda: shares_module.get_authorization_service())

    async def ready_capabilities():
        return SimpleNamespace(
            collaboration_ready=True,
            conditional_writes_required=False,
        )

    model_by_resource = {
        "flow": Flow,
        "project": Folder,
        "deployment": Deployment,
        "knowledge_base": KnowledgeBaseRecord,
        "variable": Variable,
        "file": File,
    }

    async def resolve_resource(session, *, resource_type, resource_id, lock=False):  # noqa: ARG001
        model = model_by_resource.get(resource_type)
        row = await session.get(model, resource_id) if model is not None else None
        if row is None and resource_type == "knowledge_base":
            row = await session.get(MemoryBase, resource_id)
        if row is None:
            raise ShareManagementError(
                status_code=404,
                code="SHARE_RESOURCE_NOT_FOUND",
                message="Resource not found.",
            )
        project_id = getattr(row, "folder_id", None)
        if resource_type == "project":
            project_id = row.id
        elif resource_type == "deployment":
            project_id = getattr(row, "project_id", None)
        return ResourceRecord(
            resource_type=resource_type,
            resource_id=row.id,
            owner_id=row.user_id,
            project_id=project_id,
            workspace_id=getattr(row, "workspace_id", None),
            display_name=getattr(row, "name", getattr(row, "display_name", None)),
        )

    async def get_share(session, share_id):
        row = await session.get(AuthzShare, share_id)
        if row is None:
            raise ShareManagementError(status_code=404, code="SHARE_NOT_FOUND", message="Share not found.")
        resource = await resolve_resource(
            session,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
        )
        return row, resource

    async def create_share_transaction(
        session,
        *,
        actor_id,
        resource_type,
        resource_id,
        scope,
        target_id,
        permission_level,
    ):
        _validate_value_contract(
            resource_type=resource_type,
            scope=scope,
            permission_level=permission_level,
        )
        resource = await resolve_resource(
            session,
            resource_type=resource_type,
            resource_id=resource_id,
            lock=True,
        )
        row = AuthzShare(
            resource_type=resource_type,
            resource_id=resource_id,
            scope=scope,
            target_id=target_id,
            permission_level=permission_level,
            revision=1,
            created_by=actor_id,
        )
        session.add(row)
        session.store(row)
        await session.flush()
        return ShareMutationResult(row=row, resource=resource, changed=True)

    async def update_share_transaction(
        session,
        *,
        actor_id,  # noqa: ARG001
        share_id,
        permission_level,
        if_match,  # noqa: ARG001
        precondition_required,  # noqa: ARG001
    ):
        row, resource = await get_share(session, share_id)
        _validate_value_contract(
            resource_type=row.resource_type,
            scope=row.scope,
            permission_level=permission_level,
        )
        changed = row.permission_level != permission_level
        if changed:
            row.permission_level = permission_level
            row.revision += 1
            session.add(row)
            await session.flush()
        return ShareMutationResult(row=row, resource=resource, changed=changed)

    async def delete_share_transaction(
        session,
        *,
        actor_id,  # noqa: ARG001
        share_id,
        if_match,  # noqa: ARG001
        precondition_required,  # noqa: ARG001
    ):
        row, resource = await get_share(session, share_id)
        snapshot = ShareRuleSnapshot(
            share_id=row.id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            scope=row.scope,
            target_id=row.target_id,
            permission_level=row.permission_level,
        )
        await session.delete(row)
        await session.flush()
        return ShareDeletionResult(snapshot=snapshot, resource=resource)

    async def load_active_user(_session, user_id):
        user = _TEST_USERS.get(user_id)
        return user if user is not None and user.is_active is True else None

    async def empty_management_scopes(*_args, **_kwargs):
        return ShareManagementScopes()

    async def can_manage_resource_shares(_session, *, user, **_kwargs):
        return user.is_superuser is True

    monkeypatch.setattr(shares_module, "discover_collaboration_capabilities", ready_capabilities)
    monkeypatch.setattr(shares_module, "resolve_resource_for_share", resolve_resource)
    monkeypatch.setattr(shares_module, "get_share_for_authorization", get_share)
    monkeypatch.setattr(shares_module, "create_share_transaction", create_share_transaction)
    monkeypatch.setattr(shares_module, "update_share_transaction", update_share_transaction)
    monkeypatch.setattr(shares_module, "delete_share_transaction", delete_share_transaction)
    monkeypatch.setattr(shares_module, "load_active_user", load_active_user)
    monkeypatch.setattr(shares_module, "share_management_scopes", empty_management_scopes)
    monkeypatch.setattr(shares_module, "user_can_manage_resource_shares", can_manage_resource_shares)


class _FakeAsyncSession:
    """Minimal async-session stand-in: stores get() results and records writes."""

    def __init__(self, get_by_type: dict[tuple[type, UUID], Any] | None = None) -> None:
        self._get_by_type = get_by_type or {}
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushed = 0
        self.committed = 0
        self.rolled_back = 0
        self.events: list[str] = []

    async def get(self, model: type, key: UUID) -> Any:
        return self._get_by_type.get((model, key))

    def store(self, obj: Any) -> None:
        self._get_by_type[(type(obj), obj.id)] = obj

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        self.flushed += 1
        self.events.append("flush")

    async def commit(self) -> None:
        self.committed += 1
        self.events.append("commit")

    async def refresh(self, obj: Any) -> None:  # noqa: ARG002
        return None

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def exec(self, _stmt: Any) -> _ExecResult:
        # Match SQLModel's result shape so column-pair serialization is real.
        return _ExecResult([])


class _StubAuthz(BaseAuthorizationService):
    """Pass-through authz service: allow everything, no cross-user fetch."""

    def __init__(self, *, cross_user: bool = False, enabled: bool = False, allow: bool = True) -> None:
        self._cross_user = cross_user
        self._enabled = enabled
        self._allow = allow
        self.enforce_calls: list[dict] = []
        self.invalidated_users: list[UUID] = []
        self.invalidate_all_calls = 0
        self.sync_shares_calls = 0
        self.events: list[str] = []

    async def supports_cross_user_fetch(self) -> bool:
        return self._cross_user

    async def is_enabled(self) -> bool:
        return self._enabled

    async def enforce(self, **kwargs) -> bool:
        self.enforce_calls.append(kwargs)
        return self._allow

    async def batch_enforce(self, **kwargs) -> list[bool]:
        return [self._allow] * len(kwargs.get("requests", []))

    async def invalidate_user(self, user_id: UUID, *_args, **_kwargs) -> None:
        self.invalidated_users.append(user_id)
        self.events.append("invalidate_user")

    async def invalidate_all(self, *_args, **_kwargs) -> None:
        self.invalidate_all_calls += 1
        self.events.append("invalidate_all")


class _SyncingAuthz(_StubAuthz):
    async def sync_shares(self) -> None:
        self.sync_shares_calls += 1
        self.events.append("sync_shares")


class _TargetedAuthz(_SyncingAuthz):
    def __init__(self, *, targeted_raises: bool = False, coarse_raises: bool = False) -> None:
        super().__init__()
        self.targeted_raises = targeted_raises
        self.coarse_raises = coarse_raises
        self.synced_share_ids: list[UUID] = []
        self.removed_snapshots: list[ShareRuleSnapshot] = []

    async def sync_share(self, share_id: UUID) -> None:
        self.synced_share_ids.append(share_id)
        self.events.append("sync_share")
        if self.targeted_raises:
            msg = "targeted sync failed"
            raise RuntimeError(msg)

    async def remove_share_rules(self, snapshot: ShareRuleSnapshot) -> None:
        self.removed_snapshots.append(snapshot)
        self.events.append("remove_share_rules")
        if self.targeted_raises:
            msg = "targeted removal failed"
            raise RuntimeError(msg)

    async def sync_shares(self) -> None:
        self.sync_shares_calls += 1
        self.events.append("sync_shares")
        if self.coarse_raises:
            msg = "coarse sync failed"
            raise RuntimeError(msg)


class _HangingTargetedAuthz(_TargetedAuthz):
    async def sync_share(self, share_id: UUID) -> None:
        self.synced_share_ids.append(share_id)
        self.events.append("sync_share")
        await asyncio.Event().wait()

    async def remove_share_rules(self, snapshot: ShareRuleSnapshot) -> None:
        self.removed_snapshots.append(snapshot)
        self.events.append("remove_share_rules")
        await asyncio.Event().wait()


class _HangingCoarseAuthz(_SyncingAuthz):
    async def sync_shares(self) -> None:
        self.sync_shares_calls += 1
        self.events.append("sync_shares")
        await asyncio.Event().wait()


class _HangingInvalidationAuthz(_StubAuthz):
    async def invalidate_user(self, user_id: UUID, *_args, **_kwargs) -> None:
        self.invalidated_users.append(user_id)
        self.events.append("invalidate_user")
        await asyncio.Event().wait()


@pytest.fixture
def patch_authz(monkeypatch):
    """Install a stub authz service into the shares module and the split helper modules."""
    from langflow.services.authorization import audit as authz_audit
    from langflow.services.authorization import guards as authz_guards
    from langflow.services.authorization import listing as authz_listing

    def _apply(*, cross_user: bool = False, enabled: bool = False, allow: bool = True) -> _StubAuthz:
        stub = _StubAuthz(cross_user=cross_user, enabled=enabled, allow=allow)
        monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
        for module in (authz_guards, authz_listing):
            monkeypatch.setattr(module, "get_authorization_service", lambda: stub)
        # Mirror the requested AUTHZ_ENABLED state so the guard's early-return
        # only fires under OSS. Audit is always off so we don't open real
        # sessions for background writes.
        settings = SimpleNamespace(
            auth_settings=SimpleNamespace(AUTHZ_ENABLED=enabled, AUTHZ_AUDIT_ENABLED=False),
        )
        for module in (authz_audit, authz_guards, authz_listing):
            monkeypatch.setattr(module, "get_settings_service", lambda s=settings: s)
        return stub

    return _apply


@pytest.fixture
def silence_audit(monkeypatch):
    """Replace audit_decision with a no-op so we don't spawn background tasks."""

    async def _noop(**_kwargs):
        return None

    monkeypatch.setattr(shares_module, "audit_decision", _noop)


def _make_user(*, is_superuser: bool = False) -> SimpleNamespace:
    user = SimpleNamespace(
        id=uuid4(),
        is_superuser=is_superuser,
        is_active=True,
        username="u",
        profile_image=None,
    )
    _TEST_USERS[user.id] = user
    return user


def _make_flow_owned_by(owner_id: UUID) -> Any:
    from langflow.services.database.models.flow.model import Flow

    return SimpleNamespace(_model=Flow, id=uuid4(), user_id=owner_id)


def _payload_for(resource_id: UUID) -> ShareCreate:
    return ShareCreate(
        resource_type="flow",
        resource_id=resource_id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
    )


async def test_memory_base_resolves_as_knowledge_base_resource_owner():
    from langflow.services.database.models.memory_base.model import MemoryBase

    owner_id = uuid4()
    memory_base_id = uuid4()
    memory_base = SimpleNamespace(id=memory_base_id, user_id=owner_id)
    session = _FakeAsyncSession({(MemoryBase, memory_base_id): memory_base})

    resolved = await shares_module._resolve_resource_owner(
        session,
        resource_type="knowledge_base",
        resource_id=memory_base_id,
    )

    assert resolved == owner_id


# --------------------------------------------------------------------------- #
# CREATE — OSS floor must block non-owner / non-superuser
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_create_share_blocks_non_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """An OSS-floor deny is indistinguishable from a missing resource."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    attacker = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(payload=payload, current_user=attacker, session=session)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Resource not found"
    # Floor fires before any DB write — no share row was added.
    assert session.added == []


@pytest.mark.asyncio
async def test_create_share_allows_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """The resource owner can mint a share row under OSS pass-through."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    result = await shares_module.create_share(payload=payload, current_user=owner, session=session)

    assert result.resource_id == flow.id
    assert len(session.added) == 1
    assert session.flushed == 1
    assert session.committed == 1


@pytest.mark.asyncio
async def test_create_share_commits_before_policy_refresh(patch_authz, silence_audit):  # noqa: ARG001
    """Policy refresh happens only after the authz_share row is committed."""
    from langflow.services.database.models.flow.model import Flow

    stub = patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    stub.events = session.events

    await shares_module.create_share(payload=_payload_for(flow.id), current_user=owner, session=session)

    assert session.events == ["flush", "commit", "invalidate_user"]


@pytest.mark.asyncio
async def test_create_share_prefers_targeted_sync_after_commit(monkeypatch, silence_audit):  # noqa: ARG001
    from langflow.services.database.models.flow.model import Flow

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    stub = _TargetedAuthz()
    stub.events = session.events
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)

    result = await shares_module.create_share(payload=_payload_for(flow.id), current_user=owner, session=session)

    assert stub.synced_share_ids == [result.id]
    assert session.events == ["flush", "commit", "sync_share"]
    assert stub.sync_shares_calls == 0
    assert stub.invalidated_users == []


@pytest.mark.asyncio
async def test_create_share_allows_superuser_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """A superuser can mint a share row for a resource they don't own."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    admin = _make_user(is_superuser=True)
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    result = await shares_module.create_share(payload=payload, current_user=admin, session=session)

    assert result.resource_id == flow.id
    assert len(session.added) == 1
    assert session.committed == 1


@pytest.mark.asyncio
async def test_create_share_returns_404_when_resource_missing(patch_authz, silence_audit):  # noqa: ARG001
    """A missing resource yields 404 — not 403 — to preserve UUID privacy."""
    patch_authz(cross_user=False, enabled=False)

    attacker = _make_user()
    session = _FakeAsyncSession({})  # no resource present
    payload = _payload_for(uuid4())

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(payload=payload, current_user=attacker, session=session)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Resource not found"


@pytest.mark.parametrize(
    "permission_level",
    [
        SharePermissionLevel.READ.value,
        SharePermissionLevel.WRITE.value,
        SharePermissionLevel.ADMIN.value,
    ],
)
@pytest.mark.asyncio
async def test_create_share_rejects_non_executable_public_flow(permission_level, patch_authz, silence_audit):  # noqa: ARG001
    """The public flow product is an executable playground, not a generic anonymous grant."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = ShareCreate(
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.PUBLIC.value,
        permission_level=permission_level,
    )

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(payload=payload, current_user=owner, session=session)

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == {
        "code": "SHARE_PUBLIC_FLOW_EXECUTE_REQUIRED",
        "message": "Public flow shares require execute permission.",
    }
    assert session.added == []
    assert session.flushed == 0


@pytest.mark.asyncio
async def test_create_share_allows_executable_public_flow(patch_authz, silence_audit):  # noqa: ARG001
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = ShareCreate(
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.PUBLIC.value,
        permission_level=SharePermissionLevel.EXECUTE.value,
    )

    result = await shares_module.create_share(payload=payload, current_user=owner, session=session)

    assert result.permission_level == SharePermissionLevel.EXECUTE.value
    assert session.flushed == 1
    assert session.committed == 1


@pytest.mark.asyncio
async def test_create_share_keeps_public_read_for_non_flow_resources(patch_authz, silence_audit):  # noqa: ARG001
    from langflow.services.database.models.file.model import File

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    file = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(File, file.id): file})
    payload = ShareCreate(
        resource_type="file",
        resource_id=file.id,
        scope=ShareScope.PUBLIC.value,
        permission_level=SharePermissionLevel.READ.value,
    )

    result = await shares_module.create_share(payload=payload, current_user=owner, session=session)

    assert result.permission_level == SharePermissionLevel.READ.value
    assert session.flushed == 1
    assert session.committed == 1


# --------------------------------------------------------------------------- #
# PATCH — same floor
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_update_share_blocks_non_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """A non-owner cannot PATCH a share on another user's resource under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    attacker = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=attacker.id,  # attacker is even the creator — floor still blocks
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    update = ShareUpdate(permission_level=SharePermissionLevel.WRITE.value)

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.update_share(
            share_id=share.id,
            payload=update,
            current_user=attacker,
            session=session,
            response=Response(),
        )

    assert excinfo.value.status_code == 404
    # PATCH was rejected — no flush should have happened.
    assert session.flushed == 0


@pytest.mark.asyncio
async def test_update_share_allows_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """The resource owner can PATCH a share on their resource under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    update = ShareUpdate(permission_level=SharePermissionLevel.WRITE.value)

    result = await shares_module.update_share(
        share_id=share.id,
        payload=update,
        current_user=owner,
        session=session,
        response=Response(),
    )

    assert result.permission_level == SharePermissionLevel.WRITE.value
    assert session.flushed == 1
    assert session.committed == 1


@pytest.mark.asyncio
async def test_update_share_prefers_targeted_sync_after_commit(monkeypatch, silence_audit):  # noqa: ARG001
    from langflow.services.database.models.flow.model import Flow

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    stub = _TargetedAuthz()
    stub.events = session.events
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)

    await shares_module.update_share(
        share_id=share.id,
        payload=ShareUpdate(permission_level=SharePermissionLevel.WRITE.value),
        current_user=owner,
        session=session,
        response=Response(),
    )

    assert stub.synced_share_ids == [share.id]
    assert session.events == ["flush", "commit", "sync_share"]
    assert stub.sync_shares_calls == 0


@pytest.mark.parametrize(
    "permission_level",
    [
        SharePermissionLevel.READ.value,
        SharePermissionLevel.WRITE.value,
        SharePermissionLevel.ADMIN.value,
    ],
)
@pytest.mark.asyncio
async def test_update_share_rejects_non_executable_public_flow(permission_level, patch_authz, silence_audit):  # noqa: ARG001
    """PATCH cannot turn a PUBLIC flow share into a grant with no matching product behavior."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.PUBLIC.value,
        target_id=None,
        permission_level=SharePermissionLevel.EXECUTE.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.update_share(
            share_id=share.id,
            payload=ShareUpdate(permission_level=permission_level),
            current_user=owner,
            session=session,
            response=Response(),
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == {
        "code": "SHARE_PUBLIC_FLOW_EXECUTE_REQUIRED",
        "message": "Public flow shares require execute permission.",
    }
    assert share.permission_level == SharePermissionLevel.EXECUTE.value
    assert session.flushed == 0


@pytest.mark.asyncio
async def test_update_share_allows_executable_public_flow(patch_authz, silence_audit):  # noqa: ARG001
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.PUBLIC.value,
        target_id=None,
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})

    result = await shares_module.update_share(
        share_id=share.id,
        payload=ShareUpdate(permission_level=SharePermissionLevel.EXECUTE.value),
        current_user=owner,
        session=session,
        response=Response(),
    )

    assert result.permission_level == SharePermissionLevel.EXECUTE.value
    assert session.flushed == 1
    assert session.committed == 1


# --------------------------------------------------------------------------- #
# DELETE — same floor
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_delete_share_blocks_non_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """A non-owner cannot DELETE a share on another user's resource under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    attacker = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=attacker.id,  # attacker created it but is not the resource owner
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.delete_share(share_id=share.id, current_user=attacker, session=session)

    assert excinfo.value.status_code == 404
    # The floor blocks before the DELETE.
    assert session.deleted == []


@pytest.mark.asyncio
async def test_delete_share_allows_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """The resource owner can DELETE a share on their resource under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})

    await shares_module.delete_share(share_id=share.id, current_user=owner, session=session)

    assert len(session.deleted) == 1
    assert session.committed == 1


@pytest.mark.asyncio
async def test_delete_share_snapshots_then_removes_targeted_rules_after_commit(monkeypatch, silence_audit):  # noqa: ARG001
    from langflow.services.database.models.flow.model import Flow

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.TEAM.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.WRITE.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    stub = _TargetedAuthz()
    stub.events = session.events
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)

    await shares_module.delete_share(share_id=share.id, current_user=owner, session=session)

    assert session.events == ["flush", "commit", "remove_share_rules"]
    assert stub.removed_snapshots == [
        ShareRuleSnapshot(
            share_id=share.id,
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.TEAM.value,
            target_id=share.target_id,
            permission_level=SharePermissionLevel.WRITE.value,
        )
    ]
    assert stub.sync_shares_calls == 0


@pytest.mark.parametrize("mutation", ["create", "update", "delete"])
@pytest.mark.asyncio
async def test_share_mutations_reauthorize_inside_each_lock_retry(
    mutation,
    monkeypatch,
    patch_authz,
    silence_audit,  # noqa: ARG001
):
    """Every fresh retry transaction must rebuild policy and audit state."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)
    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    authorization_sessions = []
    original_authorize = shares_module._authorize_resource

    async def tracked_authorize(**kwargs):
        authorization_sessions.append(kwargs.get("audit_session"))
        await original_authorize(**kwargs)

    class RetryOnceError(RuntimeError):
        pass

    transaction_name = f"{mutation}_share_transaction"
    original_transaction = getattr(shares_module, transaction_name)
    transaction_attempts = 0

    async def flaky_transaction(*args, **kwargs):
        nonlocal transaction_attempts
        transaction_attempts += 1
        if transaction_attempts == 1:
            raise RetryOnceError
        return await original_transaction(*args, **kwargs)

    async def force_one_retry(operation, *, session, description):  # noqa: ARG001
        try:
            await operation(0)
        except RetryOnceError:
            await session.rollback()
        return await operation(1)

    monkeypatch.setattr(shares_module, "_authorize_resource", tracked_authorize)
    monkeypatch.setattr(shares_module, transaction_name, flaky_transaction)
    monkeypatch.setattr(shares_module, "run_with_lock_retry", force_one_retry)

    if mutation == "create":
        await shares_module.create_share(payload=_payload_for(flow.id), current_user=owner, session=session)
    elif mutation == "update":
        await shares_module.update_share(
            share_id=share.id,
            payload=ShareUpdate(permission_level=SharePermissionLevel.WRITE.value),
            current_user=owner,
            session=session,
            response=Response(),
        )
    else:
        await shares_module.delete_share(share_id=share.id, current_user=owner, session=session)

    assert transaction_attempts == 2
    assert authorization_sessions == [session, session]
    assert session.rolled_back == 1
    assert session.committed == 1


# --------------------------------------------------------------------------- #
# Floor behavior when the authorization plugin is active
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_floor_is_skipped_when_plugin_active(patch_authz, silence_audit):  # noqa: ARG001
    """OSS floor is skipped when the authorization plugin is actively enforcing.

    When supports_cross_user_fetch=True AND AUTHZ_ENABLED=true, the OSS floor
    is skipped so a plugin-granted share:create role can administer shares on
    another user's resource. ``ensure_resource_share_administration``
    becomes the authoritative check.
    """
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    delegate = _make_user()  # non-owner, but allowed by plugin policy
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    result = await shares_module.create_share(payload=payload, current_user=delegate, session=session)

    # The floor is skipped; the stub authz allows the operation; the row is
    # written. If the floor still fired we'd see a 403 instead.
    assert result.resource_id == flow.id
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_create_share_invokes_plugin_enforce_for_non_owner(patch_authz, silence_audit):  # noqa: ARG001
    """Regression: plugin enforce() must run for non-owner share-create.

    Previously ``create_share`` passed ``share_user_id=current_user.id`` which
    tripped the owner-override fast path in the generic share guard and
    the plugin was never consulted — letting any authenticated user mint share
    rows once the OSS floor was bypassed.  The fix passes the *resource*
    owner so only the resource owner gets the override.
    """
    from langflow.services.database.models.flow.model import Flow

    stub = patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    delegate = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    await shares_module.create_share(payload=payload, current_user=delegate, session=session)

    # enforce() was actually called for the non-owner.
    assert any(call.get("user_id") == delegate.id for call in stub.enforce_calls), (
        f"expected at least one enforce() call for delegate, got: {stub.enforce_calls}"
    )


@pytest.mark.asyncio
async def test_create_share_denied_when_plugin_denies_non_owner(patch_authz, silence_audit):  # noqa: ARG001
    """A plugin deny on share-create must preserve resource UUID privacy."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True, allow=False)

    owner = _make_user()
    delegate = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(payload=payload, current_user=delegate, session=session)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Resource not found"
    assert session.added == []


@pytest.mark.asyncio
async def test_create_share_preserves_non_403_permission_errors(monkeypatch, patch_authz, silence_audit):  # noqa: ARG001
    """Only permission denies are masked; unexpected guard errors stay intact."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True)

    async def _raise_service_error(*_args, **_kwargs):
        raise HTTPException(status_code=503, detail="Authorization service unavailable")

    monkeypatch.setattr(shares_module, "ensure_resource_share_administration", _raise_service_error)

    owner = _make_user()
    delegate = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(
            payload=_payload_for(flow.id),
            current_user=delegate,
            session=session,
        )

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "Authorization service unavailable"
    assert session.added == []


@pytest.mark.asyncio
async def test_update_share_invokes_plugin_enforce_for_share_creator(patch_authz, silence_audit):  # noqa: ARG001
    """Regression: share *creator* who is not the resource owner must hit plugin enforce()."""
    from langflow.services.database.models.flow.model import Flow

    stub = patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    delegate = _make_user()  # not the resource owner, but is the share row creator
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=delegate.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    update = ShareUpdate(permission_level=SharePermissionLevel.WRITE.value)

    await shares_module.update_share(
        share_id=share.id,
        payload=update,
        current_user=delegate,
        session=session,
        response=Response(),
    )

    assert any(call.get("user_id") == delegate.id for call in stub.enforce_calls), (
        f"expected plugin enforce() to run for share creator non-owner, got: {stub.enforce_calls}"
    )


@pytest.mark.asyncio
async def test_delete_share_denied_when_plugin_denies_share_creator(patch_authz, silence_audit):  # noqa: ARG001
    """Regression: share creator can no longer bypass plugin policy on DELETE."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True, allow=False)

    owner = _make_user()
    delegate = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=delegate.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.delete_share(share_id=share.id, current_user=delegate, session=session)

    assert excinfo.value.status_code == 404
    assert session.deleted == []


# --------------------------------------------------------------------------- #
# Visibility predicate — owner / creator / PUBLIC / USER / TEAM / PRIVATE
# --------------------------------------------------------------------------- #


def _share(*, scope: str, target_id: UUID | None, created_by: UUID) -> AuthzShare:
    return AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=uuid4(),
        scope=scope,
        target_id=target_id,
        permission_level=SharePermissionLevel.READ.value,
        created_by=created_by,
    )


def test_share_visible_owner_but_not_creator_without_current_authority():
    """Creator status alone never becomes durable share-management authority."""
    owner = uuid4()
    creator = uuid4()
    # PRIVATE row owned by `owner`, created by `creator`.
    row = _share(scope=ShareScope.PRIVATE.value, target_id=None, created_by=creator)
    assert shares_module._share_visible(row=row, user_id=owner, resource_owner_id=owner, is_team_member=False)
    assert not shares_module._share_visible(row=row, user_id=creator, resource_owner_id=owner, is_team_member=False)


def test_share_visible_public_is_direct_link_only():
    owner = uuid4()
    creator = uuid4()
    row = _share(scope=ShareScope.PUBLIC.value, target_id=None, created_by=creator)
    assert shares_module._share_visible(row=row, user_id=owner, resource_owner_id=owner, is_team_member=False)
    assert not shares_module._share_visible(
        row=row,
        user_id=creator,
        resource_owner_id=owner,
        is_team_member=False,
    )
    assert not shares_module._share_visible(
        row=row,
        user_id=uuid4(),
        resource_owner_id=uuid4(),
        is_team_member=False,
    )


def test_share_visible_user_scope_matches_target_only():
    target = uuid4()
    row = _share(scope=ShareScope.USER.value, target_id=target, created_by=uuid4())
    assert shares_module._share_visible(row=row, user_id=target, resource_owner_id=uuid4(), is_team_member=False)
    # A different user (not owner/creator/target) cannot see it.
    assert not shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=False)


def test_share_visible_team_scope_follows_membership_flag():
    row = _share(scope=ShareScope.TEAM.value, target_id=uuid4(), created_by=uuid4())
    assert shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=True)
    assert not shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=False)


def test_share_visible_private_hidden_from_non_owner():
    row = _share(scope=ShareScope.PRIVATE.value, target_id=None, created_by=uuid4())
    assert not shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=True)


# --------------------------------------------------------------------------- #
# Cache invalidation contract — USER scope targets the user; others drop all
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_invalidate_for_share_user_scope_targets_user(patch_authz):
    stub = patch_authz(cross_user=False, enabled=False)
    target = uuid4()
    await shares_module._invalidate_for_share(ShareScope.USER.value, target)
    assert stub.invalidated_users == [target]
    assert stub.invalidate_all_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scope", "target_id"),
    [
        (ShareScope.PUBLIC.value, None),
        (ShareScope.TEAM.value, "team"),
        (ShareScope.PRIVATE.value, None),
    ],
)
async def test_invalidate_for_share_non_user_scope_invalidates_all(patch_authz, scope, target_id):
    stub = patch_authz(cross_user=False, enabled=False)
    resolved = uuid4() if target_id == "team" else None
    await shares_module._invalidate_for_share(scope, resolved)
    assert stub.invalidate_all_calls == 1
    assert stub.invalidated_users == []


@pytest.mark.asyncio
async def test_refresh_policy_for_share_prefers_sync_shares(monkeypatch):
    """A plugin-provided share sync hook runs instead of the legacy invalidate path."""
    stub = _SyncingAuthz()
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)

    await shares_module._refresh_policy_for_share(uuid4(), ShareScope.USER.value, uuid4(), op="share:test")

    assert stub.sync_shares_calls == 1
    assert stub.invalidated_users == []
    assert stub.invalidate_all_calls == 0


@pytest.mark.asyncio
async def test_refresh_policy_skips_inherited_base_noop_hooks(monkeypatch):
    """Inherited no-op targeted/coarse methods must not suppress safe invalidation."""

    class _BaseHooksOnly(LfxAuthorizationService):
        def __init__(self) -> None:
            super().__init__()
            self.invalidated_users = []

        async def invalidate_user(self, user_id: UUID) -> None:
            self.invalidated_users.append(user_id)

    stub = _BaseHooksOnly()
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
    target_id = uuid4()

    await shares_module._refresh_policy_for_share(uuid4(), ShareScope.USER.value, target_id, op="share:test")

    assert stub.invalidated_users == [target_id]


@pytest.mark.asyncio
async def test_targeted_sync_failure_falls_back_to_coarse_sync(monkeypatch):
    stub = _TargetedAuthz(targeted_raises=True)
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)

    share_id = uuid4()
    await shares_module._refresh_policy_for_share(share_id, ShareScope.USER.value, uuid4(), op="share:test")

    assert stub.synced_share_ids == [share_id]
    assert stub.events == ["sync_share", "sync_shares"]
    assert stub.invalidated_users == []


async def test_targeted_sync_timeout_falls_back_to_coarse_sync(monkeypatch):
    stub = _HangingTargetedAuthz()
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
    monkeypatch.setattr(shares_module, "_SHARE_POLICY_HOOK_TIMEOUT_SECONDS", 0.01)

    share_id = uuid4()
    await shares_module._refresh_policy_for_share(share_id, ShareScope.USER.value, uuid4(), op="share:test")

    assert stub.synced_share_ids == [share_id]
    assert stub.events == ["sync_share", "sync_shares"]
    assert stub.invalidated_users == []


async def test_coarse_sync_timeout_falls_back_to_invalidation(monkeypatch):
    stub = _HangingCoarseAuthz()
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
    monkeypatch.setattr(shares_module, "_SHARE_POLICY_HOOK_TIMEOUT_SECONDS", 0.01)
    target_id = uuid4()

    await shares_module._refresh_policy_for_share(uuid4(), ShareScope.USER.value, target_id, op="share:test")

    assert stub.events == ["sync_shares", "invalidate_user"]
    assert stub.invalidated_users == [target_id]


async def test_invalidation_timeout_does_not_block_share_write(monkeypatch):
    stub = _HangingInvalidationAuthz()
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
    monkeypatch.setattr(shares_module, "_SHARE_POLICY_HOOK_TIMEOUT_SECONDS", 0.01)
    target_id = uuid4()

    await shares_module._refresh_policy_for_share(uuid4(), ShareScope.USER.value, target_id, op="share:test")

    assert stub.events == ["invalidate_user", "invalidate_all"]
    assert stub.invalidated_users == [target_id]
    assert stub.invalidate_all_calls == 1


@pytest.mark.asyncio
async def test_targeted_and_coarse_sync_failure_falls_back_to_invalidation(monkeypatch):
    stub = _TargetedAuthz(targeted_raises=True, coarse_raises=True)
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)

    target_id = uuid4()
    await shares_module._refresh_policy_for_share(uuid4(), ShareScope.USER.value, target_id, op="share:test")

    assert stub.events == ["sync_share", "sync_shares", "invalidate_user"]
    assert stub.invalidated_users == [target_id]


@pytest.mark.asyncio
async def test_targeted_remove_failure_falls_back_to_coarse_sync(monkeypatch):
    stub = _TargetedAuthz(targeted_raises=True)
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
    snapshot = ShareRuleSnapshot(
        share_id=uuid4(),
        resource_type="flow",
        resource_id=uuid4(),
        scope=ShareScope.PUBLIC.value,
        target_id=None,
        permission_level=SharePermissionLevel.READ.value,
    )

    await shares_module._remove_policy_for_share(snapshot, op="share:delete")

    assert stub.removed_snapshots == [snapshot]
    assert stub.events == ["remove_share_rules", "sync_shares"]
    assert stub.invalidate_all_calls == 0


async def test_targeted_remove_timeout_falls_back_to_coarse_sync(monkeypatch):
    stub = _HangingTargetedAuthz()
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
    monkeypatch.setattr(shares_module, "_SHARE_POLICY_HOOK_TIMEOUT_SECONDS", 0.01)
    snapshot = ShareRuleSnapshot(
        share_id=uuid4(),
        resource_type="flow",
        resource_id=uuid4(),
        scope=ShareScope.PUBLIC.value,
        target_id=None,
        permission_level=SharePermissionLevel.READ.value,
    )

    await shares_module._remove_policy_for_share(snapshot, op="share:delete")

    assert stub.removed_snapshots == [snapshot]
    assert stub.events == ["remove_share_rules", "sync_shares"]
    assert stub.invalidate_all_calls == 0


@pytest.mark.asyncio
async def test_targeted_and_coarse_remove_failure_falls_back_to_invalidation(monkeypatch):
    stub = _TargetedAuthz(targeted_raises=True, coarse_raises=True)
    monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
    target_id = uuid4()
    snapshot = ShareRuleSnapshot(
        share_id=uuid4(),
        resource_type="flow",
        resource_id=uuid4(),
        scope=ShareScope.USER.value,
        target_id=target_id,
        permission_level=SharePermissionLevel.READ.value,
    )

    await shares_module._remove_policy_for_share(snapshot, op="share:delete")

    assert stub.events == ["remove_share_rules", "sync_shares", "invalidate_user"]
    assert stub.invalidated_users == [target_id]


# --------------------------------------------------------------------------- #
# TEAM-scope reachability through get_share / list_shares
# --------------------------------------------------------------------------- #


class _ExecResult:
    """Result wrapper supporting the .first()/iteration shapes the routes use."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = list(rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class _QueueSession(_FakeAsyncSession):
    """``_FakeAsyncSession`` whose exec() returns queued result-sets in order."""

    def __init__(self, get_by_type: dict[tuple[type, UUID], Any] | None = None, *, exec_queue=None) -> None:
        super().__init__(get_by_type)
        self._exec_queue = [list(rows) for rows in (exec_queue or [])]
        self.statements: list[Any] = []

    async def exec(self, stmt: Any) -> _ExecResult:
        self.statements.append(stmt)
        rows = self._exec_queue.pop(0) if self._exec_queue else []
        return _ExecResult(rows)


def test_team_share_visibility_query_requires_active_team():
    statement = shares_module._active_team_ids_for_user(uuid4())
    sql = str(statement).lower()

    assert "join authz_team" in sql
    assert "authz_team.is_active = true" in sql
    assert '"user".is_active = true' in sql
    assert "exists" in sql
    assert "admin" in statement.compile().params.values()


@pytest.mark.asyncio
async def test_team_share_visibility_query_requires_an_active_admin():
    from langflow.services.database.models.auth import AuthzTeam, AuthzTeamMember, TeamRole
    from langflow.services.database.models.user.model import User
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: SQLModel.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, AuthzTeam.__table__, AuthzTeamMember.__table__],
                )
            )

        actor = User(username="actor", password=str(uuid4()), is_active=True)
        active_admin = User(username="active-admin", password=str(uuid4()), is_active=True)
        inactive_admin = User(username="inactive-admin", password=str(uuid4()), is_active=False)
        valid_team = AuthzTeam(team_name="Valid", adom_name="valid")
        no_admin_team = AuthzTeam(team_name="No admin", adom_name="no-admin")
        inactive_admin_team = AuthzTeam(team_name="Inactive admin", adom_name="inactive-admin")

        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add_all([actor, active_admin, inactive_admin, valid_team, no_admin_team, inactive_admin_team])
            await session.flush()
            session.add_all(
                [
                    AuthzTeamMember(team_id=valid_team.id, user_id=actor.id),
                    AuthzTeamMember(
                        team_id=valid_team.id,
                        user_id=active_admin.id,
                        role=TeamRole.ADMIN.value,
                    ),
                    AuthzTeamMember(team_id=no_admin_team.id, user_id=actor.id),
                    AuthzTeamMember(team_id=inactive_admin_team.id, user_id=actor.id),
                    AuthzTeamMember(
                        team_id=inactive_admin_team.id,
                        user_id=inactive_admin.id,
                        role=TeamRole.ADMIN.value,
                    ),
                ]
            )
            await session.commit()

            team_ids = set((await session.exec(shares_module._active_team_ids_for_user(actor.id))).all())

        assert team_ids == {valid_team.id}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_share_team_member_can_see(patch_authz, silence_audit):  # noqa: ARG001
    """A team member (neither owner nor creator) can read a TEAM-scope share."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    creator = _make_user()
    viewer = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.TEAM.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=creator.id,
    )
    # Membership query returns one row → viewer is a team member.
    session = _QueueSession({(AuthzShare, share.id): share, (Flow, flow.id): flow}, exec_queue=[[SimpleNamespace()]])

    result = await shares_module.get_share(
        share_id=share.id,
        current_user=viewer,
        session=session,
        response=Response(),
    )
    assert result.id == share.id


@pytest.mark.asyncio
async def test_get_share_team_non_member_gets_404(patch_authz, silence_audit):  # noqa: ARG001
    """A non-member sees 404 (not 403) for a TEAM-scope share — UUID privacy."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    creator = _make_user()
    outsider = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.TEAM.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=creator.id,
    )
    # Empty membership query → outsider is not a member.
    session = _QueueSession({(AuthzShare, share.id): share, (Flow, flow.id): flow}, exec_queue=[[]])

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.get_share(
            share_id=share.id,
            current_user=outsider,
            session=session,
            response=Response(),
        )
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_list_shares_filters_by_visibility_for_non_superuser(patch_authz, silence_audit):  # noqa: ARG001
    """list_shares returns only rows the (non-superuser) caller may see."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    caller = _make_user()
    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    visible = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=caller.id,  # targets the caller → visible
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    hidden = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),  # targets someone else → hidden
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    # The database predicate has already removed the hidden row; the second
    # result-set resolves the visible USER recipient's display name.
    session = _QueueSession({(Flow, flow.id): flow}, exec_queue=[[visible], []])

    results = await shares_module.list_shares(current_user=caller, session=session)
    ids = {r.id for r in results}
    assert visible.id in ids
    assert hidden.id not in ids
    assert caller.id in session.statements[0].compile().params.values()


@pytest.mark.asyncio
async def test_list_shares_includes_user_and_team_target_names(patch_authz, silence_audit):  # noqa: ARG001
    """Share responses expose display names without dropping UUID compatibility."""
    patch_authz(cross_user=False, enabled=False)

    admin = _make_user(is_superuser=True)
    owner = _make_user()
    user_id = uuid4()
    team_id = uuid4()
    user_share = _share(scope=ShareScope.USER.value, target_id=user_id, created_by=owner.id)
    team_share = _share(scope=ShareScope.TEAM.value, target_id=team_id, created_by=owner.id)
    public_share = _share(scope=ShareScope.PUBLIC.value, target_id=None, created_by=owner.id)
    session = _QueueSession(
        exec_queue=[
            [user_share, team_share, public_share],
            [(user_id, "alice")],
            [(team_id, "Platform")],
        ]
    )

    results = await shares_module.list_shares(current_user=admin, session=session)
    by_id = {result.id: result for result in results}

    assert by_id[user_share.id].target_id == user_id
    assert by_id[user_share.id].target_name == "alice"
    assert by_id[team_share.id].target_name == "Platform"
    assert by_id[public_share.id].target_name is None


@pytest.mark.asyncio
async def test_serialize_shares_resolves_names_with_real_sqlmodel_result():
    """Column-pair results must be consumed via ``.all()`` before building maps."""
    from langflow.services.database.models.auth import AuthzTeam
    from langflow.services.database.models.user.model import User
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: SQLModel.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, AuthzTeam.__table__],
                )
            )

        user = User(username="alice", password=str(uuid4()), is_active=True)
        team = AuthzTeam(team_name="Platform", adom_name="platform")
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add_all([user, team])
            await session.commit()

            serialized = await shares_module._serialize_shares(
                session,
                [
                    _share(scope=ShareScope.USER.value, target_id=user.id, created_by=user.id),
                    _share(scope=ShareScope.TEAM.value, target_id=team.id, created_by=user.id),
                ],
            )

        assert [share.target_name for share in serialized] == ["alice", "Platform"]
    finally:
        await engine.dispose()
