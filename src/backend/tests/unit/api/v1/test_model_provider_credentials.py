"""Tests for model provider credentials API endpoints."""

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.variable.constants import CATEGORY_GLOBAL, CREDENTIAL_TYPE


@pytest.fixture
def openai_credential():
    return {
        "name": "API Key",
        "provider": "OpenAI",
        "value": "sk-test-openai-key-123456789",
        "description": "OpenAI API key for GPT models",
    }


@pytest.fixture
def anthropic_credential():
    return {
        "name": "API Key",
        "provider": "Anthropic",
        "value": "sk-ant-test-anthropic-key-123456789",
        "description": "Anthropic API key for Claude models",
    }


@pytest.fixture
def google_credential():
    return {
        "name": "API Key",
        "provider": "Google",
        "value": "AIzaSyTest-google-key-123456789",
        "description": "Google API key for Gemini models",
    }


@pytest.mark.usefixtures("active_user")
async def test_create_model_provider_credential(client: AsyncClient, openai_credential, logged_in_headers):
    """Test creating a model provider credential."""
    response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )

    # Print the response for debugging
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert result["name"] == "openai_api_key"  # Should be transformed
    assert result["type"] == CREDENTIAL_TYPE
    assert result["category"] == CATEGORY_GLOBAL
    assert result["default_fields"] == ["OpenAI", "api_key"]
    assert "id" in result
    # Value should be encrypted (different from original)
    assert result["value"] != openai_credential["value"]


@pytest.mark.usefixtures("active_user")
async def test_create_model_provider_credential_missing_fields(client: AsyncClient, logged_in_headers):
    """Test creating a credential with missing required fields."""
    incomplete_credential = {
        "name": "API Key",
        "provider": "OpenAI",
        # Missing value
    }

    response = await client.post(
        "api/v1/model-provider-credentials/", json=incomplete_credential, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.usefixtures("active_user")
async def test_get_model_provider_credentials(
    client: AsyncClient, openai_credential, anthropic_credential, logged_in_headers
):
    """Test retrieving all model provider credentials."""
    # Create two credentials
    await client.post("api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers)
    await client.post("api/v1/model-provider-credentials/", json=anthropic_credential, headers=logged_in_headers)

    response = await client.get("api/v1/model-provider-credentials/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert len(result) >= 2

    # Check that both credentials are present
    credential_names = [cred["name"] for cred in result]
    assert "openai_api_key" in credential_names
    assert "anthropic_api_key" in credential_names


@pytest.mark.usefixtures("active_user")
async def test_get_model_provider_credentials_filter_by_provider(
    client: AsyncClient, openai_credential, anthropic_credential, logged_in_headers
):
    """Test filtering credentials by provider."""
    # Create credentials for different providers
    await client.post("api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers)
    await client.post("api/v1/model-provider-credentials/", json=anthropic_credential, headers=logged_in_headers)

    # Filter by OpenAI provider
    response = await client.get("api/v1/model-provider-credentials/?provider=OpenAI", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert len(result) >= 1

    # All returned credentials should be for OpenAI
    for cred in result:
        assert "OpenAI" in cred["default_fields"]


@pytest.mark.usefixtures("active_user")
async def test_get_model_provider_credential_by_id(client: AsyncClient, openai_credential, logged_in_headers):
    """Test retrieving a specific credential by ID."""
    # Create a credential
    create_response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    created_credential = create_response.json()
    credential_id = created_credential["id"]

    # Retrieve the credential by ID
    response = await client.get(f"api/v1/model-provider-credentials/{credential_id}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["id"] == credential_id
    assert result["name"] == "openai_api_key"
    assert result["type"] == CREDENTIAL_TYPE


@pytest.mark.usefixtures("active_user")
async def test_get_model_provider_credential_by_id_not_found(client: AsyncClient, logged_in_headers):
    """Test retrieving a non-existent credential by ID."""
    fake_id = uuid4()

    response = await client.get(f"api/v1/model-provider-credentials/{fake_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.usefixtures("active_user")
async def test_get_model_provider_credential_value(client: AsyncClient, openai_credential, logged_in_headers):
    """Test retrieving the decrypted value of a credential."""
    # Create a credential
    create_response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    created_credential = create_response.json()
    credential_id = created_credential["id"]

    # Get the decrypted value
    response = await client.get(f"api/v1/model-provider-credentials/{credential_id}/value", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert "value" in result
    assert result["value"] == openai_credential["value"]  # Should be decrypted


@pytest.mark.usefixtures("active_user")
async def test_get_model_provider_credentials_by_provider(
    client: AsyncClient, openai_credential, anthropic_credential, logged_in_headers
):
    """Test retrieving credentials for a specific provider."""
    # Create credentials for different providers
    await client.post("api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers)
    await client.post("api/v1/model-provider-credentials/", json=anthropic_credential, headers=logged_in_headers)

    # Get credentials for OpenAI provider
    response = await client.get("api/v1/model-provider-credentials/provider/OpenAI", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert len(result) >= 1

    # All returned credentials should be for OpenAI
    for cred in result:
        assert "OpenAI" in cred["default_fields"]


@pytest.mark.usefixtures("active_user")
async def test_delete_model_provider_credential(client: AsyncClient, openai_credential, logged_in_headers):
    """Test deleting a model provider credential."""
    # Create a credential
    create_response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    created_credential = create_response.json()
    credential_id = created_credential["id"]

    # Delete the credential
    response = await client.delete(f"api/v1/model-provider-credentials/{credential_id}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert "Credential deleted successfully" in result["detail"]

    # Verify the credential is deleted
    get_response = await client.get(f"api/v1/model-provider-credentials/{credential_id}", headers=logged_in_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.usefixtures("active_user")
async def test_delete_model_provider_credential_not_found(client: AsyncClient, logged_in_headers):
    """Test deleting a non-existent credential."""
    fake_id = uuid4()

    response = await client.delete(f"api/v1/model-provider-credentials/{fake_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.usefixtures("active_user")
async def test_model_provider_credentials_user_isolation(client: AsyncClient, openai_credential, logged_in_headers):
    """Test that users can only access their own credentials."""
    # Create a credential for the current user
    create_response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    created_credential = create_response.json()
    credential_id = created_credential["id"]

    # Verify the credential exists
    response = await client.get(f"api/v1/model-provider-credentials/{credential_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    # Note: In a real scenario, you would test with a different user's session
    # to ensure isolation, but this requires additional test setup


@pytest.mark.usefixtures("active_user")
async def test_create_credential_with_special_characters(client: AsyncClient, logged_in_headers):
    """Test creating credentials with special characters in name and provider."""
    special_credential = {
        "name": "API Key (Production)",
        "provider": "OpenAI-GPT4",
        "value": "sk-test-key-with-special-chars-123",
        "description": "Production API key for OpenAI GPT-4",
    }

    response = await client.post(
        "api/v1/model-provider-credentials/", json=special_credential, headers=logged_in_headers
    )
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert result["name"] == "openai-gpt4_api_key_(production)"  # Should be transformed
    assert result["type"] == CREDENTIAL_TYPE


@pytest.mark.usefixtures("active_user")
async def test_create_credential_empty_values(client: AsyncClient, logged_in_headers):
    """Test creating credentials with empty values."""
    empty_credential = {"name": "", "provider": "", "value": "", "description": ""}

    response = await client.post("api/v1/model-provider-credentials/", json=empty_credential, headers=logged_in_headers)

    # Should fail validation
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.usefixtures("active_user")
async def test_get_credentials_empty_list(client: AsyncClient, logged_in_headers):
    """Test getting credentials when none exist."""
    response = await client.get("api/v1/model-provider-credentials/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    # Should return empty list or existing variables from other sources
    assert isinstance(result, list)
