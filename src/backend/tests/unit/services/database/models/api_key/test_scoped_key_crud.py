"""Credential ceilings are enforced at the shared CRUD boundary."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.database.models.api_key import crud
from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate
from langflow.services.database.models.user.model import User

_TEST_PASSWORD = "unused"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def clear_credential_context():
    clear_current_auth_context()
    yield
    clear_current_auth_context()


def settings(*, enabled=True, scopes_enabled=True):
    return SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=enabled,
            API_KEY_SCOPES_ENABLED=scopes_enabled,
            API_KEY_SOURCE="db",  # pragma: allowlist secret
            EXTERNAL_AUTH_ACCESS_CEILING_ENABLED=False,
            EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS=False,
        ),
        settings=SimpleNamespace(disable_track_apikey_usage=True),
    )


def policy():
    return {"restrictions": [{"resource_type": "flow", "actions": ["read", "execute"]}]}


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["create", "edit"])
async def test_rollout_switch_blocks_scoped_issuance_at_shared_boundary(operation, monkeypatch):
    owner_id = uuid4()
    key = ApiKey(api_key="stored", user_id=owner_id, created_at=datetime.now(timezone.utc))
    session = AsyncMock()
    session.add = MagicMock()
    session.exec.return_value = MagicMock(first=MagicMock(return_value=key))
    authorization = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True), validate_api_key_permissions=AsyncMock()
    )
    monkeypatch.setattr(crud, "get_settings_service", lambda: settings(scopes_enabled=False))
    monkeypatch.setattr(crud, "get_authorization_service", lambda: authorization)

    request = (
        crud.create_api_key(session, ApiKeyCreate(name="Runner", permissions=policy()), owner_id)
        if operation == "create"
        else crud.update_api_key_permissions(session, api_key_id=key.id, user_id=owner_id, permissions=policy())
    )
    with pytest.raises(PermissionError, match="issuance is disabled"):
        await request

    authorization.validate_api_key_permissions.assert_not_awaited()
    session.add.assert_not_called()
    assert key.permissions is None


@pytest.mark.anyio
async def test_disabling_issuance_preserves_existing_scoped_key_authentication(monkeypatch):
    key = ApiKey(api_key="stored", user_id=uuid4(), permissions=policy())
    authorization = SimpleNamespace(supports_api_key_scopes=AsyncMock(return_value=True))
    monkeypatch.setattr(crud, "get_authorization_service", lambda: authorization)

    assert await crud._scoped_key_can_authenticate(key, settings(scopes_enabled=False))


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["list", "create", "delete"])
async def test_restricted_key_cannot_manage_credentials(operation, monkeypatch):
    user_id = uuid4()
    key = ApiKey(api_key="encrypted", user_id=user_id)
    session = AsyncMock()
    session.exec.return_value = MagicMock(all=MagicMock(return_value=[]))
    session.get.return_value = key
    monkeypatch.setattr(crud, "get_settings_service", lambda: settings())
    monkeypatch.setattr(crud.auth_utils, "encrypt_api_key", lambda value: value)
    set_current_auth_context(AuthCredentialContext(method="api_key", api_key_id=uuid4(), api_key_restricted=True))

    operations = {
        "list": lambda: crud.get_api_keys(session, user_id),
        "create": lambda: crud.create_api_key(session, ApiKeyCreate(name="escape"), user_id),
        "delete": lambda: crud.delete_api_key(session, key.id, user_id),
    }
    with pytest.raises(PermissionError, match="Restricted API keys"):
        await operations[operation]()

    session.exec.assert_not_awaited()
    session.get.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(("enabled", "supports"), [(False, True), (True, False)])
async def test_authentication_rejects_scoped_key_without_enforcement(enabled, supports, monkeypatch):
    owner = User(username="owner", password=_TEST_PASSWORD, is_active=True)
    key = ApiKey(api_key="stored", user_id=owner.id, permissions=policy())
    session = AsyncMock()
    session.exec.return_value = MagicMock(all=MagicMock(return_value=[key]))
    session.get.return_value = owner
    monkeypatch.setattr(
        crud,
        "get_authorization_service",
        lambda: SimpleNamespace(supports_api_key_scopes=AsyncMock(return_value=supports)),
        raising=False,
    )

    result = await crud._check_key_from_db_with_context(session, "candidate", settings(enabled=enabled))

    assert result is None
    session.flush.assert_not_awaited()


@pytest.mark.anyio
async def test_authentication_carries_current_scoped_policy(monkeypatch):
    owner = User(username="owner", password=_TEST_PASSWORD, is_active=True)
    key = ApiKey(api_key="stored", user_id=owner.id, permissions=policy())
    session = AsyncMock()
    session.exec.return_value = MagicMock(all=MagicMock(return_value=[key]))
    session.get.return_value = owner
    monkeypatch.setattr(
        crud,
        "get_authorization_service",
        lambda: SimpleNamespace(supports_api_key_scopes=AsyncMock(return_value=True)),
        raising=False,
    )

    result = await crud._check_key_from_db_with_context(session, "candidate", settings())

    assert result is not None
    assert result.api_key_restricted is True
    assert result.api_key_permissions == key.permissions
    context = AuthCredentialContext.from_api_key_result(result).to_authz_context()
    assert context["api_key_restricted"] is True
    assert context["api_key_permissions"] == key.permissions


@pytest.mark.anyio
async def test_scoped_creation_asks_plugin_before_staging(monkeypatch):
    validate = AsyncMock(side_effect=PermissionError("resource unavailable"))
    authorization = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True), validate_api_key_permissions=validate
    )
    session = AsyncMock()
    monkeypatch.setattr(crud, "get_settings_service", lambda: settings())
    monkeypatch.setattr(crud, "get_authorization_service", lambda: authorization, raising=False)

    with pytest.raises(PermissionError, match="resource unavailable"):
        await crud.create_api_key(session, ApiKeyCreate(name="runner", permissions=policy()), uuid4())

    validate.assert_awaited_once()
    session.add.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("invalid", [{}, {"restrictions": [{"resource_type": "flow", "actions": ["manage"]}]}])
async def test_malformed_stored_policy_fails_closed(invalid, monkeypatch):
    key = ApiKey(api_key="stored", user_id=uuid4(), permissions=invalid)
    authorization = SimpleNamespace(supports_api_key_scopes=AsyncMock(return_value=True))
    monkeypatch.setattr(crud, "get_authorization_service", lambda: authorization)
    assert not await crud._scoped_key_can_authenticate(key, settings())


@pytest.mark.anyio
async def test_scoped_authentication_refusal_audits_key_identity_without_secret(monkeypatch):
    owner_id = uuid4()
    key = ApiKey(api_key="never-record-this-secret", user_id=owner_id, permissions={})
    session = AsyncMock()
    session.exec.return_value = MagicMock(all=MagicMock(return_value=[key]))
    stage = MagicMock(return_value=True)
    monkeypatch.setattr("langflow.services.authorization.audit.stage_audit_decision", stage)

    assert await crud._check_key_from_db_with_context(session, "never-record-this-secret", settings()) is None

    stage.assert_called_once()
    event = stage.call_args.kwargs
    assert event["principal"].actor_type == "api_key"
    assert event["principal"].actor_id == key.id
    assert event["result"] == "deny"
    assert event["details"]["reason"] == "api_key_scope_enforcement_unavailable"
    assert "never-record-this-secret" not in str(event)


@pytest.mark.anyio
async def test_permission_update_cannot_disclose_or_rotate_secret(monkeypatch):
    from datetime import datetime, timezone

    owner_id = uuid4()
    key = ApiKey(api_key="encrypted-existing-secret", user_id=owner_id, created_at=datetime.now(timezone.utc))
    session = AsyncMock()
    session.add = MagicMock()
    session.exec.return_value = MagicMock(first=MagicMock(return_value=key))
    authorization = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True), validate_api_key_permissions=AsyncMock()
    )
    monkeypatch.setattr(crud, "get_authorization_service", lambda: authorization)
    monkeypatch.setattr(crud, "get_settings_service", lambda: settings())

    updated = await crud.update_api_key_permissions(session, api_key_id=key.id, user_id=owner_id, permissions=policy())

    assert updated.permissions == policy()
    assert updated.api_key == "********"
    assert key.api_key == "encrypted-existing-secret"  # pragma: allowlist secret
    assert key.api_key_hash is None


@pytest.mark.anyio
async def test_legacy_key_does_not_require_authorization_plugin(monkeypatch):
    key = ApiKey(api_key="stored", user_id=uuid4())
    monkeypatch.setattr(crud, "get_authorization_service", MagicMock(side_effect=AssertionError("must not probe")))
    assert await crud._scoped_key_can_authenticate(key, settings(enabled=False))


@pytest.mark.anyio
async def test_restricted_superuser_cannot_use_superuser_dependencies():
    from langflow.services.auth.service import AuthService

    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=True)
    service = object.__new__(AuthService)
    set_current_auth_context(AuthCredentialContext(method="api_key", api_key_id=uuid4(), api_key_restricted=True))
    assert await service.get_current_active_superuser(user) is None
