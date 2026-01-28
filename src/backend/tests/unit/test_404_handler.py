from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient


class TestAPI404Handler:
    """Test that API routes return JSON 404 instead of HTML."""

    async def test_api_nonexistent_resource_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that a non-existent resource returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.get(
            f"/api/v1/projects/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")
        result = response.json()
        assert "detail" in result

    async def test_api_invalid_uuid_returns_validation_error_not_html(self, client: AsyncClient, logged_in_headers):
        """Test that invalid UUID returns validation error, not HTML."""
        response = await client.get(
            "/api/v1/projects/not-a-valid-uuid",
            headers=logged_in_headers,
        )

        assert response.status_code in (
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        )
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/v1/projects/00000000-0000-0000-0000-000000000000",
            "/api/v1/flows/00000000-0000-0000-0000-000000000000",
            "/api/v2/files/00000000-0000-0000-0000-000000000000",
        ],
    )
    async def test_various_api_endpoints_return_json_404(self, client: AsyncClient, logged_in_headers, endpoint):
        """Test multiple API endpoints return JSON 404 for non-existent resources."""
        response = await client.get(endpoint, headers=logged_in_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")

    async def test_project_not_found_has_correct_message(self, client: AsyncClient, logged_in_headers):
        """Test that project not found returns correct error message."""
        fake_id = str(uuid4())

        response = await client.get(
            f"/api/v1/projects/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        result = response.json()
        assert result["detail"] == "Project not found"

    async def test_flow_not_found_has_correct_message(self, client: AsyncClient, logged_in_headers):
        """Test that flow not found returns correct error message."""
        fake_id = str(uuid4())

        response = await client.get(
            f"/api/v1/flows/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        result = response.json()
        assert "detail" in result


class TestFlowEndpoints404:
    """Test 404 responses for flow endpoints."""

    async def test_delete_nonexistent_flow_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that deleting a non-existent flow returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.delete(
            f"/api/v1/flows/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")

    async def test_patch_nonexistent_flow_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that patching a non-existent flow returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.patch(
            f"/api/v1/flows/{fake_id}",
            json={"name": "Updated Name"},
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")


class TestProjectEndpoints404:
    """Test 404 responses for project endpoints."""

    async def test_get_nonexistent_project_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that getting a non-existent project returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.get(
            f"/api/v1/projects/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")
        assert response.json()["detail"] == "Project not found"

    async def test_delete_nonexistent_project_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that deleting a non-existent project returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.delete(
            f"/api/v1/projects/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")

    async def test_patch_nonexistent_project_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that patching a non-existent project returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.patch(
            f"/api/v1/projects/{fake_id}",
            json={"name": "Updated Name"},
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")


class TestUserEndpoints404:
    """Test 404 responses for user endpoints."""

    async def test_patch_nonexistent_user_returns_json_404(self, client: AsyncClient, logged_in_headers_super_user):
        """Test that patching a non-existent user returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.patch(
            f"/api/v1/users/{fake_id}",
            json={"username": "new_username"},
            headers=logged_in_headers_super_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")

    async def test_delete_nonexistent_user_returns_json_404(self, client: AsyncClient, logged_in_headers_super_user):
        """Test that deleting a non-existent user returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.delete(
            f"/api/v1/users/{fake_id}",
            headers=logged_in_headers_super_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")


class TestVariableEndpoints404:
    """Test 404 responses for variable endpoints."""

    async def test_patch_nonexistent_variable_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that patching a non-existent variable returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.patch(
            f"/api/v1/variables/{fake_id}",
            json={"id": fake_id, "name": "updated_var", "value": "new_value"},
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")

    async def test_delete_nonexistent_variable_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that deleting a non-existent variable returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.delete(
            f"/api/v1/variables/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")


class TestKnowledgeBaseEndpoints404:
    """Test 404 responses for knowledge base endpoints."""

    async def test_get_nonexistent_knowledge_base_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that getting a non-existent knowledge base returns 404 JSON."""
        fake_name = "nonexistent-kb-12345"

        response = await client.get(
            f"/api/v1/knowledge_bases/{fake_name}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")
        assert "not found" in response.json()["detail"].lower()

    async def test_delete_nonexistent_knowledge_base_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that deleting a non-existent knowledge base returns 404 JSON."""
        fake_name = "nonexistent-kb-12345"

        response = await client.delete(
            f"/api/v1/knowledge_bases/{fake_name}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")
        assert "not found" in response.json()["detail"].lower()


class TestApiKeyEndpoints404:
    """Test 404 responses for API key endpoints."""

    async def test_delete_nonexistent_api_key_returns_json_error(self, client: AsyncClient, logged_in_headers):
        """Test that deleting a non-existent API key returns JSON error."""
        fake_id = str(uuid4())

        response = await client.delete(
            f"/api/v1/api_key/{fake_id}",
            headers=logged_in_headers,
        )

        # API key deletion returns 400 to not reveal if key exists
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")


class TestFilesV2Endpoints404:
    """Test 404 responses for files v2 endpoints."""

    async def test_get_nonexistent_file_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that getting a non-existent file returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.get(
            f"/api/v2/files/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")

    async def test_put_nonexistent_file_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that updating a non-existent file returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.put(
            f"/api/v2/files/{fake_id}",
            params={"name": "updated_file"},
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")

    async def test_delete_nonexistent_file_returns_json_404(self, client: AsyncClient, logged_in_headers):
        """Test that deleting a non-existent file returns 404 JSON."""
        fake_id = str(uuid4())

        response = await client.delete(
            f"/api/v2/files/{fake_id}",
            headers=logged_in_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "application/json" in response.headers["content-type"]
        assert "text/html" not in response.headers.get("content-type", "")
