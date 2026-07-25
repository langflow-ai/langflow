"""Workflows API helpers for performance-suite integration tests."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest
from langflow.services.database.models.jobs.model import Job
from lfx.services.deps import session_scope

if TYPE_CHECKING:
    from httpx import AsyncClient


async def wait_job_status(job_id: str, *, want: set[str], timeout_s: float = 30.0) -> str:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
            if row is not None:
                status = row.status.value if hasattr(row.status, "value") else str(row.status)
                if status in want:
                    return status
        await asyncio.sleep(0.05)
    pytest.fail(f"job {job_id} did not reach {sorted(want)} within {timeout_s}s")


async def post_workflow(
    client: AsyncClient,
    *,
    api_key: str,
    flow_id: UUID,
    mode: str,
    input_value: str,
    session_id: str,
) -> dict[str, Any]:
    response = await client.post(
        "api/v2/workflows",
        headers={"x-api-key": api_key},
        json={
            "flow_id": str(flow_id),
            "input_value": input_value,
            "mode": mode,
            "stream_protocol": "langflow",
            "session_id": session_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def stream_workflow_until_terminal(
    client: AsyncClient,
    *,
    api_key: str,
    flow_id: UUID,
    input_value: str,
    session_id: str,
    timeout_s: float = 30.0,
) -> str:
    """POST mode=stream (langflow protocol) and collect SSE until a terminal event."""
    body = ""
    async with client.stream(
        "POST",
        "api/v2/workflows",
        headers={"x-api-key": api_key},
        json={
            "flow_id": str(flow_id),
            "input_value": input_value,
            "mode": "stream",
            "stream_protocol": "langflow",
            "session_id": session_id,
        },
        timeout=timeout_s,
    ) as response:
        assert response.status_code == 200, await response.aread()
        assert "text/event-stream" in response.headers.get("content-type", "")
        async for line in response.aiter_lines():
            body += line + "\n"
            if '"event": "end"' in line or '"event":"end"' in line or line.strip() == "event: end":
                return body
            if '"event": "error"' in line or '"event":"error"' in line or line.strip() == "event: error":
                return body
    pytest.fail(f"workflows stream did not emit a terminal event; body={body!r}")
