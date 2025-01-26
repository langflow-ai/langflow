import json
import uuid
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from langflow.memory import aget_messages
from langflow.services.database.models.flow import FlowUpdate


@pytest.mark.benchmark
async def test_build_flow(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test the build flow endpoint with the new two-step process."""
    # First create the flow
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await _build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]
    assert job_id is not None

    # Get the events stream
    events_response = await _get_build_events(client, job_id, logged_in_headers)
    assert events_response.status_code == 200

    # Consume and verify the events
    await consume_and_assert_stream(events_response, job_id)


@pytest.mark.benchmark
async def test_build_flow_from_request_data(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test building a flow from request data."""
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    flow_data = response.json()

    # Start the build and get job_id
    build_response = await _build_flow(client, flow_id, logged_in_headers, json={"data": flow_data["data"]})
    job_id = build_response["job_id"]

    # Get the events stream
    events_response = await _get_build_events(client, job_id, logged_in_headers)
    assert events_response.status_code == 200

    # Consume and verify the events
    await consume_and_assert_stream(events_response, job_id)
    await check_messages(flow_id)


async def test_build_flow_with_frozen_path(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test building a flow with a frozen path."""
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    flow_data = response.json()
    flow_data["data"]["nodes"][0]["data"]["node"]["frozen"] = True

    # Update the flow with frozen path
    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json=FlowUpdate(name="Flow", description="description", data=flow_data["data"]).model_dump(),
        headers=logged_in_headers,
    )
    response.raise_for_status()

    # Start the build and get job_id
    build_response = await _build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]

    # Get the events stream
    events_response = await _get_build_events(client, job_id, logged_in_headers)
    assert events_response.status_code == 200

    # Consume and verify the events
    await consume_and_assert_stream(events_response, job_id)
    await check_messages(flow_id)


async def check_messages(flow_id):
    if isinstance(flow_id, str):
        flow_id = UUID(flow_id)
    messages = await aget_messages(flow_id=flow_id, order="ASC")
    flow_id_str = str(flow_id)
    assert len(messages) == 2
    assert messages[0].session_id == flow_id_str
    assert messages[0].sender == "User"
    assert messages[0].sender_name == "User"
    assert messages[0].text == ""
    assert messages[1].session_id == flow_id_str
    assert messages[1].sender == "Machine"
    assert messages[1].sender_name == "AI"


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


async def _create_flow(client: AsyncClient, flow_data: str, headers: dict[str, str]) -> uuid.UUID:
    response = await client.post("api/v1/flows/", json=json.loads(flow_data), headers=headers)
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


async def _build_flow(
    client: AsyncClient, flow_id: uuid.UUID, headers: dict[str, str], json: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Start a flow build and return the job_id."""
    if json is None:
        json = {}
    response = await client.post(f"api/v1/build/{flow_id}/flow", json=json, headers=headers)
    assert response.status_code == 200
    return response.json()


async def _get_build_events(client: AsyncClient, job_id: str, headers: dict[str, str]):
    """Get events for a build job."""
    return await client.get(f"api/v1/build/{job_id}/events", headers=headers)


# TODO: Fix this test
# async def test_multiple_runs_with_no_payload_generate_max_vertex_builds(
#     client, json_memory_chatbot_no_llm, logged_in_headers
# ):
#     """Test that multiple builds of a flow generate the correct number of vertex builds."""
#     # Create the initial flow
#     flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

#     # Get the flow data to count nodes before making requests
#     response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
#     flow_data = response.json()
#     num_nodes = len(flow_data["data"]["nodes"])
#     max_vertex_builds = get_settings_service().settings.max_vertex_builds_per_vertex

#     logger.debug(f"Starting test with {num_nodes} nodes, max_vertex_builds={max_vertex_builds}")

#     # Make multiple build requests - ensure we exceed max_vertex_builds significantly
#     num_requests = max_vertex_builds * 3  # Triple the max to ensure rotation
#     for i in range(num_requests):
#         # Generate a random session ID for each request
#         session_id = session_id_generator()
#         payload = {"inputs": {"session": session_id, "type": "chat", "input_value": f"Test message {i + 1}"}}

#         async with client.stream("POST", f"api/v1/build/{flow_id}/flow",
# json=payload, headers=logged_in_headers) as r:
#             await consume_and_assert_stream(r)

#         # Add a small delay between requests to ensure proper ordering
#         await asyncio.sleep(0.1)

#         # Track builds after each request
#         async with session_scope() as session:
#             builds = await get_vertex_builds_by_flow_id(db=session, flow_id=flow_id)
#             by_vertex = {}
#             for build in builds:
#                 build_dict = build.model_dump()
#                 vertex_id = build_dict.get("id")
#                 by_vertex.setdefault(vertex_id, []).append(build_dict)

#             # Log state of each vertex with more details
#             for vertex_id, vertex_builds in by_vertex.items():
#                 vertex_builds.sort(key=lambda x: x.get("timestamp"))
#                 logger.debug(
#                     f"Request {i + 1} (session={session_id}) - Vertex {vertex_id}: {len(vertex_builds)} builds "
#                     f"(max allowed: {max_vertex_builds}), "
#                     f"build_ids: {[b.get('build_id') for b in vertex_builds]}"
#                 )

#     # Wait a bit before final verification to ensure all DB operations complete
#     await asyncio.sleep(0.5)

#     # Final verification with detailed logging
#     async with session_scope() as session:
#         vertex_builds = await get_vertex_builds_by_flow_id(db=session, flow_id=flow_id)
#         assert len(vertex_builds) > 0, "No vertex builds found"

#         builds_by_vertex = {}
#         for build in vertex_builds:
#             build_dict = build.model_dump()
#             vertex_id = build_dict.get("id")
#             builds_by_vertex.setdefault(vertex_id, []).append(build_dict)

#         # Log detailed final state
#         logger.debug(f"\nFinal state after {num_requests} requests:")
#         for vertex_id, builds in builds_by_vertex.items():
#             builds.sort(key=lambda x: x.get("timestamp"))
#             logger.debug(
#                 f"Vertex {vertex_id}: {len(builds)} builds "
#                 f"(oldest: {builds[0].get('timestamp')}, "
#                 f"newest: {builds[-1].get('timestamp')}), "
#                 f"build_ids: {[b.get('build_id') for b in builds]}"
#             )

#             # Log individual build details for debugging
#             for build in builds:
#                 logger.debug(
#                     f"  - Build {build.get('build_id')}: timestamp={build.get('timestamp')}, "
#                     f"valid={build.get('valid')}"
#                 )

#         # Verify each vertex has correct number of builds
#         for vertex_id, vertex_builds_list in builds_by_vertex.items():
#             assert len(vertex_builds_list) == max_vertex_builds, (
#                 f"Vertex {vertex_id} has {len(vertex_builds_list)} builds, expected {max_vertex_builds}"
#             )

#         # Verify total number of builds
#         total_builds = len(vertex_builds)
#         expected_total = max_vertex_builds * num_nodes
#         assert total_builds == expected_total, (
#             f"Total builds ({total_builds}) doesn't match expected "
#             f"({max_vertex_builds} builds/vertex * {num_nodes} nodes = {expected_total})"
#         )
#         assert all(vertex_build.get("valid") for vertex_build in vertex_builds)


@pytest.mark.benchmark
async def test_build_flow_invalid_job_id(client, logged_in_headers):
    """Test getting events for an invalid job ID."""
    invalid_job_id = str(uuid.uuid4())
    response = await _get_build_events(client, invalid_job_id, logged_in_headers)
    assert response.status_code == 404
    assert "No queue found for job_id" in response.json()["detail"]


@pytest.mark.benchmark
async def test_build_flow_invalid_flow_id(client, logged_in_headers):
    """Test starting a build with an invalid flow ID."""
    invalid_flow_id = uuid.uuid4()
    response = await client.post(f"api/v1/build/{invalid_flow_id}/flow", json={}, headers=logged_in_headers)
    assert response.status_code == 404


@pytest.mark.benchmark
async def test_build_flow_start_only(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test only the build flow start endpoint."""
    # First create the flow
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await _build_flow(client, flow_id, logged_in_headers)

    # Assert response structure
    assert "job_id" in build_response
    assert isinstance(build_response["job_id"], str)
    # Verify it's a valid UUID
    assert uuid.UUID(build_response["job_id"])


@pytest.mark.benchmark
async def test_build_flow_start_with_inputs(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test the build flow start endpoint with input data."""
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start build with some input data
    test_inputs = {"inputs": {"session": "test_session", "input_value": "test message"}}

    build_response = await _build_flow(client, flow_id, logged_in_headers, json=test_inputs)

    assert "job_id" in build_response
    assert isinstance(build_response["job_id"], str)
    assert uuid.UUID(build_response["job_id"])
