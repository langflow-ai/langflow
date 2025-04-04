"""Keycloak Service Test Suite.

This module provides comprehensive test coverage for the KeycloakService class,
which handles authentication and authorization via Keycloak/OpenID Connect.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from jose import jwt
from keycloak import KeycloakOpenID
from langflow.services.keycloak.service import KeycloakService
from pytest_mock import MockerFixture

# ----- Test Fixtures ----- #


@pytest.fixture(name="fixture_auth_settings")
def auth_settings() -> SimpleNamespace:
    """Create a dummy AuthSettings instance with test configuration values.

    Returns:
        SimpleNamespace: An object mimicking AuthSettings with test values.
    """
    # Create a secret value with a getter to simulate pydantic's SecretStr
    secret = SimpleNamespace(get_secret_value=lambda: "test_client_secret")

    # Return a test configuration
    return SimpleNamespace(
        KEYCLOAK_ENABLED=True,
        KEYCLOAK_SERVER_URL="https://example.com/auth",
        KEYCLOAK_REALM="test_realm",
        KEYCLOAK_CLIENT_ID="test_client_id",
        KEYCLOAK_CLIENT_SECRET=secret,
        KEYCLOAK_ADMIN_ROLE="admin",
        KEYCLOAK_REDIRECT_URI="http://localhost:3000/api/v1/keycloak/callback",
        KEYCLOAK_FORCE_SSO=False,
    )


@pytest.fixture(name="fixture_settings_service")
def settings_service(fixture_auth_settings: SimpleNamespace) -> SimpleNamespace:
    """Create a dummy SettingsService instance with the test auth settings.

    Args:
        fixture_auth_settings: The test auth settings fixture.

    Returns:
        SimpleNamespace: An object mimicking SettingsService with the auth_settings property.
    """
    return SimpleNamespace(auth_settings=fixture_auth_settings)


@pytest.fixture(name="fixture_keycloak_service")
def keycloak_service(fixture_settings_service: SimpleNamespace) -> KeycloakService:
    """Create a KeycloakService instance for testing.

    Args:
        fixture_settings_service: The test settings service fixture.

    Returns:
        KeycloakService: A KeycloakService instance initialized with test settings.
    """
    return KeycloakService(fixture_settings_service)


@pytest.fixture(name="fixture_keycloak_openid_client")
def keycloak_openid_client(mocker: MockerFixture) -> Mock:
    """Create a mock KeycloakOpenID client for testing.

    This fixture configures the mock client with standard return values for token operations.

    Args:
        mocker: The pytest-mock fixture for creating mocks.

    Returns:
        Mock: A mock KeycloakOpenID client with pre-configured return values.
    """
    client = mocker.Mock(spec=KeycloakOpenID)

    # Configure standard token response
    token_response = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_type": "bearer",
    }

    # Set up return values for token methods
    client.token.return_value = token_response
    client.refresh_token.return_value = token_response

    return client


# ----- Property Tests ----- #


def test_keycloak_service_properties(
    fixture_keycloak_service: KeycloakService, fixture_auth_settings: SimpleNamespace
) -> None:
    """Verify that KeycloakService properties correctly reflect the configured settings.

    This test ensures that the service properly exposes all configuration values
    from the settings service.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_auth_settings: The test auth settings fixture.
    """
    # Check each property against the expected value from settings
    assert fixture_keycloak_service.is_enabled == fixture_auth_settings.KEYCLOAK_ENABLED
    assert fixture_keycloak_service.server_url == fixture_auth_settings.KEYCLOAK_SERVER_URL
    assert fixture_keycloak_service.realm == fixture_auth_settings.KEYCLOAK_REALM
    assert fixture_keycloak_service.client_id == fixture_auth_settings.KEYCLOAK_CLIENT_ID
    assert fixture_keycloak_service.client_secret == fixture_auth_settings.KEYCLOAK_CLIENT_SECRET.get_secret_value()
    assert fixture_keycloak_service.admin_role == fixture_auth_settings.KEYCLOAK_ADMIN_ROLE
    assert fixture_keycloak_service.redirect_uri == fixture_auth_settings.KEYCLOAK_REDIRECT_URI
    assert fixture_keycloak_service.force_sso == fixture_auth_settings.KEYCLOAK_FORCE_SSO


# ----- Initialization Tests ----- #


def test_initialize_success(fixture_keycloak_service: KeycloakService, fixture_keycloak_openid_client: Mock) -> None:
    """Test successful initialization and client access.

    This test verifies that the client property returns the initialized client
    when everything is set up correctly.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_keycloak_openid_client: The mock KeycloakOpenID client.
    """
    # Set up a pre-initialized service
    fixture_keycloak_service._keycloak_openid = fixture_keycloak_openid_client
    fixture_keycloak_service._initialized = True

    # Get the client through the property
    client = fixture_keycloak_service.client

    # Verify the client is returned correctly
    assert client is not None
    assert client is fixture_keycloak_openid_client


def test_initialize_failure_without_keycloak_enabled(
    fixture_keycloak_service: KeycloakService, fixture_settings_service: SimpleNamespace
) -> None:
    """Test initialization behavior when Keycloak is disabled.

    When Keycloak is disabled, initialization should complete without error
    but not create a client.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_settings_service: The test settings service fixture.
    """
    # Disable Keycloak in the settings
    fixture_settings_service.auth_settings.KEYCLOAK_ENABLED = False

    # Initialize should complete without error
    fixture_keycloak_service.initialize()

    # Client should not be created
    assert fixture_keycloak_service._keycloak_openid is None


def test_initialize_failure_without_keycloak_server_url(
    fixture_keycloak_service: KeycloakService, fixture_settings_service: SimpleNamespace
) -> None:
    """Test initialization failure when server URL is missing.

    When the server URL is missing or empty, initialization should raise
    a ValueError with an appropriate message.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_settings_service: The test settings service fixture.
    """
    # Remove the server URL
    fixture_settings_service.auth_settings.KEYCLOAK_SERVER_URL = ""

    # Initialization should raise ValueError
    with pytest.raises(ValueError, match="Keycloak server URL is not configured"):
        fixture_keycloak_service.initialize()


def test_initialize_failure_without_keycloak_realm(
    fixture_keycloak_service: KeycloakService, fixture_settings_service: SimpleNamespace
) -> None:
    """Test initialization failure when realm is missing.

    When the realm is missing or empty, initialization should raise
    a ValueError with an appropriate message.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_settings_service: The test settings service fixture.
    """
    # Remove the realm
    fixture_settings_service.auth_settings.KEYCLOAK_REALM = ""

    # Initialization should raise ValueError
    with pytest.raises(ValueError, match="Keycloak realm is not configured"):
        fixture_keycloak_service.initialize()


def test_initialize_failure_without_keycloak_client_id(
    fixture_keycloak_service: KeycloakService, fixture_settings_service: SimpleNamespace
) -> None:
    """Test initialization failure when client ID is missing.

    When the client ID is missing or empty, initialization should raise
    a ValueError with an appropriate message.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_settings_service: The test settings service fixture.
    """
    # Remove the client ID
    fixture_settings_service.auth_settings.KEYCLOAK_CLIENT_ID = ""

    # Initialization should raise ValueError
    with pytest.raises(ValueError, match="Keycloak client ID is not configured"):
        fixture_keycloak_service.initialize()


def test_initialize_failure_without_keycloak_client_secret(
    fixture_keycloak_service: KeycloakService, fixture_settings_service: SimpleNamespace
) -> None:
    """Test initialization failure when client secret is missing.

    When the client secret is missing, initialization should raise
    a ValueError with an appropriate message.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_settings_service: The test settings service fixture.
    """
    # Remove the client secret
    fixture_settings_service.auth_settings.KEYCLOAK_CLIENT_SECRET = None

    # Initialization should raise ValueError
    with pytest.raises(ValueError, match="Keycloak client secret is not configured"):
        fixture_keycloak_service.initialize()


# ----- Token Operation Tests ----- #


@pytest.mark.asyncio
async def test_get_token_success(
    fixture_keycloak_service: KeycloakService, fixture_keycloak_openid_client: Mock
) -> None:
    """Test successful token retrieval from an authorization code.

    This test verifies that the get_token method correctly calls the
    underlying client and returns the token response.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_keycloak_openid_client: The mock KeycloakOpenID client.
    """
    # Set up a pre-initialized service with the mock client
    fixture_keycloak_service._keycloak_openid = fixture_keycloak_openid_client

    # Call the get_token method
    result = await fixture_keycloak_service.get_token("test_auth_code", "http://test-redirect")

    # Verify the client method was called with correct parameters
    fixture_keycloak_openid_client.token.assert_called_once_with(
        grant_type="authorization_code", code="test_auth_code", redirect_uri="http://test-redirect"
    )

    # Verify the result matches the expected token response
    assert result == fixture_keycloak_openid_client.token.return_value


@pytest.mark.asyncio
async def test_refresh_token_success(
    fixture_keycloak_service: KeycloakService, fixture_keycloak_openid_client: Mock
) -> None:
    """Test successful token refresh operation.

    This test verifies that the refresh_token method correctly calls the
    underlying client and returns the refreshed token response.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_keycloak_openid_client: The mock KeycloakOpenID client.
    """
    # Set up a pre-initialized service with the mock client
    fixture_keycloak_service._keycloak_openid = fixture_keycloak_openid_client

    # Call the refresh_token method
    result = await fixture_keycloak_service.refresh_token("test_refresh_token")

    # Verify the client method was called with correct parameters
    fixture_keycloak_openid_client.refresh_token.assert_called_once_with("test_refresh_token")

    # Verify the result matches the expected token response
    assert result == fixture_keycloak_openid_client.refresh_token.return_value


@pytest.mark.asyncio
async def test_decode_token(fixture_keycloak_service: KeycloakService, mocker: MockerFixture) -> None:
    """Test JWT token decoding functionality.

    This test verifies that the decode_token method correctly decodes a JWT token
    without verification and returns the token claims.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        mocker: The pytest-mock fixture for creating mocks.
    """
    # Set up a mock client with a client_id
    mock_client = mocker.Mock()
    fixture_keycloak_service._keycloak_openid = mock_client

    # Mock the jwt.decode function
    mock_decode = mocker.patch("jose.jwt.decode")
    mock_decode.return_value = {"sub": "user123", "resource_access": {}}

    # Call the decode_token method
    result = await fixture_keycloak_service.decode_token("test_token")

    # Verify the jwt.decode function was called with correct parameters
    mock_decode.assert_called_once_with(
        "test_token", "", options={"verify_signature": False}, audience=fixture_keycloak_service.client_id
    )

    # Verify the result matches the expected decoded token
    assert result == mock_decode.return_value


def test_extract_roles(fixture_keycloak_service: KeycloakService) -> None:
    """Test role extraction from token claims.

    This test verifies that the extract_roles method correctly extracts and
    deduplicates roles from a token's resource_access section.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
    """
    # Set up a token with roles (including a duplicate)
    token_info = {
        "resource_access": {
            "test_client_id": {
                "roles": ["user", "admin", "editor", "admin"]  # Duplicate to test de-duplication
            }
        }
    }

    # Extract roles from the token
    roles = fixture_keycloak_service.extract_roles(token_info)

    # Verify roles are extracted and deduplicated
    assert len(roles) == 3
    assert set(roles) == {"user", "admin", "editor"}


# ----- Error Handling Tests ----- #


@pytest.mark.asyncio
async def test_token_operations_with_disabled_keycloak(
    fixture_keycloak_service: KeycloakService, fixture_settings_service: SimpleNamespace
) -> None:
    """Test token operations when Keycloak is disabled.

    This test verifies that token operations safely return empty results
    when Keycloak is disabled, rather than raising exceptions.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_settings_service: The test settings service fixture.
    """
    # Disable Keycloak in the settings
    fixture_settings_service.auth_settings.KEYCLOAK_ENABLED = False

    # Test get_token - should return empty dict without error
    result = await fixture_keycloak_service.get_token("code", "redirect")
    assert result == {}

    # Test refresh_token - should return empty dict without error
    result = await fixture_keycloak_service.refresh_token("refresh")
    assert result == {}

    # Test decode_token - should return empty dict without error
    result = await fixture_keycloak_service.decode_token("token")
    assert result == {}


@pytest.mark.asyncio
async def test_get_token_failure(
    fixture_keycloak_service: KeycloakService, fixture_keycloak_openid_client: Mock
) -> None:
    """Test exception handling in token retrieval.

    This test verifies that exceptions from the underlying client are
    properly propagated during token retrieval.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_keycloak_openid_client: The mock KeycloakOpenID client.
    """
    # Set up a pre-initialized service with the mock client
    fixture_keycloak_service._keycloak_openid = fixture_keycloak_openid_client

    # Configure the client to raise an exception
    fixture_keycloak_openid_client.token.side_effect = Exception("Token error")

    # Calling get_token should raise the same exception
    with pytest.raises(Exception, match="Token error"):
        await fixture_keycloak_service.get_token("code", "redirect")


# ----- Logout Tests ----- #


@pytest.mark.asyncio
async def test_logout_success(fixture_keycloak_service: KeycloakService, fixture_keycloak_openid_client: Mock) -> None:
    """Test successful logout operation.

    This test verifies that the logout method correctly calls the
    underlying client to invalidate the session.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_keycloak_openid_client: The mock KeycloakOpenID client.
    """
    # Set up a pre-initialized service with the mock client
    fixture_keycloak_service._keycloak_openid = fixture_keycloak_openid_client

    # Call the logout method
    await fixture_keycloak_service.logout("test_refresh_token")

    # Verify the client's logout method was called with the correct token
    fixture_keycloak_openid_client.logout.assert_called_once_with("test_refresh_token")


@pytest.mark.asyncio
async def test_logout_with_empty_token(
    fixture_keycloak_service: KeycloakService, fixture_keycloak_openid_client: Mock
) -> None:
    """Test logout behavior with an empty refresh token.

    This test verifies that the logout method handles empty tokens gracefully
    by not attempting to call the client.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        fixture_keycloak_openid_client: The mock KeycloakOpenID client.
    """
    # Set up a pre-initialized service with the mock client
    fixture_keycloak_service._keycloak_openid = fixture_keycloak_openid_client

    # Call the logout method with an empty token
    await fixture_keycloak_service.logout("")

    # Verify the client's logout method was not called
    fixture_keycloak_openid_client.logout.assert_not_called()


# ----- Edge Case Tests ----- #


@pytest.mark.asyncio
async def test_decode_invalid_token(fixture_keycloak_service: KeycloakService, mocker: MockerFixture) -> None:
    """Test handling of invalid JWT tokens during decoding.

    This test verifies that the decode_token method properly handles and
    propagates exceptions when an invalid token is provided.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        mocker: The pytest-mock fixture for creating mocks.
    """
    # Set up a mock client
    fixture_keycloak_service._keycloak_openid = mocker.Mock()

    # Configure jwt.decode to raise a JWTError
    mocker.patch("jose.jwt.decode", side_effect=jwt.JWTError("Invalid token"))

    # Decoding an invalid token should raise an exception
    with pytest.raises(Exception):  # noqa: B017, PT011
        await fixture_keycloak_service.decode_token("invalid_token")


@pytest.mark.asyncio
async def test_client_integration(fixture_keycloak_service: KeycloakService, mocker: MockerFixture) -> None:
    """Test KeycloakOpenID client initialization with correct parameters.

    This test verifies that the initialize method creates a KeycloakOpenID client
    with the correct parameters from the service configuration.

    Args:
        fixture_keycloak_service: The test KeycloakService instance.
        mocker: The pytest-mock fixture for creating mocks.
    """
    # Mock the KeycloakOpenID constructor
    mock_keycloak_class = mocker.patch("langflow.services.keycloak.service.KeycloakOpenID")

    # Ensure the service starts without a client
    mocker.patch.object(fixture_keycloak_service, "_keycloak_openid", None)

    # Run initialization
    fixture_keycloak_service.initialize()

    # Verify the KeycloakOpenID constructor was called with correct parameters
    mock_keycloak_class.assert_called_once_with(
        server_url=fixture_keycloak_service.server_url,
        client_id=fixture_keycloak_service.client_id,
        realm_name=fixture_keycloak_service.realm,
        client_secret_key=fixture_keycloak_service.client_secret,
        verify=True,
    )
