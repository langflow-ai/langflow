"""HTTP-level tests for the /monitor/traces API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import status
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import SpanStatus, SpanTable, SpanType, TraceTable
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from httpx import AsyncClient
    from langflow.services.database.models.user.model import User

# ---------------------------------------------------------------------------
# Helpers — write data via session_scope() so it's visible to the API
# ---------------------------------------------------------------------------


async def _create_flow_for_user(user_id, name: str | None = None) -> Flow:
    """Create a flow owned by the given user and return it."""
    async with session_scope() as session:
        flow = Flow(
            name=name or f"Test Flow {uuid4().hex[:8]}",
            user_id=user_id,
            data={},
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        # Detach from session so we can use the object after the context exits
        flow_data = flow.model_dump()
    # Reconstruct a plain object with the data
    return Flow(**flow_data)


async def _create_trace(flow_id, name="Test Trace", session_id="sess-1", trace_status=SpanStatus.OK) -> TraceTable:
    async with session_scope() as session:
        trace = TraceTable(
            name=name,
            flow_id=flow_id,
            session_id=session_id,
            status=trace_status,
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
            total_latency_ms=1000,
            total_tokens=50,
        )
        session.add(trace)
        await session.flush()
        await session.refresh(trace)
        trace_data = trace.model_dump()
    return TraceTable(**trace_data)


async def _create_span(trace_id, name="Test Span", parent_span_id=None) -> SpanTable:
    async with session_scope() as session:
        span = SpanTable(
            name=name,
            trace_id=trace_id,
            span_type=SpanType.CHAIN,
            status=SpanStatus.OK,
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
            latency_ms=100,
            parent_span_id=parent_span_id,
            attributes={"total_tokens": 10},
        )
        session.add(span)
        await session.flush()
        await session.refresh(span)
        span_data = span.model_dump()
    return SpanTable(**span_data)


# ---------------------------------------------------------------------------
# GET /api/v1/monitor/traces
# ---------------------------------------------------------------------------


async def test_get_traces_empty(client: AsyncClient, logged_in_headers, active_user):  # noqa: ARG001
    """Returns empty list when no traces exist for the user's flows."""
    response = await client.get("api/v1/monitor/traces", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "traces" in data
    assert "total" in data


async def test_get_traces_returns_user_traces(client: AsyncClient, logged_in_headers, active_user: User):
    """Returns traces belonging to the authenticated user's flows."""
    flow = await _create_flow_for_user(active_user.id)
    trace = await _create_trace(flow.id, name="My Trace")

    response = await client.get(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow.id)},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] >= 1
    trace_ids = [t["id"] for t in data["traces"]]
    assert str(trace.id) in trace_ids


async def test_get_traces_filters_by_flow_id(client: AsyncClient, logged_in_headers, active_user: User):
    """Only returns traces for the specified flow_id."""
    flow1 = await _create_flow_for_user(active_user.id)
    flow2 = await _create_flow_for_user(active_user.id)
    trace1 = await _create_trace(flow1.id, name="Flow1 Trace")
    await _create_trace(flow2.id, name="Flow2 Trace")

    response = await client.get(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow1.id)},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    returned_ids = [t["id"] for t in data["traces"]]
    assert str(trace1.id) in returned_ids
    # flow2's trace should not appear
    for t in data["traces"]:
        assert t["flowId"] == str(flow1.id)


async def test_get_traces_filters_by_session_id(client: AsyncClient, logged_in_headers, active_user: User):
    """Filters traces by session_id."""
    flow = await _create_flow_for_user(active_user.id)
    trace_a = await _create_trace(flow.id, name="A", session_id="session-A")
    await _create_trace(flow.id, name="B", session_id="session-B")

    response = await client.get(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow.id), "session_id": "session-A"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    returned_ids = [t["id"] for t in data["traces"]]
    assert str(trace_a.id) in returned_ids
    for t in data["traces"]:
        assert t["sessionId"] == "session-A"


async def test_get_traces_filters_by_status(client: AsyncClient, logged_in_headers, active_user: User):
    """Filters traces by status."""
    flow = await _create_flow_for_user(active_user.id)
    await _create_trace(flow.id, name="OK", trace_status=SpanStatus.OK)
    await _create_trace(flow.id, name="Error", trace_status=SpanStatus.ERROR)

    response = await client.get(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow.id), "status": "ok"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    for t in data["traces"]:
        assert t["status"] == "ok"


async def test_get_traces_search_query(client: AsyncClient, logged_in_headers, active_user: User):
    """Search query filters by trace name."""
    flow = await _create_flow_for_user(active_user.id)
    await _create_trace(flow.id, name="UniqueSearchName")
    await _create_trace(flow.id, name="OtherTrace")

    response = await client.get(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow.id), "query": "UniqueSearch"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert all("UniqueSearch" in t["name"] for t in data["traces"])


async def test_get_traces_pagination(client: AsyncClient, logged_in_headers, active_user: User):
    """Pagination returns correct page and total."""
    flow = await _create_flow_for_user(active_user.id)
    for i in range(5):
        await _create_trace(flow.id, name=f"Trace {i}", session_id=f"sess-{i}")

    response = await client.get(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow.id), "page": 1, "size": 2},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["traces"]) <= 2
    assert data["total"] >= 5
    assert data["pages"] >= 3


async def test_get_traces_does_not_return_other_users_traces(client: AsyncClient, logged_in_headers, active_user):  # noqa: ARG001
    """Traces from another user's flows are not returned."""
    other_user_id = uuid4()
    other_flow = await _create_flow_for_user(other_user_id)
    await _create_trace(other_flow.id, name="Other User Trace")

    response = await client.get(
        "api/v1/monitor/traces",
        params={"flow_id": str(other_flow.id)},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Should return empty - user doesn't own this flow
    assert data["traces"] == []


async def test_get_traces_response_shape(client: AsyncClient, logged_in_headers, active_user: User):
    """Verifies the response shape of each trace object."""
    flow = await _create_flow_for_user(active_user.id)
    await _create_trace(flow.id)

    response = await client.get(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow.id)},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["traces"]) >= 1
    trace = data["traces"][0]
    for key in (
        "id",
        "name",
        "status",
        "startTime",
        "totalLatencyMs",
        "totalTokens",
        "totalCost",
        "flowId",
        "sessionId",
    ):
        assert key in trace, f"Missing key: {key}"


async def test_get_traces_requires_auth(client: AsyncClient):
    """Unauthenticated requests are rejected."""
    response = await client.get("api/v1/monitor/traces")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# GET /api/v1/monitor/traces/{trace_id}
# ---------------------------------------------------------------------------


async def test_get_trace_returns_trace_with_spans(client: AsyncClient, logged_in_headers, active_user: User):
    """Returns a single trace with its span tree."""
    flow = await _create_flow_for_user(active_user.id)
    trace = await _create_trace(flow.id, name="Detailed Trace")
    span = await _create_span(trace.id, name="Root Span")

    response = await client.get(
        f"api/v1/monitor/traces/{trace.id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(trace.id)
    assert data["name"] == "Detailed Trace"
    assert "spans" in data
    span_ids = [s["id"] for s in data["spans"]]
    assert str(span.id) in span_ids


async def test_get_trace_returns_hierarchical_span_tree(client: AsyncClient, logged_in_headers, active_user: User):
    """Spans are returned as a nested tree (children inside parent)."""
    flow = await _create_flow_for_user(active_user.id)
    trace = await _create_trace(flow.id)
    parent_span = await _create_span(trace.id, name="Parent")
    child_span = await _create_span(trace.id, name="Child", parent_span_id=parent_span.id)

    response = await client.get(
        f"api/v1/monitor/traces/{trace.id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Parent should be at root level
    root_spans = data["spans"]
    parent_nodes = [s for s in root_spans if s["id"] == str(parent_span.id)]
    assert len(parent_nodes) == 1
    # Child should be nested inside parent
    children = parent_nodes[0]["children"]
    child_ids = [c["id"] for c in children]
    assert str(child_span.id) in child_ids


async def test_get_trace_404_for_nonexistent_trace(client: AsyncClient, logged_in_headers, active_user):  # noqa: ARG001
    """Returns 404 when trace does not exist."""
    response = await client.get(
        f"api/v1/monitor/traces/{uuid4()}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_trace_404_for_other_users_trace(client: AsyncClient, logged_in_headers, active_user):  # noqa: ARG001
    """Returns 404 when trace belongs to another user's flow."""
    other_user_id = uuid4()
    other_flow = await _create_flow_for_user(other_user_id)
    trace = await _create_trace(other_flow.id)

    response = await client.get(
        f"api/v1/monitor/traces/{trace.id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_trace_response_shape(client: AsyncClient, logged_in_headers, active_user: User):
    """Verifies the response shape of a single trace."""
    flow = await _create_flow_for_user(active_user.id)
    trace = await _create_trace(flow.id)
    await _create_span(trace.id)

    response = await client.get(
        f"api/v1/monitor/traces/{trace.id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    for key in (
        "id",
        "name",
        "status",
        "startTime",
        "endTime",
        "totalLatencyMs",
        "totalTokens",
        "totalCost",
        "flowId",
        "sessionId",
        "spans",
    ):
        assert key in data, f"Missing key: {key}"


async def test_get_trace_requires_auth(client: AsyncClient):
    """Unauthenticated requests are rejected."""
    response = await client.get(f"api/v1/monitor/traces/{uuid4()}")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# DELETE /api/v1/monitor/traces/{trace_id}
# ---------------------------------------------------------------------------


async def test_delete_trace_removes_trace_and_spans(client: AsyncClient, logged_in_headers, active_user: User):
    """Deleting a trace removes it and its spans (cascade)."""
    flow = await _create_flow_for_user(active_user.id)
    trace = await _create_trace(flow.id)
    await _create_span(trace.id)

    response = await client.delete(
        f"api/v1/monitor/traces/{trace.id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify trace is gone
    get_response = await client.get(
        f"api/v1/monitor/traces/{trace.id}",
        headers=logged_in_headers,
    )
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_trace_404_for_nonexistent_trace(client: AsyncClient, logged_in_headers, active_user):  # noqa: ARG001
    """Returns 404 when deleting a trace that doesn't exist."""
    response = await client.delete(
        f"api/v1/monitor/traces/{uuid4()}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_trace_404_for_other_users_trace(client: AsyncClient, logged_in_headers, active_user):  # noqa: ARG001
    """Cannot delete another user's trace."""
    other_user_id = uuid4()
    other_flow = await _create_flow_for_user(other_user_id)
    trace = await _create_trace(other_flow.id)

    response = await client.delete(
        f"api/v1/monitor/traces/{trace.id}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_trace_requires_auth(client: AsyncClient):
    """Unauthenticated requests are rejected."""
    response = await client.delete(f"api/v1/monitor/traces/{uuid4()}")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# DELETE /api/v1/monitor/traces?flow_id=...
# ---------------------------------------------------------------------------


async def test_delete_traces_by_flow_removes_all_traces(client: AsyncClient, logged_in_headers, active_user: User):
    """Deletes all traces for a flow."""
    flow = await _create_flow_for_user(active_user.id)
    trace1 = await _create_trace(flow.id, name="T1", session_id="s1")
    trace2 = await _create_trace(flow.id, name="T2", session_id="s2")

    response = await client.delete(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow.id)},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify both traces are gone
    for trace_id in (trace1.id, trace2.id):
        get_response = await client.get(
            f"api/v1/monitor/traces/{trace_id}",
            headers=logged_in_headers,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_traces_by_flow_404_for_nonexistent_flow(
    client: AsyncClient,
    logged_in_headers,
    active_user,  # noqa: ARG001
):
    """Returns 404 when the flow doesn't exist."""
    response = await client.delete(
        "api/v1/monitor/traces",
        params={"flow_id": str(uuid4())},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_traces_by_flow_404_for_other_users_flow(
    client: AsyncClient,
    logged_in_headers,
    active_user,  # noqa: ARG001
):
    """Cannot delete traces from another user's flow."""
    other_user_id = uuid4()
    other_flow = await _create_flow_for_user(other_user_id)
    await _create_trace(other_flow.id)

    response = await client.delete(
        "api/v1/monitor/traces",
        params={"flow_id": str(other_flow.id)},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_traces_by_flow_requires_auth(client: AsyncClient):
    """Unauthenticated requests are rejected."""
    response = await client.delete(
        "api/v1/monitor/traces",
        params={"flow_id": str(uuid4())},
    )
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


async def test_delete_traces_by_flow_succeeds_with_no_traces(client: AsyncClient, logged_in_headers, active_user: User):
    """Deleting traces for a flow with no traces returns 204 (idempotent)."""
    flow = await _create_flow_for_user(active_user.id)

    response = await client.delete(
        "api/v1/monitor/traces",
        params={"flow_id": str(flow.id)},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
