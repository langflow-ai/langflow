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
    created = (await client.post("api/v1/api_key/", json={"name": "Runner"}, headers=logged_in_headers)).json()
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
async def test_restricted_key_cannot_modify_its_owner_profile(client, logged_in_headers, active_user, monkeypatch):
    from langflow.services.deps import get_settings_service

    settings = get_settings_service()
    monkeypatch.setattr(settings.auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(settings.auth_settings, "API_KEY_SCOPES_ENABLED", True)
    plugin = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True),
        validate_api_key_permissions=AsyncMock(),
    )
    monkeypatch.setattr("langflow.services.database.models.api_key.crud.get_authorization_service", lambda: plugin)
    response = await client.post(
        "api/v1/api_key/",
        json={
            "name": "Profile-limited",
            "permissions": {"restrictions": [{"resource_type": "flow", "actions": ["read"]}]},
        },
        headers=logged_in_headers,
    )
    assert response.status_code == 200

    client.cookies.clear()
    response = await client.patch(
        f"api/v1/users/{active_user.id}",
        json={"username": "changed-through-scoped-key"},
        headers={"x-api-key": response.json()["api_key"]},
    )

    assert response.status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["list", "options", "create", "edit", "delete", "store"])
async def test_restricted_key_cannot_administer_credentials(client, logged_in_headers, monkeypatch, operation):
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(get_settings_service().auth_settings, "API_KEY_SCOPES_ENABLED", True)
    plugin = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True),
        validate_api_key_permissions=AsyncMock(),
    )
    monkeypatch.setattr("langflow.services.database.models.api_key.crud.get_authorization_service", lambda: plugin)
    created = await client.post(
        "api/v1/api_key/",
        json={"name": "Restricted", "permissions": {"restrictions": [{"resource_type": "flow", "actions": ["read"]}]}},
        headers=logged_in_headers,
    )
    assert created.status_code == 200
    key = created.json()
    requests = {
        "list": ("GET", "api/v1/api_key/", None),
        "options": ("GET", "api/v1/api_key/permission-options", None),
        "create": ("POST", "api/v1/api_key/", {"name": "Broader key"}),
        "edit": ("PATCH", f"api/v1/api_key/{key['id']}/permissions", {"permissions": None}),
        "delete": ("DELETE", f"api/v1/api_key/{key['id']}", None),
        "store": ("POST", "api/v1/api_key/store", {"api_key": "a-different-credential"}),  # pragma: allowlist secret
    }
    method, url, body = requests[operation]
    client.cookies.clear()
    denied = await client.request(method, url, json=body, headers={"x-api-key": key["api_key"]})
    assert denied.status_code == 403
    assert key["api_key"] not in denied.text


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
