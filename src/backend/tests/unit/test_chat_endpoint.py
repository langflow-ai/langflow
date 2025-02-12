import asyncio
import uuid
from uuid import UUID

import pytest
from httpx import codes
from langflow.memory import aget_messages
from langflow.services.database.models.flow import FlowUpdate

from tests.unit.build_utils import build_flow, consume_and_assert_stream, create_flow, get_build_events


@pytest.mark.benchmark
async def test_build_flow(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test the build flow endpoint with the new two-step process."""
    # First create the flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]
    assert job_id is not None

    # Get the events stream
    events_response = await get_build_events(client, job_id, logged_in_headers)
    assert events_response.status_code == codes.OK

    # Consume and verify the events
    await consume_and_assert_stream(events_response, job_id)


@pytest.mark.benchmark
async def test_build_flow_from_request_data(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test building a flow from request data."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    flow_data = response.json()

    # Start the build and get job_id
    build_response = await build_flow(client, flow_id, logged_in_headers, json={"data": flow_data["data"]})
    job_id = build_response["job_id"]

    # Get the events stream
    events_response = await get_build_events(client, job_id, logged_in_headers)
    assert events_response.status_code == codes.OK

    # Consume and verify the events
    await consume_and_assert_stream(events_response, job_id)
    await check_messages(flow_id)


async def test_build_flow_with_frozen_path(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test building a flow with a frozen path."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

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
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]

    # Get the events stream
    events_response = await get_build_events(client, job_id, logged_in_headers)
    assert events_response.status_code == codes.OK

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


@pytest.mark.benchmark
async def test_build_flow_invalid_job_id(client, logged_in_headers):
    """Test getting events for an invalid job ID."""
    invalid_job_id = str(uuid.uuid4())
    response = await get_build_events(client, invalid_job_id, logged_in_headers)
    assert response.status_code == codes.NOT_FOUND
    assert "No queue found for job_id" in response.json()["detail"]


@pytest.mark.benchmark
async def test_build_flow_invalid_flow_id(client, logged_in_headers):
    """Test starting a build with an invalid flow ID."""
    invalid_flow_id = uuid.uuid4()
    response = await client.post(f"api/v1/build/{invalid_flow_id}/flow", json={}, headers=logged_in_headers)
    assert response.status_code == codes.NOT_FOUND


@pytest.mark.benchmark
async def test_build_flow_start_only(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test only the build flow start endpoint."""
    # First create the flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await build_flow(client, flow_id, logged_in_headers)

    # Assert response structure
    assert "job_id" in build_response
    assert isinstance(build_response["job_id"], str)
    # Verify it's a valid UUID
    assert uuid.UUID(build_response["job_id"])


@pytest.mark.benchmark
async def test_build_flow_start_with_inputs(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test the build flow start endpoint with input data."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start build with some input data
    test_inputs = {"inputs": {"session": "test_session", "input_value": "test message"}}

    build_response = await build_flow(client, flow_id, logged_in_headers, json=test_inputs)

    assert "job_id" in build_response
    assert isinstance(build_response["job_id"], str)
    assert uuid.UUID(build_response["job_id"])


@pytest.mark.benchmark
async def test_build_flow_polling(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test the build flow endpoint with polling (non-streaming)."""
    # First create the flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]
    assert job_id is not None

    # Create a response object that mimics a streaming response but uses polling
    class PollingResponse:
        def __init__(self, client, job_id, headers):
            self.client = client
            self.job_id = job_id
            self.headers = headers
            self.status_code = codes.OK

        async def aiter_lines(self):
            try:
                sleeps = 0
                max_sleeps = 100
                while True:
                    response = await self.client.get(
                        f"api/v1/build/{self.job_id}/events?stream=false", headers=self.headers
                    )
                    assert response.status_code == codes.OK
                    data = response.json()

                    if data["event"] is None:
                        # No event available, add delay to prevent tight polling
                        await asyncio.sleep(0.1)
                        sleeps += 1
                        continue

                    yield data["event"]

                    # If this was the end event, stop polling
                    if '"end"' in data["event"]:
                        break
                    if sleeps > max_sleeps:
                        msg = "Build event polling timed out."
                        raise TimeoutError(msg)
            except asyncio.TimeoutError as e:
                msg = "Build event polling timed out."
                raise TimeoutError(msg) from e

    polling_response = PollingResponse(client, job_id, logged_in_headers)

    # Use the same consume_and_assert_stream function to verify the events
    await consume_and_assert_stream(polling_response, job_id)
