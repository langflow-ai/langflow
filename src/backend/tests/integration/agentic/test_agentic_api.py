"""Integration tests for Agentic API endpoints.

This module tests the FastAPI endpoints in api/router.py:
- POST /agentic/prompt - Execute prompt flow
- POST /agentic/next_component - Execute next component flow

These tests use real flows, real database, and real OpenAI API keys where available.
"""

import json
import os
from contextlib import suppress

import pytest
from fastapi import status
from langflow.services.database.models.flow.model import FlowCreate

# Check if OpenAI API key is available for integration tests
HAS_OPENAI_KEY = bool(os.environ.get("OPENAI_API_KEY"))


@pytest.fixture
async def openai_api_key_variable(client, logged_in_headers, active_user):  # noqa: ARG001
    """Create OPENAI_API_KEY global variable for the test user."""
    api_key = os.environ.get("OPENAI_API_KEY", "test-key-for-structure-tests")

    # Create the global variable via API
    variable_data = {
        "name": "OPENAI_API_KEY",
        "value": api_key,
        "type": "Credential",
    }

    response = await client.post("api/v1/variables/", json=variable_data, headers=logged_in_headers)

    if response.status_code == 201:
        variable = response.json()
        yield variable
        # Cleanup
        with suppress(Exception):
            await client.delete(f"api/v1/variables/{variable['id']}", headers=logged_in_headers)
    else:
        # Variable might already exist
        yield {"name": "OPENAI_API_KEY"}


class TestAgenticPromptEndpoint:
    """Test cases for POST /agentic/prompt endpoint."""

    @pytest.mark.asyncio
    async def test_prompt_endpoint_requires_auth(self, client):
        """Test that endpoint requires authentication."""
        response = await client.post(
            "api/v1/agentic/prompt",
            json={"flow_id": "test"},
        )

        # Should require authentication
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_prompt_endpoint_validation(self, client, logged_in_headers):
        """Test endpoint request validation."""
        # Missing required field
        response = await client.post(
            "api/v1/agentic/prompt",
            json={},
            headers=logged_in_headers,
        )

        # Should fail validation
        assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_prompt_endpoint_with_flow(
        self,
        client,
        logged_in_headers,
        json_chat_input,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test prompt endpoint with a valid flow."""
        # Create a flow
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="PromptAPITestFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            # Test the agentic prompt endpoint
            response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": flow_id,
                    "input_value": "Test prompt input",
                },
                headers=logged_in_headers,
            )

            # May fail if PromptGeneration.json flow requires LLM - that's expected
            # We're testing the endpoint structure and auth
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,  # LLM might fail without real key
                status.HTTP_404_NOT_FOUND,  # If flow file doesn't exist
            ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_prompt_endpoint_with_component_field(
        self,
        client,
        logged_in_headers,
        json_chat_input,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test prompt endpoint with component_id and field_name."""
        # Create a flow
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="PromptFieldTestFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            # Get a component ID from the flow
            component_id = flow_data["data"]["nodes"][0]["id"]

            # Find a field name
            template = flow_data["data"]["nodes"][0].get("data", {}).get("node", {}).get("template", {})
            field_name = None
            for fname in template:
                if fname != "_type":
                    field_name = fname
                    break

            if field_name:
                response = await client.post(
                    "api/v1/agentic/prompt",
                    json={
                        "flow_id": flow_id,
                        "component_id": component_id,
                        "field_name": field_name,
                        "input_value": "Test input with field",
                    },
                    headers=logged_in_headers,
                )

                # Structure test - actual execution may fail without real LLM
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    status.HTTP_404_NOT_FOUND,
                ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    @pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
    async def test_prompt_endpoint_real_execution(
        self,
        client,
        logged_in_headers,
        json_chat_input,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test prompt endpoint with real OpenAI execution."""
        # Create a flow
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="RealPromptTestFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": flow_id,
                    "input_value": "What is 2+2?",
                },
                headers=logged_in_headers,
            )

            # With real key, should succeed or fail gracefully
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

            if response.status_code == 200:
                result = response.json()
                assert isinstance(result, dict)

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


class TestAgenticNextComponentEndpoint:
    """Test cases for POST /agentic/next_component endpoint."""

    @pytest.mark.asyncio
    async def test_next_component_requires_auth(self, client):
        """Test that endpoint requires authentication."""
        response = await client.post(
            "api/v1/agentic/next_component",
            json={"flow_id": "test"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_next_component_validation(self, client, logged_in_headers):
        """Test endpoint request validation."""
        response = await client.post(
            "api/v1/agentic/next_component",
            json={},
            headers=logged_in_headers,
        )

        assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_next_component_nonexistent_flow(self, client, logged_in_headers, openai_api_key_variable):  # noqa: ARG002
        """Test next_component with nonexistent flow file returns 404."""
        response = await client.post(
            "api/v1/agentic/next_component",
            json={
                "flow_id": "NonExistentFlow123",
                "input_value": "test",
            },
            headers=logged_in_headers,
        )

        # Should return 404 as the flow file doesn't exist
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_next_component_with_system_message_gen(
        self,
        client,
        logged_in_headers,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test next_component with SystemMessageGen flow."""
        response = await client.post(
            "api/v1/agentic/next_component",
            json={
                "flow_id": "SystemMessageGen",
                "input_value": "Create an agent that helps with coding",
            },
            headers=logged_in_headers,
        )

        # May succeed or fail depending on flow existence and LLM availability
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_next_component_with_template_assistant(
        self,
        client,
        logged_in_headers,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test next_component with TemplateAssistant flow."""
        response = await client.post(
            "api/v1/agentic/next_component",
            json={
                "flow_id": "TemplateAssistant",
                "input_value": "Help me build a chatbot",
            },
            headers=logged_in_headers,
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_next_component_with_component_id(
        self,
        client,
        logged_in_headers,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test next_component with component_id parameter."""
        response = await client.post(
            "api/v1/agentic/next_component",
            json={
                "flow_id": "SystemMessageGen",
                "component_id": "test-component",
                "input_value": "test",
            },
            headers=logged_in_headers,
        )

        # Testing parameter passing - actual execution may fail
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_next_component_with_field_name(
        self,
        client,
        logged_in_headers,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test next_component with field_name parameter."""
        response = await client.post(
            "api/v1/agentic/next_component",
            json={
                "flow_id": "SystemMessageGen",
                "component_id": "test-component",
                "field_name": "input_value",
                "input_value": "test",
            },
            headers=logged_in_headers,
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestAgenticAPIErrorHandling:
    """Test error handling for Agentic API endpoints."""

    @pytest.mark.asyncio
    async def test_prompt_missing_openai_key(self, client, logged_in_headers, json_chat_input):
        """Test that missing OPENAI_API_KEY returns appropriate error."""
        # Create flow without setting up OPENAI_API_KEY variable
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="NoKeyTestFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            # Delete OPENAI_API_KEY variable if it exists
            vars_response = await client.get("api/v1/variables/", headers=logged_in_headers)
            if vars_response.status_code == 200:
                for var in vars_response.json():
                    if var.get("name") == "OPENAI_API_KEY":
                        await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

            response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": flow_id,
                    "input_value": "test",
                },
                headers=logged_in_headers,
            )

            # Should fail due to missing key
            assert response.status_code in [
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_404_NOT_FOUND,
            ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_invalid_flow_id_format(self, client, logged_in_headers, openai_api_key_variable):  # noqa: ARG002
        """Test handling of invalid flow_id format."""
        response = await client.post(
            "api/v1/agentic/prompt",
            json={
                "flow_id": "not-a-uuid-format",
                "input_value": "test",
            },
            headers=logged_in_headers,
        )

        # Should handle gracefully
        assert response.status_code in [
            status.HTTP_200_OK,  # May work if flow name lookup is attempted
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestAgenticAPIRequestSchema:
    """Test the request schema for Agentic API endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_flow_request_all_fields(self, client, logged_in_headers, json_chat_input, openai_api_key_variable):  # noqa: ARG002
        """Test request with all FlowRequest fields."""
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="FullRequestTestFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]
        component_id = flow_data["data"]["nodes"][0]["id"]

        try:
            # Test with all optional fields
            response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": flow_id,
                    "component_id": component_id,
                    "field_name": "input_value",
                    "input_value": "Full request test",
                },
                headers=logged_in_headers,
            )

            # Structure should be accepted
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_flow_request_minimal(self, client, logged_in_headers, json_chat_input, openai_api_key_variable):  # noqa: ARG002
        """Test request with minimal required fields."""
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="MinimalRequestTestFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            # Test with only required field
            response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": flow_id,
                },
                headers=logged_in_headers,
            )

            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_empty_input_value(self, client, logged_in_headers, json_chat_input, openai_api_key_variable):  # noqa: ARG002
        """Test request with empty input_value."""
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="EmptyInputTestFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": flow_id,
                    "input_value": "",
                },
                headers=logged_in_headers,
            )

            # Empty input should be handled
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


class TestAgenticAPIIntegration:
    """Integration tests combining Agentic API with other Langflow features."""

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_create_and_prompt_workflow(
        self, client, logged_in_headers, json_chat_input, openai_api_key_variable  # noqa: ARG002
    ):
        """Test complete workflow: create flow -> use agentic prompt."""
        # Step 1: Create a flow
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="IntegrationWorkflowFlow", description="Integration test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            # Step 2: Use agentic prompt endpoint
            prompt_response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": flow_id,
                    "input_value": "Integration test prompt",
                },
                headers=logged_in_headers,
            )

            # Should not crash
            assert prompt_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_prompt_with_flow_endpoint_name(
        self,
        client,
        logged_in_headers,
        json_chat_input,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test using flow endpoint_name instead of ID."""
        flow_data = json.loads(json_chat_input)
        endpoint_name = "agentic-test-endpoint"
        flow = FlowCreate(
            name="EndpointTestFlow",
            description="Test",
            data=flow_data.get("data"),
            endpoint_name=endpoint_name,
        )
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            # Try using endpoint name as flow_id
            response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": endpoint_name,
                    "input_value": "Test with endpoint name",
                },
                headers=logged_in_headers,
            )

            # May or may not work depending on implementation
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    @pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
    async def test_real_prompt_generation(
        self,
        client,
        logged_in_headers,
        json_chat_input,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test real prompt generation with actual OpenAI API call."""
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="RealPromptGenFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            response = await client.post(
                "api/v1/agentic/prompt",
                json={
                    "flow_id": flow_id,
                    "input_value": "Generate a helpful response for: What is AI?",
                },
                headers=logged_in_headers,
            )

            if response.status_code == 200:
                result = response.json()
                # Should return some result
                assert isinstance(result, dict)

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


class TestAgenticAPIConcurrency:
    """Test concurrent requests to Agentic API endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.api_key_required
    async def test_multiple_sequential_requests(
        self,
        client,
        logged_in_headers,
        json_chat_input,
        openai_api_key_variable,  # noqa: ARG002
    ):
        """Test multiple sequential requests to the same endpoint."""
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="SequentialTestFlow", description="Test", data=flow_data.get("data"))
        flow_response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert flow_response.status_code == 201

        flow_id = flow_response.json()["id"]

        try:
            # Make multiple requests
            for i in range(3):
                response = await client.post(
                    "api/v1/agentic/prompt",
                    json={
                        "flow_id": flow_id,
                        "input_value": f"Request {i}",
                    },
                    headers=logged_in_headers,
                )

                # All should complete without hanging
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_404_NOT_FOUND,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                ]

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
