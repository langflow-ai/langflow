"""Tests for ensure_permission and ensure_flow_permission helpers."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.authorization import utils as authz_utils


class _StubAuthorizationService:
    """Minimal stand-in for BaseAuthorizationService that records calls."""

    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.calls: list[dict] = []

    async def enforce(self, **kwargs) -> bool:
        self.calls.append(kwargs)
        return self.allow


@pytest.fixture
def fake_user():
    """Build a non-superuser user object compatible with ensure_permission."""
    return SimpleNamespace(id=uuid4(), is_superuser=False)


@pytest.fixture
def fake_superuser():
    """Build a superuser user object compatible with ensure_permission."""
    return SimpleNamespace(id=uuid4(), is_superuser=True)


def _install_settings(monkeypatch, *, authz_enabled: bool) -> None:
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(AUTHZ_ENABLED=authz_enabled),
    )
    monkeypatch.setattr(authz_utils, "get_settings_service", lambda: settings)


def _install_authz(monkeypatch, service: _StubAuthorizationService) -> None:
    monkeypatch.setattr(authz_utils, "get_authorization_service", lambda: service)


@pytest.mark.anyio
async def test_ensure_permission_noop_when_disabled(monkeypatch, fake_user):
    """When AUTHZ_ENABLED=False, the helper returns without consulting the service."""
    _install_settings(monkeypatch, authz_enabled=False)
    service = _StubAuthorizationService(allow=False)
    _install_authz(monkeypatch, service)

    # Even though the stub would deny, the helper short-circuits and returns None.
    await authz_utils.ensure_permission(
        fake_user,
        domain="*",
        obj="flow:abc",
        act="read",
    )
    assert service.calls == []


@pytest.mark.anyio
async def test_ensure_permission_allows_when_enforce_returns_true(monkeypatch, fake_user):
    """A True enforce result returns None and forwards the merged context."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)

    await authz_utils.ensure_permission(
        fake_user,
        domain="*",
        obj="flow:abc",
        act="read",
        context={"extra": "value"},
    )

    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["user_id"] == fake_user.id
    assert call["domain"] == "*"
    assert call["obj"] == "flow:abc"
    assert call["act"] == "read"
    # is_superuser is injected from the user, additional context flows through.
    assert call["context"] == {"is_superuser": False, "extra": "value"}


@pytest.mark.anyio
async def test_ensure_permission_raises_403_when_denied(monkeypatch, fake_user):
    """A False enforce result raises HTTP 403 with a descriptive message."""
    _install_settings(monkeypatch, authz_enabled=True)
    _install_authz(monkeypatch, _StubAuthorizationService(allow=False))

    with pytest.raises(HTTPException) as exc_info:
        await authz_utils.ensure_permission(
            fake_user,
            domain="*",
            obj="flow:abc",
            act="write",
        )

    assert exc_info.value.status_code == 403
    assert "write" in exc_info.value.detail
    assert "flow:abc" in exc_info.value.detail


@pytest.mark.anyio
async def test_ensure_flow_permission_builds_obj_key(monkeypatch, fake_user):
    """ensure_flow_permission constructs the canonical flow:<id> obj key."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)

    flow_id = uuid4()
    owner_id = uuid4()
    await authz_utils.ensure_flow_permission(
        fake_user,
        "read",
        flow_id=flow_id,
        flow_user_id=owner_id,
    )

    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["obj"] == f"flow:{flow_id}"
    assert call["act"] == "read"
    assert call["context"]["flow_user_id"] == owner_id
    assert call["context"]["is_superuser"] is False


@pytest.mark.anyio
async def test_ensure_flow_permission_wildcard_when_no_flow_id(monkeypatch, fake_user):
    """Without flow_id, the obj key falls back to flow:* (used for create/list paths)."""
    _install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    _install_authz(monkeypatch, service)

    await authz_utils.ensure_flow_permission(fake_user, "create")
    assert service.calls[0]["obj"] == "flow:*"


@pytest.mark.anyio
async def test_ensure_flow_permission_raises_403_on_denial(monkeypatch, fake_user):
    """ensure_flow_permission propagates the 403 from ensure_permission."""
    _install_settings(monkeypatch, authz_enabled=True)
    _install_authz(monkeypatch, _StubAuthorizationService(allow=False))

    with pytest.raises(HTTPException) as exc_info:
        await authz_utils.ensure_flow_permission(
            fake_user,
            "delete",
            flow_id=uuid4(),
        )

    assert exc_info.value.status_code == 403
