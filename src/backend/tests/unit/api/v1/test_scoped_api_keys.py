"""Owner-only API-key policy editing and capability discovery."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.anyio
async def test_disabled_issuance_hides_options_from_scope_capable_plugin(client, logged_in_headers, monkeypatch):
    from langflow.services.deps import get_settings_service

    auth_settings = get_settings_service().auth_settings
    monkeypatch.setattr(auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(auth_settings, "API_KEY_SCOPES_ENABLED", False)
    plugin = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True),
        get_api_key_permission_options=AsyncMock(return_value={"supported": True}),
    )
    monkeypatch.setattr("langflow.api.v1.api_key.get_authorization_service", lambda: plugin)

    response = await client.get("api/v1/api_key/permission-options", headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json() == {"supported": False, "roles": [], "resource_actions": {}, "scope_types": {}}
    plugin.get_api_key_permission_options.assert_not_awaited()


@pytest.mark.anyio
async def test_permission_options_reports_unsupported_without_plugin(client, logged_in_headers):
    response = await client.get("api/v1/api_key/permission-options", headers=logged_in_headers)
    assert response.status_code == 200
    assert response.json() == {"supported": False, "roles": [], "resource_actions": {}, "scope_types": {}}


@pytest.mark.anyio
async def test_owner_can_replace_and_remove_permissions_without_rotating_secret(client, logged_in_headers, monkeypatch):
    response = await client.post("api/v1/api_key/", json={"name": "Runner"}, headers=logged_in_headers)
    assert response.status_code == 200, response.text
    created = response.json()
    original_secret = created["api_key"]
    validate = AsyncMock()
    plugin = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True), validate_api_key_permissions=validate
    )
    monkeypatch.setattr("langflow.services.database.models.api_key.crud.get_authorization_service", lambda: plugin)
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(get_settings_service().auth_settings, "API_KEY_SCOPES_ENABLED", True)
    policy = {"restrictions": [{"resource_type": "flow", "actions": ["read", "execute"]}]}

    updated = await client.patch(
        f"api/v1/api_key/{created['id']}/permissions", json={"permissions": policy}, headers=logged_in_headers
    )
    assert updated.status_code == 200
    assert updated.json()["permissions"] == policy
    assert original_secret not in updated.text
    assert "*" in updated.json()["api_key"]
    validate.assert_awaited_once()

    monkeypatch.setattr(get_settings_service().auth_settings, "API_KEY_SCOPES_ENABLED", False)
    removed = await client.patch(
        f"api/v1/api_key/{created['id']}/permissions", json={"permissions": None}, headers=logged_in_headers
    )
    assert removed.status_code == 200
    assert removed.json()["permissions"] is None
    client.cookies.clear()
    response = await client.get("api/v1/api_key/", headers={"x-api-key": original_secret})
    assert response.status_code == 200


@pytest.mark.anyio
async def test_scoped_creation_retries_a_stale_sqlite_snapshot(client, logged_in_headers, monkeypatch):
    from datetime import datetime, timezone

    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_settings_service, session_scope
    from sqlalchemy import text

    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEY_SCOPES_ENABLED", True)

    requested_permissions = {"restrictions": [{"resource_type": "flow", "actions": ["read"]}]}

    async def commit_concurrent_write(*, session, user_id, permissions):
        assert permissions == requested_permissions
        if validate.await_count == 1:
            # SQLite's legacy transaction mode does not start a transaction on SELECT.
            await session.execute(text("BEGIN"))
            await session.get(User, user_id, populate_existing=True)
            async with session_scope() as writer:
                user = await writer.get(User, user_id)
                user.last_login_at = datetime.now(timezone.utc)

    validate = AsyncMock(side_effect=commit_concurrent_write)
    plugin = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True), validate_api_key_permissions=validate
    )
    monkeypatch.setattr("langflow.services.database.models.api_key.crud.get_authorization_service", lambda: plugin)
    created = await client.post(
        "api/v1/api_key/", json={"name": "Restricted", "permissions": requested_permissions}, headers=logged_in_headers
    )

    assert created.status_code == 200
    assert created.json()["permissions"] == requested_permissions
    assert validate.await_count == 2
    keys = await client.get("api/v1/api_key/", headers=logged_in_headers)
    assert keys.status_code == 200
    assert [key["id"] for key in keys.json()["api_keys"]] == [created.json()["id"]]


@pytest.mark.anyio
async def test_scoped_creation_is_refused_without_enforcement(client, logged_in_headers):
    response = await client.post(
        "api/v1/api_key/",
        json={"name": "Unsupported", "permissions": {"restrictions": [{"resource_type": "flow", "actions": ["read"]}]}},
        headers=logged_in_headers,
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_permission_patch_does_not_disclose_unknown_key(client, logged_in_headers):
    from uuid import uuid4

    response = await client.patch(
        f"api/v1/api_key/{uuid4()}/permissions", json={"permissions": None}, headers=logged_in_headers
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_permission_patch_rejects_empty_policy(client, logged_in_headers):
    from uuid import uuid4

    response = await client.patch(
        f"api/v1/api_key/{uuid4()}/permissions", json={"permissions": {}}, headers=logged_in_headers
    )
    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("unavailable", ["role", "project"])
async def test_permission_patch_refusal_preserves_key_and_audits_denial(
    client, logged_in_headers, active_user, monkeypatch, unavailable
):
    from uuid import UUID, uuid4

    from langflow.services.database.models.api_key.model import ApiKey
    from langflow.services.database.models.auth import AuthzAuditLog
    from langflow.services.deps import get_settings_service, session_scope
    from sqlmodel import select

    auth_settings = get_settings_service().auth_settings
    monkeypatch.setattr(auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(auth_settings, "API_KEY_SCOPES_ENABLED", True)
    validate = AsyncMock()
    plugin = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True), validate_api_key_permissions=validate
    )
    monkeypatch.setattr("langflow.services.database.models.api_key.crud.get_authorization_service", lambda: plugin)
    original_policy = {"restrictions": [{"resource_type": "flow", "actions": ["read"]}]}
    created = await client.post(
        "api/v1/api_key/",
        json={"name": "Unchanged on refusal", "permissions": original_policy},
        headers=logged_in_headers,
    )
    assert created.status_code == 200
    key_id = UUID(created.json()["id"])
    async with session_scope() as session:
        key = await session.get(ApiKey, key_id)
        original_secret, original_hash = key.api_key, key.api_key_hash
    detail = (
        "Role is not available for this API key"
        if unavailable == "role"
        else "Project is not available for this API key"
    )
    validate.side_effect = PermissionError(detail)
    refused_policy = (
        {"roles": [{"role_id": str(uuid4()), "domain_type": "global"}]}
        if unavailable == "role"
        else {
            "restrictions": [
                {"resource_type": "flow", "actions": ["read"], "domain_type": "project", "domain_id": str(uuid4())}
            ]
        }
    )
    monkeypatch.setattr(auth_settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(auth_settings, "AUTHZ_AUDIT_DURABLE", True)

    refused = await client.patch(
        f"api/v1/api_key/{key_id}/permissions", json={"permissions": refused_policy}, headers=logged_in_headers
    )

    assert refused.status_code == 403
    assert refused.json() == {"detail": detail}
    async with session_scope() as session:
        key = await session.get(ApiKey, key_id)
        assert key.permissions == original_policy
        assert (key.api_key, key.api_key_hash) == (original_secret, original_hash)
        events = (
            await session.exec(
                select(AuthzAuditLog).where(
                    AuthzAuditLog.resource_id == key_id, AuthzAuditLog.action == "api_key:permissions_update"
                )
            )
        ).all()
    assert len(events) == 1
    assert events[0].user_id == active_user.id
    assert events[0].result == "deny"
    assert events[0].details["reason"] == "permission_policy_refused"
    assert original_secret not in str(events[0].model_dump())


@pytest.fixture
async def restricted_api_key(active_user, monkeypatch):
    """Set up a restricted credential for tests of what the key can do."""
    from langflow.services.database.models.api_key.crud import create_api_key
    from langflow.services.database.models.api_key.model import ApiKeyCreate
    from langflow.services.deps import get_settings_service, session_scope

    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEY_SCOPES_ENABLED", True)
    plugin = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True),
        validate_api_key_permissions=AsyncMock(),
    )
    monkeypatch.setattr("langflow.services.database.models.api_key.crud.get_authorization_service", lambda: plugin)
    key = ApiKeyCreate(
        name="Restricted", permissions={"restrictions": [{"resource_type": "flow", "actions": ["read"]}]}
    )
    async with session_scope() as session:
        return await create_api_key(session, key, user_id=active_user.id)


@pytest.mark.anyio
async def test_restricted_key_cannot_modify_its_owner_profile(client, active_user, restricted_api_key):
    response = await client.patch(
        f"api/v1/users/{active_user.id}",
        json={"username": "changed-through-scoped-key"},
        headers={"x-api-key": restricted_api_key.api_key},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Restricted API keys cannot administer users"


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["list", "options", "create", "edit", "delete", "store"])
async def test_restricted_key_cannot_administer_credentials(client, restricted_api_key, operation):
    requests = {
        "list": ("GET", "api/v1/api_key/", None),
        "options": ("GET", "api/v1/api_key/permission-options", None),
        "create": ("POST", "api/v1/api_key/", {"name": "Broader key"}),
        "edit": ("PATCH", f"api/v1/api_key/{restricted_api_key.id}/permissions", {"permissions": None}),
        "delete": ("DELETE", f"api/v1/api_key/{restricted_api_key.id}", None),
        "store": ("POST", "api/v1/api_key/store", {"api_key": "a-different-credential"}),  # pragma: allowlist secret
    }
    method, url, body = requests[operation]
    denied = await client.request(method, url, json=body, headers={"x-api-key": restricted_api_key.api_key})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Restricted API keys cannot manage credentials"
    assert restricted_api_key.api_key not in denied.text


@pytest.mark.anyio
async def test_unavailable_scope_enforcement_durably_audits_authentication_refusal(client, active_user, monkeypatch):
    from langflow.services.database.models.api_key.crud import hash_api_key
    from langflow.services.database.models.api_key.model import ApiKey
    from langflow.services.database.models.auth import AuthzAuditLog
    from langflow.services.deps import get_settings_service, session_scope
    from sqlmodel import select

    auth_settings = get_settings_service().auth_settings
    monkeypatch.setattr(auth_settings, "AUTHZ_ENABLED", False)
    monkeypatch.setattr(auth_settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(auth_settings, "AUTHZ_AUDIT_DURABLE", True)
    secret = "scoped-refused-test-credential"  # noqa: S105  # pragma: allowlist secret
    async with session_scope() as session:
        key = ApiKey(
            name="Unavailable enforcement",
            api_key=secret,
            api_key_hash=hash_api_key(secret),
            user_id=active_user.id,
            permissions={"restrictions": [{"resource_type": "flow", "actions": ["read"]}]},
        )
        session.add(key)
        await session.flush()
        key_id = key.id
    client.cookies.clear()

    refused = await client.get("api/v1/users/whoami", headers={"x-api-key": secret})

    assert refused.status_code in {401, 403}
    async with session_scope() as session:
        events = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.actor_id == key_id))).all()
    assert len(events) == 1
    event = events[0]
    assert event.actor_type == "api_key"
    assert event.user_id == active_user.id
    assert event.action == "api_key:authenticate"
    assert event.result == "deny"
    assert event.details["reason"] == "api_key_scope_enforcement_unavailable"
    assert secret not in str(event.model_dump())
