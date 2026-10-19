"""Verify cookie routing when Langflow instances share a hostname."""

from http.cookies import SimpleCookie

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langflow.main import setup_app
from langflow.services.deps import get_settings_service


def _instance(monkeypatch: pytest.MonkeyPatch, prefix: str) -> FastAPI:
    with monkeypatch.context() as settings_patch:
        settings_patch.setattr(get_settings_service().settings, "root_path", prefix)
        return setup_app()


def _assert_cookie_paths(response, path: str, names: set[str]) -> None:
    cookies = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookies.load(header)
    assert set(cookies) == names
    assert {cookie["path"] for cookie in cookies.values()} == {path}


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
        _assert_cookie_paths(response, path, names)

        response = await browser.post(f"{path}api/v1/refresh")
        assert response.status_code == 200
        _assert_cookie_paths(response, path, {"access_token_lf", "refresh_token_lf"})

        response = await browser.post(f"{path}api/v1/logout")
        assert response.status_code == 200
        _assert_cookie_paths(response, path, names)
        assert not list(browser.cookies.jar)
        assert (await browser.post(f"{path}api/v1/refresh")).status_code == 401


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
