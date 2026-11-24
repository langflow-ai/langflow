"""Tests for login logging functionality."""

import hashlib
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select


@pytest.mark.asyncio
async def test_failed_login_nonexistent_user_logs(client: AsyncClient):
    """Test that failed login for non-existent user is logged with hashed username."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": "nonexistent_user", "password": "wrong_password"},  # pragma: allowlist secret
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"

        # Verify warning was logged with structlog kwargs
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "Login failed: user not found"
        # Structlog uses kwargs, not extra dict
        assert call_args[1]["auth_event"] == "login_failed"
        assert call_args[1]["reason"] == "user_not_found"
        # Username should be hashed, not plain text
        assert "username_hash" in call_args[1]
        assert call_args[1]["username_hash"] == hashlib.sha256(b"nonexistent_user").hexdigest()[:16]
        assert "client_ip" in call_args[1]
        # Should NOT contain plain username
        assert "username" not in call_args[1]


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

        # Verify warning was logged with structlog kwargs
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "Login failed: incorrect password"
        assert call_args[1]["auth_event"] == "login_failed"
        assert call_args[1]["reason"] == "incorrect_password"
        assert "auth_id" in call_args[1]
        assert "client_ip" in call_args[1]


@pytest.mark.asyncio
async def test_failed_login_inactive_user_logs(client: AsyncClient):
    """Test that failed login for inactive user is logged."""
    # Create an inactive user with last_login_at set (so it returns 401, not 400)
    async with session_scope() as session:
        from datetime import datetime, timezone

        from langflow.services.deps import get_auth_service

        inactive_user = User(
            username="inactiveuser",
            password=get_auth_service().get_password_hash("testpassword"),  # pragma: allowlist secret
            is_active=False,
            is_superuser=False,
            last_login_at=datetime.now(timezone.utc),  # Set to avoid "Waiting for approval"
        )
        session.add(inactive_user)
        await session.commit()
        await session.refresh(inactive_user)
        user_id = str(inactive_user.id)

    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": "inactiveuser", "password": "testpassword"},  # pragma: allowlist secret
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Inactive user"

        # Verify warning was logged with structlog kwargs
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "Login failed: inactive user"
        assert call_args[1]["auth_event"] == "login_failed"
        assert call_args[1]["reason"] == "user_inactive"
        assert call_args[1]["auth_id"] == user_id
        assert "client_ip" in call_args[1]

    # Cleanup
    async with session_scope() as session:
        stmt = select(User).where(User.username == "inactiveuser")
        user = (await session.exec(stmt)).first()
        if user:
            await session.delete(user)
            await session.commit()


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

        # Verify info log was called with structlog kwargs
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "Login successful"
        assert call_args[1]["auth_event"] == "login_success"
        assert "auth_id" in call_args[1]
        assert "client_ip" in call_args[1]


@pytest.mark.asyncio
async def test_login_logs_contain_ip_address(client: AsyncClient):
    """Test that login logs contain IP address."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": "nonexistent", "password": "wrong"},  # pragma: allowlist secret
        )

        assert response.status_code == 401

        # Verify IP was captured in structlog kwargs
        call_args = mock_logger.warning.call_args
        assert "client_ip" in call_args[1]
        # IP should be a string (testclient uses "testclient" as default)
        assert isinstance(call_args[1]["client_ip"], str)


@pytest.mark.asyncio
async def test_login_logs_no_pii(client: AsyncClient):
    """Test that login logs do not contain PII (email, full name, plain username)."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": "test_user", "password": "wrong"},  # pragma: allowlist secret
        )

        assert response.status_code == 401

        # Verify no PII in logs (structlog kwargs)
        call_args = mock_logger.warning.call_args
        kwargs = call_args[1]

        # Should NOT contain these PII fields
        assert "email" not in kwargs
        assert "first_name" not in kwargs
        assert "last_name" not in kwargs
        assert "full_name" not in kwargs
        assert "phone" not in kwargs
        assert "address" not in kwargs
        assert "username" not in kwargs  # Plain username is PII

        # Should contain safe identifiers
        assert "username_hash" in kwargs or "auth_id" in kwargs
        assert "auth_event" in kwargs
        assert "reason" in kwargs


@pytest.mark.asyncio
async def test_login_logs_real_output_format(client: AsyncClient):
    """Test that login logs use structlog kwargs format (not nested extra dict)."""
    with patch("langflow.services.auth.service.logger") as mock_logger:
        response = await client.post(
            "/api/v1/login",
            data={"username": "nonexistent_user", "password": "wrong"},  # pragma: allowlist secret
        )

        assert response.status_code == 401

        # Verify logger was called with kwargs (flat format), not extra dict
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        # Verify it's using kwargs format (call_args[1] contains kwargs)
        assert "auth_event" in call_args[1]
        assert "reason" in call_args[1]
        assert "username_hash" in call_args[1]
        assert "client_ip" in call_args[1]

        # Verify it's NOT using the old extra dict format
        assert "extra" not in call_args[1]

        # Verify the actual values
        assert call_args[1]["auth_event"] == "login_failed"
        assert call_args[1]["reason"] == "user_not_found"
