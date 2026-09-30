"""Unit tests for file-based push/pull helpers on both client variants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from langflow_sdk import AsyncClient, Client
from langflow_sdk.exceptions import LangflowHTTPError
from langflow_sdk.models import Flow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_URL = "http://langflow.test"
_FLOW_ID = "00000000-0000-0000-0000-000000000042"

_SAMPLE_FLOW: dict[str, Any] = {
    "id": _FLOW_ID,
    "name": "My Flow",
    "description": "A sample flow",
    "data": {"nodes": [], "edges": []},
    "is_component": False,
    "endpoint_name": None,
    "tags": None,
    "folder_id": None,
    "icon": None,
    "icon_bg_color": None,
    "locked": False,
    "mcp_enabled": False,
    # Volatile fields that should be stripped on pull
    "updated_at": "2024-01-01T00:00:00Z",
    "user_id": "99999999-0000-0000-0000-000000000000",
    "webhook": False,
    "access_type": "PRIVATE",
}

_FLOW_RESPONSE = {
    "id": _FLOW_ID,
    "name": "My Flow",
    "description": "A sample flow",
    "data": {"nodes": [], "edges": []},
    "is_component": False,
    "updated_at": "2024-01-01T00:00:00Z",
    "endpoint_name": None,
    "folder_id": None,
    "user_id": "99999999-0000-0000-0000-000000000000",
    "locked": False,
    "mcp_enabled": False,
    "webhook": False,
    "access_type": "PRIVATE",
}


class _MockTransport(httpx.BaseTransport):
    """Simple transport returning a fixed response."""

    def __init__(self, *, status: int = 200, body: Any = None, created: bool = False) -> None:
        self._status = status
        self._body = body
        self._created = created

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201 if self._created else self._status,
            json=self._body,
            request=request,
        )


class _AsyncMockTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, status: int = 200, body: Any = None, created: bool = False) -> None:
        self._status = status
        self._body = body
        self._created = created

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201 if self._created else self._status,
            json=self._body,
            request=request,
        )


def _sync_client(transport: _MockTransport) -> Client:
    http = httpx.Client(base_url=_BASE_URL, transport=transport)
    return Client(_BASE_URL, httpx_client=http)


def _async_client(transport: _AsyncMockTransport) -> AsyncClient:
    http = httpx.AsyncClient(base_url=_BASE_URL, transport=transport)
    return AsyncClient(_BASE_URL, httpx_client=http)


# ---------------------------------------------------------------------------
# client.push() — sync
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_push_upserts_flow_from_file(tmp_path: Path) -> None:
    flow_file = tmp_path / "my-flow.json"
    flow_file.write_text(json.dumps(_SAMPLE_FLOW), encoding="utf-8")

    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE, created=False))
    flow, created = client.push(flow_file)

    assert isinstance(flow, Flow)
    assert flow.id == UUID(_FLOW_ID)
    assert flow.name == "My Flow"
    assert created is False
    client.close()


@pytest.mark.unit
def test_push_reports_created_on_201(tmp_path: Path) -> None:
    flow_file = tmp_path / "new-flow.json"
    flow_file.write_text(json.dumps(_SAMPLE_FLOW), encoding="utf-8")

    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE, created=True))
    _, created = client.push(flow_file)

    assert created is True
    client.close()


@pytest.mark.unit
def test_push_accepts_string_path(tmp_path: Path) -> None:
    flow_file = tmp_path / "flow.json"
    flow_file.write_text(json.dumps(_SAMPLE_FLOW), encoding="utf-8")

    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE))
    flow, _ = client.push(str(flow_file))  # string, not Path

    assert flow.name == "My Flow"
    client.close()


@pytest.mark.unit
def test_push_raises_on_missing_id(tmp_path: Path) -> None:
    no_id = {k: v for k, v in _SAMPLE_FLOW.items() if k != "id"}
    flow_file = tmp_path / "no-id.json"
    flow_file.write_text(json.dumps(no_id), encoding="utf-8")

    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE))
    with pytest.raises(ValueError, match="'id'"):
        client.push(flow_file)
    client.close()


@pytest.mark.unit
def test_push_sends_put_request(tmp_path: Path) -> None:
    captured: list[httpx.Request] = []

    class _CapturingTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_FLOW_RESPONSE, request=request)

    flow_file = tmp_path / "flow.json"
    flow_file.write_text(json.dumps(_SAMPLE_FLOW), encoding="utf-8")

    http = httpx.Client(base_url=_BASE_URL, transport=_CapturingTransport())
    client = Client(_BASE_URL, httpx_client=http)
    client.push(flow_file)
    client.close()

    assert len(captured) == 1
    assert captured[0].method == "PUT"
    assert _FLOW_ID in str(captured[0].url)


@pytest.mark.unit
def test_push_does_not_include_id_in_body(tmp_path: Path) -> None:
    captured: list[httpx.Request] = []

    class _CapturingTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_FLOW_RESPONSE, request=request)

    flow_file = tmp_path / "flow.json"
    flow_file.write_text(json.dumps(_SAMPLE_FLOW), encoding="utf-8")

    http = httpx.Client(base_url=_BASE_URL, transport=_CapturingTransport())
    client = Client(_BASE_URL, httpx_client=http)
    client.push(flow_file)
    client.close()

    body = json.loads(captured[0].content)
    # ID belongs in the URL, not the body
    assert "id" not in body


# ---------------------------------------------------------------------------
# client.pull() — sync
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_returns_normalized_dict() -> None:
    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE))
    data = client.pull(_FLOW_ID)

    assert isinstance(data, dict)
    assert data["name"] == "My Flow"
    # Volatile fields should be stripped
    assert "updated_at" not in data
    assert "user_id" not in data
    client.close()


@pytest.mark.unit
def test_pull_writes_to_file_when_output_given(tmp_path: Path) -> None:
    out_file = tmp_path / "pulled.json"
    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE))
    client.pull(_FLOW_ID, output=out_file)

    assert out_file.exists()
    loaded = json.loads(out_file.read_text())
    assert loaded["name"] == "My Flow"
    client.close()


@pytest.mark.unit
def test_pull_creates_parent_dirs(tmp_path: Path) -> None:
    out_file = tmp_path / "deep" / "dir" / "flow.json"
    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE))
    client.pull(_FLOW_ID, output=out_file)

    assert out_file.exists()
    client.close()


@pytest.mark.unit
def test_pull_returns_dict_without_output() -> None:
    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE))
    data = client.pull(_FLOW_ID)  # no output arg

    assert isinstance(data, dict)
    assert data["id"] == _FLOW_ID
    client.close()


@pytest.mark.unit
def test_pull_raises_on_http_error() -> None:
    client = _sync_client(_MockTransport(status=404, body={"detail": "Not found"}))
    with pytest.raises(LangflowHTTPError):
        client.pull(_FLOW_ID)
    client.close()


# ---------------------------------------------------------------------------
# client.push_project() — sync
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_push_project_pushes_all_json_files(tmp_path: Path) -> None:
    for name in ("flow-a", "flow-b"):
        data = {**_SAMPLE_FLOW, "id": f"00000000-0000-0000-0000-{name[-1] * 12}", "name": name}
        (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")

    captured: list[httpx.Request] = []

    class _CapturingTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_FLOW_RESPONSE, request=request)

    http = httpx.Client(base_url=_BASE_URL, transport=_CapturingTransport())
    client = Client(_BASE_URL, httpx_client=http)
    results = client.push_project(tmp_path)
    client.close()

    assert len(results) == 2  # noqa: PLR2004
    assert all(isinstance(flow, Flow) for flow, _ in results)
    assert len(captured) == 2  # noqa: PLR2004


@pytest.mark.unit
def test_push_project_returns_empty_for_empty_dir(tmp_path: Path) -> None:
    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE))
    results = client.push_project(tmp_path)
    assert results == []
    client.close()


@pytest.mark.unit
def test_push_project_ignores_non_json_files(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("ignore me")
    (tmp_path / "flow.json").write_text(json.dumps(_SAMPLE_FLOW), encoding="utf-8")

    client = _sync_client(_MockTransport(body=_FLOW_RESPONSE))
    results = client.push_project(tmp_path)
    assert len(results) == 1
    client.close()


# ---------------------------------------------------------------------------
# client.pull_project() — sync
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_project_writes_normalized_flows(tmp_path: Path) -> None:
    import io
    import zipfile

    flow_a = {**_FLOW_RESPONSE, "name": "Flow A"}
    flow_b = {**_FLOW_RESPONSE, "name": "Flow B", "id": "00000000-0000-0000-0000-000000000099"}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("flow_a.json", json.dumps(flow_a))
        zf.writestr("flow_b.json", json.dumps(flow_b))
    zip_bytes = buf.getvalue()

    class _ZipTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes, request=request)

    http = httpx.Client(base_url=_BASE_URL, transport=_ZipTransport())
    client = Client(_BASE_URL, httpx_client=http)
    out_dir = tmp_path / "project"
    written = client.pull_project("some-project-id", output_dir=out_dir)
    client.close()

    assert len(written) == 2  # noqa: PLR2004
    assert "Flow A" in written
    assert "Flow B" in written
    assert written["Flow A"].exists()
    # Volatile fields stripped
    loaded = json.loads(written["Flow A"].read_text())
    assert "updated_at" not in loaded
    assert "user_id" not in loaded


@pytest.mark.unit
def test_pull_project_creates_output_dir(tmp_path: Path) -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("flow.json", json.dumps(_FLOW_RESPONSE))
    zip_bytes = buf.getvalue()

    class _ZipTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes, request=request)

    http = httpx.Client(base_url=_BASE_URL, transport=_ZipTransport())
    client = Client(_BASE_URL, httpx_client=http)
    out_dir = tmp_path / "new" / "deep" / "dir"
    client.pull_project("proj-id", output_dir=out_dir)
    client.close()

    assert out_dir.exists()


# ---------------------------------------------------------------------------
# AsyncClient variants
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_push_returns_flow(tmp_path: Path) -> None:
    flow_file = tmp_path / "flow.json"
    flow_file.write_text(json.dumps(_SAMPLE_FLOW), encoding="utf-8")

    client = _async_client(_AsyncMockTransport(body=_FLOW_RESPONSE, created=True))
    flow, created = await client.push(flow_file)

    assert isinstance(flow, Flow)
    assert created is True
    await client.aclose()


@pytest.mark.unit
async def test_async_push_raises_on_missing_id(tmp_path: Path) -> None:
    no_id = {k: v for k, v in _SAMPLE_FLOW.items() if k != "id"}
    flow_file = tmp_path / "no-id.json"
    flow_file.write_text(json.dumps(no_id), encoding="utf-8")

    client = _async_client(_AsyncMockTransport(body=_FLOW_RESPONSE))
    with pytest.raises(ValueError, match="'id'"):
        await client.push(flow_file)
    await client.aclose()


@pytest.mark.unit
async def test_async_pull_returns_normalized_dict() -> None:
    client = _async_client(_AsyncMockTransport(body=_FLOW_RESPONSE))
    data = await client.pull(_FLOW_ID)

    assert isinstance(data, dict)
    assert "updated_at" not in data
    await client.aclose()


@pytest.mark.unit
async def test_async_pull_writes_to_file(tmp_path: Path) -> None:
    out_file = tmp_path / "flow.json"
    client = _async_client(_AsyncMockTransport(body=_FLOW_RESPONSE))
    await client.pull(_FLOW_ID, output=out_file)

    assert out_file.exists()
    await client.aclose()


@pytest.mark.unit
async def test_async_push_project_pushes_all_files(tmp_path: Path) -> None:
    for name in ("flow-x", "flow-y"):
        data = {**_SAMPLE_FLOW, "id": f"00000000-0000-0000-0000-{name[-1] * 12}", "name": name}
        (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")

    client = _async_client(_AsyncMockTransport(body=_FLOW_RESPONSE))
    results = await client.push_project(tmp_path)
    await client.aclose()

    assert len(results) == 2  # noqa: PLR2004


@pytest.mark.unit
async def test_async_pull_project_writes_flows(tmp_path: Path) -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("flow.json", json.dumps({**_FLOW_RESPONSE, "name": "Async Flow"}))
    zip_bytes = buf.getvalue()

    class _AsyncZipTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes, request=request)

    http = httpx.AsyncClient(base_url=_BASE_URL, transport=_AsyncZipTransport())
    client = AsyncClient(_BASE_URL, httpx_client=http)
    out_dir = tmp_path / "output"
    written = await client.pull_project("proj-id", output_dir=out_dir)
    await client.aclose()

    assert "Async Flow" in written
    assert written["Async Flow"].exists()
