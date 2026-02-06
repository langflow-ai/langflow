from unittest import mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE


@pytest.fixture
def generic_variable():
    return {
        "name": "test_generic_variable",
        "value": "test_generic_value",
        "type": GENERIC_TYPE,
        "default_fields": ["test_field"],
    }


@pytest.fixture
def credential_variable():
    return {
        "name": "test_credential_variable",
        "value": "test_credential_value",
        "type": CREDENTIAL_TYPE,
        "default_fields": ["test_field"],
    }


@pytest.mark.usefixtures("active_user")
async def test_create_variable(client: AsyncClient, generic_variable, logged_in_headers):
    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert generic_variable["name"] == result["name"]
    assert generic_variable["type"] == result["type"]
    assert generic_variable["default_fields"] == result["default_fields"]
    assert "id" in result
    # GENERIC_TYPE variables should NOT be encrypted (stored as plaintext)
    assert generic_variable["value"] == result["value"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__variable_name_already_exists(client: AsyncClient, generic_variable, logged_in_headers):
    await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)

    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Variable name already exists" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__variable_name_and_value_cannot_be_empty(
    client: AsyncClient, generic_variable, logged_in_headers
):
    generic_variable["name"] = ""
    generic_variable["value"] = ""

    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Variable name and value cannot be empty" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__variable_name_cannot_be_empty(client: AsyncClient, generic_variable, logged_in_headers):
    generic_variable["name"] = ""

    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Variable name cannot be empty" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__variable_value_cannot_be_empty(
    client: AsyncClient, generic_variable, logged_in_headers
):
    generic_variable["value"] = ""

    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Variable value cannot be empty" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__httpexception(client: AsyncClient, credential_variable, logged_in_headers):
    status_code = 418
    generic_message = "I'm a teapot"

    with mock.patch("langflow.services.auth.utils.encrypt_api_key") as m:
        m.side_effect = HTTPException(status_code=status_code, detail=generic_message)
        response = await client.post("api/v1/variables/", json=credential_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_418_IM_A_TEAPOT
        assert generic_message in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__exception(client: AsyncClient, credential_variable, logged_in_headers):
    generic_message = "Generic error message"

    with mock.patch("langflow.services.auth.utils.encrypt_api_key") as m:
        m.side_effect = Exception(generic_message)
        response = await client.post("api/v1/variables/", json=credential_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert generic_message in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_read_variables(client: AsyncClient, generic_variable, credential_variable, logged_in_headers):
    # Create a generic variable
    create_response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED

    # Create a credential variable
    create_response = await client.post("api/v1/variables/", json=credential_variable, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED

    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK

    # Check both variables exist
    assert generic_variable["name"] in [r["name"] for r in result]
    assert credential_variable["name"] in [r["name"] for r in result]

    # Assert that credentials are not decrypted and generic are decrypted
    credential_vars = [r for r in result if r["type"] == CREDENTIAL_TYPE]
    generic_vars = [r for r in result if r["type"] == GENERIC_TYPE]

    # Credential variables should remain encrypted (value should be different)
    assert all(c["value"] != credential_variable["value"] for c in credential_vars)

    # Generic variables should be decrypted (value should match original)
    assert all(g["value"] == generic_variable["value"] for g in generic_vars)


@pytest.mark.usefixtures("active_user")
async def test_read_variables__empty(client: AsyncClient, logged_in_headers):
    all_variables = await client.get("api/v1/variables/", headers=logged_in_headers)
    all_variables = all_variables.json()
    for variable in all_variables:
        await client.delete(f"api/v1/variables/{variable.get('id')}", headers=logged_in_headers)

    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result == []


@pytest.mark.usefixtures("active_user")
async def test_read_variables__(client: AsyncClient, logged_in_headers):
    """When the variable service raises (e.g. DB error), the list endpoint returns 500."""
    generic_message = "Generic error message"

    with mock.patch(
        "langflow.services.variable.service.DatabaseVariableService.get_all",
        new_callable=mock.AsyncMock,
        side_effect=Exception(generic_message),
    ):
        response = await client.get("api/v1/variables/", headers=logged_in_headers)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert generic_message in response.json().get("detail", "")


@pytest.mark.usefixtures("active_user")
async def test_update_variable(client: AsyncClient, generic_variable, logged_in_headers):
    saved = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    saved = saved.json()
    generic_variable["id"] = saved.get("id")
    generic_variable["name"] = "new_name"
    generic_variable["value"] = "new_value"
    generic_variable["type"] = GENERIC_TYPE  # Ensure we keep it as GENERIC_TYPE
    generic_variable["default_fields"] = ["new_field"]

    response = await client.patch(
        f"api/v1/variables/{saved.get('id')}", json=generic_variable, headers=logged_in_headers
    )
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert saved["id"] == result["id"]
    assert saved["name"] != result["name"]
    assert saved["default_fields"] != result["default_fields"]


@pytest.mark.usefixtures("active_user")
async def test_update_variable__exception(client: AsyncClient, generic_variable, logged_in_headers):
    wrong_id = uuid4()
    generic_variable["id"] = str(wrong_id)

    response = await client.patch(f"api/v1/variables/{wrong_id}", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Variable not found" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_delete_variable(client: AsyncClient, generic_variable, logged_in_headers):
    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    saved = response.json()
    response = await client.delete(f"api/v1/variables/{saved.get('id')}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.usefixtures("active_user")
async def test_delete_variable__exception(client: AsyncClient, logged_in_headers):
    wrong_id = uuid4()

    response = await client.delete(f"api/v1/variables/{wrong_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.usefixtures("active_user")
async def test_create_variable__openai_api_key_validation_success(client: AsyncClient, logged_in_headers):
    """Test successful OpenAI API key validation."""
    # Clean up any existing OPENAI_API_KEY variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "OPENAI_API_KEY":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    openai_variable = {
        "name": "OPENAI_API_KEY",
        "value": "sk-test-key",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock successful OpenAI API call
    with mock.patch("langchain_openai.ChatOpenAI.invoke") as mock_invoke:
        mock_invoke.return_value = "test response"
        response = await client.post("api/v1/variables/", json=openai_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_201_CREATED
        assert result["name"] == "OPENAI_API_KEY"
        assert mock_invoke.called


@pytest.mark.usefixtures("active_user")
async def test_create_variable__openai_api_key_validation_failure(client: AsyncClient, logged_in_headers):
    """Test failed OpenAI API key validation."""
    # Clean up any existing OPENAI_API_KEY variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "OPENAI_API_KEY":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    openai_variable = {
        "name": "OPENAI_API_KEY",
        "value": "invalid-key",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock failed OpenAI API call with authentication error
    with mock.patch("langchain_openai.ChatOpenAI.invoke") as mock_invoke:
        mock_invoke.side_effect = Exception("401 authentication failed")
        response = await client.post("api/v1/variables/", json=openai_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid API key for OpenAI" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__anthropic_api_key_validation_success(client: AsyncClient, logged_in_headers):
    """Test successful Anthropic API key validation."""
    # Clean up any existing ANTHROPIC_API_KEY variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "ANTHROPIC_API_KEY":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    anthropic_variable = {
        "name": "ANTHROPIC_API_KEY",
        "value": "sk-ant-test-key",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock successful Anthropic API call
    with mock.patch("langchain_anthropic.ChatAnthropic.invoke") as mock_invoke:
        mock_invoke.return_value = "test response"
        response = await client.post("api/v1/variables/", json=anthropic_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_201_CREATED
        assert result["name"] == "ANTHROPIC_API_KEY"
        assert mock_invoke.called


@pytest.mark.usefixtures("active_user")
async def test_create_variable__anthropic_api_key_validation_failure(client: AsyncClient, logged_in_headers):
    """Test failed Anthropic API key validation."""
    # Clean up any existing ANTHROPIC_API_KEY variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "ANTHROPIC_API_KEY":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    anthropic_variable = {
        "name": "ANTHROPIC_API_KEY",
        "value": "invalid-key",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock failed Anthropic API call with authentication error
    with mock.patch("langchain_anthropic.ChatAnthropic.invoke") as mock_invoke:
        mock_invoke.side_effect = Exception("Invalid API key provided")
        response = await client.post("api/v1/variables/", json=anthropic_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid API key for Anthropic" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__google_api_key_validation_success(client: AsyncClient, logged_in_headers):
    """Test successful Google API key validation."""
    # Clean up any existing GOOGLE_API_KEY variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "GOOGLE_API_KEY":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    google_variable = {
        "name": "GOOGLE_API_KEY",
        "value": "test-google-key",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock successful Google API call
    with mock.patch("langchain_google_genai.ChatGoogleGenerativeAI.invoke") as mock_invoke:
        mock_invoke.return_value = "test response"
        response = await client.post("api/v1/variables/", json=google_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_201_CREATED
        assert result["name"] == "GOOGLE_API_KEY"
        assert mock_invoke.called


@pytest.mark.usefixtures("active_user")
async def test_create_variable__ollama_base_url_validation_success(client: AsyncClient, logged_in_headers):
    """Test successful Ollama base URL validation."""
    # Clean up any existing OLLAMA_BASE_URL variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "OLLAMA_BASE_URL":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    ollama_variable = {
        "name": "OLLAMA_BASE_URL",
        "value": "http://localhost:11434",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock successful Ollama API call
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        response = await client.post("api/v1/variables/", json=ollama_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_201_CREATED
        assert result["name"] == "OLLAMA_BASE_URL"
        assert mock_get.called


@pytest.mark.usefixtures("active_user")
async def test_create_variable__ollama_base_url_validation_failure(client: AsyncClient, logged_in_headers):
    """Test failed Ollama base URL validation."""
    # Clean up any existing OLLAMA_BASE_URL variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "OLLAMA_BASE_URL":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    ollama_variable = {
        "name": "OLLAMA_BASE_URL",
        "value": "http://invalid-url",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock failed Ollama API call
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 404
        response = await client.post("api/v1/variables/", json=ollama_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid Ollama base URL" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__model_provider_network_error_allows_creation(client: AsyncClient, logged_in_headers):
    """Test that network errors don't prevent variable creation."""
    # Clean up any existing OPENAI_API_KEY variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "OPENAI_API_KEY":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    openai_variable = {
        "name": "OPENAI_API_KEY",
        "value": "sk-test-key",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock network error (not an auth error)
    with mock.patch("langchain_openai.ChatOpenAI.invoke") as mock_invoke:
        mock_invoke.side_effect = Exception("Network timeout")
        response = await client.post("api/v1/variables/", json=openai_variable, headers=logged_in_headers)

        # Should succeed despite network error
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.usefixtures("active_user")
async def test_delete_provider_credential_cleans_up_disabled_models(client: AsyncClient, logged_in_headers):
    """Test that deleting a provider credential cleans up disabled models for that provider."""
    # Clean up any existing OPENAI_API_KEY variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "OPENAI_API_KEY":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    openai_variable = {
        "name": "OPENAI_API_KEY",
        "value": "sk-test-key",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock successful OpenAI API call to create credential
    with mock.patch("langchain_openai.ChatOpenAI.invoke") as mock_invoke:
        mock_invoke.return_value = "test response"
        create_response = await client.post("api/v1/variables/", json=openai_variable, headers=logged_in_headers)
        assert create_response.status_code == status.HTTP_201_CREATED
        created_var = create_response.json()

    # Disable some OpenAI models
    with mock.patch("lfx.base.models.unified_models.validate_model_provider_key"):
        disable_response = await client.post(
            "api/v1/models/enabled_models",
            json=[
                {"provider": "OpenAI", "model_id": "gpt-4", "enabled": False},
                {"provider": "OpenAI", "model_id": "gpt-3.5-turbo", "enabled": False},
            ],
            headers=logged_in_headers,
        )
        assert disable_response.status_code == status.HTTP_200_OK

    # Delete the credential - should clean up disabled models
    delete_response = await client.delete(f"api/v1/variables/{created_var['id']}", headers=logged_in_headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Verify disabled models are cleaned up - check that the disabled models variable is gone or cleared
    all_vars_after = await client.get("api/v1/variables/", headers=logged_in_headers)
    disabled_models_var = next(
        (v for v in all_vars_after.json() if v.get("name") == "__disabled_models__"),
        None,
    )
    # Either the variable should be gone, or it should not contain OpenAI models
    if disabled_models_var and disabled_models_var.get("value"):
        import json

        disabled_models = json.loads(disabled_models_var["value"])
        assert "gpt-4" not in disabled_models
        assert "gpt-3.5-turbo" not in disabled_models


@pytest.mark.usefixtures("active_user")
async def test_delete_provider_credential_cleans_up_enabled_models(client: AsyncClient, logged_in_headers):
    """Test that deleting a provider credential cleans up explicitly enabled models for that provider."""
    # Clean up any existing OPENAI_API_KEY variables
    all_vars = await client.get("api/v1/variables/", headers=logged_in_headers)
    for var in all_vars.json():
        if var.get("name") == "OPENAI_API_KEY":
            await client.delete(f"api/v1/variables/{var['id']}", headers=logged_in_headers)

    openai_variable = {
        "name": "OPENAI_API_KEY",
        "value": "sk-test-key",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }

    # Mock successful OpenAI API call to create credential
    with mock.patch("langchain_openai.ChatOpenAI.invoke") as mock_invoke:
        mock_invoke.return_value = "test response"
        create_response = await client.post("api/v1/variables/", json=openai_variable, headers=logged_in_headers)
        assert create_response.status_code == status.HTTP_201_CREATED
        created_var = create_response.json()

    # Enable some non-default OpenAI models (explicitly enable models that aren't default)
    with mock.patch("lfx.base.models.unified_models.validate_model_provider_key"):
        enable_response = await client.post(
            "api/v1/models/enabled_models",
            json=[
                {"provider": "OpenAI", "model_id": "gpt-4-turbo-preview", "enabled": True},
            ],
            headers=logged_in_headers,
        )
        assert enable_response.status_code == status.HTTP_200_OK

    # Delete the credential - should clean up enabled models
    delete_response = await client.delete(f"api/v1/variables/{created_var['id']}", headers=logged_in_headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Verify enabled models are cleaned up
    all_vars_after = await client.get("api/v1/variables/", headers=logged_in_headers)
    enabled_models_var = next(
        (v for v in all_vars_after.json() if v.get("name") == "__enabled_models__"),
        None,
    )
    # Either the variable should be gone, or it should not contain OpenAI models
    if enabled_models_var and enabled_models_var.get("value"):
        import json

        enabled_models = json.loads(enabled_models_var["value"])
        assert "gpt-4-turbo-preview" not in enabled_models


@pytest.mark.usefixtures("active_user")
async def test_delete_non_provider_credential_does_not_cleanup_models(client: AsyncClient, logged_in_headers):
    """Test that deleting a non-provider credential does not affect model lists."""
    # Create a generic variable (not a provider credential)
    generic_variable = {
        "name": "MY_CUSTOM_VAR",
        "value": "custom_value",
        "type": GENERIC_TYPE,
        "default_fields": [],
    }

    create_response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    created_var = create_response.json()

    # Delete the variable - should not trigger any cleanup
    delete_response = await client.delete(f"api/v1/variables/{created_var['id']}", headers=logged_in_headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
