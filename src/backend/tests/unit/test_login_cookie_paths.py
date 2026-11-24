"""Verify cookie routing when Langflow instances share a hostname."""

from http.cookies import SimpleCookie
from unittest.mock import AsyncMock
from urllib.parse import quote

import pytest
from fastapi import FastAPI, Request, WebSocket
from httpx import ASGITransport, AsyncClient
from langflow.main import setup_app
from langflow.services.auth.utils import (
    get_current_user_for_sse,
    get_current_user_for_websocket,
    get_current_user_optional,
)
from langflow.services.deps import get_settings_service, session_scope


def _instance(monkeypatch: pytest.MonkeyPatch, prefix: str) -> FastAPI:
    with monkeypatch.context() as settings_patch:
        settings_patch.setattr(get_settings_service().settings, "root_path", prefix)
        return setup_app(backend_only=True)


def _assert_cookie_paths(response, path: str, names: set[str]) -> None:
    cookies = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookies.load(header)
    assert set(cookies) == names
    assert {cookie["path"] for cookie in cookies.values()} == {path}


def _cookie_names(prefix: str, names: set[str]) -> set[str]:
    suffix = f"_{quote(prefix.rstrip('/'), safe='')}" if prefix else ""
    return {f"{name}{suffix}" for name in names}


@pytest.mark.parametrize("prefix", ["", "/langflow", "/tools/langflow/"])
@pytest.mark.parametrize("automatic", [False, True])
async def test_auth_cookie_lifecycle(client, active_user, monkeypatch, prefix, automatic):  # noqa: ARG001
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", automatic)
    path = f"{prefix.rstrip('/')}/"
    app = _instance(monkeypatch, prefix)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as browser:
        if automatic:
            response = await browser.get(f"{path}api/v1/auto_login")
        else:
            response = await browser.post(
                f"{path}api/v1/login",
                data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
            )
        assert response.status_code == 200
        names = {"access_token_lf", "refresh_token_lf", "apikey_tkn_lflw"}
        _assert_cookie_paths(response, path, _cookie_names(prefix, names))

        response = await browser.post(f"{path}api/v1/refresh")
        assert response.status_code == 200
        _assert_cookie_paths(response, path, _cookie_names(prefix, {"access_token_lf", "refresh_token_lf"}))

        response = await browser.post(f"{path}api/v1/logout")
        assert response.status_code == 200
        _assert_cookie_paths(response, path, _cookie_names(prefix, names))
        assert not list(browser.cookies.jar)
        assert (await browser.post(f"{path}api/v1/refresh")).status_code == 401


@pytest.mark.parametrize("prefix", ["", "/langflow", "/tools/langflow/"])
async def test_store_api_key_cookie_matches_login_cookie(client, active_user, monkeypatch, prefix):  # noqa: ARG001
    path = f"{prefix.rstrip('/')}/"
    app = _instance(monkeypatch, prefix)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as browser:
        response = await browser.post(
            f"{path}api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
        )
        assert response.status_code == 200

        response = await browser.post(
            f"{path}api/v1/api_key/store",
            json={"api_key": "synthetic-store-key"},  # pragma: allowlist secret
        )
        assert response.status_code == 200, response.text
        _assert_cookie_paths(response, path, _cookie_names(prefix, {"apikey_tkn_lflw"}))


async def test_sibling_instances_keep_separate_sessions(client, active_user, monkeypatch):  # noqa: ARG001
    app = FastAPI()
    first, second = "/langflow-a", "/tools/langflow-b"
    for prefix in (first, second):
        app.mount(prefix, _instance(monkeypatch, prefix))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as browser:
        for prefix, username, password in (
            (first, active_user.username, "testpassword"),
            (second, "langflow", "test-superuser-password"),
        ):
            response = await browser.post(f"{prefix}/api/v1/login", data={"username": username, "password": password})
            assert response.status_code == 200

        for prefix, username in ((first, active_user.username), (second, "langflow")):
            response = await browser.get(f"{prefix}/api/v1/session")
            assert response.json()["user"]["username"] == username
            assert (await browser.post(f"{prefix}/api/v1/refresh")).status_code == 200

        assert (await browser.post(f"{first}/api/v1/logout")).status_code == 200
        assert (await browser.get(f"{first}/api/v1/session")).json()["authenticated"] is False
        assert (await browser.post(f"{first}/api/v1/refresh")).status_code == 401
        response = await browser.get(f"{second}/api/v1/session")
        assert response.json()["user"]["username"] == "langflow"
        assert (await browser.post(f"{second}/api/v1/refresh")).status_code == 200

        for unrelated in ("/", "/langflow-a-other/api/v1/session"):
            request = browser.build_request("GET", unrelated)
            assert "cookie" not in request.headers


@pytest.mark.parametrize("prefix", ["/langflow-openrag", "/tools/langflow"])
@pytest.mark.parametrize("automatic", [False, True])
async def test_prefixed_login_with_stale_root_cookies(client, active_user, monkeypatch, prefix, automatic):  # noqa: ARG001
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", automatic)
    app = _instance(monkeypatch, prefix)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as browser:
        for name in ("access_token_lf", "refresh_token_lf"):
            browser.cookies.set(name, "stale-root-token", path="/")

        if automatic:
            response = await browser.get(f"{prefix}/api/v1/auto_login")
            username = "langflow"
        else:
            response = await browser.post(
                f"{prefix}/api/v1/login",
                data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
            )
            username = active_user.username
        assert response.status_code == 200

        response = await browser.get(f"{prefix}/api/v1/users/whoami")
        assert response.status_code == 200, response.text
        assert response.json()["username"] == username
        response = await browser.get(f"{prefix}/api/v1/session")
        assert response.json()["user"]["username"] == username
        assert (await browser.post(f"{prefix}/api/v1/refresh")).status_code == 200

        cookie_header = browser.build_request("GET", f"{prefix}/api/v1/session").headers["cookie"]
        scope = {"app": app, "headers": [(b"cookie", cookie_header.encode())], "query_string": b""}
        async with session_scope() as db:
            request = Request({**scope, "type": "http"})
            assert (await get_current_user_for_sse(request, db)).username == username
            assert (await get_current_user_optional(request, db)).username == username
            websocket = WebSocket({**scope, "type": "websocket"}, receive=AsyncMock(), send=AsyncMock())
            assert (await get_current_user_for_websocket(websocket, db)).username == username

        response = await browser.get(
            f"{prefix}/api/v1/users/whoami", headers={"Authorization": "Bearer invalid-explicit-token"}
        )
        assert response.status_code == 401

        assert (await browser.post(f"{prefix}/api/v1/logout")).status_code == 200
        assert (await browser.get(f"{prefix}/api/v1/session")).json()["authenticated"] is False
        assert (await browser.post(f"{prefix}/api/v1/refresh")).status_code == 401
        assert {cookie.path for cookie in browser.cookies.jar} == {"/"}
        assert {cookie.value for cookie in browser.cookies.jar} == {"stale-root-token"}


async def test_prefixed_logout_does_not_restore_or_clear_parent_session(client, active_user, monkeypatch):  # noqa: ARG001
    app = FastAPI()
    prefix = "/langflow-openrag"
    app.mount(prefix, _instance(monkeypatch, prefix))
    app.mount("/", _instance(monkeypatch, ""))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as browser:
        for path, username, password in (
            ("", active_user.username, "testpassword"),
            (prefix, "langflow", "test-superuser-password"),
        ):
            response = await browser.post(f"{path}/api/v1/login", data={"username": username, "password": password})
            assert response.status_code == 200
            response = await browser.get(f"{path}/api/v1/session")
            assert response.json()["user"]["username"] == username

        assert (await browser.post(f"{prefix}/api/v1/logout")).status_code == 200
        assert (await browser.get(f"{prefix}/api/v1/session")).json()["authenticated"] is False
        assert (await browser.post(f"{prefix}/api/v1/refresh")).status_code == 401
        response = await browser.get("/api/v1/session")
        assert response.json()["user"]["username"] == active_user.username
        assert (await browser.post("/api/v1/refresh")).status_code == 200
