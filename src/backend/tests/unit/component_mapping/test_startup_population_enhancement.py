"""Unit tests for startup population service tool capability enhancements."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from langflow.services.component_mapping.startup_population import StartupPopulationService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentCategoryEnum,
)


@pytest.fixture
def startup_service():
    """Create a StartupPopulationService instance."""
    return StartupPopulationService()


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def sample_mappings_without_capabilities():
    """Create sample mappings without tool capabilities."""
    return [
        ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:agent",
            base_config={"model": "gpt-4"},
            component_category=ComponentCategoryEnum.AGENT.value,
            tool_capabilities=None,  # No capabilities yet
            version="1.0.0"
        ),
        ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:calculator",
            base_config={"precision": 2},
            component_category=ComponentCategoryEnum.TOOL.value,
            tool_capabilities=None,  # No capabilities yet
            version="1.0.0"
        ),
        ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:autonomize_model",
            base_config={"selected_model": "Clinical LLM"},
            component_category=ComponentCategoryEnum.LLM.value,
            tool_capabilities=None,  # No capabilities yet
            version="1.0.0"
        )
    ]


@pytest.fixture
def sample_mappings_with_capabilities():
    """Create sample mappings that already have tool capabilities."""
    return [
        ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:existing_agent",
            base_config={"model": "gpt-4"},
            component_category=ComponentCategoryEnum.AGENT.value,
            tool_capabilities={
                "accepts_tools": True,
                "provides_tools": False,
                "discovery_method": "existing"
            },
            version="1.0.0"
        )
    ]


class TestStartupPopulationEnhancement:
    """Test suite for startup population service tool capability enhancements."""

    @pytest.mark.asyncio
    async def test_populate_tool_capabilities_success(self, startup_service, mock_session, sample_mappings_without_capabilities):
        """Test successful population of tool capabilities."""
        # Mock the component mapping service
        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = sample_mappings_without_capabilities

            # Mock the capability service
            with patch.object(startup_service.capability_service, 'introspect_component_capabilities') as mock_introspect:
                with patch.object(startup_service.capability_service, 'update_tool_capabilities') as mock_update:
                    # Configure introspection responses
                    mock_introspect.side_effect = [
                        {"accepts_tools": True, "provides_tools": False, "discovery_method": "type_pattern_agent"},
                        {"accepts_tools": False, "provides_tools": True, "discovery_method": "type_pattern_tool"},
                        {"accepts_tools": True, "provides_tools": True, "discovery_method": "type_pattern_model"}
                    ]
                    mock_update.return_value = True

                    # Test the population
                    result = await startup_service._populate_tool_capabilities(mock_session)

                    assert result["capabilities_populated"] == 3
                    assert len(result["errors"]) == 0

                    # Verify introspection was called for each mapping
                    assert mock_introspect.call_count == 3
                    mock_introspect.assert_any_call(mock_session, "genesis:agent")
                    mock_introspect.assert_any_call(mock_session, "genesis:calculator")
                    mock_introspect.assert_any_call(mock_session, "genesis:autonomize_model")

                    # Verify update was called for each mapping
                    assert mock_update.call_count == 3

    @pytest.mark.asyncio
    async def test_populate_tool_capabilities_skips_existing(self, startup_service, mock_session, sample_mappings_with_capabilities):
        """Test that population skips mappings that already have capabilities."""
        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = sample_mappings_with_capabilities

            with patch.object(startup_service.capability_service, 'introspect_component_capabilities') as mock_introspect:
                with patch.object(startup_service.capability_service, 'update_tool_capabilities') as mock_update:

                    result = await startup_service._populate_tool_capabilities(mock_session)

                    # Should skip existing capabilities
                    assert result["capabilities_populated"] == 0
                    assert len(result["errors"]) == 0

                    # Introspection should not be called
                    mock_introspect.assert_not_called()
                    mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_populate_tool_capabilities_handles_errors(self, startup_service, mock_session, sample_mappings_without_capabilities):
        """Test that population handles errors gracefully."""
        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = sample_mappings_without_capabilities

            with patch.object(startup_service.capability_service, 'introspect_component_capabilities') as mock_introspect:
                with patch.object(startup_service.capability_service, 'update_tool_capabilities') as mock_update:
                    # Configure introspection to succeed for some, fail for others
                    mock_introspect.side_effect = [
                        {"accepts_tools": True, "provides_tools": False},  # Success
                        Exception("Introspection failed"),  # Error
                        {"accepts_tools": False, "provides_tools": True}   # Success
                    ]
                    mock_update.return_value = True

                    result = await startup_service._populate_tool_capabilities(mock_session)

                    # Should succeed for 2 out of 3
                    assert result["capabilities_populated"] == 2
                    assert len(result["errors"]) == 1
                    assert "genesis:calculator" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_populate_tool_capabilities_update_failure(self, startup_service, mock_session, sample_mappings_without_capabilities):
        """Test handling of capability update failures."""
        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = sample_mappings_without_capabilities[:1]  # Just one mapping

            with patch.object(startup_service.capability_service, 'introspect_component_capabilities') as mock_introspect:
                with patch.object(startup_service.capability_service, 'update_tool_capabilities') as mock_update:
                    mock_introspect.return_value = {"accepts_tools": True, "provides_tools": False}
                    mock_update.return_value = False  # Update fails

                    result = await startup_service._populate_tool_capabilities(mock_session)

                    # Should have 0 successful populations due to update failure
                    assert result["capabilities_populated"] == 0
                    assert len(result["errors"]) == 0  # No exceptions, just failed update

    @pytest.mark.asyncio
    async def test_populate_tool_capabilities_static_mappings(self, startup_service, mock_session):
        """Test population of capabilities for static mappings."""
        # Mock empty database mappings
        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = []

            # Mock static mappings on the mapper
            static_mapping = ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:static_test",
                base_config={},
                component_category=ComponentCategoryEnum.TOOL.value,
                tool_capabilities=None,
                version="1.0.0"
            )

            with patch.object(startup_service.component_mapping_service, 'get_component_mapping_by_genesis_type') as mock_get_by_type:
                mock_get_by_type.return_value = static_mapping

                with patch.object(startup_service.capability_service, 'introspect_component_capabilities') as mock_introspect:
                    with patch.object(startup_service.capability_service, 'update_tool_capabilities') as mock_update:
                        # Mock mapper to have static mappings
                        startup_service.mapper.AUTONOMIZE_MODELS = {
                            "genesis:static_test": {"component": "TestComponent", "config": {}}
                        }

                        mock_introspect.return_value = {"accepts_tools": False, "provides_tools": True}
                        mock_update.return_value = True

                        result = await startup_service._populate_tool_capabilities(mock_session)

                        assert result["capabilities_populated"] == 1

    @pytest.mark.asyncio
    async def test_startup_population_includes_capability_phase(self, startup_service, mock_session):
        """Test that startup population includes the tool capability phase."""
        # Mock all dependencies to avoid actual database operations
        with patch.object(startup_service, '_is_already_populated', return_value=False):
            with patch.object(startup_service, '_migrate_hardcoded_mappings') as mock_migrate:
                with patch.object(startup_service, '_populate_healthcare_mappings') as mock_healthcare:
                    with patch.object(startup_service, '_integrate_component_schemas') as mock_schemas:
                        with patch.object(startup_service, '_populate_tool_capabilities') as mock_capabilities:
                            with patch.object(startup_service, '_mark_population_complete'):

                                # Configure mock returns
                                mock_migrate.return_value = {"created": 5, "updated": 0, "errors": []}
                                mock_healthcare.return_value = {"created": 3, "updated": 0, "errors": []}
                                mock_schemas.return_value = {"schemas_integrated": 10, "errors": []}
                                mock_capabilities.return_value = {"capabilities_populated": 8, "errors": []}

                                result = await startup_service.populate_on_startup(mock_session)

                                # Verify the capability phase was called
                                mock_capabilities.assert_called_once_with(mock_session)

                                # Verify result includes capability phase
                                assert "tool_capabilities" in result["phases"]
                                assert result["phases"]["tool_capabilities"]["capabilities_populated"] == 8

    @pytest.mark.asyncio
    async def test_capability_service_initialization(self, startup_service):
        """Test that capability service is properly initialized."""
        assert startup_service.capability_service is not None
        assert hasattr(startup_service.capability_service, 'introspect_component_capabilities')
        assert hasattr(startup_service.capability_service, 'update_tool_capabilities')

    @pytest.mark.asyncio
    async def test_populate_tool_capabilities_empty_database(self, startup_service, mock_session):
        """Test population with empty database."""
        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = []

            # Mock empty static mappings
            startup_service.mapper.AUTONOMIZE_MODELS = {}

            result = await startup_service._populate_tool_capabilities(mock_session)

            assert result["capabilities_populated"] == 0
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_populate_tool_capabilities_service_exception(self, startup_service, mock_session):
        """Test population when service throws an exception."""
        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.side_effect = Exception("Database connection failed")

            result = await startup_service._populate_tool_capabilities(mock_session)

            assert result["capabilities_populated"] == 0
            assert len(result["errors"]) == 1
            assert "Database connection failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_capability_introspection_patterns(self, startup_service, mock_session):
        """Test that capability introspection follows correct patterns."""
        mappings = [
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:agent",
                component_category=ComponentCategoryEnum.AGENT.value,
                tool_capabilities=None,
                version="1.0.0"
            ),
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:tool_component",
                component_category=ComponentCategoryEnum.TOOL.value,
                tool_capabilities=None,
                version="1.0.0"
            )
        ]

        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = mappings

            with patch.object(startup_service.capability_service, 'introspect_component_capabilities') as mock_introspect:
                with patch.object(startup_service.capability_service, 'update_tool_capabilities') as mock_update:
                    mock_update.return_value = True

                    # Configure different introspection results based on component type
                    def introspect_side_effect(session, genesis_type):
                        if "agent" in genesis_type:
                            return {"accepts_tools": True, "provides_tools": False, "discovery_method": "type_pattern_agent"}
                        elif "tool" in genesis_type:
                            return {"accepts_tools": False, "provides_tools": True, "discovery_method": "type_pattern_tool"}
                        else:
                            return {"accepts_tools": False, "provides_tools": False, "discovery_method": "default"}

                    mock_introspect.side_effect = introspect_side_effect

                    result = await startup_service._populate_tool_capabilities(mock_session)

                    assert result["capabilities_populated"] == 2

                    # Verify correct introspection calls
                    calls = mock_introspect.call_args_list
                    assert any("genesis:agent" in str(call) for call in calls)
                    assert any("genesis:tool_component" in str(call) for call in calls)