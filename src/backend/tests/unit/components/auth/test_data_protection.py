"""Test cases for Data Protection component."""

from unittest.mock import Mock, patch

import pytest
from langflow.base.auth.error_constants import AuthErrors
from langflow.components.auth.data_protection import DataProtectionComponent


@pytest.fixture
def mock_permit_client():
    """Create a mock Permit client."""
    return Mock()


@pytest.fixture
def component():
    """Create a component instance."""
    return DataProtectionComponent()


@pytest.mark.asyncio
async def test_initialization(component):
    """Test Data Protection initialization."""
    assert component.display_name == "Data Protection"
    assert component.permit is None


@pytest.mark.asyncio
async def test_validate_auth_no_permit(component):
    """Test validation without initialized permit client."""
    with pytest.raises(ValueError, match=AuthErrors.PERMIT_NOT_INITIALIZED.message):
        await component.validate_auth()


@pytest.mark.asyncio
async def test_get_all_permissions(component, mock_permit_client):
    """Test retrieving all permissions."""
    mock_permissions = [
        Mock(resource_id="doc1", resource="document", action="read"),
        Mock(resource_id="doc2", resource="document", action="read"),
        Mock(resource_id="doc3", resource="document", action="write"),
    ]

    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.get_user_permissions.return_value = mock_permissions

        component.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        component.user_id = "test-user"
        component.action = "read"
        component.resource_type = "document"

        result = await component.validate_auth()

        assert len(result) == 2
        assert "doc1" in result
        assert "doc2" in result
        assert "doc3" not in result


@pytest.mark.asyncio
async def test_filter_permissions(component, mock_permit_client):
    """Test filtering specific resource IDs."""
    filter_ids = ["doc1", "doc2", "doc3"]
    mock_filtered = [{"id": "doc1"}, {"id": "doc2"}]

    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.filter_objects.return_value = mock_filtered

        component.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        component.user_id = "test-user"
        component.action = "read"
        component.resource_type = "document"

        result = await component.validate_auth(filter_ids=filter_ids)

        assert len(result) == 2
        assert "doc1" in result
        assert "doc2" in result
        assert "doc3" not in result


def test_filter_response(component):
    """Test filtering sensitive fields from response."""
    test_response = {"id": "123", "access_key": "sensitive-data", "contact_info": "personal-data"}
    sensitive_fields = ["access_key", "contact_info"]

    result = component.filter_response(test_response, sensitive_fields)

    assert result["id"] == "123"
    assert result["access_key"] == "[REDACTED]"
    assert result["contact_info"] == "[REDACTED]"
