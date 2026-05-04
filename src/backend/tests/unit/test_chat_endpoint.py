import asyncio
import contextlib
import json
import uuid
from uuid import UUID

import pytest
from httpx import codes
from langflow.services.database.models.flow import FlowUpdate
from langflow.services.job_queue.service import JobQueueService
from lfx.log.logger import logger
from lfx.memory import aget_messages

from tests.unit.build_utils import build_flow, consume_and_assert_stream, create_flow, get_build_events


@pytest.fixture(autouse=True)
def allow_custom_components_by_default(monkeypatch):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "true")


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


async def test_build_flow_validates_request_data_instead_of_stale_db_flow(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """When request data is provided, preflight validation should use it instead of the saved flow."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    flow_data = response.json()
    request_data = json.loads(json.dumps(flow_data["data"]))
    request_data["nodes"][0]["data"]["node"]["display_name"] = "Updated Request Flow"
    saved_flow_validation_message = "saved flow should not be validated when request data is provided"

    def fail_if_saved_flow_is_validated(target):
        if target == flow_data["data"]:
            raise ValueError(saved_flow_validation_message)

    monkeypatch.setattr(
        "langflow.api.v1.chat.validate_flow_for_current_settings",
        fail_if_saved_flow_is_validated,
    )

    response = await client.post(
        f"api/v1/build/{flow_id}/flow",
        json={"data": request_data},
        headers=logged_in_headers,
    )

    assert response.status_code == codes.OK
    assert "job_id" in response.json()


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
    assert "Job not found" in response.json()["detail"]


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
    assert "job_id" in build_response, f"Expected job_id in build_response, got {build_response}"
    job_id = build_response["job_id"]
    assert job_id is not None

    # Create a response object that mimics a streaming response but uses polling
    class PollingResponse:
        def __init__(self, client, job_id, headers):
            self.client = client
            self.job_id = job_id
            self.headers = headers
            self.status_code = codes.OK
            self.max_total_events = 50  # Limit to prevent infinite loops
            self.max_empty_polls = 10  # Maximum number of empty polls before giving up
            self.poll_timeout = 3.0  # Timeout for each polling request
            self._closed = False

        async def aiter_lines(self):
            if self._closed:
                return

            try:
                empty_polls = 0
                total_events = 0
                end_event_found = False

                while (
                    empty_polls < self.max_empty_polls
                    and total_events < self.max_total_events
                    and not end_event_found
                    and not self._closed
                ):
                    # Add Accept header for NDJSON
                    headers = {**self.headers, "Accept": "application/x-ndjson"}

                    try:
                        # Set a timeout for the request
                        response = await asyncio.wait_for(
                            self.client.get(
                                f"api/v1/build/{self.job_id}/events?event_delivery=polling",
                                headers=headers,
                            ),
                            timeout=self.poll_timeout,
                        )

                        if response.status_code != codes.OK:
                            break

                        # Get the NDJSON response as text
                        text = response.text

                        # Skip if response is empty
                        if not text.strip():
                            empty_polls += 1
                            await asyncio.sleep(0.1)
                            continue

                        # Reset empty polls counter since we got data
                        empty_polls = 0

                        # Process each line as an individual JSON object
                        line_count = 0
                        for line in text.splitlines():
                            if not line.strip():
                                continue

                            line_count += 1
                            total_events += 1

                            # Check for end event with multiple possible formats
                            if '"event":"end"' in line or '"event": "end"' in line:
                                end_event_found = True

                            # Validate it's proper JSON before yielding
                            try:
                                json.loads(line)  # Test parse to ensure it's valid JSON
                                yield line
                            except json.JSONDecodeError as e:
                                logger.debug(f"WARNING: Skipping invalid JSON: {line}")
                                logger.debug(f"Error: {e}")
                                # Don't yield invalid JSON, but continue processing other lines

                        # If we had no events in this batch, count as empty poll
                        if line_count == 0:
                            empty_polls += 1

                        # Add a small delay to prevent tight polling
                        await asyncio.sleep(0.1)

                    except asyncio.TimeoutError:
                        logger.debug(f"WARNING: Polling request timed out after {self.poll_timeout}s")
                        empty_polls += 1
                        continue

                # If we hit the limit without finding the end event, log a warning
                if total_events >= self.max_total_events:
                    logger.debug(
                        f"WARNING: Reached maximum event limit ({self.max_total_events}) without finding end event"
                    )

                if empty_polls >= self.max_empty_polls and not end_event_found:
                    logger.debug(
                        f"WARNING: Reached maximum empty polls ({self.max_empty_polls}) without finding end event"
                    )

            except Exception as e:
                logger.debug(f"ERROR: Unexpected error during polling: {e!s}")
                raise
            finally:
                self._closed = True

        def close(self):
            self._closed = True

    polling_response = PollingResponse(client, job_id, logged_in_headers)

    # Use the same consume_and_assert_stream function to verify the events
    await consume_and_assert_stream(polling_response, job_id)


@pytest.mark.benchmark
async def test_cancel_build_unexpected_error(client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch):
    """Test handling of unexpected exceptions during flow build cancellation."""
    # First create the flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]
    assert job_id is not None

    # Mock the cancel_flow_build function to raise an unexpected exception
    import langflow.api.v1.chat

    original_cancel_flow_build = langflow.api.v1.chat.cancel_flow_build

    async def mock_cancel_flow_build_with_error(*_args, **_kwargs):
        msg = "Unexpected error during cancellation"
        raise RuntimeError(msg)

    monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", mock_cancel_flow_build_with_error)

    try:
        # Try to cancel the build - should return 500 Internal Server Error
        cancel_response = await client.post(f"api/v1/build/{job_id}/cancel", headers=logged_in_headers)
        assert cancel_response.status_code == codes.INTERNAL_SERVER_ERROR

        # Verify the error message
        response_data = cancel_response.json()
        assert "detail" in response_data
        assert "Unexpected error during cancellation" in response_data["detail"]
    finally:
        # Restore the original function to avoid affecting other tests
        monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", original_cancel_flow_build)


@pytest.mark.benchmark
async def test_cancel_build_success(client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch):
    """Test successful cancellation of a flow build."""
    # First create the flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]
    assert job_id is not None

    # Mock the cancel_flow_build function to simulate a successful cancellation
    import langflow.api.v1.chat

    original_cancel_flow_build = langflow.api.v1.chat.cancel_flow_build

    async def mock_successful_cancel_flow_build(*_args, **_kwargs):
        return True  # Return True to indicate successful cancellation

    monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", mock_successful_cancel_flow_build)

    try:
        # Try to cancel the build (should return success)
        cancel_response = await client.post(f"api/v1/build/{job_id}/cancel", headers=logged_in_headers)
        assert cancel_response.status_code == codes.OK

        # Verify the response structure indicates success
        response_data = cancel_response.json()
        assert "success" in response_data
        assert "message" in response_data
        assert response_data["success"] is True
        assert "cancelled successfully" in response_data["message"].lower()
    finally:
        # Restore the original function to avoid affecting other tests
        monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", original_cancel_flow_build)


@pytest.mark.benchmark
async def test_cancel_nonexistent_build(client, logged_in_headers):
    """Test cancelling a non-existent flow build."""
    # Generate a random job_id that doesn't exist
    invalid_job_id = str(uuid.uuid4())

    # Try to cancel a non-existent build
    response = await client.post(f"api/v1/build/{invalid_job_id}/cancel", headers=logged_in_headers)
    assert response.status_code == codes.NOT_FOUND
    assert "Job not found" in response.json()["detail"]


@pytest.mark.benchmark
async def test_cancel_build_failure(client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch):
    """Test handling of cancellation failure."""
    # First create the flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]
    assert job_id is not None

    # Mock the cancel_flow_build function to simulate a failure
    # The import path in monkeypatch should match exactly how it's imported in the application
    import langflow.api.v1.chat

    original_cancel_flow_build = langflow.api.v1.chat.cancel_flow_build

    async def mock_cancel_flow_build(*_args, **_kwargs):
        return False  # Return False to indicate cancellation failure

    monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", mock_cancel_flow_build)

    try:
        # Try to cancel the build (should return failure but success=False)
        cancel_response = await client.post(f"api/v1/build/{job_id}/cancel", headers=logged_in_headers)
        assert cancel_response.status_code == codes.OK

        # Verify the response structure indicates failure
        response_data = cancel_response.json()
        assert "success" in response_data
        assert "message" in response_data
        assert response_data["success"] is False
        assert "Failed to cancel" in response_data["message"]
    finally:
        # Restore the original function to avoid affecting other tests
        monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", original_cancel_flow_build)


@pytest.mark.benchmark
async def test_cancel_build_with_cancelled_error(client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch):
    """Test handling of CancelledError during cancellation (should be treated as failure)."""
    # First create the flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Start the build and get job_id
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]
    assert job_id is not None

    # Mock the cancel_flow_build function to raise CancelledError
    import asyncio

    import langflow.api.v1.chat

    original_cancel_flow_build = langflow.api.v1.chat.cancel_flow_build

    async def mock_cancel_flow_build_with_cancelled_error(*_args, **_kwargs):
        msg = "Task cancellation failed"
        raise asyncio.CancelledError(msg)

    monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", mock_cancel_flow_build_with_cancelled_error)

    try:
        # Try to cancel the build - should return failure when CancelledError is raised
        # since our implementation treats CancelledError as a failed cancellation
        cancel_response = await client.post(f"api/v1/build/{job_id}/cancel", headers=logged_in_headers)
        assert cancel_response.status_code == codes.OK

        # Verify the response structure indicates failure
        response_data = cancel_response.json()
        assert "success" in response_data
        assert "message" in response_data
        assert response_data["success"] is False
        assert "failed to cancel" in response_data["message"].lower()
    finally:
        # Restore the original function to avoid affecting other tests
        monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", original_cancel_flow_build)


@pytest.mark.benchmark
@pytest.mark.usefixtures("logged_in_headers")
async def test_should_have_public_events_endpoint_accessible_without_auth(client):
    """Test that public events endpoint exists and is accessible without authentication.

    Bug: After sending a message in the Shareable Playground, the chat input resets
    but no response is rendered. The root cause is that the events endpoint
    (/build/{job_id}/events) requires authentication, which the unauthenticated
    shareable playground user does not have.

    This test proves:
    1. The PUBLIC events endpoint exists and responds without auth (404 = route exists, job not found)
    2. The AUTHENTICATED events endpoint rejects unauthenticated requests (403)
    """
    fake_job_id = str(uuid.uuid4())

    # Assert 1 — the PUBLIC events endpoint is accessible without auth
    # Returns 404 "Job not found" (route exists, but job doesn't) — NOT 401/403
    events_response = await client.get(
        f"api/v1/build_public_tmp/{fake_job_id}/events?event_delivery=polling",
        headers={"Accept": "application/x-ndjson"},
    )
    assert events_response.status_code == codes.NOT_FOUND

    # The key proof: the public endpoint responded with 404 (route exists, job not found)
    # rather than 401/403 (authentication required). Before the fix, this endpoint
    # didn't exist at all and would return 404 for the route, not the job.
    assert "Job not found" in events_response.json()["detail"]


@pytest.mark.benchmark
@pytest.mark.usefixtures("logged_in_headers")
async def test_should_have_public_cancel_endpoint_accessible_without_auth(client):
    """Test that public cancel endpoint exists and is accessible without authentication.

    Same root cause as the events bug: the cancel endpoint requires auth
    but the shareable playground user is unauthenticated.
    """
    fake_job_id = str(uuid.uuid4())

    # The PUBLIC cancel endpoint is accessible without auth
    # Returns 404 "Job not found" (route exists, but job doesn't) — NOT 401/403
    cancel_response = await client.post(
        f"api/v1/build_public_tmp/{fake_job_id}/cancel",
        headers={"Content-Type": "application/json"},
    )
    assert cancel_response.status_code == codes.NOT_FOUND
    assert "Job not found" in cancel_response.json()["detail"]


@pytest.mark.benchmark
async def test_build_public_tmp_ignores_data_parameter(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test that build_public_tmp endpoint silently ignores data parameter for security.

    Security Test: Verifies that when a user attempts to provide custom flow data
    to the public flow endpoint, FastAPI silently ignores the extra parameter and
    the endpoint functions normally using the stored flow data from the database.
    """
    # Create a flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Make the flow public
    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert response.status_code == codes.OK

    # Create malicious flow data with different structure
    malicious_data = {"nodes": [{"id": "malicious", "data": {"type": "CustomComponent"}}], "edges": []}

    # Set a client_id cookie
    client.cookies.set("client_id", "test-security-client-123")

    # Attempt to build with malicious data - FastAPI will silently ignore it
    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={
            "inputs": {"session": "test_session"},
            "data": malicious_data,  # This will be silently ignored by FastAPI
        },
        headers={"Content-Type": "application/json"},
    )

    # Verify the request succeeded - the data parameter is simply ignored
    assert response.status_code == codes.OK
    response_data = response.json()
    assert "job_id" in response_data


@pytest.mark.benchmark
async def test_build_public_tmp_checks_public_access_before_validation(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """Private flows should fail at the public-access gate before any policy validation runs."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    client.cookies.set("client_id", "test-private-flow-client")
    public_access_validation_message = "validation should not run before public access checks"

    def fail_if_validation_runs(_target):
        raise ValueError(public_access_validation_message)

    monkeypatch.setattr(
        "langflow.api.v1.chat.validate_flow_for_current_settings",
        fail_if_validation_runs,
    )

    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": "test_session"}},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == codes.FORBIDDEN
    assert response.json()["detail"] == "Flow is not public"


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_flow_cross_user_blocked(client, json_memory_chatbot_no_llm, logged_in_headers, user_two):
    """Security (GHSA-qj98-rhf8-v93f): authenticated user cannot build another user's private flow.

    Regression guard: verifies that the ownership check added to build_flow rejects
    requests where flow.user_id != current_user.id and the flow is not PUBLIC.
    """
    victim_flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    login_data = {"username": user_two.username, "password": "hashed_password"}  # pragma: allowlist secret
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    attacker_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.post(f"api/v1/build/{victim_flow_id}/flow", json={}, headers=attacker_headers)
    assert response.status_code == 404


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_flow_unauthenticated_blocked(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Unauthenticated request to build_flow must be rejected (4xx — no valid credentials)."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    # Clear any cookies retained from previous tests to ensure a truly unauthenticated request.
    client.cookies.clear()
    response = await client.post(f"api/v1/build/{flow_id}/flow", json={})
    assert response.status_code == 403


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_flow_nonexistent_flow_returns_404(client, logged_in_headers):
    """Non-existent flow UUID must return 404."""
    nonexistent_id = uuid.uuid4()
    response = await client.post(f"api/v1/build/{nonexistent_id}/flow", json={}, headers=logged_in_headers)
    assert response.status_code == 404


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_events_cross_user_blocked(client, json_memory_chatbot_no_llm, logged_in_headers, user_two):
    """Security (GHSA-qj98-rhf8-v93f): user cannot poll build events owned by another user.

    Even if an attacker somehow obtains a valid job_id, the events endpoint independently
    enforces ownership via the _job_owners registry in JobQueueService.
    """
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]

    login_data = {"username": user_two.username, "password": "hashed_password"}  # pragma: allowlist secret
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    attacker_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await get_build_events(client, job_id, attacker_headers)
    assert response.status_code == 404


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_flow_public_flow_accessible_by_other_user(
    client, json_memory_chatbot_no_llm, logged_in_headers, user_two
):
    """A PUBLIC flow can be built by any authenticated user, not only the owner.

    Verifies that the ownership check correctly allows access_type == PUBLIC flows
    and does not over-restrict the multi-tenant sharing use case.
    """
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == 200

    login_data = {"username": user_two.username, "password": "hashed_password"}  # pragma: allowlist secret
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    other_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.post(f"api/v1/build/{flow_id}/flow", json={}, headers=other_headers)
    assert response.status_code == 200


@pytest.mark.benchmark
@pytest.mark.security
async def test_cancel_build_cross_user_blocked(client, json_memory_chatbot_no_llm, logged_in_headers, user_two):
    """Security: authenticated user cannot cancel a build job owned by another user.

    cancel_build carries the same DoS risk as get_build_events — an attacker who
    obtains a job_id should not be able to abort the victim's running build.
    """
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    build_response = await build_flow(client, flow_id, logged_in_headers)
    job_id = build_response["job_id"]

    login_data = {"username": user_two.username, "password": "hashed_password"}  # pragma: allowlist secret
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    attacker_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.post(f"api/v1/build/{job_id}/cancel", headers=attacker_headers)
    assert response.status_code == 404


@pytest.mark.benchmark
async def test_build_public_tmp_without_data_parameter(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Test that build_public_tmp endpoint works without data parameter.

    Security Test: Verifies that when no data parameter is provided, the endpoint
    works normally and returns a job_id. This proves the data parameter is optional
    and the stored flow definition is always used.
    """
    # Create a flow
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Make the flow public
    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert response.status_code == codes.OK

    # Set a client_id cookie
    client.cookies.set("client_id", "test-no-data-client")

    # Build without providing data parameter
    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": "test_session"}},
        headers={"Content-Type": "application/json"},
    )

    # Verify the request succeeded
    assert response.status_code == codes.OK
    response_data = response.json()
    assert "job_id" in response_data


@pytest.mark.benchmark
@pytest.mark.security
async def test_get_build_events_public_tmp_job_accessible_by_any_auth_user(
    client, json_memory_chatbot_no_llm, logged_in_headers, user_two, monkeypatch
):
    """A job started via build_public_tmp has no registered owner and is accessible to any authenticated user.

    Verifies that get_build_events skips the ownership check when get_job_owner returns None.
    """
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    client.cookies.set("client_id", "test-public-tmp-events-client")
    start_response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={},
        headers={"Content-Type": "application/json"},
    )
    assert start_response.status_code == codes.OK
    job_id = start_response.json()["job_id"]

    login_data = {"username": user_two.username, "password": "hashed_password"}  # pragma: allowlist secret
    login_response = await client.post("api/v1/login", data=login_data)
    assert login_response.status_code == codes.OK
    other_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    import langflow.api.v1.chat
    from fastapi import Response

    async def mock_get_flow_events_response(**_kwargs):
        return Response(content="", media_type="application/x-ndjson")

    monkeypatch.setattr(langflow.api.v1.chat, "get_flow_events_response", mock_get_flow_events_response)

    events_response = await get_build_events(client, job_id, other_headers)
    assert events_response.status_code == codes.OK


@pytest.mark.benchmark
@pytest.mark.security
async def test_cancel_build_public_tmp_job_accessible_by_any_auth_user(
    client, json_memory_chatbot_no_llm, logged_in_headers, user_two, monkeypatch
):
    """A job started via build_public_tmp has no registered owner and can be cancelled by any authenticated user.

    Verifies that cancel_build skips the ownership check when get_job_owner returns None.
    """
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    client.cookies.set("client_id", "test-public-tmp-cancel-client")
    start_response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={},
        headers={"Content-Type": "application/json"},
    )
    assert start_response.status_code == codes.OK
    job_id = start_response.json()["job_id"]

    login_data = {"username": user_two.username, "password": "hashed_password"}  # pragma: allowlist secret
    login_response = await client.post("api/v1/login", data=login_data)
    assert login_response.status_code == codes.OK
    other_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    import langflow.api.v1.chat

    async def mock_cancel_flow_build(*_args, **_kwargs):
        return True

    monkeypatch.setattr(langflow.api.v1.chat, "cancel_flow_build", mock_cancel_flow_build)

    cancel_response = await client.post(f"api/v1/build/{job_id}/cancel", headers=other_headers)
    assert cancel_response.status_code == codes.OK
    assert cancel_response.json()["success"] is True


@pytest.mark.asyncio
@pytest.mark.security
async def test_job_owner_cleaned_up_after_cleanup_job():
    """JobQueueService.cleanup_job removes the _job_owners entry for the job."""
    service = JobQueueService()
    service.start()

    try:
        job_id = str(uuid.uuid4())
        user_id = uuid.uuid4()

        service.create_queue(job_id)

        async def _noop():
            await asyncio.sleep(0)

        service.start_job(job_id, _noop())
        await asyncio.sleep(0.05)
        service.register_job_owner(job_id, user_id)

        assert service.get_job_owner(job_id) == user_id

        await service.cleanup_job(job_id)

        assert service.get_job_owner(job_id) is None
    finally:
        service._closed = True
        if service._cleanup_task:
            service._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await service._cleanup_task


# ---------------------------------------------------------------------------
# CVE-2026-33017: session-id namespacing on build_public_tmp
# ---------------------------------------------------------------------------


def _stub_start_flow_build(monkeypatch, captured: dict) -> None:
    """Capture the kwargs that would be dispatched to start_flow_build without running the build."""
    import langflow.api.v1.chat as chat_module

    async def _fake_start_flow_build(**kwargs):
        captured.update(kwargs)
        return "00000000-0000-0000-0000-00000000ffff"

    monkeypatch.setattr(chat_module, "start_flow_build", _fake_start_flow_build)


def _send_unauthenticated(client, client_id: str) -> None:
    """Drop login cookies and set the public client_id cookie.

    The shared AsyncClient persists access-token cookies from logged_in_headers
    that would otherwise let get_current_user_optional resolve a user and
    namespace under user_id -- not the unauthenticated shape the CVE targets.
    """
    client.cookies.clear()
    client.cookies.set("client_id", client_id)


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_public_tmp_namespaces_caller_session(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """Caller-supplied session equal to the real flow UUID is wrapped under the namespace.

    The threat: /api/v1/run hands out session_id == flow_id by default, and the
    flow UUID is visible in URLs. Without namespacing, an unauthenticated caller
    can pass that UUID as inputs.session and a Memory component reads its history.
    """
    from langflow.api.utils.flow_utils import compute_virtual_flow_id

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    captured: dict = {}
    _stub_start_flow_build(monkeypatch, captured)

    client_id = "ns-test-client"
    _send_unauthenticated(client, client_id)
    victim_session = str(flow_id)

    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": victim_session}},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.OK

    expected_namespace = str(compute_virtual_flow_id(client_id, flow_id))
    sent_inputs = captured["inputs"]
    assert sent_inputs is not None
    assert sent_inputs.session == f"{expected_namespace}:{victim_session}"
    assert sent_inputs.session != victim_session


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_public_tmp_session_already_namespaced_unchanged(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """Idempotency: a value already in-namespace is forwarded as-is, not double-wrapped."""
    from langflow.api.utils.flow_utils import compute_virtual_flow_id

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    captured: dict = {}
    _stub_start_flow_build(monkeypatch, captured)

    client_id = "ns-passthrough-client"
    _send_unauthenticated(client, client_id)
    namespace = str(compute_virtual_flow_id(client_id, flow_id))
    already_scoped = f"{namespace}:thread-1"

    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": already_scoped}},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.OK
    assert captured["inputs"].session == already_scoped


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_public_tmp_isolates_disjoint_clients(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """Different client_ids submitting the same session string land in disjoint namespaces."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    captured: dict = {}
    _stub_start_flow_build(monkeypatch, captured)

    shared_session = "shared-session-name"

    _send_unauthenticated(client, "client-A")
    response_a = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": shared_session}},
        headers={"Content-Type": "application/json"},
    )
    assert response_a.status_code == codes.OK
    session_a = captured["inputs"].session

    captured.clear()
    _send_unauthenticated(client, "client-B")
    response_b = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": shared_session}},
        headers={"Content-Type": "application/json"},
    )
    assert response_b.status_code == codes.OK
    session_b = captured["inputs"].session

    assert session_a != session_b
    assert session_a.endswith(f":{shared_session}")
    assert session_b.endswith(f":{shared_session}")


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_public_tmp_no_session_passthrough(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """No inputs supplied: namespacing is skipped; downstream falls back to the virtual flow ID."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    captured: dict = {}
    _stub_start_flow_build(monkeypatch, captured)

    _send_unauthenticated(client, "ns-default-client")
    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": None},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.OK
    assert captured["inputs"] is None


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_public_tmp_empty_session_is_namespaced(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """An empty-string session is scoped, not forwarded as-is.

    Empty string is currently *coincidentally* safe (downstream `or virtual_id`
    fallbacks save it), but a refactor of either branch would silently regress.
    Pin the contract here: empty becomes ``f"{namespace}:"``.
    """
    from langflow.api.utils.flow_utils import compute_virtual_flow_id

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    captured: dict = {}
    _stub_start_flow_build(monkeypatch, captured)

    client_id = "ns-empty-client"
    _send_unauthenticated(client, client_id)

    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": ""}},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.OK

    expected_namespace = str(compute_virtual_flow_id(client_id, flow_id))
    sent_session = captured["inputs"].session
    assert sent_session != ""
    assert sent_session == f"{expected_namespace}:"


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_public_tmp_authenticated_namespace_uses_user_id(
    client, json_memory_chatbot_no_llm, logged_in_headers, active_user, monkeypatch
):
    """AUTO_LOGIN=False (prod-like) + valid bearer: the namespace is derived from user.id."""
    from langflow.api.utils.flow_utils import compute_virtual_flow_id

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    captured: dict = {}
    _stub_start_flow_build(monkeypatch, captured)

    client.cookies.set("client_id", "should-be-ignored")
    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": "thread-A"}},
        headers={**logged_in_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == codes.OK

    expected_namespace = str(compute_virtual_flow_id(active_user.id, flow_id))
    assert captured["inputs"].session == f"{expected_namespace}:thread-A"


@pytest.mark.benchmark
@pytest.mark.security
async def test_build_public_tmp_namespacing_blocks_memory_query_collision(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """End-to-end proof that namespacing prevents Memory query collision.

    A victim message stored under ``session_id == flow_id`` is unreachable via a
    Memory query keyed on the namespaced session that build_public_tmp forwards.
    This is the test that catches a regression in either the endpoint guard or
    the helper -- the shape-only tests above would still pass if the rewrite
    was applied but the downstream query stopped honoring it.
    """
    from lfx.memory import aadd_messages, aget_messages
    from lfx.schema.message import Message

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == codes.OK

    victim_session = str(flow_id)
    await aadd_messages(
        Message(text="victim-secret", sender="User", sender_name="User", session_id=victim_session),
        flow_id=flow_id,
    )
    seeded = await aget_messages(session_id=victim_session)
    assert any(m.text == "victim-secret" for m in seeded)

    captured: dict = {}
    _stub_start_flow_build(monkeypatch, captured)
    _send_unauthenticated(client, "leak-test-client")

    response = await client.post(
        f"api/v1/build_public_tmp/{flow_id}/flow",
        json={"inputs": {"session": victim_session}},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.OK

    namespaced_session = captured["inputs"].session
    assert namespaced_session != victim_session

    leaked = await aget_messages(session_id=namespaced_session)
    assert all(m.text != "victim-secret" for m in leaked)

    still_seeded = await aget_messages(session_id=victim_session)
    assert any(m.text == "victim-secret" for m in still_seeded)


def test_scope_session_to_namespace_helper():
    from langflow.api.utils import scope_session_to_namespace

    ns = "namespace-A"
    assert scope_session_to_namespace(None, ns) is None
    assert scope_session_to_namespace("", ns) == f"{ns}:"
    assert scope_session_to_namespace(ns, ns) == ns
    assert scope_session_to_namespace(f"{ns}:thread-1", ns) == f"{ns}:thread-1"
    assert scope_session_to_namespace("victim-session", ns) == f"{ns}:victim-session"
    assert scope_session_to_namespace("victim-session", "namespace-B") == "namespace-B:victim-session"
    # A foreign-namespace prefix is treated as out-of-namespace and gets re-wrapped.
    assert scope_session_to_namespace("namespace-B:victim", "namespace-A") == "namespace-A:namespace-B:victim"
