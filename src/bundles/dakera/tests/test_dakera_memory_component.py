"""Unit tests for the Dakera Memory extension bundle (``lfx-dakera``).

These tests travel with the bundle and import the public entry point. The
Dakera server is mocked at the ``httpx.Client`` boundary so no live server is
required; each test asserts the request the component sends and the DataFrame
it builds from the mocked response.
"""

from __future__ import annotations

import json

import pytest
from lfx.schema.dataframe import DataFrame
from lfx_dakera import DakeraMemoryComponent


class _FakeResponse:
    def __init__(self, payload: dict | None, status_code: int = 200):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.text = json.dumps(self._payload)

    @property
    def content(self) -> bytes:
        return json.dumps(self._payload).encode()

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """Context-manager stand-in for ``httpx.Client`` that records the last call."""

    calls: list[dict] = []

    def __init__(self, response: _FakeResponse):
        self._response = response

    def __call__(self, *_args, **_kwargs):  # httpx.Client(...) constructor
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def request(self, method, path, *, json=None, params=None):
        _FakeClient.calls.append({"method": method, "path": path, "json": json, "params": params})
        return self._response


def _patch_httpx(monkeypatch, payload: dict | None, status_code: int = 200):
    _FakeClient.calls = []
    fake = _FakeClient(_FakeResponse(payload, status_code))
    monkeypatch.setattr(
        "lfx_dakera.components.dakera.dakera_memory.httpx.Client",
        fake,
    )
    return fake


@pytest.fixture
def base_kwargs():
    return {
        "api_url": "http://localhost:3000",
        "api_key": "dk-test",
        "agent_id": "unit-agent",
        "_session_id": "test-session",
    }


def _memory(**over):
    mem = {
        "id": "mem-1",
        "content": "User prefers dark mode",
        "importance": 0.7,
        "memory_type": "semantic",
        "tags": ["preference"],
        "agent_id": "unit-agent",
        "session_id": None,
        "metadata": None,
        "created_at": 1_700_000_000,
        "last_accessed_at": 1_700_000_000,
        "access_count": 0,
    }
    mem.update(over)
    return mem


def test_component_initialization(base_kwargs):
    component = DakeraMemoryComponent(**base_kwargs, mode="Recall")
    node = component.to_frontend_node()["data"]["node"]
    assert node["template"]["mode"]["value"] == "Recall"
    assert node["template"]["api_url"]["value"] == "http://localhost:3000"
    assert node["template"]["agent_id"]["value"] == "unit-agent"


def test_store_sends_expected_body(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, {"memory": _memory(), "embedding_time_ms": 3})
    component = DakeraMemoryComponent(
        **base_kwargs,
        mode="Store",
        content="User prefers dark mode",
        importance=0.7,
        tags="preference, ui",
    )
    result = component.run_action()
    assert isinstance(result, DataFrame)
    call = _FakeClient.calls[-1]
    assert call["method"] == "POST"
    assert call["path"] == "/v1/memory/store"
    assert call["json"]["content"] == "User prefers dark mode"
    assert call["json"]["agent_id"] == "unit-agent"
    assert call["json"]["importance"] == 0.7
    assert call["json"]["tags"] == ["preference", "ui"]
    assert result.iloc[0]["id"] == "mem-1"


def test_store_requires_content(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, {})
    component = DakeraMemoryComponent(**base_kwargs, mode="Store", content="   ")
    with pytest.raises(ValueError, match="content"):
        component.run_action()


def test_recall_parses_scored_results(base_kwargs, monkeypatch):
    payload = {
        "memories": [
            {"memory": _memory(id="mem-1"), "score": 0.912345, "smart_score": 0.88},
            {"memory": _memory(id="mem-2"), "score": 0.4},
        ],
        "query_embedding_time_ms": 2,
        "search_time_ms": 1,
    }
    _patch_httpx(monkeypatch, payload)
    component = DakeraMemoryComponent(**base_kwargs, mode="Recall", query="what does the user prefer?", top_k=5)
    result = component.run_action()
    call = _FakeClient.calls[-1]
    assert call["path"] == "/v1/memory/recall"
    assert call["json"]["query"] == "what does the user prefer?"
    assert call["json"]["top_k"] == 5
    assert len(result) == 2
    assert result.iloc[0]["score"] == 0.9123
    assert result.iloc[0]["smart_score"] == 0.88


def test_recall_requires_query(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, {"memories": []})
    component = DakeraMemoryComponent(**base_kwargs, mode="Recall", query="")
    with pytest.raises(ValueError, match="query"):
        component.run_action()


def test_search_sends_filters(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, {"memories": [], "total_count": 0})
    component = DakeraMemoryComponent(
        **base_kwargs,
        mode="Search",
        query="",
        tags="preference",
        min_importance=0.3,
        sort_by="importance",
        top_k=10,
    )
    component.run_action()
    body = _FakeClient.calls[-1]["json"]
    assert body["tags"] == ["preference"]
    assert body["min_importance"] == 0.3
    assert body["sort_by"] == "importance"
    assert "query" not in body  # empty query omitted


def test_get_uses_path_and_agent_query(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, _memory(id="mem-42"))
    component = DakeraMemoryComponent(**base_kwargs, mode="Get", memory_id="mem-42")
    result = component.run_action()
    call = _FakeClient.calls[-1]
    assert call["method"] == "GET"
    assert call["path"] == "/v1/memory/get/mem-42"
    assert call["params"] == {"agent_id": "unit-agent"}
    assert result.iloc[0]["id"] == "mem-42"


def test_update_sends_only_changed_fields(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, _memory(id="mem-1", content="Updated"))
    component = DakeraMemoryComponent(
        **base_kwargs,
        mode="Update",
        memory_id="mem-1",
        content="Updated",
        importance=0.9,
    )
    component.run_action()
    call = _FakeClient.calls[-1]
    assert call["method"] == "PUT"
    assert call["path"] == "/v1/memory/update/mem-1"
    assert call["params"] == {"agent_id": "unit-agent"}
    assert call["json"] == {"content": "Updated", "importance": 0.9}


def test_update_requires_a_change(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, _memory())
    # importance left at default 0.5 and no content/tags/metadata -> nothing to change
    component = DakeraMemoryComponent(**base_kwargs, mode="Update", memory_id="mem-1", content="")
    with pytest.raises(ValueError, match="at least one field"):
        component.run_action()


def test_forget_requires_a_selector(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, {"deleted_count": 0})
    component = DakeraMemoryComponent(**base_kwargs, mode="Forget", memory_id="", tags="")
    with pytest.raises(ValueError, match="selector"):
        component.run_action()


def test_forget_by_id(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, {"deleted_count": 1})
    component = DakeraMemoryComponent(**base_kwargs, mode="Forget", memory_id="mem-1")
    result = component.run_action()
    body = _FakeClient.calls[-1]["json"]
    assert body["memory_ids"] == ["mem-1"]
    assert result.iloc[0]["deleted_count"] == 1


def test_http_error_raises_with_detail(base_kwargs, monkeypatch):
    _patch_httpx(monkeypatch, {"error": "unauthorized"}, status_code=401)
    component = DakeraMemoryComponent(**base_kwargs, mode="Recall", query="hi")
    with pytest.raises(ValueError, match="HTTP 401"):
        component.run_action()


def test_bearer_header_set_when_api_key_present(base_kwargs, monkeypatch):
    captured = {}

    def fake_client(*_args, **kwargs):
        captured.update(kwargs)
        return _FakeClient(_FakeResponse({"memories": []}))

    monkeypatch.setattr("lfx_dakera.components.dakera.dakera_memory.httpx.Client", fake_client)
    component = DakeraMemoryComponent(**base_kwargs, mode="Recall", query="hi")
    component.run_action()
    assert captured["headers"]["Authorization"] == "Bearer dk-test"


def test_unknown_mode_raises(base_kwargs):
    component = DakeraMemoryComponent(**base_kwargs, mode="Explode")
    with pytest.raises(ValueError, match="Unknown Dakera mode"):
        component.run_action()


def test_update_build_config_toggles_fields():
    """Selecting the Store mode shows Store fields and hides Recall-only fields."""
    component = DakeraMemoryComponent(mode="Store")
    # Minimal build_config with the fields we assert on; each entry needs a
    # ``show`` key for set_field_display to toggle it.
    build_config = {
        "mode": {"value": "Store", "show": True},
        "content": {"show": False},
        "importance": {"show": False},
        "query": {"show": True},
        "top_k": {"show": True},
        "agent_id": {"show": True},
    }
    updated = component.update_build_config(build_config, "Store", "mode")
    assert updated["content"]["show"] is True  # Store field -> shown
    assert updated["importance"]["show"] is True  # Store field -> shown
    assert updated["query"]["show"] is False  # Recall-only -> hidden
    assert updated["agent_id"]["show"] is True  # default field -> always shown
