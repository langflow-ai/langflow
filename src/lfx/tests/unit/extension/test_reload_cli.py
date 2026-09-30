"""Tests for the reload CLI: HTTP client + ``lfx extension reload``."""

from __future__ import annotations

import pytest
from lfx.cli._extension_reload_client import (
    DEFAULT_TARGET,
    ReloadHttpResponse,
    reload_via_http,
    resolve_api_key,
    resolve_target,
)

# ---------------------------------------------------------------------------
# resolve_target / resolve_api_key
# ---------------------------------------------------------------------------


def test_resolve_target_prefers_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_HOST", "http://from-env")
    assert resolve_target("http://explicit/") == "http://explicit"


def test_resolve_target_uses_langflow_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_HOST", "http://from-env/")
    monkeypatch.delenv("LANGFLOW_SERVER_URL", raising=False)
    assert resolve_target(None) == "http://from-env"


def test_resolve_target_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFLOW_HOST", raising=False)
    monkeypatch.delenv("LANGFLOW_SERVER_URL", raising=False)
    assert resolve_target(None) == DEFAULT_TARGET


def test_resolve_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_API_KEY", "envkey")
    assert resolve_api_key(None) == "envkey"
    assert resolve_api_key("explicit") == "explicit"


# ---------------------------------------------------------------------------
# reload_via_http
# ---------------------------------------------------------------------------


class _StubResponse:
    """Minimal stand-in for ``httpx.Response``."""

    def __init__(self, status_code: int, body: object) -> None:
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self) -> object:
        if isinstance(self._body, ValueError):
            raise self._body
        return self._body


class _StubClient:
    """Stand-in for ``httpx.Client`` returning a queued response."""

    def __init__(self, response: _StubResponse) -> None:
        self._response = response
        self.captured: dict[str, object] = {}

    def __enter__(self) -> _StubClient:  # noqa: PYI034 - test stub mimics httpx.Client.__enter__
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url: str, *, headers: dict[str, str]) -> _StubResponse:
        self.captured["url"] = url
        self.captured["headers"] = headers
        return self._response


@pytest.fixture
def patched_httpx(monkeypatch: pytest.MonkeyPatch) -> dict[str, _StubClient | None]:
    holder: dict[str, _StubClient | None] = {"client": None}

    def _factory_for(response: _StubResponse) -> None:
        client = _StubClient(response)
        holder["client"] = client
        monkeypatch.setattr(
            "lfx.cli._extension_reload_client.httpx.Client",
            lambda *_args, **_kwargs: client,
        )

    holder["install"] = _factory_for  # type: ignore[assignment]
    return holder


def test_reload_via_http_success(patched_httpx: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFLOW_HOST", raising=False)
    monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)
    response_body = {"ok": True, "bundle": "pilot", "components_added": ["X"], "components_removed": []}
    patched_httpx["install"](_StubResponse(200, response_body))  # type: ignore[operator]

    result = reload_via_http(
        target="http://server",
        api_key="abc",
        extension_id="lfx-pilot",
        bundle_name="pilot",
    )
    assert isinstance(result, ReloadHttpResponse)
    assert result.ok
    assert result.exit_code() == 0
    assert result.payload == response_body

    captured = patched_httpx["client"].captured  # type: ignore[union-attr]
    assert captured["url"] == "http://server/api/v1/extensions/lfx-pilot/bundles/pilot/reload"
    assert captured["headers"]["x-api-key"] == "abc"


def test_reload_via_http_propagates_typed_error(patched_httpx: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFLOW_HOST", raising=False)
    body = {"ok": False, "errors": [{"code": "module-import-failed", "message": "boom", "hint": "fix"}]}
    patched_httpx["install"](_StubResponse(200, body))  # type: ignore[operator]

    result = reload_via_http(
        target="http://server",
        api_key=None,
        extension_id="ext",
        bundle_name="ext",
    )
    assert not result.ok
    assert result.exit_code() == 1
    assert result.payload["errors"][0]["code"] == "module-import-failed"


def test_reload_via_http_409_in_progress(patched_httpx: dict) -> None:
    body = {"detail": {"code": "reload-in-progress", "message": "in flight", "bundle": "pilot"}}
    patched_httpx["install"](_StubResponse(409, body))  # type: ignore[operator]

    result = reload_via_http(
        target="http://server",
        api_key=None,
        extension_id="lfx-pilot",
        bundle_name="pilot",
    )
    assert result.status == 409
    assert not result.ok
    assert result.payload["detail"]["code"] == "reload-in-progress"


def test_reload_via_http_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class _ExplodingClient:
        def __enter__(self) -> _ExplodingClient:  # noqa: PYI034 - test stub mimics httpx.Client.__enter__
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> None:
            error_message = "connect refused"
            raise httpx.RequestError(error_message)

    monkeypatch.setattr(
        "lfx.cli._extension_reload_client.httpx.Client",
        lambda *_a, **_kw: _ExplodingClient(),
    )

    result = reload_via_http(
        target="http://server",
        api_key=None,
        extension_id="ext",
        bundle_name="ext",
    )
    assert result.status == 0
    assert not result.ok
    assert result.payload["errors"][0]["code"] == "reload-transport-error"


def test_reload_via_http_non_json_body(patched_httpx: dict) -> None:
    patched_httpx["install"](_StubResponse(500, ValueError("not json")))  # type: ignore[operator]
    result = reload_via_http(
        target="http://server",
        api_key=None,
        extension_id="ext",
        bundle_name="ext",
    )
    assert result.status == 500
    assert not result.ok
    assert result.payload["errors"][0]["code"] == "reload-transport-error"
