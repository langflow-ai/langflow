"""Logout invalidates captured native refresh tokens from the browser's session."""

import pytest
from httpx import ASGITransport, AsyncClient
from langflow.main import setup_app
from langflow.services.deps import get_settings_service


@pytest.mark.parametrize("refresh_first", [False, True])
async def test_logged_out_refresh_token_cannot_be_replayed(client, active_user, monkeypatch, refresh_first):  # noqa: ARG001
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", False)
    app = setup_app(backend_only=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as browser:
        response = await browser.post(
            "/api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
        )
        assert response.status_code == 200
        captured = response.json()["refresh_token"]
        tokens = [captured, captured + "="]
        if refresh_first:
            response = await browser.post("/api/v1/refresh")
            assert response.status_code == 200
            tokens.append(response.json()["refresh_token"])
        assert (await browser.post("/api/v1/logout")).status_code == 200
        for token in tokens:
            browser.cookies.set("refresh_token_lf", token)
            response = await browser.post("/api/v1/refresh")
            assert response.status_code == 401
