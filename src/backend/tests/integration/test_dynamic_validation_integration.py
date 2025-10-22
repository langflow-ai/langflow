"""Integration tests for dynamic tool capability validation system."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from langflow.services.component_mapping.capability_service import ComponentCapabilityService
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.component_mapping.startup_population import StartupPopulationService
from langflow.custom.genesis.spec.converter import FlowConverter
from langflow.custom.genesis.spec.mapper import ComponentMapper
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentCategoryEnum,
)
from langflow.custom.genesis.spec.models import AgentSpec, Component, Provides


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def capability_service():
    """Create a ComponentCapabilityService instance."""
    return ComponentCapabilityService()


@pytest.fixture
def mapping_service():
    """Create a ComponentMappingService instance."""
    return ComponentMappingService()


@pytest.fixture
def startup_service():
    """Create a StartupPopulationService instance."""
    return StartupPopulationService()


@pytest.fixture
def converter():
    """Create a FlowConverter instance."""
    return FlowConverter()


@pytest.fixture
def mapper():
    """Create a ComponentMapper instance."""
    return ComponentMapper()


@pytest.fixture
def sample_agent_component():
    """Create a sample agent component."""
    return Component(
        id="test_agent",
        type="genesis:agent",
        config={"model": "gpt-4"}
    )


@pytest.fixture
def sample_tool_component():
    """Create a sample tool component."""
    return Component(
        id="test_tool",
        type="genesis:calculator",
        config={"precision": 2},
        provides=[Provides(in_="test_agent", useAs="tool")]
    )


@pytest.fixture
def sample_spec():
    """Create a sample AgentSpec for testing."""
    agent = Component(
        id="test_agent",
        type="genesis:agent",
        config={"model": "gpt-4"}
    )
    tool = Component(
        id="test_tool",
        type="genesis:calculator",
        config={"precision": 2},
        provides=[Provides(in_="test_agent", useAs="tool")]
    )

    return AgentSpec(
        components=[agent, tool],
        name="test_spec",
        version="1.0.0"
    )


class TestDynamicValidationIntegration:
    """Integration tests for the dynamic validation system."""

    @pytest.mark.asyncio
    async def test_capability_service_integration(self, capability_service, mapping_service, mock_session):
        """Test integration between capability service and mapping service."""
        # Create a test mapping
        mapping_data = ComponentMappingCreate(
            genesis_type="genesis:test_agent",
            base_config={"model": "gpt-4"},
            component_category=ComponentCategoryEnum.AGENT.value,
            tool_capabilities={
                "accepts_tools": True,
                "provides_tools": False,
                "discovery_method": "test_integration"
            },
            version="1.0.0"
        )

        # Mock the database operations
        mock_mapping = ComponentMapping(
            id=uuid4(),
            **mapping_data.model_dump()
        )

        with patch.object(mapping_service, 'get_component_mapping_by_genesis_type') as mock_get:
            mock_get.return_value = mock_mapping

            # Test capability retrieval
            capabilities = await capability_service.get_tool_capabilities(
                mock_session, "genesis:test_agent"
            )

            assert capabilities["accepts_tools"] is True
            assert capabilities["provides_tools"] is False
            assert capabilities["discovery_method"] == "test_integration"

            # Test validation
            accepts_result = await capability_service.component_accepts_tools(
                mock_session, "genesis:test_agent"
            )
            provides_result = await capability_service.component_provides_tools(
                mock_session, "genesis:test_agent"
            )

            assert accepts_result is True
            assert provides_result is False

    @pytest.mark.asyncio
    async def test_converter_database_integration(self, converter, mock_session):
        """Test FlowConverter integration with database validation."""
        # Mock successful session acquisition
        with patch('langflow.custom.genesis.spec.converter.get_session', return_value=mock_session):
            # Mock component mapping
            with patch.object(converter.mapper, 'map_component_async') as mock_map:
                mock_map.return_value = {
                    "component": "Agent",
                    "config": {},
                    "dataType": "Agent"
                }

                # Mock capability validation
                with patch.object(converter.capability_service, 'component_accepts_tools') as mock_accepts:
                    with patch.object(converter.capability_service, 'component_provides_tools') as mock_provides:
                        mock_accepts.return_value = True
                        mock_provides.return_value = True

                        # Test spec conversion
                        spec_data = {
                            "name": "test_flow",
                            "version": "1.0.0",
                            "components": [
                                {
                                    "id": "agent1",
                                    "type": "genesis:agent",
                                    "config": {"model": "gpt-4"}
                                },
                                {
                                    "id": "tool1",
                                    "type": "genesis:calculator",
                                    "config": {"precision": 2},
                                    "provides": [{"in": "agent1", "useAs": "tool"}]
                                }
                            ]
                        }

                        result = await converter.convert(spec_data)

                        assert result is not None
                        assert "data" in result
                        assert "nodes" in result["data"]
                        assert "edges" in result["data"]

                        # Verify database methods were called
                        mock_map.assert_called()
                        mock_accepts.assert_called()
                        mock_provides.assert_called()

    @pytest.mark.asyncio
    async def test_mapper_async_functionality(self, mapper, mock_session):
        """Test ComponentMapper async functionality."""
        # Mock component mapping service
        mock_mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test_component",
            base_config={"test": "config"},
            component_category=ComponentCategoryEnum.TOOL.value,
            io_mapping={
                "component": "TestComponent",
                "dataType": "Tool"
            },
            version="1.0.0"
        )

        with patch.object(mapper, 'component_mapping_service') as mock_service:
            mock_service.get_component_mapping_by_genesis_type.return_value = mock_mapping

            # Test async mapping
            result = await mapper.map_component_async("genesis:test_component", mock_session)

            assert result["component"] == "TestComponent"
            assert result["dataType"] == "Tool"
            assert result["config"] == {"test": "config"}

            # Verify caching
            assert "genesis:test_component" in mapper._database_cache

    @pytest.mark.asyncio
    async def test_startup_population_integration(self, startup_service, mock_session):
        """Test startup population service integration."""
        # Mock existing mappings
        mock_mappings = [
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:agent",
                base_config={},
                component_category=ComponentCategoryEnum.AGENT.value,
                tool_capabilities=None,  # No capabilities yet
                version="1.0.0"
            ),
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:calculator",
                base_config={},
                component_category=ComponentCategoryEnum.TOOL.value,
                tool_capabilities=None,  # No capabilities yet
                version="1.0.0"
            )
        ]

        with patch.object(startup_service.component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = mock_mappings

            with patch.object(startup_service.capability_service, 'introspect_component_capabilities') as mock_introspect:
                with patch.object(startup_service.capability_service, 'update_tool_capabilities') as mock_update:
                    # Configure mocks
                    mock_introspect.side_effect = [
                        {"accepts_tools": True, "provides_tools": False, "discovery_method": "test"},
                        {"accepts_tools": False, "provides_tools": True, "discovery_method": "test"}
                    ]
                    mock_update.return_value = True

                    # Test capability population
                    result = await startup_service._populate_tool_capabilities(mock_session)

                    assert result["capabilities_populated"] == 2
                    assert len(result["errors"]) == 0

                    # Verify introspection was called for each mapping
                    assert mock_introspect.call_count == 2
                    assert mock_update.call_count == 2

    @pytest.mark.asyncio
    async def test_end_to_end_validation_flow(self, converter, mock_session):
        """Test end-to-end validation flow from spec to conversion."""
        # Setup mock database state
        agent_mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:agent",
            base_config={"model": "gpt-4"},
            component_category=ComponentCategoryEnum.AGENT.value,
            tool_capabilities={
                "accepts_tools": True,
                "provides_tools": False,
                "discovery_method": "database"
            },
            io_mapping={"component": "Agent", "dataType": "Agent"},
            version="1.0.0"
        )

        tool_mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:calculator",
            base_config={"precision": 2},
            component_category=ComponentCategoryEnum.TOOL.value,
            tool_capabilities={
                "accepts_tools": False,
                "provides_tools": True,
                "discovery_method": "database"
            },
            io_mapping={"component": "Calculator", "dataType": "Tool"},
            version="1.0.0"
        )

        # Mock session acquisition
        with patch('langflow.custom.genesis.spec.converter.get_session', return_value=mock_session):
            # Mock mapper service
            with patch.object(converter.mapper, 'component_mapping_service') as mock_mapper_service:
                mock_mapper_service.get_component_mapping_by_genesis_type.side_effect = [
                    agent_mapping, tool_mapping
                ]

                # Mock capability service
                with patch.object(converter.capability_service, 'component_mapping_service') as mock_cap_service:
                    mock_cap_service.get_component_mapping_by_genesis_type.side_effect = [
                        agent_mapping, tool_mapping
                    ]

                    # Test spec with tool connection
                    spec_data = {
                        "name": "test_agent_with_tool",
                        "version": "1.0.0",
                        "components": [
                            {
                                "id": "my_agent",
                                "type": "genesis:agent",
                                "config": {"model": "gpt-4"}
                            },
                            {
                                "id": "my_tool",
                                "type": "genesis:calculator",
                                "config": {"precision": 2},
                                "provides": [{"in": "my_agent", "useAs": "tool"}]
                            }
                        ]
                    }

                    result = await converter.convert(spec_data)

                    # Verify conversion succeeded
                    assert result is not None
                    assert "data" in result
                    assert len(result["data"]["nodes"]) == 2
                    assert len(result["data"]["edges"]) == 1

                    # Verify edge represents valid tool connection
                    edge = result["data"]["edges"][0]
                    assert edge["source"] == "my_tool"
                    assert edge["target"] == "my_agent"

    @pytest.mark.asyncio
    async def test_validation_with_invalid_tool_connection(self, converter, mock_session):
        """Test validation rejects invalid tool connections."""
        # Setup mappings where source cannot provide tools and target cannot accept tools
        input_mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:input",
            base_config={},
            component_category=ComponentCategoryEnum.IO.value,
            tool_capabilities={
                "accepts_tools": False,
                "provides_tools": False,
                "discovery_method": "database"
            },
            io_mapping={"component": "ChatInput", "dataType": "Message"},
            version="1.0.0"
        )

        output_mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:output",
            base_config={},
            component_category=ComponentCategoryEnum.IO.value,
            tool_capabilities={
                "accepts_tools": False,
                "provides_tools": False,
                "discovery_method": "database"
            },
            io_mapping={"component": "ChatOutput", "dataType": "Message"},
            version="1.0.0"
        )

        with patch('langflow.custom.genesis.spec.converter.get_session', return_value=mock_session):
            with patch.object(converter.mapper, 'component_mapping_service') as mock_mapper_service:
                mock_mapper_service.get_component_mapping_by_genesis_type.side_effect = [
                    input_mapping, output_mapping
                ]

                with patch.object(converter.capability_service, 'component_mapping_service') as mock_cap_service:
                    mock_cap_service.get_component_mapping_by_genesis_type.side_effect = [
                        input_mapping, output_mapping
                    ]

                    # Test spec with invalid tool connection
                    spec_data = {
                        "name": "invalid_tool_connection",
                        "version": "1.0.0",
                        "components": [
                            {
                                "id": "input_comp",
                                "type": "genesis:input",
                                "config": {}
                            },
                            {
                                "id": "output_comp",
                                "type": "genesis:output",
                                "config": {},
                                "provides": [{"in": "input_comp", "useAs": "tool"}]
                            }
                        ]
                    }

                    result = await converter.convert(spec_data)

                    # Conversion should still succeed but edge should be rejected
                    assert result is not None
                    assert len(result["data"]["nodes"]) == 2
                    # Invalid tool connection should not create an edge
                    assert len(result["data"]["edges"]) == 0

    @pytest.mark.asyncio
    async def test_cache_population_and_usage(self, mapper, mock_session):
        """Test database cache population and subsequent usage."""
        # Setup mock mappings
        mock_mappings = [
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:agent",
                base_config={"model": "gpt-4"},
                component_category=ComponentCategoryEnum.AGENT.value,
                io_mapping={"component": "Agent", "dataType": "Agent"},
                version="1.0.0"
            ),
            ComponentMapping(
                id=uuid4(),
                genesis_type="genesis:calculator",
                base_config={"precision": 2},
                component_category=ComponentCategoryEnum.TOOL.value,
                io_mapping={"component": "Calculator", "dataType": "Tool"},
                version="1.0.0"
            )
        ]

        with patch.object(mapper, 'component_mapping_service') as mock_service:
            mock_service.get_all_component_mappings.return_value = mock_mappings
            mock_service.get_all_adapters_for_genesis_type.side_effect = [
                [],  # No adapters for first mapping
                []   # No adapters for second mapping
            ]

            # Test cache population
            cached_count = await mapper.populate_database_cache(mock_session)

            assert cached_count == 2
            assert len(mapper._database_cache) == 2
            assert "genesis:agent" in mapper._database_cache
            assert "genesis:calculator" in mapper._database_cache

            # Test using cached data
            result = await mapper.map_component_async("genesis:agent", mock_session)
            assert result["component"] == "Agent"
            assert result["dataType"] == "Agent"