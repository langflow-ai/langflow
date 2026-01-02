from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope


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

        assert response.status_code == 404
        result = response.json()
        assert "This endpoint is not available" in result["detail"]

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

        assert response.status_code == 404
        result = response.json()
        assert "This endpoint is not available" in result["detail"]

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
        assert "Flow identifier" in response.text
        assert "not found" in response.text
        assert "This endpoint is not available" not in response.text

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

        assert response.status_code == 404
        result = response.json()
        assert "This endpoint is not available" in result["detail"]

    async def test_execute_workflow_allowed_when_dev_api_enabled_flow_exists(
        self,
        client: AsyncClient,
        created_api_key,
        mock_settings_dev_api_enabled,  # noqa: ARG002
    ):
        """Test POST /workflow allowed when dev API enabled - flow exists (501 not implemented)."""
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

            # Should return 501 because endpoint is not implemented yet
            assert response.status_code == 501
            assert "Not implemented" in response.text
            assert "This endpoint is not available" not in response.text

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

        # Test GET /workflow without API key
        response = await client.get("api/v2/workflow?job_id=550e8400-e29b-41d4-a716-446655440001")
        assert response.status_code == 403
        assert "API key must be passed" in response.json()["detail"]

        # Test POST /workflow/stop without API key
        response = await client.post(
            "api/v2/workflow/stop",
            json={"job_id": "550e8400-e29b-41d4-a716-446655440001"},
        )
        assert response.status_code == 403
        assert "API key must be passed" in response.json()["detail"]
