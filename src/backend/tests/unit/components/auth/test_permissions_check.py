"""Test cases for Permissions Check component."""

from unittest.mock import AsyncMock, patch

import pytest
from langflow.components.auth import PermissionsCheckComponent
from langflow.schema.message import Message

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPermissionsCheckComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return PermissionsCheckComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "user_id": "test-user",
            "action": "book",
            "resource": "flight",
            "pdp_url": "http://localhost:7766",
            "api_key": "permit_key_",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return [
            {"version": "1.0.19", "module": "components", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "components", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "components", "file_name": DID_NOT_EXIST},
        ]

    @pytest.mark.asyncio
    async def test_latest_version(self, component_class, default_kwargs):
        """Test that the component works with the latest version."""
        component = await self.component_setup(component_class, default_kwargs)
        with patch("components.permissions_check.Permit") as mock_permit:
            mock_instance = mock_permit.return_value
            mock_instance.check = AsyncMock(return_value=True)
            result = await component.validate_auth()
            assert result is not None, "Component returned None for the latest version"
            assert result is True, "Expected True for allowed permission"

    @pytest.mark.asyncio
    async def test_initialization(self, component_class, default_kwargs):
        """Test Permissions Check initialization."""
        component = await self.component_setup(component_class, default_kwargs)
        assert component.display_name == "Permissions Check"

    @pytest.mark.asyncio
    async def test_allowed_result(self, component_class, default_kwargs):
        """Test allowed result output."""
        component = await self.component_setup(component_class, default_kwargs)
        with patch("components.permissions_check.Permit") as mock_permit:
            mock_instance = mock_permit.return_value
            mock_instance.check = AsyncMock(return_value=True)
            await component.validate_auth()
            result = component.allowed_result()
            assert isinstance(result, Message), "Result should be a Message"
            assert result.content == "Permission granted for test-user to book on flight"

            mock_instance.check = AsyncMock(return_value=False)
            await component.validate_auth()
            result = component.allowed_result()
            assert isinstance(result, Message), "Result should be a Message"
            assert result.content == "", "Expected empty content when denied"

    @pytest.mark.asyncio
    async def test_denied_result(self, component_class, default_kwargs):
        """Test denied result output."""
        component = await self.component_setup(component_class, default_kwargs)
        with patch("components.permissions_check.Permit") as mock_permit:
            mock_instance = mock_permit.return_value
            mock_instance.check = AsyncMock(return_value=False)
            await component.validate_auth()
            result = component.denied_result()
            assert isinstance(result, Message), "Result should be a Message"
            assert result.content == "Permission denied for test-user to book on flight"

            mock_instance.check = AsyncMock(return_value=True)
            await component.validate_auth()
            result = component.denied_result()
            assert isinstance(result, Message), "Result should be a Message"
            assert result.content == "", "Expected empty content when allowed"

    @pytest.mark.asyncio
    async def test_validate_auth_with_tenant(self, component_class, default_kwargs):
        """Test validation with tenant context."""
        default_kwargs["tenant"] = "tenant-1"
        component = await self.component_setup(component_class, default_kwargs)
        with patch("components.permissions_check.Permit") as mock_permit:
            mock_instance = mock_permit.return_value
            mock_instance.check = AsyncMock(return_value=True)
            result = await component.validate_auth()
            assert result is True, "Expected True for allowed permission with tenant"
            mock_instance.check.assert_awaited_with("test-user", "book", "flight", context={"tenant": "tenant-1"})
