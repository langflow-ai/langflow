"""Tests for model provider enabled_providers endpoint and credential redaction."""

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.variable.constants import CREDENTIAL_TYPE


@pytest.fixture
def openai_credential():
    """OpenAI credential fixture."""
    return {
        "name": "API Key",
        "provider": "OpenAI",
        "value": "sk-test-openai-key-123456789",
        "description": "OpenAI API key for GPT models",
    }


@pytest.fixture
def anthropic_credential():
    """Anthropic credential fixture."""
    return {
        "name": "API Key",
        "provider": "Anthropic",
        "value": "sk-ant-test-anthropic-key-123456789",
        "description": "Anthropic API key for Claude models",
    }


@pytest.fixture
def google_credential():
    """Google credential fixture."""
    return {
        "name": "API Key",
        "provider": "Google Generative AI",
        "value": "AIzaSyTest-google-key-123456789",
        "description": "Google API key for Gemini models",
    }


@pytest.mark.usefixtures("active_user")
async def test_enabled_providers_empty_initially(client: AsyncClient, logged_in_headers):
    """Test that enabled_providers returns empty status when no credentials exist."""
    response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert "enabled_providers" in result
    assert "provider_status" in result
    assert isinstance(result["enabled_providers"], list)
    assert isinstance(result["provider_status"], dict)


@pytest.mark.usefixtures("active_user")
async def test_enabled_providers_after_credential_creation(client: AsyncClient, openai_credential, logged_in_headers):
    """Test that provider status changes after credential creation."""
    # Check initial status
    initial_response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    initial_result = initial_response.json()

    assert initial_response.status_code == status.HTTP_200_OK
    openai_initially_enabled = initial_result.get("provider_status", {}).get("OpenAI", False)

    # Create OpenAI credential
    create_response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    # Check status after credential creation
    after_response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    after_result = after_response.json()

    assert after_response.status_code == status.HTTP_200_OK
    assert "OpenAI" in after_result["enabled_providers"]
    assert after_result["provider_status"]["OpenAI"] is True

    # Verify the status changed
    assert after_result["provider_status"]["OpenAI"] != openai_initially_enabled or openai_initially_enabled is True


@pytest.mark.usefixtures("active_user")
async def test_enabled_providers_multiple_credentials(
    client: AsyncClient, openai_credential, anthropic_credential, google_credential, logged_in_headers
):
    """Test provider status with multiple credentials."""
    # Create multiple credentials
    await client.post("api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers)
    await client.post("api/v1/model-provider-credentials/", json=anthropic_credential, headers=logged_in_headers)
    await client.post("api/v1/model-provider-credentials/", json=google_credential, headers=logged_in_headers)

    # Check enabled providers
    response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert "OpenAI" in result["enabled_providers"]
    assert "Anthropic" in result["enabled_providers"]
    assert "Google Generative AI" in result["enabled_providers"]

    assert result["provider_status"]["OpenAI"] is True
    assert result["provider_status"]["Anthropic"] is True
    assert result["provider_status"]["Google Generative AI"] is True


@pytest.mark.usefixtures("active_user")
async def test_enabled_providers_after_credential_deletion(client: AsyncClient, openai_credential, logged_in_headers):
    """Test that provider status updates after credential deletion."""
    # Get initial OpenAI credentials to clean up
    initial_creds = await client.get("api/v1/model-provider-credentials/?provider=OpenAI", headers=logged_in_headers)
    for cred in initial_creds.json():
        await client.delete(f"api/v1/model-provider-credentials/{cred['id']}", headers=logged_in_headers)

    # Create credential
    create_response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    created_credential = create_response.json()
    credential_id = created_credential["id"]

    # Verify enabled
    enabled_response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    enabled_result = enabled_response.json()
    assert "OpenAI" in enabled_result["enabled_providers"]
    assert enabled_result["provider_status"]["OpenAI"] is True

    # Delete credential
    delete_response = await client.delete(
        f"api/v1/model-provider-credentials/{credential_id}", headers=logged_in_headers
    )
    assert delete_response.status_code == status.HTTP_200_OK

    # Verify disabled
    disabled_response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    disabled_result = disabled_response.json()
    assert "OpenAI" not in disabled_result["enabled_providers"]
    # When no credentials exist, provider_status may be empty or OpenAI should be False
    assert disabled_result["provider_status"].get("OpenAI", False) is False


@pytest.mark.usefixtures("active_user")
async def test_enabled_providers_filter_by_specific_providers(
    client: AsyncClient, openai_credential, anthropic_credential, logged_in_headers
):
    """Test filtering enabled_providers by specific providers."""
    # Create credentials
    await client.post("api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers)
    await client.post("api/v1/model-provider-credentials/", json=anthropic_credential, headers=logged_in_headers)

    # Request specific providers (only providers that are in the mapping)
    response = await client.get(
        "api/v1/models/enabled_providers?providers=OpenAI&providers=Anthropic", headers=logged_in_headers
    )
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert "OpenAI" in result["enabled_providers"]
    assert "Anthropic" in result["enabled_providers"]
    assert "OpenAI" in result["provider_status"]
    assert result["provider_status"]["OpenAI"] is True
    assert "Anthropic" in result["provider_status"]
    assert result["provider_status"]["Anthropic"] is True

    # Test filtering with non-existent provider (should not error, just return empty)
    response2 = await client.get(
        "api/v1/models/enabled_providers?providers=NonExistentProvider", headers=logged_in_headers
    )
    result2 = response2.json()
    assert response2.status_code == status.HTTP_200_OK
    assert result2["enabled_providers"] == []
    # NonExistentProvider is not in the mapping, so it won't be in provider_status
    assert "NonExistentProvider" not in result2["provider_status"]


@pytest.mark.usefixtures("active_user")
async def test_variables_credential_redaction(client: AsyncClient, openai_credential, logged_in_headers):
    """Test that credential variables have credentials properly redacted."""
    # Create a credential
    create_response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created_credential = create_response.json()

    # Get all variables
    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list)

    # Find the created credential in the response
    credential_variables = [v for v in result if v.get("id") == created_credential["id"]]
    assert len(credential_variables) == 1

    credential_variable = credential_variables[0]

    # Verify credential is redacted (value should be None for CREDENTIAL_TYPE)
    assert credential_variable["value"] is None
    assert credential_variable["type"] == CREDENTIAL_TYPE


@pytest.mark.usefixtures("active_user")
async def test_variables_multiple_credentials_all_redacted(
    client: AsyncClient, openai_credential, anthropic_credential, logged_in_headers
):
    """Test that all credentials are redacted when fetching all variables."""
    # Create multiple credentials
    create_response1 = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    create_response2 = await client.post(
        "api/v1/model-provider-credentials/", json=anthropic_credential, headers=logged_in_headers
    )

    assert create_response1.status_code == status.HTTP_201_CREATED
    assert create_response2.status_code == status.HTTP_201_CREATED

    # Get all variables
    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK

    # Verify all credentials are redacted
    for variable in result:
        if variable.get("type") == CREDENTIAL_TYPE:
            # Credential values should be None (redacted)
            assert variable["value"] is None


@pytest.mark.usefixtures("active_user")
async def test_enabled_providers_reflects_models_endpoint(client: AsyncClient, openai_credential, logged_in_headers):
    """Test that /models endpoint reflects same is_enabled status as /enabled_providers."""
    # Create credential
    await client.post("api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers)

    # Get enabled providers
    enabled_response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    enabled_result = enabled_response.json()

    # Get models (which should include provider information)
    models_response = await client.get("api/v1/models", headers=logged_in_headers)
    models_result = models_response.json()

    assert models_response.status_code == status.HTTP_200_OK

    # Check that OpenAI models have is_enabled=True
    openai_models = [m for m in models_result if m.get("provider") == "OpenAI"]
    if openai_models:
        for model in openai_models:
            assert model.get("is_enabled") is True

    # Verify consistency with enabled_providers
    assert enabled_result["provider_status"]["OpenAI"] is True


@pytest.mark.usefixtures("active_user")
async def test_security_credential_value_never_exposed_in_variables_endpoint(
    client: AsyncClient, openai_credential, logged_in_headers
):
    """Critical security test: ensure credential values are NEVER exposed in plain text."""
    original_value = openai_credential["value"]

    # Create credential
    create_response = await client.post(
        "api/v1/model-provider-credentials/", json=openai_credential, headers=logged_in_headers
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    # Get all variables - this is the security-critical path
    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    # CRITICAL: Original value must NEVER appear in response
    response_text = str(result)
    assert original_value not in response_text

    # Verify each credential is properly redacted (set to None)
    for variable in result:
        if variable.get("type") == CREDENTIAL_TYPE:
            # CRITICAL: Value must be None (redacted), never the original value
            assert variable["value"] is None
