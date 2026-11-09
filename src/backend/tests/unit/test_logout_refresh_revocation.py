"""Logout invalidates captured native refresh tokens from the browser's session."""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from langflow.main import setup_app
from langflow.services.deps import get_auth_service, get_settings_service


async def test_logout_storage_failure_returns_error_without_clearing_cookies(client, active_user, monkeypatch):  # noqa: ARG001
    """A failed revocation returns an error, and retrying logout revokes the captured token."""
    from langflow.api.v1 import login

    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", False)
    app = setup_app(backend_only=True)
    revoke = login.revoke_refresh_token

    async def unavailable(*_args, **_kwargs):
        message = "Revocation storage is unavailable"
        raise RuntimeError(message)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver"
    ) as browser:
        response = await browser.post(
            "/api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
        )
        assert response.status_code == 200
        captured = response.json()["refresh_token"]
        monkeypatch.setattr(login, "revoke_refresh_token", unavailable)

        response = await browser.post("/api/v1/logout")
        assert response.status_code == 500
        assert not any("Max-Age=0" in value for value in response.headers.get_list("set-cookie"))
        assert browser.cookies.get("refresh_token_lf") == captured

        monkeypatch.setattr(login, "revoke_refresh_token", revoke)
        assert (await browser.post("/api/v1/logout")).status_code == 200
        browser.cookies.set("refresh_token_lf", captured)
        assert (await browser.post("/api/v1/refresh")).status_code == 401


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


async def test_legacy_refresh_cookie_requires_fresh_sign_in(client, active_user, monkeypatch):  # noqa: ARG001
    """Upgrade rejects old refresh cookies, logout remains idempotent, and sign-in restores refresh."""
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", False)
    app = setup_app(backend_only=True)
    legacy = get_auth_service().create_token({"sub": str(active_user.id), "type": "refresh"}, timedelta(minutes=5))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as browser:
        browser.cookies.set("refresh_token_lf", legacy)
        response = await browser.post("/api/v1/refresh")
        assert response.status_code == 401
        for _ in range(2):
            response = await browser.post("/api/v1/logout")
            assert response.status_code == 200
            assert any(
                "refresh_token_lf=" in value and "Max-Age=0" in value
                for value in response.headers.get_list("set-cookie")
            )
        response = await browser.post(
            "/api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
        )
        assert response.status_code == 200
        assert (await browser.post("/api/v1/refresh")).status_code == 200
