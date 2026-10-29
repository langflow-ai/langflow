"""A scoped credential must never inherit an unconditional user shortcut."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.authorization import guards
from langflow.services.authorization.admin import is_administrator

from ._common import _StubAuthorizationService, install_audit_recorder, install_authz, install_settings


@pytest.fixture(autouse=True)
def reset_credential():
    clear_current_auth_context()
    yield
    clear_current_auth_context()


def credential(*, restricted):
    context = AuthCredentialContext(method="api_key", api_key_id=uuid4(), api_key_source="db")
    object.__setattr__(context, "api_key_restricted", restricted)
    set_current_auth_context(context)


async def test_unrestricted_key_keeps_owner_override_with_scope_plugin(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=False, supports_api_key_scopes=True)
    install_authz(monkeypatch, service)
    install_audit_recorder(monkeypatch)
    credential(restricted=False)
    await guards.ensure_flow_permission(fake_user, "delete", flow_id=uuid4(), flow_user_id=fake_user.id)
    assert not service.calls


async def test_restricted_key_cannot_use_owner_override_without_plugin(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=True))
    install_audit_recorder(monkeypatch)
    credential(restricted=True)
    with pytest.raises(HTTPException) as exc:
        await guards.ensure_flow_permission(fake_user, "delete", flow_id=uuid4(), flow_user_id=fake_user.id)
    assert exc.value.status_code == 403


async def test_restricted_key_cannot_use_disabled_authorization(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=False)
    install_authz(monkeypatch, _StubAuthorizationService(allow=True, supports_api_key_scopes=True))
    install_audit_recorder(monkeypatch)
    credential(restricted=True)
    with pytest.raises(HTTPException) as exc:
        await guards.ensure_permission(fake_user, domain="*", obj=f"flow:{uuid4()}", act="read")
    assert exc.value.status_code == 403


async def test_restricted_key_cannot_administer_even_as_superuser(fake_superuser):
    credential(restricted=True)
    assert not await is_administrator(fake_superuser, resource="role", authorization_service=AsyncMock())


async def test_restricted_permission_denial_records_key_and_reason(monkeypatch, fake_user):
    from langflow.services.auth.context import get_current_auth_context

    install_settings(monkeypatch, authz_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=False, supports_api_key_scopes=True))
    events = install_audit_recorder(monkeypatch)
    credential(restricted=True)
    with pytest.raises(HTTPException):
        await guards.ensure_permission(fake_user, domain="*", obj=f"flow:{uuid4()}", act="execute")
    assert events[0]["details"]["reason"] == "api_key_or_owner_access_denied"
    assert events[0]["details"]["api_key_id"] == str(get_current_auth_context().api_key_id)
