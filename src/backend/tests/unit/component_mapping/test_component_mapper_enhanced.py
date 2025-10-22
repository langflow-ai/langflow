"""Unit tests for enhanced ComponentMapper functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from langflow.custom.genesis.spec.mapper import ComponentMapper
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentCategoryEnum,
)


@pytest.fixture
def component_mapper():
    """Create a ComponentMapper instance for testing."""
    return ComponentMapper()


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def sample_database_mapping():
    """Create a sample database mapping."""
    return ComponentMapping(
        id=uuid4(),
        genesis_type="genesis:database_component",
        base_config={"test_config": "value"},
        io_mapping={
            "component": "DatabaseComponent",
            "dataType": "Data",
            "input_field": "input",
            "output_field": "output",
            "input_types": ["str"],
            "output_types": ["Data"],
        },
        component_category=ComponentCategoryEnum.DATA,
        description="Database test component",
        version="1.0.0",
        active=True,
    )


class TestComponentMapperCache:
    """Test cases for ComponentMapper cache functionality."""

    def test_cache_initialization(self, component_mapper):
        """Test cache is properly initialized."""
        assert hasattr(component_mapper, '_mapping_cache')
        assert isinstance(component_mapper._mapping_cache, dict)
        assert len(component_mapper._mapping_cache) == 0

    def test_populate_mapping_cache(self, component_mapper):
        """Test populating the mapping cache."""
        test_mappings = {
            "genesis:test1": {"component": "TestComponent1", "config": {}},
            "genesis:test2": {"component": "TestComponent2", "config": {}},
        }

        component_mapper.populate_mapping_cache(test_mappings)

        assert len(component_mapper._mapping_cache) == 2
        assert "mapping_cache_genesis:test1" in component_mapper._mapping_cache
        assert "mapping_cache_genesis:test2" in component_mapper._mapping_cache

    def test_clear_mapping_cache(self, component_mapper):
        """Test clearing the mapping cache."""
        # Populate cache first
        test_mappings = {"genesis:test": {"component": "TestComponent", "config": {}}}
        component_mapper.populate_mapping_cache(test_mappings)
        assert len(component_mapper._mapping_cache) > 0

        # Clear cache
        component_mapper.clear_mapping_cache()
        assert len(component_mapper._mapping_cache) == 0

    def test_get_cache_status(self, component_mapper):
        """Test getting cache status."""
        status = component_mapper.get_cache_status()

        assert "cache_enabled" in status
        assert "cached_mappings" in status
        assert "cached_types" in status
        assert isinstance(status["cache_enabled"], bool)
        assert isinstance(status["cached_mappings"], int)
        assert isinstance(status["cached_types"], list)

    def test_get_mapping_from_database_with_cache(self, component_mapper):
        """Test getting mapping from database cache."""
        # Test without cache
        result = component_mapper._get_mapping_from_database("genesis:nonexistent")
        assert result is None

        # Populate cache
        test_mappings = {
            "genesis:cached_component": {
                "component": "CachedComponent",
                "config": {"test": "value"},
                "dataType": "Data"
            }
        }
        component_mapper.populate_mapping_cache(test_mappings)

        # Test with cache
        result = component_mapper._get_mapping_from_database("genesis:cached_component")
        assert result is not None
        assert result["component"] == "CachedComponent"
        assert result["config"]["test"] == "value"

    @pytest.mark.asyncio
    async def test_refresh_cache_from_database(self, component_mapper, mock_session, sample_database_mapping):
        """Test refreshing cache from database."""
        # Mock the mapping service
        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.return_value = [sample_database_mapping]

        with patch.object(component_mapper, '_get_component_mapping_service', return_value=mock_service):
            result = await component_mapper.refresh_cache_from_database(mock_session)

            assert result["status"] == "success"
            assert result["refreshed"] == 1
            assert "genesis:database_component" in result["cached_types"]

        # Verify cache was populated
        cached_mapping = component_mapper._get_mapping_from_database("genesis:database_component")
        assert cached_mapping is not None
        assert cached_mapping["component"] == "DatabaseComponent"

    @pytest.mark.asyncio
    async def test_refresh_cache_no_service(self, component_mapper, mock_session):
        """Test refresh cache when service is not available."""
        with patch.object(component_mapper, '_get_component_mapping_service', return_value=None):
            result = await component_mapper.refresh_cache_from_database(mock_session)

            assert "error" in result
            assert "ComponentMappingService not available" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_cache_service_error(self, component_mapper, mock_session):
        """Test refresh cache when service raises error."""
        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.side_effect = Exception("Service error")

        with patch.object(component_mapper, '_get_component_mapping_service', return_value=mock_service):
            result = await component_mapper.refresh_cache_from_database(mock_session)

            assert "error" in result
            assert "Service error" in result["error"]


class TestComponentMapperMappingSource:
    """Test cases for mapping source identification."""

    def test_get_mapping_source_hardcoded_autonomize(self, component_mapper):
        """Test mapping source for hardcoded autonomize models."""
        source = component_mapper.get_mapping_source("genesis:autonomize_model")
        assert source == "hardcoded_autonomize"

        source = component_mapper.get_mapping_source("genesis:rxnorm")
        assert source == "hardcoded_autonomize"

    def test_get_mapping_source_hardcoded_mcp(self, component_mapper):
        """Test mapping source for hardcoded MCP mappings."""
        source = component_mapper.get_mapping_source("genesis:mcp_tool")
        assert source == "hardcoded_mcp"

        source = component_mapper.get_mapping_source("genesis:mcp_client")
        assert source == "hardcoded_mcp"

    def test_get_mapping_source_hardcoded_standard(self, component_mapper):
        """Test mapping source for hardcoded standard mappings."""
        source = component_mapper.get_mapping_source("genesis:agent")
        assert source == "hardcoded_standard"

        source = component_mapper.get_mapping_source("genesis:chat_input")
        assert source == "hardcoded_standard"

    def test_get_mapping_source_database_cached(self, component_mapper):
        """Test mapping source for database cached mappings."""
        # Populate cache
        test_mappings = {"genesis:cached_component": {"component": "CachedComponent"}}
        component_mapper.populate_mapping_cache(test_mappings)

        source = component_mapper.get_mapping_source("genesis:cached_component")
        assert source == "database_cached"

    def test_get_mapping_source_unknown(self, component_mapper):
        """Test mapping source for unknown mappings."""
        source = component_mapper.get_mapping_source("genesis:completely_unknown")
        assert source == "unknown"


class TestComponentMapperIntegration:
    """Test cases for integration with database fallback."""

    def test_map_component_with_cache_fallback(self, component_mapper):
        """Test component mapping with cache fallback."""
        # Test hardcoded mapping first
        result = component_mapper.map_component("genesis:agent")
        assert result["component"] == "Agent"

        # Add to cache and test fallback
        test_mappings = {
            "genesis:cached_component": {
                "component": "CachedComponent",
                "config": {"cached": True},
                "dataType": "Data"
            }
        }
        component_mapper.populate_mapping_cache(test_mappings)

        result = component_mapper.map_component("genesis:cached_component")
        assert result["component"] == "CachedComponent"
        assert result["config"]["cached"] is True

    def test_map_component_fallback_order(self, component_mapper):
        """Test the fallback order for component mapping."""
        # Test unknown component without cache
        result = component_mapper.map_component("genesis:unknown_component")
        # Should use intelligent fallback
        assert "component" in result

        # Add to cache and test it takes precedence over fallback
        test_mappings = {
            "genesis:unknown_component": {
                "component": "KnownFromDatabase",
                "config": {},
            }
        }
        component_mapper.populate_mapping_cache(test_mappings)

        result = component_mapper.map_component("genesis:unknown_component")
        assert result["component"] == "KnownFromDatabase"

    def test_database_fallback_disabled(self, component_mapper):
        """Test behavior when database fallback is disabled."""
        component_mapper.enable_database_fallback(False)

        # Add to cache
        test_mappings = {"genesis:cached_component": {"component": "CachedComponent"}}
        component_mapper.populate_mapping_cache(test_mappings)

        # Should not use cache when disabled
        result = component_mapper.map_component("genesis:cached_component")
        # Should use intelligent fallback instead
        assert result["component"] != "CachedComponent"

    @pytest.mark.asyncio
    async def test_async_database_methods(self, component_mapper, mock_session, sample_database_mapping):
        """Test async database methods."""
        mock_service = AsyncMock()
        mock_service.get_component_mapping_by_genesis_type.return_value = sample_database_mapping

        with patch.object(component_mapper, '_get_component_mapping_service', return_value=mock_service):
            # Test async mapping retrieval
            result = await component_mapper.get_mapping_from_database_async(
                mock_session, "genesis:database_component"
            )

            assert result is not None
            assert result["component"] == "DatabaseComponent"
            assert result["config"]["test_config"] == "value"

    @pytest.mark.asyncio
    async def test_async_runtime_adapter_retrieval(self, component_mapper, mock_session):
        """Test async runtime adapter retrieval."""
        from langflow.services.database.models.component_mapping.runtime_adapter import (
            RuntimeAdapter, RuntimeTypeEnum
        )

        mock_adapter = RuntimeAdapter(
            id=uuid4(),
            genesis_type="genesis:test_component",
            runtime_type=RuntimeTypeEnum.LANGFLOW.value,
            target_component="TestComponent",
            adapter_config={"test": "config"},
            version="1.0.0",
            description="Test adapter",
            active=True,
            priority=100,
        )

        mock_service = AsyncMock()
        mock_service.get_runtime_adapter_for_genesis_type.return_value = mock_adapter

        with patch.object(component_mapper, '_get_component_mapping_service', return_value=mock_service):
            result = await component_mapper.get_runtime_adapter_async(
                mock_session, "genesis:test_component", "langflow"
            )

            assert result is not None
            assert result["target_component"] == "TestComponent"
            assert result["adapter_config"]["test"] == "config"

    @pytest.mark.asyncio
    async def test_migration_functionality(self, component_mapper, mock_session):
        """Test migration of hardcoded mappings to database."""
        mock_service = AsyncMock()
        mock_service.migrate_hardcoded_mappings.return_value = {
            "created": 94,  # Total hardcoded mappings
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

        with patch.object(component_mapper, '_get_component_mapping_service', return_value=mock_service):
            result = await component_mapper.migrate_hardcoded_mappings_to_database(mock_session)

            assert result["created"] == 94
            assert len(result["errors"]) == 0

        # Verify service was called with all mappings
        mock_service.migrate_hardcoded_mappings.assert_called_once()
        call_args = mock_service.migrate_hardcoded_mappings.call_args[0]
        all_mappings = call_args[1]

        # Should include all mapping categories
        assert any(key.startswith("genesis:autonomize") for key in all_mappings)
        assert any(key.startswith("genesis:mcp") for key in all_mappings)
        assert "genesis:agent" in all_mappings


class TestComponentMapperErrorHandling:
    """Test cases for error handling in ComponentMapper."""

    def test_cache_operations_with_invalid_data(self, component_mapper):
        """Test cache operations with invalid data."""
        # Test with invalid mapping data
        invalid_mappings = {
            "genesis:test": None,  # Invalid data
            "invalid_key": {"component": "Test"},  # Invalid key
        }

        # Should handle gracefully
        component_mapper.populate_mapping_cache(invalid_mappings)

        # Should cache valid data despite invalid entries
        assert "mapping_cache_invalid_key" in component_mapper._mapping_cache

    def test_get_mapping_source_with_cache_corruption(self, component_mapper):
        """Test mapping source detection with corrupted cache."""
        # Manually corrupt cache
        component_mapper._mapping_cache = {"invalid_key": "invalid_value"}

        # Should still handle gracefully
        source = component_mapper.get_mapping_source("genesis:test")
        assert source == "unknown"

    @pytest.mark.asyncio
    async def test_async_methods_with_no_service(self, component_mapper, mock_session):
        """Test async methods when service is not available."""
        with patch.object(component_mapper, '_get_component_mapping_service', return_value=None):
            result = await component_mapper.get_mapping_from_database_async(
                mock_session, "genesis:test"
            )
            assert result is None

            result = await component_mapper.get_runtime_adapter_async(
                mock_session, "genesis:test", "langflow"
            )
            assert result is None


# Performance Tests

class TestComponentMapperPerformance:
    """Test cases for ComponentMapper performance."""

    def test_cache_performance_with_large_dataset(self, component_mapper):
        """Test cache performance with large number of mappings."""
        # Create large dataset
        large_mappings = {
            f"genesis:component_{i}": {
                "component": f"Component{i}",
                "config": {"index": i},
            }
            for i in range(1000)
        }

        # Test population performance
        import time
        start_time = time.time()
        component_mapper.populate_mapping_cache(large_mappings)
        population_time = time.time() - start_time

        assert population_time < 1.0  # Should complete in under 1 second

        # Test retrieval performance
        start_time = time.time()
        for i in range(100):  # Test 100 random retrievals
            result = component_mapper._get_mapping_from_database(f"genesis:component_{i}")
            assert result is not None
        retrieval_time = time.time() - start_time

        assert retrieval_time < 0.1  # Should complete in under 0.1 seconds

    def test_mapping_lookup_performance(self, component_mapper):
        """Test performance of mapping lookup with different sources."""
        import time

        # Test hardcoded lookup performance
        start_time = time.time()
        for _ in range(1000):
            component_mapper.map_component("genesis:agent")
        hardcoded_time = time.time() - start_time

        # Test cached lookup performance
        test_mappings = {"genesis:cached": {"component": "Cached", "config": {}}}
        component_mapper.populate_mapping_cache(test_mappings)

        start_time = time.time()
        for _ in range(1000):
            component_mapper.map_component("genesis:cached")
        cached_time = time.time() - start_time

        # Both should be fast, cached might be slightly slower due to cache key lookup
        assert hardcoded_time < 0.5
        assert cached_time < 0.5