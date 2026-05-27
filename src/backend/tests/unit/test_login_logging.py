"""Tests for login logging functionality."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_failed_login_nonexistent_user_logs(client: AsyncClient):
    """Test that failed login for non-existent user is logged."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": "nonexistent_user", "password": "wrong_password"},  # pragma: allowlist secret
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"

        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "Login failed: user not found"
        assert call_args[1]["extra"]["event"] == "login_failed"
        assert call_args[1]["extra"]["reason"] == "user_not_found"
        assert call_args[1]["extra"]["username"] == "nonexistent_user"
        assert "ip" in call_args[1]["extra"]


@pytest.mark.asyncio
async def test_failed_login_wrong_password_logs(client: AsyncClient, active_user):
    """Test that failed login with wrong password is logged."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": active_user.username, "password": "wrong_password"},  # pragma: allowlist secret
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"

        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "Login failed: incorrect password"
        assert call_args[1]["extra"]["event"] == "login_failed"
        assert call_args[1]["extra"]["reason"] == "incorrect_password"
        assert "auth_id" in call_args[1]["extra"]
        assert "ip" in call_args[1]["extra"]


@pytest.mark.asyncio
async def test_successful_login_logs(client: AsyncClient, active_user):
    """Test that successful login is logged."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

        # Verify info log was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "Login successful"
        assert call_args[1]["extra"]["event"] == "login_success"
        assert "auth_id" in call_args[1]["extra"]
        assert "ip" in call_args[1]["extra"]


@pytest.mark.asyncio
async def test_login_logs_contain_ip_address(client: AsyncClient):
    """Test that login logs contain IP address."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": "nonexistent", "password": "wrong"},  # pragma: allowlist secret
        )

        assert response.status_code == 401

        # Verify IP was captured
        call_args = mock_logger.warning.call_args
        assert "ip" in call_args[1]["extra"]
        # IP should be a string (testclient uses "testclient" as default)
        assert isinstance(call_args[1]["extra"]["ip"], str)


@pytest.mark.asyncio
async def test_login_logs_no_pii(client: AsyncClient):
    """Test that login logs do not contain PII (email, full name)."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": "test_user", "password": "wrong"},  # pragma: allowlist secret
        )

        assert response.status_code == 401

        # Verify no PII in logs
        call_args = mock_logger.warning.call_args
        extra = call_args[1]["extra"]

        # Should NOT contain these PII fields
        assert "email" not in extra
        assert "first_name" not in extra
        assert "last_name" not in extra
        assert "full_name" not in extra
        assert "phone" not in extra
        assert "address" not in extra

        # Should contain safe identifiers
        assert "username" in extra or "auth_id" in extra
        assert "event" in extra
        assert "reason" in extra
