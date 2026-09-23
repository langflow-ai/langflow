"""Exercise the documented transition using the existing account and user API."""

from secrets import token_urlsafe

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from langflow.services.utils import setup_superuser
from pydantic import SecretStr
from sqlmodel import select


@pytest.mark.parametrize("username", ["langflow", "custom-bootstrap-owner"])
@pytest.mark.parametrize("has_known_password", [False, True])
async def test_auto_login_upgrade_preserves_account_password_and_flows(
    client, monkeypatch, username, has_known_password
):
    """Preparing a password retains ownership; startup never silently resets it."""
    auth = get_auth_service()
    settings = get_settings_service()
    monkeypatch.setattr(settings.auth_settings, "AUTO_LOGIN", True)
    monkeypatch.setattr(settings.auth_settings, "SUPERUSER", username)
    password = token_urlsafe(32)

    # Model a persisted, already-used auto-login account and its existing flow.
    async with session_scope() as session:
        user = (await session.exec(select(User).where(User.username == username))).first()
        if user is None:
            user = User(username=username, password="", is_active=True, is_superuser=True)
            session.add(user)
            await session.flush()
        user.password = auth.get_password_hash(password if has_known_password else token_urlsafe(32))
        user_id = user.id
        tokens = await auth.create_user_tokens(user_id, session, update_last_login=True)
        flow = Flow(name="Existing workspace", data={"nodes": [], "edges": []}, user_id=user_id)
        session.add(flow)
        await session.flush()
        flow_id = flow.id

    if not has_known_password:
        response = await client.patch(
            f"api/v1/users/{user_id}",
            json={"password": password},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(user_id)

    # Verify the prepared password before switching, as required by the guide.
    response = await client.post("api/v1/login", data={"username": username, "password": password})
    assert response.status_code == 200
    monkeypatch.setattr(settings.auth_settings, "AUTO_LOGIN", False)
    # A different configured value must not replace a user's established password.
    configured_password = token_urlsafe(32)
    monkeypatch.setattr(settings.auth_settings, "SUPERUSER_PASSWORD", SecretStr(configured_password))
    async with session_scope() as session:
        await setup_superuser(settings, session)

    client.cookies.clear()
    assert (await client.get("api/v1/auto_login")).status_code == 403
    response = await client.post("api/v1/login", data={"username": username, "password": configured_password})
    assert response.status_code == 401
    response = await client.post("api/v1/login", data={"username": username, "password": password})
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    profile = await client.get("api/v1/users/whoami", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["id"] == str(user_id)
    saved_flow = await client.get(f"api/v1/flows/{flow_id}", headers=headers)
    assert saved_flow.status_code == 200
    assert saved_flow.json()["user_id"] == str(user_id)
    assert saved_flow.json()["data"] == {"nodes": [], "edges": []}
