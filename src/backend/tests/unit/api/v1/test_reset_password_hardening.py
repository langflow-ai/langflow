from uuid import uuid4

from fastapi import status
from httpx import AsyncClient
from langflow.api.v1.users import PASSWORD_RESET_ATTEMPTS_PER_MINUTE


async def _user_session(client: AsyncClient, admin_headers: dict) -> tuple[str, dict]:
    username = f"reset-{uuid4().hex[:8]}"
    created = await client.post(
        "api/v1/users/", json={"username": username, "password": "password-123"}, headers=admin_headers
    )
    user_id = created.json()["id"]
    await client.patch(f"api/v1/users/{user_id}", json={"is_active": True}, headers=admin_headers)
    login = await client.post("api/v1/login", data={"username": username, "password": "password-123"})
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_should_refuse_a_password_change_made_with_an_api_key(client: AsyncClient, logged_in_headers_super_user):
    user_id, headers = await _user_session(client, logged_in_headers_super_user)
    key = (await client.post("api/v1/api_key/", json={"name": "k"}, headers=headers)).json()["api_key"]
    client.cookies.clear()

    response = await client.patch(
        f"api/v1/users/{user_id}/reset-password",
        json={"current_password": "password-123", "password": "new-password-456"},
        headers={"x-api-key": key},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.headers["X-Langflow-Error-Code"] == "interactive_login_required"


async def test_should_rate_limit_password_guessing(client: AsyncClient, logged_in_headers_super_user):
    user_id, headers = await _user_session(client, logged_in_headers_super_user)
    wrong = {"current_password": "not-it", "password": "new-password-456"}

    codes = [
        (await client.patch(f"api/v1/users/{user_id}/reset-password", json=wrong, headers=headers)).status_code
        for _ in range(PASSWORD_RESET_ATTEMPTS_PER_MINUTE + 1)
    ]

    assert (
        codes[:PASSWORD_RESET_ATTEMPTS_PER_MINUTE] == [status.HTTP_400_BAD_REQUEST] * PASSWORD_RESET_ATTEMPTS_PER_MINUTE
    )
    assert codes[-1] == status.HTTP_429_TOO_MANY_REQUESTS
