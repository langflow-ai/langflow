"""Test cases for Get User Permissions component."""
import pytest
from unittest.mock import Mock, patch
from langflow.components.auth import GetUserPermissionsComponent

@pytest.fixture
def mock_permit_client():
    """Create a mock Permit client."""
    return Mock()

def test_initialization():
    """Test Get User Permissions initialization."""
    permissions = GetUserPermissionsComponent()
    assert permissions.display_name == "Get User Permissions"
    assert hasattr(permissions, "validate_auth")

def test_configuration():
    """Test Get User Permissions configuration."""
    permissions = GetUserPermissionsComponent()
    config = permissions.build_config()
    assert "pdp_url" in config
    assert "api_key" in config

@pytest.mark.asyncio
async def test_get_all_permissions(mock_permit_client):
    """Test retrieving all permissions."""
    permissions = GetUserPermissionsComponent()
    mock_permissions = [
        Mock(resource_id="doc1", action="read"),
        Mock(resource_id="doc2", action="read"),
        Mock(resource_id="doc3", action="write")
    ]
    
    with patch('permit.Permit') as MockPermit:
        MockPermit.return_value = mock_permit_client
        mock_permit_client.get_user_permissions.return_value = mock_permissions
        
        permissions.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        result = await permissions.validate_auth(
            user_id="test-user",
            action="read",
            resource_type="document"
        )
        
        assert len(result) == 2  # Should only get the 'read' permissions
        assert "doc1" in result
        assert "doc2" in result
        assert "doc3" not in result

@pytest.mark.asyncio
async def test_filter_permissions(mock_permit_client):
    """Test filtering specific resource IDs."""
    permissions = GetUserPermissionsComponent()
    filter_ids = ["doc1", "doc2", "doc3"]
    mock_filtered = [
        {"id": "doc1"},
        {"id": "doc2"}
    ]
    
    with patch('permit.Permit') as MockPermit:
        MockPermit.return_value = mock_permit_client
        mock_permit_client.filter_objects.return_value = mock_filtered
        
        permissions.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        result = await permissions.validate_auth(
            user_id="test-user",
            action="read",
            resource_type="document",
            filter_ids=filter_ids
        )
        
        assert len(result) == 2
        assert "doc1" in result
        assert "doc2" in result
        assert "doc3" not in result