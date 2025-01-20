import json
from uuid import UUID

import pytest
from langflow.memory import aget_messages
from langflow.services.database.models.flow import FlowCreate, FlowUpdate
from orjson import orjson


@pytest.mark.benchmark
async def test_build_flow(client, json_memory_chatbot_no_llm, logged_in_headers):
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    async with client.stream("POST", f"api/v1/build/{flow_id}/flow", json={}, headers=logged_in_headers) as r:
        await consume_and_assert_stream(r)

    await check_messages(flow_id)


@pytest.mark.benchmark
async def test_build_flow_from_request_data(client, json_memory_chatbot_no_llm, logged_in_headers):
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    response = await client.get("api/v1/flows/" + str(flow_id), headers=logged_in_headers)
    flow_data = response.json()

    async with client.stream(
        "POST", f"api/v1/build/{flow_id}/flow", json={"data": flow_data["data"]}, headers=logged_in_headers
    ) as r:
        await consume_and_assert_stream(r)

    await check_messages(flow_id)


async def test_build_flow_with_frozen_path(client, json_memory_chatbot_no_llm, logged_in_headers):
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    response = await client.get("api/v1/flows/" + str(flow_id), headers=logged_in_headers)
    flow_data = response.json()
    flow_data["data"]["nodes"][0]["data"]["node"]["frozen"] = True
    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json=FlowUpdate(name="Flow", description="description", data=flow_data["data"]).model_dump(),
        headers=logged_in_headers,
    )
    response.raise_for_status()

    async with client.stream("POST", f"api/v1/build/{flow_id}/flow", json={}, headers=logged_in_headers) as r:
        await consume_and_assert_stream(r)

    await check_messages(flow_id)


async def check_messages(flow_id):
    messages = await aget_messages(flow_id=UUID(flow_id), order="ASC")
    assert len(messages) == 2
    assert messages[0].session_id == flow_id
    assert messages[0].sender == "User"
    assert messages[0].sender_name == "User"
    assert messages[0].text == ""
    assert messages[1].session_id == flow_id
    assert messages[1].sender == "Machine"
    assert messages[1].sender_name == "AI"


async def consume_and_assert_stream(r):
    count = 0
    async for line in r.aiter_lines():
        # httpx split by \n, but ndjson sends two \n for each line
        if not line:
            continue
        parsed = json.loads(line)
        if count == 0:
            assert parsed["event"] == "vertices_sorted"
            ids = parsed["data"]["ids"]
            ids.sort()
            assert ids == ["ChatInput-CIGht"]

            to_run = parsed["data"]["to_run"]
            to_run.sort()
            assert to_run == ["ChatInput-CIGht", "ChatOutput-QA7ej", "Memory-amN4Z", "Prompt-iWbCC"]
        elif count > 0 and count < 5:
            assert parsed["event"] == "end_vertex"
            assert parsed["data"]["build_data"] is not None
        elif count == 5:
            assert parsed["event"] == "end"
        else:
            msg = f"Unexpected line: {line}"
            raise ValueError(msg)
        count += 1


async def _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers):
    vector_store = orjson.loads(json_memory_chatbot_no_llm)
    data = vector_store["data"]
    vector_store = FlowCreate(name="Flow", description="description", data=data, endpoint_name="f")
    response = await client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
    response.raise_for_status()
    return response.json()["id"]


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
