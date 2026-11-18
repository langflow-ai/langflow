"""Password changes retire existing native sessions."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope

CURRENT_PASSWORD = "test" + "password"  # pragma: allowlist secret
NEW_PASSWORD = "replacement" + "-password"  # pragma: allowlist secret


@pytest.fixture
async def password_user(client):  # noqa: ARG001 - initialize application services
    user = User(
        username=f"password-session-{uuid4()}",
        password=get_auth_service().get_password_hash(CURRENT_PASSWORD),
        is_active=True,
    )
    async with session_scope() as session:
        session.add(user)
        await session.flush()
        await session.refresh(user)
    yield user
    async with session_scope() as session:
        await session.delete(await session.get(User, user.id))


@pytest.mark.parametrize("change_route", ["self", "administrator"])
@pytest.mark.parametrize("token_kind", ["access", "refresh"])
async def test_password_change_rejects_existing_tokens(
    client: AsyncClient, password_user, logged_in_headers_super_user, change_route, token_kind
):
    active_user = password_user
    client.cookies.clear()
    login = await client.post("api/v1/login", data={"username": active_user.username, "password": CURRENT_PASSWORD})
    assert login.status_code == 200
    old_tokens = login.json()
    old_headers = {"Authorization": f"Bearer {old_tokens['access_token']}"}
    if change_route == "self":
        changed = await client.patch(
            f"api/v1/users/{active_user.id}/reset-password",
            json={"current_password": CURRENT_PASSWORD, "password": NEW_PASSWORD},
            headers=old_headers,
        )
    else:
        changed = await client.patch(
            f"api/v1/users/{active_user.id}",
            json={"password": NEW_PASSWORD},
            headers=logged_in_headers_super_user,
        )
    assert changed.status_code == 200
    assert "session_version" not in changed.json()

    other_user = await client.get("api/v1/users/whoami", headers=logged_in_headers_super_user)
    assert other_user.status_code == 200

    client.cookies.clear()
    if token_kind == "access":  # noqa: S105 - token category
        rejected = await client.get("api/v1/users/whoami", headers=old_headers)
    else:
        client.cookies.set("refresh_token_lf", old_tokens["refresh_token"])
        rejected = await client.post("api/v1/refresh")
    assert rejected.status_code == 401

    client.cookies.clear()
    fresh = await client.post("api/v1/login", data={"username": active_user.username, "password": NEW_PASSWORD})
    assert fresh.status_code == 200
    accepted = await client.get(
        "api/v1/users/whoami", headers={"Authorization": f"Bearer {fresh.json()['access_token']}"}
    )
    assert accepted.status_code == 200
    assert (await client.post("api/v1/refresh")).status_code == 200


async def test_password_change_preserves_api_keys(client: AsyncClient, password_user):
    login = await client.post("api/v1/login", data={"username": password_user.username, "password": CURRENT_PASSWORD})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created_key = await client.post("api/v1/api_key/", json={"name": "preserved-key"}, headers=headers)
    assert created_key.status_code == 200
    changed = await client.patch(
        f"api/v1/users/{password_user.id}/reset-password",
        json={"current_password": CURRENT_PASSWORD, "password": NEW_PASSWORD},
        headers=headers,
    )
    assert changed.status_code == 200
    client.cookies.clear()
    accepted = await client.get("api/v1/users/whoami", headers={"x-api-key": created_key.json()["api_key"]})
    assert accepted.status_code == 200
    assert accepted.json()["id"] == str(password_user.id)


async def test_rejected_password_change_preserves_native_sessions(client: AsyncClient, password_user):
    login = await client.post("api/v1/login", data={"username": password_user.username, "password": CURRENT_PASSWORD})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = await client.patch(
        f"api/v1/users/{password_user.id}/reset-password",
        json={"current_password": "incorrect", "password": NEW_PASSWORD},  # pragma: allowlist secret
        headers=headers,
    )
    assert changed.status_code == 400
    assert (await client.get("api/v1/users/whoami", headers=headers)).status_code == 200
    assert (await client.post("api/v1/refresh")).status_code == 200
