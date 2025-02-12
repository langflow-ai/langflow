"""Test cases for Permit Check component."""
import pytest
from unittest.mock import Mock, patch
from langflow.components.auth import PermitCheckComponent

@pytest.fixture
def mock_permit_client():
    """Create a mock Permit client."""
    return Mock()

def test_initialization():
    """Test Permit Check initialization."""
    checker = PermitCheckComponent()
    assert checker.display_name == "Permit Check"
    assert hasattr(checker, "validate_auth")

def test_configuration():
    """Test Permit Check configuration."""
    checker = PermitCheckComponent()
    config = checker.build_config()
    assert "pdp_url" in config
    assert "api_key" in config

@pytest.mark.asyncio
async def test_permission_check(mock_permit_client):
    """Test permission check with mock client."""
    checker = PermitCheckComponent()
    with patch('permit.Permit') as MockPermit:
        MockPermit.return_value = mock_permit_client
        mock_permit_client.check.return_value = True
        
        checker.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        result = await checker.validate_auth(
            user="test-user",
            action="read",
            resource="document-1"
        )
        
        assert result is True
        mock_permit_client.check.assert_called_once()

@pytest.mark.asyncio
async def test_permission_check_with_tenant(mock_permit_client):
    """Test permission check with tenant context."""
    checker = PermitCheckComponent()
    with patch('permit.Permit') as MockPermit:
        MockPermit.return_value = mock_permit_client
        mock_permit_client.check.return_value = True
        
        checker.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        result = await checker.validate_auth(
            user="test-user",
            action="read",
            resource="document-1",
            tenant="tenant-1"
        )
        
        assert result is True
        mock_permit_client.check.assert_called_once_with(
            user="test-user",
            action="read",
            resource="document-1",
            context={"tenant": "tenant-1"}
        )