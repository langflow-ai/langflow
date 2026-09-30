"""Tests for serving the built frontend via FastAPI's ``app.frontend()``.

``setup_static_files`` serves the build with ``app.frontend()`` instead of a
manual ``StaticFiles`` mount. ``app.frontend()`` returns ``index.html`` for any
unmatched GET, so a ``/api`` GET/HEAD reservation plus the app-wide 404 handler
keep the old contract: missing API paths stay JSON 404s, wrong methods stay 405,
and non-API deep links (including dotted ones) load the SPA.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langflow.main import setup_app


@pytest.fixture
def frontend_client(tmp_path: Path) -> TestClient:
    dist = tmp_path / "frontend"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Langflow</title><div id='root'></div>")
    (dist / "assets" / "app.js").write_text("console.log('app')")
    app = setup_app(static_files_dir=dist)
    return TestClient(app, raise_server_exceptions=False)


def test_serves_spa_index_at_root(frontend_client: TestClient):
    response = frontend_client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "id='root'" in response.text


def test_serves_static_asset(frontend_client: TestClient):
    response = frontend_client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_client_route_falls_back_to_index(frontend_client: TestClient):
    # Extensionless deep links are served the SPA shell by app.frontend() itself.
    response = frontend_client.get("/flows/some/client/route")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "id='root'" in response.text


def test_dotted_client_route_falls_back_to_index(frontend_client: TestClient):
    # A deep link whose last segment has a dot is not a "navigation" request to
    # app.frontend(), so the app-wide 404 handler must still return the SPA.
    response = frontend_client.get("/flow/my.flow.v2")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "id='root'" in response.text


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
