import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from langflow.main import setup_app


@pytest.fixture
def static_files_dir():
    """Create a temporary directory with a fake index.html."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = Path(tmpdir) / "index.html"
        index_path.write_text("<!DOCTYPE html><html><body>SPA App</body></html>")
        yield Path(tmpdir)


@pytest.fixture
async def app_with_static_files(static_files_dir):
    """Create app with static files handler (production-like setup)."""
    return setup_app(static_files_dir=static_files_dir, backend_only=False)


class TestProjectEndpoints404Integration:
    """Integration tests for project endpoints returning JSON when ID not found."""

    @pytest.mark.no_blockbuster
    async def test_get_nonexistent_project_returns_json_not_html(self, app_with_static_files):
        """Test that getting a non-existent project returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.get(f"/api/v1/projects/{fake_id}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")


class TestFlowEndpoints404Integration:
    """Integration tests for flow endpoints returning JSON when ID not found."""

    @pytest.mark.no_blockbuster
    async def test_get_nonexistent_flow_returns_json_not_html(self, app_with_static_files):
        """Test that getting a non-existent flow returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.get(f"/api/v1/flows/{fake_id}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.no_blockbuster
    async def test_delete_nonexistent_flow_returns_json_not_html(self, app_with_static_files):
        """Test that deleting a non-existent flow returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.delete(f"/api/v1/flows/{fake_id}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.no_blockbuster
    async def test_patch_nonexistent_flow_returns_json_not_html(self, app_with_static_files):
        """Test that patching a non-existent flow returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.patch(
                f"/api/v1/flows/{fake_id}",
                json={"name": "Updated Name"},
            )

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")


class TestVariableEndpoints404Integration:
    """Integration tests for variable endpoints returning JSON when ID not found."""

    @pytest.mark.no_blockbuster
    async def test_patch_nonexistent_variable_returns_json_not_html(self, app_with_static_files):
        """Test that patching a non-existent variable returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.patch(
                f"/api/v1/variables/{fake_id}",
                json={"id": fake_id, "name": "updated_var", "value": "new_value"},
            )

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.no_blockbuster
    async def test_delete_nonexistent_variable_returns_json_not_html(self, app_with_static_files):
        """Test that deleting a non-existent variable returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.delete(f"/api/v1/variables/{fake_id}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")


class TestUserEndpoints404Integration:
    """Integration tests for user endpoints returning JSON when ID not found."""

    @pytest.mark.no_blockbuster
    async def test_patch_nonexistent_user_returns_json_not_html(self, app_with_static_files):
        """Test that patching a non-existent user returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.patch(
                f"/api/v1/users/{fake_id}",
                json={"username": "new_username"},
            )

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.no_blockbuster
    async def test_delete_nonexistent_user_returns_json_not_html(self, app_with_static_files):
        """Test that deleting a non-existent user returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.delete(f"/api/v1/users/{fake_id}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")


class TestKnowledgeBaseEndpoints404Integration:
    """Integration tests for knowledge base endpoints returning JSON when ID not found."""

    @pytest.mark.no_blockbuster
    async def test_get_nonexistent_knowledge_base_returns_json_not_html(self, app_with_static_files):
        """Test that getting a non-existent knowledge base returns JSON, not HTML."""
        fake_name = "nonexistent-kb-12345"

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.get(f"/api/v1/knowledge_bases/{fake_name}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.no_blockbuster
    async def test_delete_nonexistent_knowledge_base_returns_json_not_html(self, app_with_static_files):
        """Test that deleting a non-existent knowledge base returns JSON, not HTML."""
        fake_name = "nonexistent-kb-12345"

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.delete(f"/api/v1/knowledge_bases/{fake_name}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")


class TestApiKeyEndpoints404Integration:
    """Integration tests for API key endpoints returning JSON when ID not found."""

    @pytest.mark.no_blockbuster
    async def test_delete_nonexistent_api_key_returns_json_not_html(self, app_with_static_files):
        """Test that deleting a non-existent API key returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.delete(f"/api/v1/api_key/{fake_id}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")


class TestFilesV2Endpoints404Integration:
    """Integration tests for files v2 endpoints returning JSON when ID not found."""

    @pytest.mark.no_blockbuster
    async def test_get_nonexistent_file_returns_json_not_html(self, app_with_static_files):
        """Test that getting a non-existent file returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.get(f"/api/v2/files/{fake_id}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.no_blockbuster
    async def test_put_nonexistent_file_returns_json_not_html(self, app_with_static_files):
        """Test that updating a non-existent file returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.put(
                f"/api/v2/files/{fake_id}",
                params={"name": "updated_file"},
            )

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.no_blockbuster
    async def test_delete_nonexistent_file_returns_json_not_html(self, app_with_static_files):
        """Test that deleting a non-existent file returns JSON, not HTML."""
        fake_id = str(uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app_with_static_files),
            base_url="http://testserver",
        ) as client:
            response = await client.delete(f"/api/v2/files/{fake_id}")

            assert "text/html" not in response.headers.get("content-type", "")
            assert "application/json" in response.headers.get("content-type", "")
