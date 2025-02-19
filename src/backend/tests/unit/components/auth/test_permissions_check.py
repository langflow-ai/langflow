"""Test cases for Permissions Check component."""

from unittest.mock import Mock, patch

import pytest
from langflow.base.auth.error_constants import AuthErrors
from langflow.components.auth.permissions_check import PermissionsCheckComponent


@pytest.fixture
def mock_permit_client():
    return Mock()


@pytest.fixture
def component():
    return PermissionsCheckComponent()


@pytest.mark.asyncio
async def test_initialization(component):
    assert component.display_name == "Permissions Check"
    assert component.permit is None


@pytest.mark.asyncio
async def test_evaluate_access():
    assert PermissionsCheckComponent.evaluate_access("granted") == "proceed"
    assert "error" in PermissionsCheckComponent.evaluate_access("")


@pytest.mark.asyncio
async def test_validate_auth_no_permit(component):
    with pytest.raises(ValueError, match=AuthErrors.PERMIT_NOT_INITIALIZED.message):
        await component.validate_auth()


def test_filter_response(component):
    test_response = {"id": "123", "sensitive_data": "confidential", "contact": "private"}
    sensitive_fields = ["sensitive_data", "contact"]

    result = component.filter_response(test_response, sensitive_fields)

    assert result["id"] == "123"
    assert result["sensitive_data"] == "[REDACTED]"
    assert result["contact"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_permission_check(component, mock_permit_client):
    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.check.return_value = True

        component.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        component.user_id = "test-user"
        component.action = "read"
        component.resource = "document-1"

        result = await component.validate_auth()
        assert result is True


@pytest.mark.asyncio
async def test_permission_check_with_tenant(component, mock_permit_client):
    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.check.return_value = True

        component.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        component.user_id = "test-user"
        component.action = "read"
        component.resource = "document-1"
        component.tenant = "tenant-1"

        result = await component.validate_auth()
        assert result is True
        mock_permit_client.check.assert_called_with(
            user="test-user", action="read", resource="document-1", context={"tenant": "tenant-1"}
        )


@pytest.mark.asyncio
async def test_get_allowed(component, mock_permit_client):
    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.check.return_value = True

        component.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        component.user_id = "test-user"
        component.action = "read"
        component.resource = "document-1"

        result = await component.get_allowed()
        assert result is True


@pytest.mark.asyncio
async def test_get_denied(component, mock_permit_client):
    with patch("permit.Permit") as mock_permit:
        mock_permit.return_value = mock_permit_client
        mock_permit_client.check.return_value = False

        component.build(pdp_url="https://test.pdp.permit.io", api_key="test-key")
        component.user_id = "test-user"
        component.action = "read"
        component.resource = "document-1"

        result = await component.get_denied()
        assert result is True
