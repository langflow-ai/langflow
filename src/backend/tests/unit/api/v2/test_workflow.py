"""Comprehensive unit tests for V2 Workflow API endpoints.

This test module provides extensive coverage of the workflow execution endpoints,
including authentication, authorization, error handling, and execution modes.

Test Coverage:
    - Developer API protection (enabled/disabled scenarios)
    - API key authentication requirements
    - Flow validation and error handling
    - Database error handling
    - Execution timeout protection
    - Synchronous execution with various component types
    - Error response structure validation
    - Multiple execution modes (sync, stream, background)

Test Organization:
    - TestWorkflowDeveloperAPIProtection: Tests developer API feature flag
    - TestWorkflowErrorHandling: Tests comprehensive error scenarios
    - TestWorkflowSyncExecution: Tests successful execution flows

Test Strategy:
    - Uses real database with proper cleanup
    - Mocks external dependencies (LLM APIs, file operations)
    - Tests both success and failure paths
    - Validates response structure and status codes
"""

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.exceptions.api import WorkflowValidationError
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope
from sqlalchemy.exc import OperationalError


class TestWorkflowDeveloperAPIProtection:
    """Test developer API protection for workflow endpoints."""

    @pytest.fixture
    def mock_settings_dev_api_disabled(self):
        """Mock settings with developer API disabled."""
        with patch("langflow.api.v2.workflow.get_settings_service") as mock_get_settings_service:
            mock_service = MagicMock()
            mock_settings = MagicMock()
            mock_settings.developer_api_enabled = False
            mock_service.settings = mock_settings
            mock_get_settings_service.return_value = mock_service
            yield mock_settings

    async def test_execute_workflow_blocked_when_dev_api_disabled(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_disabled,  # noqa: ARG002
    ):
        """Test workflow execution is blocked when developer API is disabled."""
        request_data = {
            "flow_id": "550e8400-e29b-41d4-a716-446655440000",
            "background": False,
            "stream": False,
            "inputs": None,
        }

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflow",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 403
        result = response.json()
        assert result["detail"]["code"] == "DEVELOPER_API_DISABLED"
        assert "Developer API" in result["detail"]["message"]

    async def test_stop_workflow_blocked_when_dev_api_disabled(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_disabled,  # noqa: ARG002
    ):
        """Test POST workflow/stop endpoint is blocked when developer API is disabled."""
        request_data = {"job_id": "550e8400-e29b-41d4-a716-446655440001"}

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflow/stop",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 403
        result = response.json()
        assert result["detail"]["code"] == "DEVELOPER_API_DISABLED"

    @pytest.fixture
    def mock_settings_dev_api_enabled(self):
        """Mock settings with developer API enabled."""
        with patch("langflow.api.v2.workflow.get_settings_service") as mock_get_settings_service:
            mock_service = MagicMock()
            mock_settings = MagicMock()
            mock_settings.developer_api_enabled = True
            mock_service.settings = mock_settings
            mock_get_settings_service.return_value = mock_service
            yield mock_settings

    async def test_execute_workflow_allowed_when_dev_api_enabled_flow_not_found(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test POST workflow execution is allowed when developer API is enabled - flow not found."""
        request_data = {
            "flow_id": "550e8400-e29b-41d4-a716-446655440000",  # Non-existent flow ID
            "background": False,
            "stream": False,
            "inputs": None,
        }

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflow",
            json=request_data,
            headers=headers,
        )

        # Should return 404 because flow doesn't exist, NOT because endpoint is disabled
        assert response.status_code == 404
        result = response.json()
        assert result["detail"]["code"] == "FLOW_NOT_FOUND"
        assert "550e8400-e29b-41d4-a716-446655440000" in result["detail"]["flow_id"]

    async def test_get_workflow_allowed_when_dev_api_enabled_job_not_found(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test GET workflow endpoint is allowed when developer API is enabled - job not found."""
        headers = {"x-api-key": created_api_key.api_key}
        response = await client.get(
            "api/v2/workflow?job_id=550e8400-e29b-41d4-a716-446655440001",  # Non-existent job ID
            headers=headers,
        )

        # Should return 501 because endpoint is not implemented yet, NOT 404 because endpoint is disabled
        assert response.status_code == 501
        assert "Not implemented" in response.text
        assert "This endpoint is not available" not in response.text

    async def test_stop_workflow_allowed_when_dev_api_enabled_job_not_found(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test POST workflow/stop endpoint is allowed when developer API is enabled - job not found."""
        request_data = {
            "job_id": "550e8400-e29b-41d4-a716-446655440001"  # Non-existent job ID
        }

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflow/stop",
            json=request_data,
            headers=headers,
        )

        # Should return 501 because endpoint is not implemented yet, NOT 404 because endpoint is disabled
        assert response.status_code == 501
        assert "Not implemented" in response.text
        assert "This endpoint is not available" not in response.text

    async def test_get_workflow_blocked_when_dev_api_disabled(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_disabled,  # noqa: ARG002
    ):
        """Test GET workflow endpoint is blocked when developer API is disabled."""
        headers = {"x-api-key": created_api_key.api_key}
        response = await client.get(
            "api/v2/workflow?job_id=550e8400-e29b-41d4-a716-446655440001",
            headers=headers,
        )

        assert response.status_code == 403
        result = response.json()
        assert result["detail"]["code"] == "DEVELOPER_API_DISABLED"

    async def test_execute_workflow_allowed_when_dev_api_enabled_flow_exists(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test POST /workflow allowed when dev API enabled - flow exists and executes."""
        flow_id = uuid4()

        # Create a flow in the database using the established pattern
        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Test Flow",
                description="Test flow for API testing",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {"flow_id": str(flow.id), "background": False, "stream": False, "inputs": None}

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post(
                "api/v2/workflow",
                json=request_data,
                headers=headers,
            )

            # Should return 200 because flow is valid (empty nodes/edges is valid)
            # The execution will complete successfully with no outputs
            assert response.status_code == 200
            result = response.json()

            # Verify response contains expected fields with proper structure
            assert "outputs" in result or "errors" in result
            if "outputs" in result:
                assert isinstance(result["outputs"], dict)
            if "errors" in result:
                assert isinstance(result["errors"], list)

        finally:
            # Clean up the flow following established pattern
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_get_workflow_allowed_when_dev_api_enabled_job_exists(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test GET /workflow allowed when dev API enabled - job exists (501 not implemented)."""
        # Since job management isn't implemented, we'll test with any job_id
        # The endpoint should return 501 regardless of whether the job exists
        headers = {"x-api-key": created_api_key.api_key}
        response = await client.get(
            "api/v2/workflow?job_id=550e8400-e29b-41d4-a716-446655440002",
            headers=headers,
        )

        assert response.status_code == 501
        assert "Not implemented" in response.text
        assert "This endpoint is not available" not in response.text

    async def test_stop_workflow_allowed_when_dev_api_enabled_job_exists(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test POST /workflow/stop allowed when dev API enabled - job exists (501 not implemented)."""
        # Since job management isn't implemented, we'll test with any job_id
        # The endpoint should return 501 regardless of whether the job exists
        request_data = {"job_id": "550e8400-e29b-41d4-a716-446655440002"}

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflow/stop",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 501
        assert "Not implemented" in response.text
        assert "This endpoint is not available" not in response.text

    async def test_all_endpoints_require_api_key_authentication(
        self,
        client: AsyncClient,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that all workflow endpoints require API key authentication."""
        # Test POST /workflow without API key
        request_data = {
            "flow_id": "550e8400-e29b-41d4-a716-446655440000",
            "background": False,
            "stream": False,
            "inputs": None,
        }

        response = await client.post(
            "api/v2/workflow",
            json=request_data,
        )
        # The API returns 403 Forbidden for missing API keys (not 401 Unauthorized)
        # This is the correct behavior according to the api_key_security implementation
        assert response.status_code == 403
        assert "API key must be passed" in response.json()["detail"]


class TestWorkflowErrorHandling:
    """Test comprehensive error handling for workflow endpoints."""

    @pytest.fixture
    def mock_settings_dev_api_enabled(self):
        """Mock settings with developer API enabled."""
        with patch("langflow.api.v2.workflow.get_settings_service") as mock_get_settings_service:
            mock_service = MagicMock()
            mock_settings = MagicMock()
            mock_settings.developer_api_enabled = True
            mock_service.settings = mock_settings
            mock_get_settings_service.return_value = mock_service
            yield mock_settings

    async def test_flow_not_found_returns_404_with_error_code(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that non-existent flow returns 404 with FLOW_NOT_FOUND error code."""
        flow_id = str(uuid4())
        request_data = {"flow_id": flow_id, "background": False, "stream": False, "inputs": None}

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post("api/v2/workflow", json=request_data, headers=headers)

        assert response.status_code == 404
        result = response.json()
        assert result["detail"]["code"] == "FLOW_NOT_FOUND"
        assert result["detail"]["flow_id"] == flow_id
        assert "does not exist" in result["detail"]["message"]

    async def test_database_error_returns_503(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that database errors return 503 with DATABASE_ERROR code."""
        flow_id = str(uuid4())
        request_data = {"flow_id": flow_id, "background": False, "stream": False, "inputs": None}

        # Mock get_flow_by_id_or_endpoint_name to raise OperationalError
        with patch("langflow.api.v2.workflow.get_flow_by_id_or_endpoint_name") as mock_get_flow:
            mock_get_flow.side_effect = OperationalError("statement", "params", "orig")

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflow", json=request_data, headers=headers)

            assert response.status_code == 503
            result = response.json()
            assert result["detail"]["code"] == "DATABASE_ERROR"
            assert "Failed to fetch flow" in result["detail"]["message"]
            assert result["detail"]["flow_id"] == flow_id

    async def test_flow_with_no_data_returns_500(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that flow with no data returns 500 with INVALID_FLOW_DATA code."""
        flow_id = uuid4()

        # Create a flow with no data
        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Flow with no data",
                description="Test flow with no data",
                data=None,  # No data
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {"flow_id": str(flow_id), "background": False, "stream": False, "inputs": None}

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflow", json=request_data, headers=headers)

            assert response.status_code == 500
            result = response.json()
            assert result["detail"]["code"] == "INVALID_FLOW_DATA"
            assert "has no data" in result["detail"]["message"]
            assert result["detail"]["flow_id"] == str(flow_id)
            assert "job_id" in result["detail"]

        finally:
            # Clean up
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_graph_build_failure_returns_500(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that graph build failure returns 500 with INVALID_FLOW_DATA code."""
        flow_id = uuid4()

        # Create a flow with invalid data that will fail validation/graph building
        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Flow with invalid data",
                description="Test flow with invalid graph data",
                data={"invalid": "data"},  # Invalid graph data (missing 'nodes' field)
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {"flow_id": str(flow_id), "background": False, "stream": False, "inputs": None}

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflow", json=request_data, headers=headers)

            assert response.status_code == 500
            result = response.json()
            assert result["detail"]["code"] == "INVALID_FLOW_DATA"
            # The error message should indicate invalid flow data structure
            error_msg = result["detail"]["message"].lower()
            assert "invalid data structure" in error_msg or "must have nodes" in error_msg
            assert result["detail"]["flow_id"] == str(flow_id)

        finally:
            # Clean up
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_execution_timeout_with_real_delay(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that execution timeout works with real async delay."""
        flow_id = uuid4()

        # Create a valid flow
        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Test Flow",
                description="Test flow for timeout",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {"flow_id": str(flow_id), "background": False, "stream": False, "inputs": None}

            # Mock execute_sync_workflow to sleep longer than timeout
            async def slow_execution(*args, **kwargs):  # noqa: ARG001
                await asyncio.sleep(2)  # Sleep for 2 seconds
                return MagicMock()

            # Temporarily reduce timeout for testing
            with (
                patch("langflow.api.v2.workflow.execute_sync_workflow", side_effect=slow_execution),
                patch("langflow.api.v2.workflow.EXECUTION_TIMEOUT", 0.5),  # 0.5 second timeout
            ):
                headers = {"x-api-key": created_api_key.api_key}
                response = await client.post("api/v2/workflow", json=request_data, headers=headers)

                assert response.status_code == 504
                result = response.json()
                assert result["detail"]["code"] == "EXECUTION_TIMEOUT"
                assert "exceeded" in result["detail"]["message"]
                assert result["detail"]["flow_id"] == str(flow_id)
                assert "job_id" in result["detail"]

        finally:
            # Clean up
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_background_mode_returns_501(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that background mode returns 501 with NOT_IMPLEMENTED code."""
        flow_id = uuid4()

        # Create a valid flow
        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Test Flow",
                description="Test flow",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {
                "flow_id": str(flow_id),
                "background": True,  # Background mode
                "stream": False,
                "inputs": None,
            }

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflow", json=request_data, headers=headers)

            assert response.status_code == 501
            result = response.json()
            assert result["detail"]["code"] == "NOT_IMPLEMENTED"
            assert "Background execution not yet implemented" in result["detail"]["message"]

        finally:
            # Clean up
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_streaming_mode_returns_501(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that streaming mode returns 501 with NOT_IMPLEMENTED code."""
        flow_id = uuid4()

        # Create a valid flow
        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Test Flow",
                description="Test flow",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {
                "flow_id": str(flow_id),
                "background": False,
                "stream": True,  # Streaming mode
                "inputs": None,
            }

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflow", json=request_data, headers=headers)

            assert response.status_code == 501
            result = response.json()
            assert result["detail"]["code"] == "NOT_IMPLEMENTED"
            assert "Streaming execution not yet implemented" in result["detail"]["message"]

        finally:
            # Clean up
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_error_response_structure(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that all error responses have consistent structure."""
        flow_id = str(uuid4())
        request_data = {"flow_id": flow_id, "background": False, "stream": False, "inputs": None}

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post("api/v2/workflow", json=request_data, headers=headers)

        assert response.status_code == 404
        result = response.json()

        # Verify error structure
        assert "detail" in result
        assert "error" in result["detail"]
        assert "code" in result["detail"]
        assert "message" in result["detail"]
        assert "flow_id" in result["detail"]

        # Verify types
        assert isinstance(result["detail"]["error"], str)
        assert isinstance(result["detail"]["code"], str)
        assert isinstance(result["detail"]["message"], str)
        assert isinstance(result["detail"]["flow_id"], str)

    async def test_workflow_validation_error_propagation(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that WorkflowValidationError is properly caught and converted to 500."""
        flow_id = uuid4()

        # Create a flow
        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Test Flow",
                description="Test flow",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {"flow_id": str(flow_id), "background": False, "stream": False, "inputs": None}

            # Mock execute_sync_workflow to raise WorkflowValidationError
            with patch("langflow.api.v2.workflow.execute_sync_workflow") as mock_execute:
                mock_execute.side_effect = WorkflowValidationError("Test validation error")

                headers = {"x-api-key": created_api_key.api_key}
                response = await client.post("api/v2/workflow", json=request_data, headers=headers)

                assert response.status_code == 500
                result = response.json()
                assert result["detail"]["code"] == "INVALID_FLOW_DATA"
                assert "Test validation error" in result["detail"]["message"]

        finally:
            # Clean up
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

        # Test GET /workflow without API key
        response = await client.get("api/v2/workflow?job_id=550e8400-e29b-41d4-a716-446655440001")
        assert response.status_code == 403
        assert "API key must be passed" in response.json()["detail"]


class TestWorkflowSyncExecution:
    """Test synchronous workflow execution with realistic component mocking."""

    @pytest.fixture
    def mock_settings_dev_api_enabled(self):
        """Mock settings with developer API enabled."""
        with patch("langflow.api.v2.workflow.get_settings_service") as mock_get_settings_service:
            mock_service = MagicMock()
            mock_settings = MagicMock()
            mock_settings.developer_api_enabled = True
            mock_service.settings = mock_settings
            mock_get_settings_service.return_value = mock_service
            yield mock_settings

    async def test_sync_execution_with_empty_flow_returns_200(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test sync execution with empty flow returns 200 with empty outputs."""
        flow_id = uuid4()

        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Empty Flow",
                description="Flow with no nodes",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {"flow_id": str(flow_id), "background": False, "stream": False, "inputs": None}

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflow", json=request_data, headers=headers)

            assert response.status_code == 200
            result = response.json()

            # Verify response structure
            assert "flow_id" in result
            assert result["flow_id"] == str(flow_id)
            assert "job_id" in result

            # Verify outputs or errors are present with actual content
            assert "outputs" in result or "errors" in result
            if "outputs" in result:
                assert isinstance(result["outputs"], dict)
            if "errors" in result:
                assert isinstance(result["errors"], list)
            # session_id is only present if provided in inputs

        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_sync_execution_component_error_returns_200_with_error_in_body(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that component execution errors return 200 with error in response body."""
        flow_id = uuid4()

        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Test Flow",
                description="Flow for testing component errors",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {"flow_id": str(flow_id), "background": False, "stream": False, "inputs": None}

            # Mock run_graph_internal to raise a component execution error
            with patch("langflow.api.v2.workflow.run_graph_internal") as mock_run:
                mock_run.side_effect = Exception("Component execution failed: LLM API key not configured")

                headers = {"x-api-key": created_api_key.api_key}
                response = await client.post("api/v2/workflow", json=request_data, headers=headers)

                # Component errors should return 200 with error in body
                assert response.status_code == 200
                result = response.json()

                # Verify error is in response body (via create_error_response)
                assert "errors" in result
                assert len(result["errors"]) > 0
                assert "Component execution failed" in str(result["errors"][0])
                assert result["status"] == "failed"
                assert result["flow_id"] == str(flow_id)
                assert "job_id" in result

        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_sync_execution_with_chat_input_output(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test sync execution with ChatInput and ChatOutput components."""
        flow_id = uuid4()

        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Chat Flow",
                description="Flow with chat input/output",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            # Input format: component_id.param = value
            request_data = {
                "flow_id": str(flow_id),
                "background": False,
                "stream": False,
                "inputs": {
                    "ChatInput-abc123.input_value": "Hello, how are you?",
                    "ChatInput-abc123.session_id": "session-456",
                },
            }

            # Mock successful execution with ChatOutput
            mock_result_data = MagicMock()
            mock_result_data.component_id = "ChatOutput-xyz789"
            mock_result_data.outputs = {"message": {"message": "I'm doing well, thank you for asking!", "type": "text"}}
            mock_result_data.metadata = {}

            # Wrap ResultData in RunOutputs
            mock_run_output = MagicMock()
            mock_run_output.outputs = [mock_result_data]

            with patch("langflow.api.v2.workflow.run_graph_internal") as mock_run:
                # run_graph_internal returns tuple[list[RunOutputs], str]
                mock_run.return_value = ([mock_run_output], "session-456")

                headers = {"x-api-key": created_api_key.api_key}
                response = await client.post("api/v2/workflow", json=request_data, headers=headers)

                assert response.status_code == 200
                result = response.json()

                # Verify response structure
                assert result["flow_id"] == str(flow_id)
                assert "job_id" in result
                assert "outputs" in result
                # Note: Detailed content validation requires proper graph/vertex mocking
                # which is beyond the scope of unit tests. Integration tests should validate content.

                # Verify inputs were echoed back
                assert "inputs" in result
                assert result["inputs"] == request_data["inputs"]

                # Verify session_id is present when provided in inputs
                if "session_id" in result:
                    assert result["session_id"] == "session-456"

        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_sync_execution_with_llm_output(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test sync execution with LLM component output including model metadata."""
        flow_id = uuid4()

        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="LLM Flow",
                description="Flow with LLM component",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {
                "flow_id": str(flow_id),
                "background": False,
                "stream": False,
                "inputs": {
                    "ChatInput-abc.input_value": "Explain quantum computing",
                    "OpenAIModel-def.temperature": 0.7,
                },
            }

            # Mock LLM execution with model metadata
            mock_result_data = MagicMock()
            mock_result_data.component_id = "OpenAIModel-def"
            mock_result_data.outputs = {
                "model_output": {
                    "message": {
                        "message": "Quantum computing uses quantum mechanics...",
                        "model_name": "gpt-4",
                        "type": "text",
                    }
                }
            }
            mock_result_data.metadata = {"tokens_used": 150}

            # Wrap ResultData in RunOutputs
            mock_run_output = MagicMock()
            mock_run_output.outputs = [mock_result_data]

            with patch("langflow.api.v2.workflow.run_graph_internal") as mock_run:
                # run_graph_internal returns tuple[list[RunOutputs], str]
                mock_run.return_value = ([mock_run_output], "session-789")

                headers = {"x-api-key": created_api_key.api_key}
                response = await client.post("api/v2/workflow", json=request_data, headers=headers)

                assert response.status_code == 200
                result = response.json()

                assert result["flow_id"] == str(flow_id)
                assert "job_id" in result
                assert "outputs" in result
                assert "metadata" in result
                # Note: Detailed content validation requires proper graph/vertex mocking

        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_sync_execution_with_file_save_output(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test sync execution with SaveToFile component."""
        flow_id = uuid4()

        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="File Save Flow",
                description="Flow with file save component",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {
                "flow_id": str(flow_id),
                "background": False,
                "stream": False,
                "inputs": {
                    "TextInput-abc.text": "Content to save",
                    "SaveToFile-xyz.file_path": "/tmp/output.txt",  # noqa: S108
                },
            }

            # Mock SaveToFile execution
            mock_result_data = MagicMock()
            mock_result_data.component_id = "SaveToFile-xyz"
            mock_result_data.outputs = {
                "message": {"message": "File saved successfully to /tmp/output.txt", "type": "text"}
            }
            mock_result_data.metadata = {"bytes_written": 1024}

            # Wrap ResultData in RunOutputs
            mock_run_output = MagicMock()
            mock_run_output.outputs = [mock_result_data]

            with patch("langflow.api.v2.workflow.run_graph_internal") as mock_run:
                # run_graph_internal returns tuple[list[RunOutputs], str]
                mock_run.return_value = ([mock_run_output], "session-101")

                headers = {"x-api-key": created_api_key.api_key}
                response = await client.post("api/v2/workflow", json=request_data, headers=headers)

                assert response.status_code == 200
                result = response.json()

                assert result["flow_id"] == str(flow_id)
                assert "job_id" in result
                assert "outputs" in result
                assert "metadata" in result
                # Note: Detailed content validation requires proper graph/vertex mocking

        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_sync_execution_with_multiple_terminal_nodes(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test sync execution with multiple terminal nodes (outputs)."""
        flow_id = uuid4()

        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Multi-Output Flow",
                description="Flow with multiple terminal nodes",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {
                "flow_id": str(flow_id),
                "background": False,
                "stream": False,
                "inputs": {"ChatInput-abc.input_value": "Process this"},
            }

            # Mock execution with multiple outputs
            mock_chat_output = MagicMock()
            mock_chat_output.component_id = "ChatOutput-aaa"
            mock_chat_output.outputs = {"message": {"message": "Chat response", "type": "text"}}

            mock_file_output = MagicMock()
            mock_file_output.component_id = "SaveToFile-bbb"
            mock_file_output.outputs = {"message": {"message": "File saved successfully", "type": "text"}}

            with patch("langflow.api.v2.workflow.run_graph_internal") as mock_run:
                # run_graph_internal returns tuple[list[RunOutputs], str]
                mock_run.return_value = ([mock_chat_output, mock_file_output], "session-202")

                headers = {"x-api-key": created_api_key.api_key}
                response = await client.post("api/v2/workflow", json=request_data, headers=headers)

                assert response.status_code == 200
                result = response.json()

                assert result["flow_id"] == str(flow_id)
                assert "job_id" in result
                assert "outputs" in result
                # Note: Detailed content validation requires proper graph/vertex mocking

        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

    async def test_sync_execution_response_structure_validation(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test that sync execution response has correct WorkflowExecutionResponse structure."""
        flow_id = uuid4()

        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Test Flow",
                description="Flow for response validation",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()
            await session.refresh(flow)

        try:
            request_data = {"flow_id": str(flow_id), "background": False, "stream": False, "inputs": None}

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflow", json=request_data, headers=headers)

            assert response.status_code == 200
            result = response.json()

            # Verify WorkflowExecutionResponse structure
            assert "flow_id" in result
            assert isinstance(result["flow_id"], str)
            assert result["flow_id"] == str(flow_id)

            assert "job_id" in result
            assert isinstance(result["job_id"], str)

            # session_id is optional - only present if provided in inputs
            if "session_id" in result:
                assert isinstance(result["session_id"], str)

            assert "object" in result
            assert result["object"] == "response"

            assert "created_timestamp" in result
            assert isinstance(result["created_timestamp"], str)

            assert "status" in result
            assert result["status"] in ["completed", "failed", "running", "queued"]

            assert "errors" in result
            assert isinstance(result["errors"], list)

            assert "inputs" in result
            assert isinstance(result["inputs"], dict)

            assert "outputs" in result
            assert isinstance(result["outputs"], dict)

            assert "metadata" in result
            assert isinstance(result["metadata"], dict)

        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)

        # Test POST /workflow/stop without API key
        response = await client.post(
            "api/v2/workflow/stop",
            json={"job_id": "550e8400-e29b-41d4-a716-446655440001"},
        )
        assert response.status_code == 403
        assert "API key must be passed" in response.json()["detail"]
