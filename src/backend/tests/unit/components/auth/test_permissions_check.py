"""Test cases for Permissions Check component."""

from unittest.mock import Mock, patch

import pytest
from langflow.components.auth.permissions_check import PermissionsCheckComponent


@pytest.fixture
def mock_permit_client():
    """Create a mock Permit client."""
    return Mock()


def test_initialization():
    """Test Permissions Check initialization."""
    checker = PermissionsCheckComponent()
    assert checker.display_name == "Permissions Check"
    assert hasattr(checker, "validate_auth")


def test_configuration():
    """Test Permissions Check configuration."""
    checker = PermissionsCheckComponent()
    config = checker.build_config()
    assert "pdp_url" in config
    assert "api_key" in config


def test_permission_check(mock_permit_client):
    """Test permission check with mock client."""
    checker = PermissionsCheckComponent()
    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.check.return_value = True

        checker.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        result = checker.validate_auth(user="test-user", action="read", resource="document-1")

        assert result is True
        mock_permit_client.check.assert_called_once()


def test_permission_check_with_tenant(mock_permit_client):
    """Test permission check with tenant context."""
    checker = PermissionsCheckComponent()
    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.check.return_value = True

        checker.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        result = checker.validate_auth(user="test-user", action="read", resource="document-1", tenant="tenant-1")

        assert result is True
        mock_permit_client.check.assert_called_once_with(
            user="test-user", action="read", resource="document-1", context={"tenant": "tenant-1"}
        )
