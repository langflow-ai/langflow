"""Test cases for Data Protection component."""
from unittest.mock import Mock, patch

import pytest
from langflow.components.auth.data_protection import DataProtectionComponent


@pytest.fixture
def mock_permit_client():
    """Create a mock Permit client."""
    return Mock()


def test_initialization():
    """Test Data Protection initialization."""
    protection = DataProtectionComponent()
    assert protection.display_name == "Data Protection"
    assert hasattr(protection, "validate_auth")


def test_configuration():
    """Test Data Protection configuration."""
    protection = DataProtectionComponent()
    config = protection.build_config()
    assert "pdp_url" in config
    assert "api_key" in config


def test_get_all_permissions(mock_permit_client):
    """Test retrieving all permissions."""
    protection = DataProtectionComponent()
    mock_permissions = [
        Mock(resource_id="doc1", action="read"),
        Mock(resource_id="doc2", action="read"),
        Mock(resource_id="doc3", action="write")
    ]

    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.get_user_permissions.return_value = mock_permissions

        protection.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        result = protection.validate_auth(
            user_id="test-user",
            action="read",
            resource_type="document"
        )

        assert len(result) == 2  # Should only get the 'read' permissions
        assert "doc1" in result
        assert "doc2" in result
        assert "doc3" not in result


def test_filter_permissions(mock_permit_client):
    """Test filtering specific resource IDs."""
    protection = DataProtectionComponent()
    filter_ids = ["doc1", "doc2", "doc3"]
    mock_filtered = [
        {"id": "doc1"},
        {"id": "doc2"}
    ]

    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.filter_objects.return_value = mock_filtered

        protection.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        result = protection.validate_auth(
            user_id="test-user",
            action="read",
            resource_type="document",
            filter_ids=filter_ids
        )

        assert len(result) == 2
        assert "doc1" in result
        assert "doc2" in result
        assert "doc3" not in result
