import aiofiles
import anyio
import pytest


@pytest.fixture(autouse=True)
def _check_openai_api_key_in_environment_variables():
    pass


async def test_webhook_endpoint_requires_api_key_when_auto_login_false(client, added_webhook_test):
    """Test that webhook endpoint requires API key when WEBHOOK_AUTH_ENABLE=true."""
    # Mock the settings service to enable webhook authentication
    from unittest.mock import patch

    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": True})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_file.txt"}  # noqa: S108

        # Should fail without API key when webhook auth is enabled
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 403
        assert "API key required when webhook authentication is enabled" in response.json()["detail"]


async def test_webhook_endpoint_with_valid_api_key(client, added_webhook_test, created_api_key):
    """Test that webhook works when valid API key is provided."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    # Create a temporary file
    async with aiofiles.tempfile.TemporaryDirectory() as tmp:
        file_path = anyio.Path(tmp) / "test_file.txt"
        payload = {"path": str(file_path)}

        # Should work with valid API key
        response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
        assert response.status_code == 202
        assert await file_path.exists(), f"File {file_path} does not exist"

    file_does_not_exist = not await file_path.exists()
    assert file_does_not_exist, f"File {file_path} still exists"


async def test_webhook_endpoint_unauthorized_user_flow(client, added_webhook_test):
    """Test that webhook fails when user doesn't own the flow."""
    # Mock the settings service to enable webhook authentication
    from unittest.mock import patch

    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": True})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        # This test would need a different user's API key to test authorization
        # For now, we'll use an invalid API key to simulate this
        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_file.txt"}  # noqa: S108

        # Should fail with invalid API key
        response = await client.post(endpoint, headers={"x-api-key": "invalid_key"}, json=payload)
        assert response.status_code == 403
        assert "Invalid API key" in response.json()["detail"]


async def test_webhook_flow_on_run_endpoint(client, added_webhook_test, created_api_key):
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/run/{endpoint_name}?stream=false"
    # Just test that "Random Payload" returns 202
    # returns 202
    payload = {
        "output_type": "any",
    }
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 200, response.json()


async def test_webhook_with_auto_login_enabled(client, added_webhook_test):
    """Test webhook behavior when WEBHOOK_AUTH_ENABLE=false - should work without API key."""
    # Mock the settings service to disable webhook authentication (default behavior)
    from unittest.mock import patch

    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": False})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_auto_login.txt"}  # noqa: S108

        # Should work without API key when webhook auth is disabled
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 202


async def test_webhook_with_random_payload_requires_auth(client, added_webhook_test, created_api_key):
    """Test that webhook with random payload still requires authentication."""
    # Mock the settings service to enable webhook authentication
    from unittest.mock import patch

    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": True})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        # Should fail without API key
        response = await client.post(endpoint, json="Random Payload")
        assert response.status_code == 403

        # Should work with API key (even with random payload)
        response = await client.post(
            endpoint,
            headers={"x-api-key": created_api_key.api_key},
            json="Random Payload",
        )
        assert response.status_code == 202
