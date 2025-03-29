"""Test cases for Data Protection component."""

from unittest.mock import AsyncMock, patch

import pytest
from langflow.components.auth import DataProtectionComponent
from langflow.schema.message import Message

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestDataProtectionComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return DataProtectionComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "user_id": "test-user",
            "action": "book",
            "resource_type": "flight",
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
        # Updated patch to target the correct import path
        with patch("components.data_protection.Permit") as mock_permit:
            mock_permit.return_value.get_user_permissions = AsyncMock(
                return_value=[
                    AsyncMock(resource_id="flight-001", resource="flight", action="book"),
                ]
            )
            result = await component.validate_auth()
            assert result is not None, "Component returned None for the latest version"
            assert isinstance(result, Message), "Result should be a Message"
            assert isinstance(result.content, list), "Content should be a list"
            assert "flight-001" in result.content, "Expected flight-001 in result"

    @pytest.mark.asyncio
    async def test_initialization(self, component_class, default_kwargs):
        """Test Data Protection initialization."""
        component = await self.component_setup(component_class, default_kwargs)
        assert component.display_name == "Data Protection"

    @pytest.mark.asyncio
    async def test_get_all_permissions(self, component_class, default_kwargs):
        """Test retrieving all permissions."""
        component = await self.component_setup(component_class, default_kwargs)
        mock_permissions = [
            AsyncMock(resource_id="flight-001", resource="flight", action="book"),
            AsyncMock(resource_id="flight-002", resource="flight", action="book"),
            AsyncMock(resource_id="flight-003", resource="flight", action="view"),
        ]

        # Updated patch to target the correct import path
        with patch("components.data_protection.Permit") as mock_permit:
            mock_permit.return_value.get_user_permissions = AsyncMock(return_value=mock_permissions)
            result = await component.validate_auth()
            assert isinstance(result, Message), "Result should be a Message"
            assert isinstance(result.content, list), "Result content should be a list"
            assert len(result.content) == 2, "Should filter to 2 matching permissions"
            assert "flight-001" in result.content, "Expected flight-001 in result"
            assert "flight-002" in result.content, "Expected flight-002 in result"
            assert "flight-003" not in result.content, "flight-003 should be filtered out"
