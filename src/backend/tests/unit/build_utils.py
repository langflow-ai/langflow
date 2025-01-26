import json
from typing import Any
from uuid import UUID

from httpx import AsyncClient


async def create_flow(client: AsyncClient, flow_data: str, headers: dict[str, str]) -> UUID:
    """Create a flow and return its ID."""
    response = await client.post("api/v1/flows/", json=json.loads(flow_data), headers=headers)
    assert response.status_code == 201
    return UUID(response.json()["id"])


async def build_flow(
    client: AsyncClient, flow_id: UUID, headers: dict[str, str], json: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Start a flow build and return the job_id."""
    if json is None:
        json = {}
    response = await client.post(f"api/v1/build/{flow_id}/flow", json=json, headers=headers)
    assert response.status_code == 200
    return response.json()


async def get_build_events(client: AsyncClient, job_id: str, headers: dict[str, str]):
    """Get events for a build job."""
    return await client.get(f"api/v1/build/{job_id}/events", headers=headers)


async def consume_and_assert_stream(response, job_id):
    """Consume the event stream and assert the expected event structure."""
    count = 0
    async for line in response.aiter_lines():
        # Skip empty lines (ndjson uses double newlines)
        if not line:
            continue

        parsed = json.loads(line)
        if "job_id" in parsed:
            assert parsed["job_id"] == job_id
            continue

        if count == 0:
            # First event should be vertices_sorted
            assert parsed["event"] == "vertices_sorted"
            ids = parsed["data"]["ids"]
            ids.sort()
            assert ids == ["ChatInput-CIGht"]

            to_run = parsed["data"]["to_run"]
            to_run.sort()
            assert to_run == ["ChatInput-CIGht", "ChatOutput-QA7ej", "Memory-amN4Z", "Prompt-iWbCC"]
        elif count > 0 and count < 5:
            # Next events should be end_vertex events
            assert parsed["event"] == "end_vertex"
            assert parsed["data"]["build_data"] is not None
        elif count == 5:
            # Final event should be end
            assert parsed["event"] == "end"
        else:
            msg = f"Unexpected line: {line}"
            raise ValueError(msg)
        count += 1
