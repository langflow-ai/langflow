"""Route-level tests for the OSS share-administration floor.

These tests assert the documented OSS contract: only the resource owner or a
superuser may administer ``authz_share`` rows for a resource when the
authorization service is the pass-through default (no enterprise plugin). The
schema-level happy path is covered in ``test_authz_share_schemas.py``; what
these tests prevent is the floor being silently dropped on a refactor.

We exercise the handlers directly (not via the FastAPI app) using a fake async
session that records writes. This keeps the test fast and isolates the floor
logic from DB and Casbin concerns.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1 import authz_shares as shares_module
from langflow.api.v1.schemas.authz_shares import ShareCreate, ShareUpdate
from langflow.services.database.models.auth import AuthzShare, SharePermissionLevel, ShareScope


class _FakeAsyncSession:
    """Minimal async-session stand-in: stores get() results and records writes."""

    def __init__(self, get_by_type: dict[tuple[type, UUID], Any] | None = None) -> None:
        self._get_by_type = get_by_type or {}
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushed = 0
        self.rolled_back = 0

    async def get(self, model: type, key: UUID) -> Any:
        return self._get_by_type.get((model, key))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        self.flushed += 1

    async def refresh(self, obj: Any) -> None:  # noqa: ARG002
        return None

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def exec(self, _stmt: Any) -> list[Any]:
        # list_shares is not exercised here; return empty by default.
        return []


class _StubAuthz:
    """Pass-through authz service: allow everything, no cross-user fetch."""

    def __init__(self, *, cross_user: bool = False, enabled: bool = False) -> None:
        self._cross_user = cross_user
        self._enabled = enabled

    async def supports_cross_user_fetch(self) -> bool:
        return self._cross_user

    async def is_enabled(self) -> bool:
        return self._enabled

    async def enforce(self, **_kwargs) -> bool:
        return True

    async def batch_enforce(self, **kwargs) -> list[bool]:
        return [True] * len(kwargs.get("requests", []))

    async def invalidate_user(self, *_args, **_kwargs) -> None:
        return None

    async def invalidate_all(self, *_args, **_kwargs) -> None:
        return None


@pytest.fixture
def patch_authz(monkeypatch):
    """Install a stub authz service into both the shares module and utils."""
    from langflow.services.authorization import utils as authz_utils

    def _apply(*, cross_user: bool = False, enabled: bool = False) -> _StubAuthz:
        stub = _StubAuthz(cross_user=cross_user, enabled=enabled)
        monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
        monkeypatch.setattr(authz_utils, "get_authorization_service", lambda: stub)
        # Disable audit + AUTHZ_ENABLED gating so audit calls inside ensure_*
        # don't open real sessions.
        settings = SimpleNamespace(
            auth_settings=SimpleNamespace(AUTHZ_ENABLED=False, AUTHZ_AUDIT_ENABLED=False),
        )
        monkeypatch.setattr(authz_utils, "get_settings_service", lambda: settings)
        return stub

    return _apply


@pytest.fixture
def silence_audit(monkeypatch):
    """Replace audit_decision with a no-op so we don't spawn background tasks."""

    async def _noop(**_kwargs):
        return None

    monkeypatch.setattr(shares_module, "audit_decision", _noop)


def _make_user(*, is_superuser: bool = False) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), is_superuser=is_superuser, username="u")


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


# --------------------------------------------------------------------------- #
# CREATE — OSS floor must block non-owner / non-superuser
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_create_share_blocks_non_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """A non-owner cannot mint a share row for another user's flow under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    attacker = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(payload=payload, current_user=attacker, session=session)

    assert excinfo.value.status_code == 403
    assert "Only the resource owner" in excinfo.value.detail
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
        )

    assert excinfo.value.status_code == 403
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
    )

    assert result.permission_level == SharePermissionLevel.WRITE.value
    assert session.flushed == 1


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

    assert excinfo.value.status_code == 403
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


# --------------------------------------------------------------------------- #
# Floor behavior when the enterprise plugin is active
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_floor_is_skipped_when_enterprise_plugin_active(patch_authz, silence_audit):  # noqa: ARG001
    """OSS floor is skipped when the enterprise plugin is actively enforcing.

    When supports_cross_user_fetch=True AND AUTHZ_ENABLED=true, the OSS floor
    is skipped so a plugin-granted share:create role can administer shares on
    another user's resource. ``ensure_share_permission`` (mocked to allow here)
    becomes the authoritative check.
    """
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    delegate = _make_user()  # non-owner, but allowed by enterprise policy
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    result = await shares_module.create_share(payload=payload, current_user=delegate, session=session)

    # The floor is skipped; the stub authz allows the operation; the row is
    # written. If the floor still fired we'd see a 403 instead.
    assert result.resource_id == flow.id
    assert len(session.added) == 1
