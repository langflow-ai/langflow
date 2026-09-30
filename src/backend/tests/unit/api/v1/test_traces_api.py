"""Unit tests for langflow.api.v1.traces HTTP handlers.

Covers:
- get_traces: happy path, timeout, DB error, unexpected error, query sanitization
- get_trace: happy path, not found, timeout, DB error, unexpected error
- delete_trace: happy path, not found, unexpected error
- delete_traces_by_flow: happy path, flow not found, unexpected error

All external dependencies (fetch_traces, fetch_single_trace, session_scope,
get_current_active_user) are mocked so no real database is required.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langflow.api.v1.traces import router
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.traces.model import (
    SpanStatus,
    TraceListResponse,
    TraceRead,
    TraceSummaryRead,
)
from sqlalchemy.exc import OperationalError, ProgrammingError

_FAKE_USER_ID = uuid4()
_FAKE_FLOW_ID = uuid4()
_FAKE_TRACE_ID = uuid4()


def _make_fake_user() -> MagicMock:
    user = MagicMock()
    user.id = _FAKE_USER_ID
    return user


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_active_user] = _make_fake_user
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=False)


def _make_trace_summary(**kwargs) -> TraceSummaryRead:
    defaults: dict = {
        "id": _FAKE_TRACE_ID,
        "name": "Test Trace",
        "status": SpanStatus.OK,
        "start_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "total_latency_ms": 100,
        "total_tokens": 50,
        "flow_id": _FAKE_FLOW_ID,
        "session_id": "sess-1",
        "input": None,
        "output": None,
    }
    defaults.update(kwargs)
    return TraceSummaryRead(**defaults)


def _make_trace_read(**kwargs) -> TraceRead:
    defaults: dict = {
        "id": _FAKE_TRACE_ID,
        "name": "Test Trace",
        "status": SpanStatus.OK,
        "start_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "end_time": datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        "total_latency_ms": 100,
        "total_tokens": 50,
        "flow_id": _FAKE_FLOW_ID,
        "session_id": "sess-1",
        "input": None,
        "output": None,
        "spans": [],
    }
    defaults.update(kwargs)
    return TraceRead(**defaults)


def _empty_list_response() -> TraceListResponse:
    return TraceListResponse(traces=[], total=0, pages=0)


class TestGetTraces:
    _PATH = "/monitor/traces"

    def test_should_return_200_with_trace_list(self, client: TestClient):
        summary = _make_trace_summary()
        response_data = TraceListResponse(traces=[summary], total=1, pages=1)

        async def _fetch(*_args, **_kwargs):
            return response_data

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            resp = client.get(self._PATH)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["pages"] == 1
        assert len(body["traces"]) == 1

    def test_should_return_empty_list_on_timeout(self, client: TestClient):
        async def _fetch(*_args, **_kwargs):
            raise asyncio.TimeoutError

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            resp = client.get(self._PATH)

        assert resp.status_code == 200
        body = resp.json()
        assert body == {"traces": [], "total": 0, "pages": 0}

    def test_should_return_empty_list_on_operational_error(self, client: TestClient):
        async def _fetch(*_args, **_kwargs):
            msg = "no such table"
            raise OperationalError(msg, None, None)

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            resp = client.get(self._PATH)

        assert resp.status_code == 200
        assert resp.json() == {"traces": [], "total": 0, "pages": 0}

    def test_should_return_empty_list_on_programming_error(self, client: TestClient):
        async def _fetch(*_args, **_kwargs):
            msg = "relation does not exist"
            raise ProgrammingError(msg, None, None)

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            resp = client.get(self._PATH)

        assert resp.status_code == 200
        assert resp.json() == {"traces": [], "total": 0, "pages": 0}

    def test_should_propagate_unexpected_error(self, client: TestClient):
        async def _fetch(*_args, **_kwargs):
            msg = "boom"
            raise RuntimeError(msg)

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            resp = client.get(self._PATH)

        assert resp.status_code == 500

    def test_should_pass_sanitized_query_to_fetch_traces(self, client: TestClient):
        """Non-printable chars in query must be stripped before reaching fetch_traces."""
        captured: list[str | None] = []

        async def _fetch(_user_id, _flow_id, _session_id, _status, query, *_rest, **_kw):
            captured.append(query)
            return _empty_list_response()

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            client.get(self._PATH, params={"query": "hello\x00world"})

        assert captured == ["helloworld"]

    def test_should_pass_none_query_when_query_is_whitespace_only(self, client: TestClient):
        """Whitespace-only query must be sanitized to None."""
        captured: list[str | None] = []

        async def _fetch(_user_id, _flow_id, _session_id, _status, query, *_rest, **_kw):
            captured.append(query)
            return _empty_list_response()

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            client.get(self._PATH, params={"query": "   "})

        assert captured == [None]

    def test_should_pass_flow_id_filter(self, client: TestClient):
        captured: list[UUID | None] = []

        async def _fetch(_user_id, flow_id, *_rest, **_kw):
            captured.append(flow_id)
            return _empty_list_response()

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            client.get(self._PATH, params={"flow_id": str(_FAKE_FLOW_ID)})

        assert captured == [_FAKE_FLOW_ID]

    def test_should_pass_status_filter(self, client: TestClient):
        captured: list = []

        async def _fetch(_user_id, _flow_id, _session_id, status, *_rest, **_kw):
            captured.append(status)
            return _empty_list_response()

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            client.get(self._PATH, params={"status": "ok"})

        assert captured == [SpanStatus.OK]

    def test_should_accept_page_zero_as_first_page(self, client: TestClient):
        async def _fetch(*_args, **_kwargs):
            return _empty_list_response()

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            resp = client.get(self._PATH, params={"page": 0})

        assert resp.status_code == 200

    def test_should_reject_size_above_maximum(self, client: TestClient):
        async def _fetch(*_args, **_kwargs):
            return _empty_list_response()

        with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
            resp = client.get(self._PATH, params={"size": 201})

        assert resp.status_code == 422


class TestGetTrace:
    def _path(self, trace_id: UUID | None = None) -> str:
        return f"/monitor/traces/{trace_id or _FAKE_TRACE_ID}"

    def test_should_return_200_with_trace(self, client: TestClient):
        trace = _make_trace_read()

        async def _fetch(_user_id, _trace_id):
            return trace

        with patch("langflow.api.v1.traces.fetch_single_trace", side_effect=_fetch):
            resp = client.get(self._path())

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(_FAKE_TRACE_ID)
        assert body["name"] == "Test Trace"

    def test_should_return_404_when_trace_not_found(self, client: TestClient):
        async def _fetch(_user_id, _trace_id):
            return None

        with patch("langflow.api.v1.traces.fetch_single_trace", side_effect=_fetch):
            resp = client.get(self._path())

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Trace not found"

    def test_should_return_504_on_timeout(self, client: TestClient):
        async def _fetch(_user_id, _trace_id):
            raise asyncio.TimeoutError

        with patch("langflow.api.v1.traces.fetch_single_trace", side_effect=_fetch):
            resp = client.get(self._path())

        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"].lower()

    def test_should_return_500_on_operational_error(self, client: TestClient):
        async def _fetch(_user_id, _trace_id):
            msg = "no such table"
            raise OperationalError(msg, None, None)

        with patch("langflow.api.v1.traces.fetch_single_trace", side_effect=_fetch):
            resp = client.get(self._path())

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Database error"

    def test_should_return_500_on_unexpected_error(self, client: TestClient):
        async def _fetch(_user_id, _trace_id):
            msg = "unexpected"
            raise RuntimeError(msg)

        with patch("langflow.api.v1.traces.fetch_single_trace", side_effect=_fetch):
            resp = client.get(self._path())

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"

    def test_should_return_422_for_invalid_trace_id(self, client: TestClient):
        resp = client.get("/monitor/traces/not-a-uuid")
        assert resp.status_code == 422

    def test_should_pass_correct_user_id_to_fetch(self, client: TestClient):
        captured: list[UUID] = []

        async def _fetch(user_id, _trace_id):
            captured.append(user_id)
            return _make_trace_read()

        with patch("langflow.api.v1.traces.fetch_single_trace", side_effect=_fetch):
            client.get(self._path())

        assert captured == [_FAKE_USER_ID]


class TestDeleteTrace:
    def _path(self, trace_id: UUID | None = None) -> str:
        return f"/monitor/traces/{trace_id or _FAKE_TRACE_ID}"

    def _make_session_scope(self, trace_obj):
        """Return a context manager that yields a mock session with trace_obj."""
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.first.return_value = trace_obj
        session.exec = AsyncMock(return_value=exec_result)
        session.delete = AsyncMock()

        @asynccontextmanager
        async def _scope():
            yield session

        return _scope, session

    def test_should_return_204_on_success(self, client: TestClient):
        fake_trace = MagicMock()
        scope, session = self._make_session_scope(fake_trace)

        with patch("langflow.api.v1.traces.session_scope", scope):
            resp = client.delete(self._path())

        assert resp.status_code == 204
        session.delete.assert_awaited_once()

    def test_should_return_404_when_trace_not_found(self, client: TestClient):
        scope, _ = self._make_session_scope(None)

        with patch("langflow.api.v1.traces.session_scope", scope):
            resp = client.delete(self._path())

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Trace not found"

    def test_should_return_500_on_unexpected_error(self, client: TestClient):
        @asynccontextmanager
        async def _scope():
            msg = "db exploded"
            raise RuntimeError(msg)
            yield  # type: ignore[misc]

        with patch("langflow.api.v1.traces.session_scope", _scope):
            resp = client.delete(self._path())

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"

    def test_should_return_422_for_invalid_trace_id(self, client: TestClient):
        resp = client.delete("/monitor/traces/not-a-uuid")
        assert resp.status_code == 422


class TestDeleteTracesByFlow:
    _PATH = "/monitor/traces"

    def _make_session_scope(self, flow_obj):
        """Return a context manager that yields a mock session with flow_obj."""
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.first.return_value = flow_obj
        session.exec = AsyncMock(return_value=exec_result)
        session.execute = AsyncMock()

        @asynccontextmanager
        async def _scope():
            yield session

        return _scope, session

    def test_should_return_204_on_success(self, client: TestClient):
        fake_flow = MagicMock()
        scope, session = self._make_session_scope(fake_flow)

        with patch("langflow.api.v1.traces.session_scope", scope):
            resp = client.delete(self._PATH, params={"flow_id": str(_FAKE_FLOW_ID)})

        assert resp.status_code == 204
        session.execute.assert_awaited_once()

    def test_should_return_404_when_flow_not_found(self, client: TestClient):
        scope, _ = self._make_session_scope(None)

        with patch("langflow.api.v1.traces.session_scope", scope):
            resp = client.delete(self._PATH, params={"flow_id": str(_FAKE_FLOW_ID)})

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Flow not found"

    def test_should_return_422_when_flow_id_missing(self, client: TestClient):
        resp = client.delete(self._PATH)
        assert resp.status_code == 422

    def test_should_return_422_for_invalid_flow_id(self, client: TestClient):
        resp = client.delete(self._PATH, params={"flow_id": "not-a-uuid"})
        assert resp.status_code == 422

    def test_should_return_500_on_unexpected_error(self, client: TestClient):
        @asynccontextmanager
        async def _scope():
            msg = "db exploded"
            raise RuntimeError(msg)
            yield  # type: ignore[misc]

        with patch("langflow.api.v1.traces.session_scope", _scope):
            resp = client.delete(self._PATH, params={"flow_id": str(_FAKE_FLOW_ID)})

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"

    def test_should_execute_bulk_delete_not_individual(self, client: TestClient):
        """Verify the bulk DELETE statement is used (not N+1 individual deletes)."""
        fake_flow = MagicMock()
        scope, session = self._make_session_scope(fake_flow)

        with patch("langflow.api.v1.traces.session_scope", scope):
            client.delete(self._PATH, params={"flow_id": str(_FAKE_FLOW_ID)})

        session.execute.assert_awaited_once()
        session.delete.assert_not_called()
