"""Verify portable frontend assets, runtime prefixes, and API error responses."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langflow.main import setup_app, setup_static_files
from langflow.services.settings.base import Settings

INDEX_HTML = '<!doctype html><html><head><base href="./" /></head><body><div id="root"></div></body></html>'


@pytest.fixture
def frontend_client(tmp_path: Path) -> TestClient:
    dist = tmp_path / "frontend"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML)
    (dist / "assets" / "app.js").write_text("console.log('app')")
    app = setup_app(static_files_dir=dist)
    return TestClient(app, raise_server_exceptions=False)


def test_serves_spa_index_at_root(frontend_client: TestClient):
    response = frontend_client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="root"' in response.text


def test_serves_static_asset(frontend_client: TestClient):
    response = frontend_client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_client_route_falls_back_to_index(frontend_client: TestClient):
    # Client-side routes receive the same runtime configuration as the root.
    response = frontend_client.get("/flows/some/client/route")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="root"' in response.text


def test_dotted_client_route_falls_back_to_index(frontend_client: TestClient):
    # Dotted deep links also reach the SPA fallback.
    response = frontend_client.get("/flow/my.flow.v2")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="root"' in response.text


def test_unknown_api_path_returns_json_404(frontend_client: TestClient):
    # Missing API paths must stay JSON 404s, not the SPA index.html.
    response = frontend_client.get("/api/v1/definitely-not-a-real-route")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}


def test_wrong_method_on_real_api_route_returns_405(frontend_client: TestClient):
    # The /api reservation only claims GET/HEAD, so a wrong method on a real
    # endpoint still gets 405, not a 404 swallowed by the catch-all.
    response = frontend_client.post("/api/v1/version")
    assert response.status_code == 405
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("prefix", ["", "/langflow", "/tools/langflow"])
def test_runtime_prefix_reuses_frontend_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: str):
    index = tmp_path / "index.html"
    index.write_text(INDEX_HTML)
    index.chmod(0o444)
    (tmp_path / "app.js").write_text("export default 'unchanged'")
    monkeypatch.setenv("LANGFLOW_ROOT_PATH", prefix)
    app = FastAPI(root_path=Settings().root_path)
    setup_static_files(app, tmp_path)
    client = TestClient(app)

    for route in ["/", "/index.html", "/settings/api-keys", "/flow/my.flow.v2"]:
        response = client.get(f"{prefix}{route}")
        assert response.status_code == 200
        assert f'<base href="{prefix}/"' in response.text
        assert response.headers["cache-control"] == "no-store"
        assert client.head(f"{prefix}{route}").content == b""

    assert client.get(f"{prefix}/app.js").text == "export default 'unchanged'"
    response = client.get(f"{prefix}/api/v1/missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    assert client.head(f"{prefix}/api/v1/missing").status_code == 404
    assert client.post(f"{prefix}/api/v1/missing").status_code == 405
    assert index.read_text() == INDEX_HTML


def test_forwarded_prefix_cannot_change_frontend_base(frontend_client: TestClient):
    response = frontend_client.get("/", headers={"X-Forwarded-Prefix": '//evil.example/"/><script>alert(1)</script>'})
    assert '<base href="/"' in response.text
    assert "evil.example" not in response.text


@pytest.mark.parametrize("prefix", ["//evil.example", "/a/../b", "/a\\b", '/a"/><script>', "/a?b", "/a#b"])
def test_rejects_unsafe_frontend_prefix(tmp_path: Path, prefix: str):
    (tmp_path / "index.html").write_text(INDEX_HTML)
    with pytest.raises(ValueError, match="LANGFLOW_ROOT_PATH"):
        setup_static_files(FastAPI(root_path=prefix), tmp_path)
