"""Keycloak API Router Unit Tests.

This module implements isolated unit tests for the Keycloak API router endpoints,
focusing on testing the router functionality without dependencies on the full
FastAPI application or database setup.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from langflow.api.v1.keycloak import KeycloakConfig, KeycloakService, get_cached_keycloak_config, router
from langflow.services.deps import get_keycloak_service, get_session


@pytest.fixture(name="fixture_mock_keycloak_service")
def mock_keycloak_service() -> MagicMock:
    """Create a mock Keycloak service with enabled configuration.

    Returns:
        MagicMock: Mock service with all required attributes for testing.
    """
    service = MagicMock(spec=KeycloakService)
    service.is_enabled = True
    service.server_url = "https://keycloak.example.com/auth"
    service.realm = "test-realm"
    service.client_id = "test-client"
    service.redirect_uri = "https://app.example.com/callback"
    service.force_sso = False
    return service


@pytest.fixture(name="fixture_mock_disabled_keycloak_service")
def mock_disabled_keycloak_service() -> MagicMock:
    """Create a mock disabled Keycloak service.

    Returns:
        MagicMock: Mock service with is_enabled set to False.
    """
    service = MagicMock(spec=KeycloakService)
    service.is_enabled = False
    return service


@pytest.fixture(name="fixture_app")
def app() -> FastAPI:
    """Create a test FastAPI app with the Keycloak router.

    Returns:
        FastAPI: Application instance with Keycloak router attached.
    """
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)
    return fastapi_app


@pytest.fixture(name="fixture_test_client")
def test_client(fixture_app: FastAPI) -> TestClient:
    """Create a test client for the FastAPI app.

    Args:
        fixture_app: FastAPI application instance with router attached.

    Returns:
        TestClient: FastAPI test client for making requests.
    """
    return TestClient(fixture_app)


def test_get_config_with_keycloak_disabled(
    fixture_test_client: TestClient, fixture_mock_disabled_keycloak_service: MagicMock
) -> None:
    """Test the get_config endpoint with Keycloak disabled.

    Verifies that when Keycloak is disabled, the endpoint returns
    a simple dictionary with enabled=False.

    Args:
        fixture_test_client: FastAPI test client
        fixture_mock_disabled_keycloak_service: Mock disabled Keycloak service
    """
    # Override the dependency to use the disabled mock service
    fixture_test_client.app.dependency_overrides = {
        get_keycloak_service: lambda: fixture_mock_disabled_keycloak_service
    }

    # Make the request
    response = fixture_test_client.get("/keycloak/config")
    result = response.json()

    # Verify response
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "enabled" in result, "The result must have an 'enabled' key"
    assert result["enabled"] is False, "The 'enabled' key must be False"


def test_get_config_with_keycloak_enabled(
    fixture_test_client: TestClient, fixture_mock_keycloak_service: MagicMock
) -> None:
    """Test the get_config endpoint with Keycloak enabled.

    Verifies that when Keycloak is enabled, the endpoint returns
    a complete configuration object with all required fields.

    Args:
        fixture_test_client: FastAPI test client
        fixture_mock_keycloak_service: Mock enabled Keycloak service
    """
    # Override the dependency to use the enabled mock service
    fixture_test_client.app.dependency_overrides = {get_keycloak_service: lambda: fixture_mock_keycloak_service}

    # Make the request
    response = fixture_test_client.get("/keycloak/config")
    result = response.json()

    # Verify response
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "enabled" in result, "The result must have an 'enabled' key"
    assert result["enabled"] is True, "The 'enabled' key must be True"

    # Verify all required config fields are present
    required_fields = ["serverUrl", "realm", "clientId", "redirectUri", "forceSSO"]
    for field in required_fields:
        assert field in result, f"The result must have a '{field}' key"


def test_keycloak_callback_with_keycloak_disabled(
    fixture_test_client: TestClient, fixture_mock_disabled_keycloak_service: MagicMock
) -> None:
    """Test the keycloak_callback endpoint with Keycloak disabled.

    Verifies that when Keycloak is disabled, the callback endpoint
    returns a 400 Bad Request error with appropriate message.

    Args:
        fixture_test_client: FastAPI test client
        fixture_mock_disabled_keycloak_service: Mock disabled Keycloak service
    """
    # Override the dependency to use the disabled mock service
    fixture_test_client.app.dependency_overrides = {
        get_keycloak_service: lambda: fixture_mock_disabled_keycloak_service
    }

    # Make the request with required query parameters
    response = fixture_test_client.get("/keycloak/callback?code=testcode&nonce=testnonce")
    result = response.json()

    # Verify response
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "detail" in result, "The result must have a 'detail' key"
    assert "Keycloak is disabled" in result["detail"], "The 'detail' key must contain 'Keycloak is disabled'"


@patch("langflow.api.v1.keycloak.process_keycloak_login")
def test_keycloak_callback_with_keycloak_enabled(
    mock_process: MagicMock, fixture_test_client: TestClient, fixture_mock_keycloak_service: MagicMock
) -> None:
    """Test the keycloak_callback endpoint with Keycloak enabled.

    Verifies that when Keycloak is enabled, the callback endpoint
    processes the login correctly and returns access tokens.

    Args:
        mock_process: Mocked process_keycloak_login function
        fixture_test_client: FastAPI test client
        fixture_mock_keycloak_service: Mock enabled Keycloak service
    """
    # Configure the mock to return authentication tokens
    mock_process.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_type": "Bearer",
    }

    # Mock all required dependencies
    mock_db = AsyncMock()
    fixture_test_client.app.dependency_overrides = {
        get_keycloak_service: lambda: fixture_mock_keycloak_service,
        get_session: lambda: mock_db,
    }

    # Make the request with required query parameters
    response = fixture_test_client.get("/keycloak/callback?code=testcode&nonce=testnonce")
    result = response.json()

    # Verify response
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"

    # Verify all token fields are present
    assert "access_token" in result, "The result must have an 'access_token' key"
    assert "refresh_token" in result, "The result must have a 'refresh_token' key"
    assert "token_type" in result, "The result must have a 'token_type' key"


def test_get_cached_keycloak_config(fixture_mock_keycloak_service: MagicMock) -> None:
    """Test the get_cached_keycloak_config function.

    Verifies that the function returns a properly configured KeycloakConfig
    object and that results are cached appropriately.

    Args:
        fixture_mock_keycloak_service: Mock enabled Keycloak service
    """
    # Clear the cache to ensure a clean test
    get_cached_keycloak_config.cache_clear()

    # Call the function with our mock service
    result1 = get_cached_keycloak_config(fixture_mock_keycloak_service)

    # Verify result type and attributes
    assert isinstance(result1, KeycloakConfig), "The result must be a KeycloakConfig instance"
    assert result1.enabled is True, "The 'enabled' attribute must be True"

    # Verify configuration values match the mock service
    assert result1.serverUrl == fixture_mock_keycloak_service.server_url
    assert result1.realm == fixture_mock_keycloak_service.realm
    assert result1.clientId == fixture_mock_keycloak_service.client_id
    assert result1.redirectUri == fixture_mock_keycloak_service.redirect_uri
    assert result1.forceSSO == fixture_mock_keycloak_service.force_sso

    # Verify caching behavior
    cache = get_cached_keycloak_config.cache
    assert len(cache) == 1, "The cache should have a single entry after one function call"

    # Now modify the mock to verify the second call uses the cache
    fixture_mock_keycloak_service.is_enabled = False

    # Second call should use cached value, not the modified mock
    result2 = get_cached_keycloak_config(fixture_mock_keycloak_service)

    # Verify we got the same object back (from cache)
    assert result2 is result1, "The second call should return the exact same object from cache"
    assert result2.enabled is True, "The cached result should maintain the original 'enabled' value"

    # Cache size should remain the same
    assert len(cache) == 1, "The cache size should not change after second call"
