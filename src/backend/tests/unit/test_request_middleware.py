"""Tests for the pure ASGI request middlewares in ``langflow.main``.

``RequestContextMiddleware`` replaces five ``@app.middleware("http")`` layers and
``JavaScriptMIMETypeMiddleware`` replaces a BaseHTTPMiddleware. These tests pin the behaviour
each former layer had.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from langflow.main import JavaScriptMIMETypeMiddleware, RequestContextMiddleware
from lfx.observability import EXECUTION_CLIENT_HEADER, get_execution_client
from pydantic_core import PydanticSerializationError

BOUNDARY = "testboundary123"


def _build_app(*, root_path: str = "") -> FastAPI:
    app = FastAPI()

    @app.get("/echo")
    def echo(request: Request):
        return {
            "locale": request.state.locale,
            "query": request.scope["query_string"].decode(),
            "root_path": request.scope.get("root_path", ""),
            "client": get_execution_client(),
        }

    @app.post("/api/v1/files/upload/{flow_id}")
    async def upload(flow_id: str, request: Request):
        return {"flow_id": flow_id, "size": len(await request.body())}

    @app.get("/assets/{name}")
    def asset(name: str):
        if name == "missing.js":
            return PlainTextResponse("missing", status_code=404)
        return PlainTextResponse("console.log(1)")

    @app.get("/api/v1/files/{name}")
    def stored_file(name: str):
        return PlainTextResponse(f"stored {name}")

    @app.get("/broken")
    def broken():
        msg = "cannot serialize"
        raise PydanticSerializationError(msg)

    app.add_middleware(JavaScriptMIMETypeMiddleware)
    app.add_middleware(RequestContextMiddleware, settings=SimpleNamespace(root_path=root_path))
    return app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        RequestContextMiddleware, "locale", _fixed_locales(RequestContextMiddleware.locale, {"en", "fr", "zh-Hans"})
    )
    return TestClient(_build_app())


def _fixed_locales(locale, supported):
    def wrapper(self, accept_lang):
        self.supported_locales = frozenset(supported)
        return locale(self, accept_lang)

    return wrapper


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("fr-FR,fr;q=0.9,en;q=0.8", "fr"),
        ("zh-Hans-CN", "zh-Hans"),
        ("xx-YY", "en"),
        (None, "en"),
    ],
)
def test_locale_is_parsed_into_request_state(client, header, expected):
    headers = {"Accept-Language": header} if header else {}
    assert client.get("/echo", headers=headers).json()["locale"] == expected


def test_comma_separated_query_values_become_repeated_parameters(client):
    query = client.get("/echo?a=1,2&q=x,y&b=3").json()["query"]
    assert query == "a=1&a=2&q=x%2Cy&b=3"


def test_forwarded_prefix_sets_root_path_only_in_reverse_proxy_mode():
    plain = TestClient(_build_app()).get("/echo", headers={"X-Forwarded-Prefix": "/proxy"})
    assert plain.json()["root_path"] == ""

    proxied = TestClient(_build_app(root_path="/configured"), root_path="/configured")
    assert proxied.get("/echo", headers={"X-Forwarded-Prefix": "/proxy/"}).json()["root_path"] == "/proxy"
    assert proxied.get("/echo", headers={"X-Forwarded-Prefix": "https://evil"}).json()["root_path"] == "/configured"


def test_upload_without_multipart_boundary_is_rejected(client):
    response = client.post("/api/v1/files/upload/f1", content=b"{}", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "boundary" in response.json()["detail"]


def test_upload_with_bad_multipart_body_is_rejected(client):
    response = client.post(
        "/api/v1/files/upload/f1",
        content=b"not multipart",
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid multipart formatting"


def test_valid_upload_reaches_the_endpoint_with_its_body(client):
    body = f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"\r\n\r\nx\r\n--{BOUNDARY}--\r\n'.encode()
    response = client.post(
        "/api/v1/files/upload/f1", content=body, headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}
    )
    assert response.status_code == 200
    assert response.json() == {"flow_id": "f1", "size": len(body)}


@pytest.mark.parametrize(("header", "expected"), [("sdk", "sdk"), ("unknown", None), (None, None)])
def test_execution_client_is_bound_for_the_request_only(client, header, expected):
    headers = {EXECUTION_CLIENT_HEADER: header} if header else {}
    assert client.get("/echo", headers=headers).json()["client"] == expected
    assert get_execution_client() is None


def test_javascript_paths_are_served_as_text_javascript(client):
    assert client.get("/assets/app.js").headers["content-type"] == "text/javascript"
    assert client.get("/assets/app.css").headers["content-type"].startswith("text/plain")
    assert client.get("/assets/missing.js").headers["content-type"].startswith("text/plain")
    assert client.get("/api/v1/files/app.js").headers["content-type"].startswith("text/plain")


def test_response_serialization_failure_becomes_http_500(client):
    with pytest.raises(HTTPException) as raised:
        client.get("/broken")
    assert raised.value.status_code == 500
    assert "cannot serialize" in raised.value.detail
