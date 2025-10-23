"""Integration tests for credential API endpoints."""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch

from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.credential.model import Credential, CredentialCreate, CredentialUpdate


@pytest.fixture
def sample_credential_data():
    """Sample credential data for testing."""
    return {
        "name": "OpenAI API Key",
        "provider": "OpenAI",
        "description": "My OpenAI API key for GPT models",
        "value": "sk-test123456789",
        "is_active": True,
    }


@pytest.fixture
def sample_credential_update_data():
    """Sample credential update data for testing."""
    return {
        "name": "Updated OpenAI API Key",
        "description": "Updated description",
        "is_active": False,
    }


@pytest.fixture
def sample_credential():
    """Sample credential object for testing."""
    return Credential(
        id=uuid4(),
        name="OpenAI API Key",
        provider="OpenAI",
        description="My OpenAI API key",
        encrypted_value="encrypted_value_here",
        is_active=True,
        usage_count=0,
        last_used=None,
        user_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )


class TestCreateCredentialEndpoint:
    """Test POST /api/v1/credentials/ endpoint."""

    @patch("langflow.api.v1.credentials.create_credential")
    async def test_create_credential_success(
        self, mock_create, client: AsyncClient, active_user, sample_credential_data, sample_credential
    ):
        """Test successful credential creation."""
        # Setup mock
        mock_create.return_value = sample_credential
        
        # Execute
        response = await client.post("/api/v1/credentials/", json=sample_credential_data)
        
        # Verify
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == sample_credential_data["name"]
        assert data["provider"] == sample_credential_data["provider"]
        assert data["description"] == sample_credential_data["description"]
        assert data["is_active"] == sample_credential_data["is_active"]
        # Value should not be returned in response for security
        assert "value" not in data
        assert "encrypted_value" not in data

    async def test_create_credential_validation_error(self, client: AsyncClient, active_user):
        """Test credential creation with validation errors."""
        # Missing required fields
        invalid_data = {
            "name": "",  # Empty name
            "provider": "OpenAI",
        }
        
        response = await client.post("/api/v1/credentials/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("langflow.api.v1.credentials.create_credential")
    async def test_create_credential_server_error(
        self, mock_create, client: AsyncClient, active_user, sample_credential_data
    ):
        """Test credential creation with server error."""
        # Setup mock to raise exception
        mock_create.side_effect = Exception("Database error")
        
        response = await client.post("/api/v1/credentials/", json=sample_credential_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Failed to create credential" in response.json()["detail"]


class TestGetCredentialsEndpoint:
    """Test GET /api/v1/credentials/ endpoint."""

    @patch("langflow.api.v1.credentials.get_credentials_by_user")
    async def test_get_credentials_success(
        self, mock_get, client: AsyncClient, active_user, sample_credential
    ):
        """Test successful credential retrieval."""
        # Setup mock
        mock_get.return_value = [sample_credential]
        
        # Execute
        response = await client.get("/api/v1/credentials/")
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_credential.name
        assert data[0]["provider"] == sample_credential.provider

    @patch("langflow.api.v1.credentials.get_credentials_by_user")
    async def test_get_credentials_with_provider_filter(
        self, mock_get, client: AsyncClient, active_user, sample_credential
    ):
        """Test credential retrieval with provider filter."""
        # Setup mock
        mock_get.return_value = [sample_credential]
        
        # Execute with provider filter
        response = await client.get("/api/v1/credentials/?provider=OpenAI")
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        mock_get.assert_called_once()
        # Check that provider filter was passed
        call_args = mock_get.call_args
        assert call_args[1]["provider"] == "OpenAI"

    @patch("langflow.api.v1.credentials.get_credentials_by_user")
    async def test_get_credentials_server_error(
        self, mock_get, client: AsyncClient, active_user
    ):
        """Test credential retrieval with server error."""
        # Setup mock to raise exception
        mock_get.side_effect = Exception("Database error")
        
        response = await client.get("/api/v1/credentials/")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to retrieve credentials" in response.json()["detail"]


class TestGetCredentialByIdEndpoint:
    """Test GET /api/v1/credentials/{credential_id} endpoint."""

    @patch("langflow.api.v1.credentials.get_credential_by_id")
    async def test_get_credential_by_id_success(
        self, mock_get, client: AsyncClient, active_user, sample_credential
    ):
        """Test successful credential retrieval by ID."""
        # Setup mock
        mock_get.return_value = sample_credential
        
        # Execute
        response = await client.get(f"/api/v1/credentials/{sample_credential.id}")
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_credential.id)
        assert data["name"] == sample_credential.name
        assert data["provider"] == sample_credential.provider

    @patch("langflow.api.v1.credentials.get_credential_by_id")
    async def test_get_credential_by_id_not_found(
        self, mock_get, client: AsyncClient, active_user
    ):
        """Test credential retrieval by ID not found."""
        # Setup mock
        mock_get.return_value = None
        
        # Execute
        response = await client.get(f"/api/v1/credentials/{uuid4()}")
        
        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Credential not found" in response.json()["detail"]

    @patch("langflow.api.v1.credentials.get_credential_by_id")
    async def test_get_credential_by_id_server_error(
        self, mock_get, client: AsyncClient, active_user, sample_credential
    ):
        """Test credential retrieval by ID with server error."""
        # Setup mock to raise exception
        mock_get.side_effect = Exception("Database error")
        
        response = await client.get(f"/api/v1/credentials/{sample_credential.id}")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to retrieve credential" in response.json()["detail"]


class TestUpdateCredentialEndpoint:
    """Test PUT /api/v1/credentials/{credential_id} endpoint."""

    @patch("langflow.api.v1.credentials.update_credential")
    async def test_update_credential_success(
        self, mock_update, client: AsyncClient, active_user, sample_credential, sample_credential_update_data
    ):
        """Test successful credential update."""
        # Setup mock
        updated_credential = Credential(
            **sample_credential.model_dump(),
            name=sample_credential_update_data["name"],
            description=sample_credential_update_data["description"],
            is_active=sample_credential_update_data["is_active"],
        )
        mock_update.return_value = updated_credential
        
        # Execute
        response = await client.put(f"/api/v1/credentials/{sample_credential.id}", json=sample_credential_update_data)
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == sample_credential_update_data["name"]
        assert data["description"] == sample_credential_update_data["description"]
        assert data["is_active"] == sample_credential_update_data["is_active"]

    @patch("langflow.api.v1.credentials.update_credential")
    async def test_update_credential_not_found(
        self, mock_update, client: AsyncClient, active_user, sample_credential_update_data
    ):
        """Test credential update not found."""
        # Setup mock to raise HTTPException
        from fastapi import HTTPException
        mock_update.side_effect = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
        
        response = await client.put(f"/api/v1/credentials/{uuid4()}", json=sample_credential_update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("langflow.api.v1.credentials.update_credential")
    async def test_update_credential_server_error(
        self, mock_update, client: AsyncClient, active_user, sample_credential, sample_credential_update_data
    ):
        """Test credential update with server error."""
        # Setup mock to raise exception
        mock_update.side_effect = Exception("Database error")
        
        response = await client.put(f"/api/v1/credentials/{sample_credential.id}", json=sample_credential_update_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Failed to update credential" in response.json()["detail"]


class TestDeleteCredentialEndpoint:
    """Test DELETE /api/v1/credentials/{credential_id} endpoint."""

    @patch("langflow.api.v1.credentials.delete_credential")
    async def test_delete_credential_success(
        self, mock_delete, client: AsyncClient, active_user, sample_credential
    ):
        """Test successful credential deletion."""
        # Setup mock
        mock_delete.return_value = None
        
        # Execute
        response = await client.delete(f"/api/v1/credentials/{sample_credential.id}")
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["detail"] == "Credential deleted successfully"

    @patch("langflow.api.v1.credentials.delete_credential")
    async def test_delete_credential_not_found(
        self, mock_delete, client: AsyncClient, active_user
    ):
        """Test credential deletion not found."""
        # Setup mock to raise HTTPException
        from fastapi import HTTPException
        mock_delete.side_effect = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
        
        response = await client.delete(f"/api/v1/credentials/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("langflow.api.v1.credentials.delete_credential")
    async def test_delete_credential_server_error(
        self, mock_delete, client: AsyncClient, active_user, sample_credential
    ):
        """Test credential deletion with server error."""
        # Setup mock to raise exception
        mock_delete.side_effect = Exception("Database error")
        
        response = await client.delete(f"/api/v1/credentials/{sample_credential.id}")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Failed to delete credential" in response.json()["detail"]


class TestCredentialSecurity:
    """Test credential security aspects."""

    @patch("langflow.api.v1.credentials.create_credential")
    async def test_credential_value_not_exposed_in_response(
        self, mock_create, client: AsyncClient, active_user, sample_credential_data, sample_credential
    ):
        """Test that credential values are not exposed in API responses."""
        # Setup mock
        mock_create.return_value = sample_credential
        
        # Execute
        response = await client.post("/api/v1/credentials/", json=sample_credential_data)
        
        # Verify
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        # Ensure sensitive data is not exposed
        assert "value" not in data
        assert "encrypted_value" not in data
        assert "sk-" not in str(data)

    @patch("langflow.api.v1.credentials.get_credentials_by_user")
    async def test_credential_list_security(
        self, mock_get, client: AsyncClient, active_user, sample_credential
    ):
        """Test that credential lists don't expose sensitive data."""
        # Setup mock
        mock_get.return_value = [sample_credential]
        
        # Execute
        response = await client.get("/api/v1/credentials/")
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        credential_data = data[0]
        # Ensure sensitive data is not exposed
        assert "value" not in credential_data
        assert "encrypted_value" not in credential_data
        assert "sk-" not in str(credential_data)


class TestCredentialValidation:
    """Test credential input validation."""

    async def test_create_credential_missing_required_fields(self, client: AsyncClient, active_user):
        """Test credential creation with missing required fields."""
        # Missing name
        invalid_data = {
            "provider": "OpenAI",
            "value": "sk-test123",
        }
        
        response = await client.post("/api/v1/credentials/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_credential_invalid_provider(self, client: AsyncClient, active_user):
        """Test credential creation with invalid provider."""
        invalid_data = {
            "name": "Test Key",
            "provider": "",  # Empty provider
            "value": "sk-test123",
        }
        
        response = await client.post("/api/v1/credentials/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_update_credential_partial_update(self, client: AsyncClient, active_user):
        """Test credential partial update."""
        # This should be allowed - only update specific fields
        update_data = {
            "description": "Updated description only",
        }
        
        # Mock the update function
        with patch("langflow.api.v1.credentials.update_credential") as mock_update:
            mock_update.return_value = Credential(
                id=uuid4(),
                name="Test Key",
                provider="OpenAI",
                description="Updated description only",
                encrypted_value="encrypted",
                user_id=active_user.id,
            )
            
            response = await client.put(f"/api/v1/credentials/{uuid4()}", json=update_data)
            assert response.status_code == status.HTTP_200_OK
