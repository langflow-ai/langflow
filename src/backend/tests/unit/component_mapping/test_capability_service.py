"""Unit tests for ComponentCapabilityService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from langflow.services.component_mapping.capability_service import ComponentCapabilityService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentCategoryEnum,
)
# Using ComponentMapping instead of legacy Component model


@pytest.fixture
def capability_service():
    """Create a ComponentCapabilityService instance for testing."""
    return ComponentCapabilityService()


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def sample_component_mapping():
    """Create a sample ComponentMapping for testing."""
    return ComponentMapping(
        id=uuid4(),
        genesis_type="genesis:test_component",
        base_config={"test": "config"},
        component_category=ComponentCategoryEnum.TOOL.value,
        tool_capabilities={
            "accepts_tools": False,
            "provides_tools": True,
            "discovery_method": "test"
        },
        active=True,
        version="1.0.0"
    )


@pytest.fixture
def sample_component():
    """Create a sample Component for testing."""
    component = MagicMock(spec=Component)
    component.type = "genesis:test_component"
    component.asTools = True
    return component


class TestComponentCapabilityService:
    """Test suite for ComponentCapabilityService."""

    @pytest.mark.asyncio
    async def test_get_tool_capabilities_found(self, capability_service, mock_session, sample_component_mapping):
        """Test get_tool_capabilities when capabilities are found."""
        # Mock the component mapping service
        with patch.object(capability_service, 'component_mapping_service') as mock_service:
            mock_service.get_component_mapping_by_genesis_type.return_value = sample_component_mapping

            result = await capability_service.get_tool_capabilities(
                mock_session, "genesis:test_component", use_cache=False
            )

            assert result == sample_component_mapping.tool_capabilities
            mock_service.get_component_mapping_by_genesis_type.assert_called_once_with(
                mock_session, "genesis:test_component", active_only=True
            )

    @pytest.mark.asyncio
    async def test_get_tool_capabilities_not_found(self, capability_service, mock_session):
        """Test get_tool_capabilities when no capabilities are found."""
        with patch.object(capability_service, 'component_mapping_service') as mock_service:
            mock_service.get_component_mapping_by_genesis_type.return_value = None

            result = await capability_service.get_tool_capabilities(
                mock_session, "genesis:nonexistent", use_cache=False
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_tool_capabilities_cached(self, capability_service, mock_session):
        """Test get_tool_capabilities using cache."""
        # Pre-populate cache
        test_capabilities = {"accepts_tools": True, "provides_tools": False}
        capability_service._capability_cache["genesis:test_component"] = test_capabilities

        result = await capability_service.get_tool_capabilities(
            mock_session, "genesis:test_component", use_cache=True
        )

        assert result == test_capabilities

    @pytest.mark.asyncio
    async def test_component_accepts_tools_database_validation(self, capability_service, mock_session):
        """Test component_accepts_tools using database validation."""
        with patch.object(capability_service, 'get_tool_capabilities') as mock_get_capabilities:
            mock_get_capabilities.return_value = {"accepts_tools": True, "provides_tools": False}

            result = await capability_service.component_accepts_tools(mock_session, "genesis:agent")

            assert result is True
            mock_get_capabilities.assert_called_once_with(mock_session, "genesis:agent")

    @pytest.mark.asyncio
    async def test_component_accepts_tools_invalid_type(self, capability_service, mock_session):
        """Test component_accepts_tools with invalid target type."""
        result = await capability_service.component_accepts_tools(mock_session, None)
        assert result is False

        result = await capability_service.component_accepts_tools(mock_session, "None")
        assert result is False

    @pytest.mark.asyncio
    async def test_component_provides_tools_database_validation(self, capability_service, mock_session):
        """Test component_provides_tools using database validation."""
        with patch.object(capability_service, 'get_tool_capabilities') as mock_get_capabilities:
            mock_get_capabilities.return_value = {"accepts_tools": False, "provides_tools": True}

            result = await capability_service.component_provides_tools(mock_session, "genesis:tool")

            assert result is True
            mock_get_capabilities.assert_called_once_with(mock_session, "genesis:tool")

    @pytest.mark.asyncio
    async def test_component_provides_tools_category_fallback(self, capability_service, mock_session, sample_component_mapping):
        """Test component_provides_tools fallback to category-based validation."""
        # No tool capabilities in mapping
        sample_component_mapping.tool_capabilities = None
        sample_component_mapping.component_category = ComponentCategoryEnum.TOOL.value

        with patch.object(capability_service, 'get_tool_capabilities') as mock_get_capabilities:
            mock_get_capabilities.return_value = None

            with patch.object(capability_service, 'component_mapping_service') as mock_service:
                mock_service.get_component_mapping_by_genesis_type.return_value = sample_component_mapping

                result = await capability_service.component_provides_tools(mock_session, "genesis:tool")

                assert result is True

    @pytest.mark.asyncio
    async def test_update_tool_capabilities_success(self, capability_service, mock_session, sample_component_mapping):
        """Test successful update of tool capabilities."""
        new_capabilities = {"accepts_tools": True, "provides_tools": True}

        with patch.object(capability_service, 'component_mapping_service') as mock_service:
            mock_service.get_component_mapping_by_genesis_type.return_value = sample_component_mapping
            mock_service.update_component_mapping.return_value = sample_component_mapping

            result = await capability_service.update_tool_capabilities(
                mock_session, "genesis:test_component", new_capabilities
            )

            assert result is True
            mock_service.update_component_mapping.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_tool_capabilities_no_mapping(self, capability_service, mock_session):
        """Test update_tool_capabilities when no mapping exists."""
        with patch.object(capability_service, 'component_mapping_service') as mock_service:
            mock_service.get_component_mapping_by_genesis_type.return_value = None

            result = await capability_service.update_tool_capabilities(
                mock_session, "genesis:nonexistent", {}
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_introspect_component_capabilities_agent_pattern(self, capability_service, mock_session):
        """Test introspection for agent component patterns."""
        result = await capability_service.introspect_component_capabilities(
            mock_session, "genesis:agent"
        )

        assert result["accepts_tools"] is True
        assert result["discovery_method"] == "type_pattern_agent"

    @pytest.mark.asyncio
    async def test_introspect_component_capabilities_tool_pattern(self, capability_service, mock_session):
        """Test introspection for tool component patterns."""
        result = await capability_service.introspect_component_capabilities(
            mock_session, "genesis:calculator"
        )

        assert result["provides_tools"] is True
        assert result["discovery_method"] == "type_pattern_tool"

    @pytest.mark.asyncio
    async def test_introspect_component_capabilities_model_pattern(self, capability_service, mock_session):
        """Test introspection for model component patterns."""
        result = await capability_service.introspect_component_capabilities(
            mock_session, "genesis:autonomize_model"
        )

        assert result["accepts_tools"] is True
        assert result["provides_tools"] is True
        assert result["discovery_method"] == "type_pattern_model"

    def test_introspect_component_class_with_astools(self, capability_service, sample_component):
        """Test component class introspection with asTools attribute."""
        result = capability_service._introspect_component_class(sample_component)

        assert result["provides_tools"] is True

    def test_introspect_component_class_with_tools_attribute(self, capability_service):
        """Test component class introspection with tools attribute."""
        component_class = MagicMock()
        component_class.tools = ["tool1", "tool2"]

        result = capability_service._introspect_component_class(component_class)

        assert result["accepts_tools"] is True

    @pytest.mark.asyncio
    async def test_validate_tool_connection_valid(self, capability_service, mock_session):
        """Test validation of a valid tool connection."""
        with patch.object(capability_service, 'component_provides_tools') as mock_provides:
            with patch.object(capability_service, 'component_accepts_tools') as mock_accepts:
                mock_provides.return_value = True
                mock_accepts.return_value = True

                result = await capability_service.validate_tool_connection(
                    mock_session, "genesis:tool", "genesis:agent"
                )

                assert result["valid"] is True
                assert result["source_provides"] is True
                assert result["target_accepts"] is True
                assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_tool_connection_invalid(self, capability_service, mock_session):
        """Test validation of an invalid tool connection."""
        with patch.object(capability_service, 'component_provides_tools') as mock_provides:
            with patch.object(capability_service, 'component_accepts_tools') as mock_accepts:
                mock_provides.return_value = False
                mock_accepts.return_value = False

                result = await capability_service.validate_tool_connection(
                    mock_session, "genesis:input", "genesis:output"
                )

                assert result["valid"] is False
                assert result["source_provides"] is False
                assert result["target_accepts"] is False
                assert len(result["errors"]) == 2

    @pytest.mark.asyncio
    async def test_get_components_by_capability(self, capability_service, mock_session, sample_component_mapping):
        """Test getting components by capability."""
        with patch.object(capability_service, 'component_mapping_service') as mock_service:
            mock_service.get_all_component_mappings.return_value = [sample_component_mapping]

            result = await capability_service.get_components_by_capability(
                mock_session, "provides_tools", True
            )

            assert len(result) == 1
            assert result[0] == sample_component_mapping

    def test_clear_capability_cache(self, capability_service):
        """Test clearing the capability cache."""
        # Populate cache
        capability_service._capability_cache["test"] = {"test": "data"}

        capability_service.clear_capability_cache()

        assert len(capability_service._capability_cache) == 0

    @pytest.mark.asyncio
    async def test_get_capability_statistics(self, capability_service, mock_session, sample_component_mapping):
        """Test getting capability statistics."""
        with patch.object(capability_service, 'component_mapping_service') as mock_service:
            mock_service.get_all_component_mappings.return_value = [sample_component_mapping]

            result = await capability_service.get_capability_statistics(mock_session)

            assert result["total_components"] == 1
            assert result["components_with_capabilities"] == 1
            assert result["provides_tools_count"] == 1
            assert result["accepts_tools_count"] == 0
            assert result["capability_coverage"] == 100.0