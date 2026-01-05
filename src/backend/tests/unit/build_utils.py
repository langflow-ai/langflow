import asyncio
import json
from typing import Any
from uuid import UUID

from httpx import AsyncClient, codes
from lfx.log.logger import logger


async def create_flow(client: AsyncClient, flow_data: str, headers: dict[str, str]) -> UUID:
    """Create a flow and return its ID."""
    response = await client.post("api/v1/flows/", json=json.loads(flow_data), headers=headers)
    assert response.status_code == codes.CREATED
    return UUID(response.json()["id"])


async def build_flow(
    client: AsyncClient, flow_id: UUID, headers: dict[str, str], json: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Start a flow build and return the job_id."""
    if json is None:
        json = {}
    response = await client.post(f"api/v1/build/{flow_id}/flow", json=json, headers=headers)
    assert response.status_code == codes.OK
    return response.json()


async def get_build_events(client: AsyncClient, job_id: str, headers: dict[str, str]):
    """Get events for a build job."""
    # Add Accept header for NDJSON format
    headers_with_accept = {**headers, "Accept": "application/x-ndjson"}
    return await client.get(f"api/v1/build/{job_id}/events", headers=headers_with_accept)


async def consume_and_assert_stream(response, job_id, timeout=30.0):
    """Consume the event stream and assert the expected event structure.

    Args:
        response: The response object with an aiter_lines method
        job_id: The job ID to verify in events
        timeout: Maximum time in seconds to wait for events (default: 10s)
    """
    count = 0
    lines = []
    first_event_seen = False
    end_event_seen = False

    # Set a timeout for the entire consumption process
    try:
        # In Python 3.10, asyncio.timeout() is not available, so we use wait_for instead
        async def process_events():
            nonlocal count, lines, first_event_seen, end_event_seen
            async for line in response.aiter_lines():
                # Skip empty lines (ndjson uses double newlines)
                if not line:
                    continue

                lines.append(line)
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug(f"ERROR: Failed to parse JSON: {line}")
                    raise

                if "job_id" in parsed:
                    assert parsed["job_id"] == job_id
                    continue

                # First event should be vertices_sorted
                if not first_event_seen:
                    assert parsed["event"] == "vertices_sorted", (
                        "Invalid first event. Expected 'vertices_sorted'. Full event stream:\n" + "\n".join(lines)
                    )
                    ids = parsed["data"]["ids"]

                    assert ids == ["ChatInput-vsgM1"], "Invalid ids in first event. Full event stream:\n" + "\n".join(
                        lines
                    )

                    to_run = parsed["data"]["to_run"]
                    expected_to_run = [
                        "ChatInput-vsgM1",
                        "Prompt-VSSGR",
                        "TypeConverterComponent-koSIz",
                        "Memory-8X8Cq",
                        "ChatOutput-NAw0P",
                    ]
                    assert set(to_run) == set(expected_to_run), (
                        "Invalid to_run list in the first event. Full event stream:\n" + "\n".join(lines)
                    )
                    first_event_seen = True
                # Last event should be end
                elif parsed["event"] == "end":
                    end_event_seen = True
                # Middle events should be end_vertex
                elif parsed["event"] == "end_vertex":
                    assert parsed["data"]["build_data"] is not None, (
                        f"Missing build_data at position {count}. Full event stream:\n" + "\n".join(lines)
                    )
                # Other event types (like token or add_message) are allowed and ignored
                else:
                    # Allow other event types to pass through without failing
                    pass

                count += 1

                # Debug output for verbose mode to track progress
                if count % 10 == 0:
                    logger.debug(f"Processed {count} events so far")

        await asyncio.wait_for(process_events(), timeout=timeout)
    except asyncio.TimeoutError as e:
        # If we timed out, logger.debug what we have so far and fail the test
        events_summary = "\n".join(
            f"{i}: {line[:80]}..." if len(line) > 80 else f"{i}: {line}" for i, line in enumerate(lines)
        )
        logger.debug(
            f"ERROR: Test timed out after {timeout}s. Processed {count} events.\nEvents received:\n{events_summary}"
        )
        if first_event_seen and not end_event_seen:
            msg = f"Test timed out after {timeout}s waiting for 'end' event"
            raise TimeoutError(msg) from e
        if not first_event_seen:
            msg = f"Test timed out after {timeout}s waiting for 'vertices_sorted' event"
            raise TimeoutError(msg) from e
        msg = f"Test timed out after {timeout}s"
        raise TimeoutError(msg) from e

    # Verify we saw both the first and end events
    assert first_event_seen, "Missing vertices_sorted event. Full event stream:\n" + "\n".join(lines)
    assert end_event_seen, "Missing end event. Full event stream:\n" + "\n".join(lines)

    # logger.debug summary of events processed
    logger.debug(f"Successfully processed {count} events for job {job_id}")
    return count
