"""Integration tests for project creation logic.

These tests verify the project creation endpoint with minimal mocking,
focusing on real database interactions and business logic.
"""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderKey,
)
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)
from langflow.services.deps import session_scope
from lfx.services.adapters.deployment.schema import DeploymentType


async def _attach_deployment_to_flow(*, user_id: UUID, flow_id: UUID, project_id: UUID) -> None:
    async with session_scope() as session:
        provider = DeploymentProviderAccount(
            user_id=user_id,
            name=f"integration-provider-{flow_id.hex[:8]}",
            provider_tenant_id="tenant-1",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            provider_url=f"https://integration-{flow_id.hex[:8]}.example.com",
            api_key="encrypted-value",  # pragma: allowlist secret
        )
        session.add(provider)
        await session.flush()

        deployment = Deployment(
            user_id=user_id,
            project_id=project_id,
            deployment_provider_account_id=provider.id,
            resource_key=f"integration-rk-{flow_id.hex[:8]}",
            name=f"integration-deployment-{flow_id.hex[:8]}",
            deployment_type=DeploymentType.AGENT,
        )
        session.add(deployment)
        await session.flush()

        flow_version = FlowVersion(
            flow_id=flow_id,
            user_id=user_id,
            version_number=1,
            data={"nodes": [], "edges": []},
        )
        session.add(flow_version)
        await session.flush()

        attachment = FlowVersionDeploymentAttachment(
            user_id=user_id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
            provider_snapshot_id=f"integration-snapshot-{flow_id.hex[:8]}",
        )
        session.add(attachment)
        await session.commit()


@pytest.mark.asyncio
async def test_project_authentication_settings(client: AsyncClient, logged_in_headers):
    """Integration test: Project authentication settings configuration."""
    # Scenario 1: AUTO_LOGIN disabled -> API key auth
    with patch("langflow.api.v1.projects.get_settings_service") as mock_get_settings:
        mock_service = MagicMock()
        mock_service.settings.add_projects_to_mcp_servers = False
        mock_service.auth_settings.AUTO_LOGIN = False
        mock_get_settings.return_value = mock_service

        with patch("langflow.api.v1.projects.encrypt_auth_settings") as mock_encrypt:
            mock_encrypt.return_value = {"encrypted": "apikey_auth"}

            response = await client.post(
                "api/v1/projects/",
                json={"name": "Auth Test 1", "description": "", "flows_list": [], "components_list": []},
                headers=logged_in_headers,
            )

            assert response.status_code == status.HTTP_201_CREATED
            project = response.json()

            # Verify encrypt was called with apikey auth type
            mock_encrypt.assert_called_once_with({"auth_type": "apikey"})
            assert project["name"] == "Auth Test 1"
            assert "id" in project

    # Scenario 2: AUTO_LOGIN enabled -> no auth
    with patch("langflow.api.v1.projects.get_settings_service") as mock_get_settings:
        mock_service = MagicMock()
        mock_service.settings.add_projects_to_mcp_servers = False
        mock_service.auth_settings.AUTO_LOGIN = True
        mock_get_settings.return_value = mock_service

        response = await client.post(
            "api/v1/projects/",
            json={"name": "Auth Test 2", "description": "", "flows_list": [], "components_list": []},
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        project = response.json()
        assert project["name"] == "Auth Test 2"
        assert "id" in project


@pytest.mark.asyncio
async def test_create_project_blocks_moving_deployed_flow(client: AsyncClient, logged_in_headers, active_user):
    flow_resp = await client.post(
        "api/v1/flows/",
        json={"name": "integration-deployed-flow", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert flow_resp.status_code == status.HTTP_201_CREATED

    payload = flow_resp.json()
    flow_id = UUID(payload["id"])
    source_project_id = UUID(payload["folder_id"])
    await _attach_deployment_to_flow(
        user_id=active_user.id,
        flow_id=flow_id,
        project_id=source_project_id,
    )

    create_resp = await client.post(
        "api/v1/projects/",
        json={"name": "integration-target-project", "flows_list": [str(flow_id)], "components_list": []},
        headers=logged_in_headers,
    )
    assert create_resp.status_code == status.HTTP_409_CONFLICT
    assert "cannot be moved to another project" in create_resp.json()["detail"]
