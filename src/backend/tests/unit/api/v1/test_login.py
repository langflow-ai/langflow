import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.fixture
async def another_client(monkeypatch):
    from langflow.main import create_app

    monkeypatch.setenv(name="LANGFLOW_AUTO_LOGIN", value=True)
    app = create_app()
    async with AsyncClient(app=app, base_url="http://testserver", http2=True) as client:
        yield client


async def test_login_to_get_access_token(client: AsyncClient, active_user):
    login_data = {"username": active_user.username, "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "access_token" in result, "The dictionary must contain a key called 'access_token'"
    assert "refresh_token" in result, "The dictionary must contain a key called 'refresh_token'"
    assert "token_type" in result, "The dictionary must contain a key called 'token_type'"


async def test_auto_login(another_client):
    response = await another_client.get("api/v1/auto_login")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "access_token" in result, "The dictionary must contain a key called 'access_token'"
    assert "refresh_token" in result, "The dictionary must contain a key called 'refresh_token'"
    assert "token_type" in result, "The dictionary must contain a key called 'token_type'"


async def test_refresh_token(another_client):
    tokens = (await another_client.get("api/v1/auto_login")).json()
    cookies = {"refresh_token_lf": tokens["refresh_token"]}
    response = await another_client.post("api/v1/refresh", cookies=cookies)

    assert response.status_code == status.HTTP_200_OK


async def test_logout(client: AsyncClient, logged_in_headers):
    response = await client.post("api/v1/logout", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "message" in result, "The dictionary must contain a key called 'message'"
