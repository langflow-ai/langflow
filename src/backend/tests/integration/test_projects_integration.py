"""Integration tests for project creation logic.

These tests verify the project creation endpoint with minimal mocking,
focusing on real database interactions and business logic.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient


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
