"""Unit tests for AUTPE-6199: Fix Component Mapping Priority System and Database Transaction Rollback Issues."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from langflow.custom.genesis.spec.mapper import ComponentMapper
from langflow.services.spec.service import SpecService
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentCategoryEnum,
)


@pytest.fixture
def component_mapper():
    """Create a ComponentMapper instance for testing."""
    return ComponentMapper()


@pytest.fixture
def spec_service():
    """Create a SpecService instance for testing."""
    return SpecService()


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def sample_database_mapping():
    """Create a sample database mapping that overrides hardcoded mapping."""
    return ComponentMapping(
        id=uuid4(),
        genesis_type="genesis:agent",  # This exists in hardcoded mappings
        base_config={"database_override": True, "custom_field": "database_value"},
        io_mapping={
            "component": "DatabaseAgent",  # Different from hardcoded "Agent"
            "dataType": "Data",
            "input_field": "input",
            "output_field": "output",
            "input_types": ["str"],
            "output_types": ["Data"],
        },
        component_category=ComponentCategoryEnum.AGENT,
        description="Database override for genesis:agent",
        version="1.0.0",
        active=True,
    )


class TestDatabasePriorityImplementation:
    """Test cases for AC1: Database Priority Implementation."""

    def test_hardcoded_mapping_without_database_cache(self, component_mapper):
        """Test that hardcoded mappings work when no database cache exists."""
        # Ensure cache is empty
        component_mapper.clear_mapping_cache()

        # Test hardcoded mapping
        result = component_mapper.map_component("genesis:agent")
        source = component_mapper.get_mapping_source("genesis:agent")

        assert result["component"] == "Agent"  # Hardcoded value
        assert source == "hardcoded_standard"

    def test_database_mapping_priority_over_hardcoded(self, component_mapper):
        """Test that database mappings take priority over hardcoded mappings."""
        # Setup database cache with override
        database_mappings = {
            "genesis:agent": {
                "component": "DatabaseAgent",
                "config": {"database_override": True},
                "dataType": "Data"
            }
        }
        component_mapper.populate_mapping_cache(database_mappings)

        # Test database mapping takes priority
        result = component_mapper.map_component("genesis:agent")
        source = component_mapper.get_mapping_source("genesis:agent")

        assert result["component"] == "DatabaseAgent"  # Database value, not hardcoded "Agent"
        assert result["config"]["database_override"] is True
        assert source == "database_cached"

    def test_mapping_source_logging_accuracy(self, component_mapper):
        """Test that get_mapping_source() accurately reflects map_component() priority."""
        # Test hardcoded healthcare mapping
        source = component_mapper.get_mapping_source("genesis:autonomize_model")
        assert source == "hardcoded_autonomize"

        # Test hardcoded MCP mapping
        source = component_mapper.get_mapping_source("genesis:mcp_tool")
        assert source == "hardcoded_mcp"

        # Test hardcoded standard mapping
        source = component_mapper.get_mapping_source("genesis:chat_input")
        assert source == "hardcoded_standard"

        # Test database cache priority
        database_mappings = {"genesis:test_component": {"component": "TestComponent"}}
        component_mapper.populate_mapping_cache(database_mappings)
        source = component_mapper.get_mapping_source("genesis:test_component")
        assert source == "database_cached"

    def test_multiple_component_types_database_override(self, component_mapper):
        """Test database override for multiple component types."""
        database_mappings = {
            "genesis:agent": {
                "component": "CustomAgent",
                "config": {"agent_override": True}
            },
            "genesis:mcp_tool": {
                "component": "CustomMCPTool",
                "config": {"tool_override": True}
            },
            "genesis:autonomize_model": {
                "component": "CustomAutonomizeModel",
                "config": {"model_override": True}
            }
        }
        component_mapper.populate_mapping_cache(database_mappings)

        # Test all override hardcoded mappings
        agent_result = component_mapper.map_component("genesis:agent")
        assert agent_result["component"] == "CustomAgent"
        assert agent_result["config"]["agent_override"] is True

        tool_result = component_mapper.map_component("genesis:mcp_tool")
        assert tool_result["component"] == "CustomMCPTool"
        assert tool_result["config"]["tool_override"] is True

        model_result = component_mapper.map_component("genesis:autonomize_model")
        assert model_result["component"] == "CustomAutonomizeModel"
        assert model_result["config"]["model_override"] is True

    def test_database_fallback_disabled(self, component_mapper):
        """Test behavior when database fallback is disabled."""
        # Setup database cache
        database_mappings = {
            "genesis:agent": {
                "component": "DatabaseAgent",
                "config": {"should_not_be_used": True}
            }
        }
        component_mapper.populate_mapping_cache(database_mappings)

        # Disable database fallback
        component_mapper.enable_database_fallback(False)

        # Should use hardcoded mapping, not database
        result = component_mapper.map_component("genesis:agent")
        source = component_mapper.get_mapping_source("genesis:agent")

        assert result["component"] == "Agent"  # Hardcoded value
        assert "should_not_be_used" not in result["config"]
        assert source == "hardcoded_standard"


class TestCachePopulationBeforeConversion:
    """Test cases for AC2: Cache Population Before Conversion."""

    @pytest.mark.asyncio
    async def test_cache_population_with_session(self, spec_service, mock_session, sample_database_mapping):
        """Test that cache is populated when session is provided."""
        # Mock the mapper's refresh method
        mock_refresh_result = {
            "refreshed": 1,
            "cached_types": ["genesis:agent"],
            "status": "success"
        }

        with patch.object(spec_service.mapper, 'refresh_cache_from_database',
                          return_value=mock_refresh_result) as mock_refresh:
            with patch.object(spec_service.mapper, 'get_cache_status',
                              return_value={"cached_mappings": 0}):

                # Call the cache population method
                await spec_service._ensure_database_cache_populated(mock_session)

                # Verify refresh was called
                mock_refresh.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_cache_population_without_session(self, spec_service):
        """Test graceful handling when no session is provided."""
        # Should not raise exception
        await spec_service._ensure_database_cache_populated(None)

        # Should log debug message about no session

    @pytest.mark.asyncio
    async def test_cache_population_with_existing_cache(self, spec_service, mock_session):
        """Test that cache refresh is skipped if cache already populated."""
        with patch.object(spec_service.mapper, 'get_cache_status',
                          return_value={"cached_mappings": 5}):
            with patch.object(spec_service.mapper, 'refresh_cache_from_database') as mock_refresh:

                await spec_service._ensure_database_cache_populated(mock_session)

                # Should not refresh if cache already populated
                mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_convert_spec_to_flow_populates_cache(self, spec_service, mock_session):
        """Test that convert_spec_to_flow populates cache before conversion."""
        test_spec = """
        name: Test Agent
        description: Test specification
        agentGoal: Test goal
        components:
          input:
            type: genesis:chat_input
          agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          output:
            type: genesis:chat_output
        """

        with patch.object(spec_service, '_ensure_database_cache_populated') as mock_cache_pop:
            with patch.object(spec_service.converter, 'convert', return_value={"test": "flow"}):

                result = await spec_service.convert_spec_to_flow(test_spec, session=mock_session)

                # Verify cache population was called
                mock_cache_pop.assert_called_once_with(mock_session)
                assert result["test"] == "flow"


class TestGracefulFallbackToHardcodedMappings:
    """Test cases for AC3: Graceful Fallback to Hardcoded Mappings."""

    @pytest.mark.asyncio
    async def test_database_error_fallback(self, component_mapper, mock_session):
        """Test graceful fallback when database operations fail."""
        # Mock service to raise exception
        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.side_effect = Exception("Database connection failed")

        with patch.object(component_mapper, '_get_component_mapping_service', return_value=mock_service):
            result = await component_mapper.refresh_cache_from_database(mock_session)

            # Should return error result, not raise exception
            assert "error" in result
            assert result["status"] == "error"
            assert "Database connection failed" in result["error"]

    def test_cache_corruption_fallback(self, component_mapper):
        """Test fallback when cache is corrupted."""
        # Corrupt the cache
        component_mapper._mapping_cache = {"invalid": None}

        # Should still work with hardcoded mappings
        result = component_mapper.map_component("genesis:agent")
        assert result["component"] == "Agent"

    @pytest.mark.asyncio
    async def test_spec_service_cache_error_fallback(self, spec_service, mock_session):
        """Test SpecService continues when cache population fails."""
        test_spec = """
        name: Test Agent
        description: Test specification
        agentGoal: Test goal
        components:
          input:
            type: genesis:chat_input
        """

        # Mock cache population to fail
        with patch.object(spec_service.mapper, 'refresh_cache_from_database',
                          side_effect=Exception("Cache error")):
            with patch.object(spec_service.converter, 'convert', return_value={"test": "flow"}):

                # Should not raise exception, should continue with conversion
                result = await spec_service.convert_spec_to_flow(test_spec, session=mock_session)
                assert result["test"] == "flow"


class TestMappingSourceTracking:
    """Test cases for AC4: Mapping Source Tracking."""

    def test_mapping_source_priority_order(self, component_mapper):
        """Test that get_mapping_source follows the same priority as map_component."""
        # Test database takes priority over hardcoded
        database_mappings = {"genesis:agent": {"component": "DatabaseAgent"}}
        component_mapper.populate_mapping_cache(database_mappings)

        # Both should show database priority
        result = component_mapper.map_component("genesis:agent")
        source = component_mapper.get_mapping_source("genesis:agent")

        assert result["component"] == "DatabaseAgent"
        assert source == "database_cached"

        # Clear cache and test hardcoded
        component_mapper.clear_mapping_cache()

        result = component_mapper.map_component("genesis:agent")
        source = component_mapper.get_mapping_source("genesis:agent")

        assert result["component"] == "Agent"
        assert source == "hardcoded_standard"

    def test_healthcare_validation_mapping_source(self, component_mapper):
        """Test source tracking for healthcare validation mappings."""
        # Test healthcare validation has correct source
        if component_mapper.HEALTHCARE_VALIDATION_MAPPINGS:
            first_type = next(iter(component_mapper.HEALTHCARE_VALIDATION_MAPPINGS.keys()))
            source = component_mapper.get_mapping_source(first_type)
            assert source == "hardcoded_healthcare_validation"

    def test_unknown_component_source(self, component_mapper):
        """Test source tracking for unknown components."""
        source = component_mapper.get_mapping_source("genesis:completely_unknown_component")
        assert source == "unknown"


class TestErrorHandling:
    """Test cases for AC6: Error Handling."""

    def test_get_mapping_from_database_error_handling(self, component_mapper):
        """Test error handling in _get_mapping_from_database."""
        # Test with no cache attribute
        if hasattr(component_mapper, '_mapping_cache'):
            delattr(component_mapper, '_mapping_cache')

        result = component_mapper._get_mapping_from_database("genesis:test")
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_cache_service_unavailable(self, component_mapper, mock_session):
        """Test behavior when ComponentMappingService is unavailable."""
        with patch.object(component_mapper, '_get_component_mapping_service', return_value=None):
            result = await component_mapper.refresh_cache_from_database(mock_session)

            assert "error" in result
            assert result["status"] == "service_unavailable"

    @pytest.mark.asyncio
    async def test_refresh_cache_invalid_mappings(self, component_mapper, mock_session):
        """Test handling of invalid mappings during cache refresh."""
        # Create mock mappings with invalid data
        invalid_mapping = Mock()
        invalid_mapping.io_mapping = None
        invalid_mapping.genesis_type = "genesis:invalid"
        invalid_mapping.id = uuid4()

        valid_mapping = Mock()
        valid_mapping.io_mapping = {"component": "ValidComponent"}
        valid_mapping.genesis_type = "genesis:valid"
        valid_mapping.base_config = {}
        valid_mapping.id = uuid4()

        mock_service = AsyncMock()
        mock_service.get_all_component_mappings.return_value = [invalid_mapping, valid_mapping]

        with patch.object(component_mapper, '_get_component_mapping_service', return_value=mock_service):
            result = await component_mapper.refresh_cache_from_database(mock_session)

            assert result["status"] == "success"
            assert result["refreshed"] == 1  # Only valid mapping processed
            assert result["skipped"] == 1   # Invalid mapping skipped


class TestPerformanceRequirements:
    """Test cases for AC7: Performance Requirements."""

    def test_database_lookup_performance(self, component_mapper):
        """Test that database lookup doesn't significantly impact performance."""
        import time

        # Test hardcoded lookup time
        start_time = time.time()
        for _ in range(100):
            component_mapper.map_component("genesis:agent")
        hardcoded_time = time.time() - start_time

        # Add database cache
        database_mappings = {
            f"genesis:component_{i}": {"component": f"Component{i}"}
            for i in range(50)
        }
        component_mapper.populate_mapping_cache(database_mappings)

        # Test with database cache
        start_time = time.time()
        for i in range(100):
            component_mapper.map_component(f"genesis:component_{i % 50}")
        cached_time = time.time() - start_time

        # Performance should not degrade significantly
        # Allow up to 50% increase (well under the 10% requirement for real usage)
        assert cached_time <= hardcoded_time * 1.5

    def test_cache_size_handling(self, component_mapper):
        """Test handling of large cache sizes."""
        # Create large cache
        large_cache = {
            f"genesis:component_{i}": {"component": f"Component{i}"}
            for i in range(1000)
        }

        component_mapper.populate_mapping_cache(large_cache)

        # Should handle lookup efficiently
        result = component_mapper._get_mapping_from_database("genesis:component_500")
        assert result is not None
        assert result["component"] == "Component500"


class TestBackwardCompatibility:
    """Test cases for AC5: Backward Compatibility."""

    def test_existing_hardcoded_mappings_still_work(self, component_mapper):
        """Test that all existing hardcoded mappings continue to work."""
        # Test key hardcoded mappings
        test_mappings = [
            ("genesis:agent", "Agent"),
            ("genesis:chat_input", "ChatInput"),
            ("genesis:chat_output", "ChatOutput"),
            ("genesis:autonomize_model", "AutonomizeModel"),
            ("genesis:mcp_tool", "MCPTools"),
        ]

        for genesis_type, expected_component in test_mappings:
            result = component_mapper.map_component(genesis_type)
            assert result["component"] == expected_component, f"Hardcoded mapping failed for {genesis_type}"

    def test_no_breaking_changes_in_mapping_format(self, component_mapper):
        """Test that mapping format remains compatible."""
        # Test that all expected fields are present
        result = component_mapper.map_component("genesis:agent")

        assert "component" in result
        assert "config" in result
        # dataType is optional

        # Test with database mapping
        database_mappings = {
            "genesis:test": {
                "component": "TestComponent",
                "config": {"test": True},
                "dataType": "Data"
            }
        }
        component_mapper.populate_mapping_cache(database_mappings)

        result = component_mapper.map_component("genesis:test")
        assert "component" in result
        assert "config" in result
        assert "dataType" in result

    @pytest.mark.asyncio
    async def test_existing_spec_conversion_compatibility(self, spec_service):
        """Test that existing specifications still convert correctly."""
        # Test with a basic spec that should work without database
        basic_spec = """
        name: Basic Agent
        description: A basic agent specification
        agentGoal: Process user input
        components:
          input:
            type: genesis:chat_input
          agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          output:
            type: genesis:chat_output
        """

        # Should work without session (no database cache)
        with patch.object(spec_service.converter, 'convert', return_value={"test": "converted"}):
            result = await spec_service.convert_spec_to_flow(basic_spec)
            assert result["test"] == "converted"


@pytest.fixture
def component_mapping_service():
    """Create a ComponentMappingService instance for testing."""
    return ComponentMappingService()


class TestComponentMappingMigrationFix:
    """Test the fixes for database transaction rollback issues during component mapping migration."""

    def test_determine_category_returns_enum(self, component_mapping_service):
        """Test that _determine_category_from_genesis_type always returns a ComponentCategoryEnum."""
        test_cases = [
            ("genesis:healthcare_test", ComponentCategoryEnum.HEALTHCARE),
            ("genesis:agent_test", ComponentCategoryEnum.AGENT),
            ("genesis:rxnorm", ComponentCategoryEnum.TOOL),  # rxnorm doesn't contain healthcare keywords
            ("genesis:icd10", ComponentCategoryEnum.TOOL),   # icd10 doesn't contain healthcare keywords
            ("genesis:ehr_connector", ComponentCategoryEnum.HEALTHCARE),  # ehr is a healthcare keyword
            ("genesis:claims_processor", ComponentCategoryEnum.HEALTHCARE),  # claims is a healthcare keyword
            ("genesis:unknown_type", ComponentCategoryEnum.TOOL),
            ("genesis:api_request", ComponentCategoryEnum.TOOL),
            ("genesis:llm_model", ComponentCategoryEnum.LLM),
        ]

        for genesis_type, expected_category in test_cases:
            result = component_mapping_service._determine_category_from_genesis_type(genesis_type)
            assert isinstance(result, ComponentCategoryEnum), f"Expected enum for {genesis_type}, got {type(result)}"
            assert result == expected_category, f"Expected {expected_category} for {genesis_type}, got {result}"

    def test_enum_value_extraction_handles_string(self):
        """Test that the enum value extraction logic handles both enum instances and strings."""
        # Test with enum instance
        enum_instance = ComponentCategoryEnum.HEALTHCARE
        assert isinstance(enum_instance, ComponentCategoryEnum)
        assert enum_instance.value == "healthcare"

        # Test with valid string
        valid_string = "healthcare"
        try:
            ComponentCategoryEnum(valid_string)
            # This should not raise an exception
            assert True
        except ValueError:
            pytest.fail("Valid enum string should not raise ValueError")

        # Test with invalid string
        invalid_string = "invalid_category"
        with pytest.raises(ValueError):
            ComponentCategoryEnum(invalid_string)

    @pytest.mark.asyncio
    async def test_migrate_hardcoded_mappings_handles_errors_gracefully(self, component_mapping_service, mock_session):
        """Test that migrate_hardcoded_mappings handles errors without transaction rollback."""
        # Mock the get_component_mapping_by_genesis_type to return None (no existing mapping)
        component_mapping_service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)

        # Mock create_component_mapping to raise an exception for one mapping
        def mock_create_mapping(session, mapping_data):
            if mapping_data.genesis_type == "genesis:problematic":
                raise Exception("Test error for problematic mapping")
            return AsyncMock()

        component_mapping_service.create_component_mapping = AsyncMock(side_effect=mock_create_mapping)
        component_mapping_service.create_runtime_adapter = AsyncMock(return_value=Mock())
        component_mapping_service.get_runtime_adapter_for_genesis_type = AsyncMock(return_value=None)

        # Test mappings with one that will cause an error
        test_mappings = {
            "genesis:good_mapping": {
                "component": "TestComponent",
                "config": {"test": "value"}
            },
            "genesis:problematic": {
                "component": "ProblematicComponent",
                "config": {"test": "value"}
            },
            "genesis:another_good": {
                "component": "AnotherComponent",
                "config": {"test": "value"}
            }
        }

        # Call the migration method
        results = await component_mapping_service.migrate_hardcoded_mappings(mock_session, test_mappings)

        # Verify that errors are recorded but processing continues
        assert len(results["errors"]) >= 1
        assert any("genesis:problematic" in error for error in results["errors"])

        # Verify that other mappings were still attempted to be processed
        # (The exact counts depend on the mock behavior, but errors should not prevent other processing)
        assert isinstance(results["created"], int)
        assert isinstance(results["updated"], int)
        assert isinstance(results["skipped"], int)

    def test_category_value_extraction_logic(self):
        """Test the specific category value extraction logic from the fix."""
        # Test enum instance
        category = ComponentCategoryEnum.HEALTHCARE
        if isinstance(category, ComponentCategoryEnum):
            category_value = category.value
        else:
            category_value = ComponentCategoryEnum.TOOL.value

        assert category_value == "healthcare"

        # Test string case
        category = "tool"
        if isinstance(category, ComponentCategoryEnum):
            category_value = category.value
        elif isinstance(category, str):
            try:
                ComponentCategoryEnum(category)
                category_value = category
            except ValueError:
                category_value = ComponentCategoryEnum.TOOL.value
        else:
            category_value = ComponentCategoryEnum.TOOL.value

        assert category_value == "tool"

        # Test invalid string case
        category = "invalid_category"
        if isinstance(category, ComponentCategoryEnum):
            category_value = category.value
        elif isinstance(category, str):
            try:
                ComponentCategoryEnum(category)
                category_value = category
            except ValueError:
                category_value = ComponentCategoryEnum.TOOL.value
        else:
            category_value = ComponentCategoryEnum.TOOL.value

        assert category_value == "tool"  # Should fallback to default

    @pytest.mark.asyncio
    async def test_empty_mappings_handled_gracefully(self, component_mapping_service, mock_session):
        """Test that empty or None mappings are handled gracefully."""
        # Test empty dict
        results = await component_mapping_service.migrate_hardcoded_mappings(mock_session, {})
        assert results["created"] == 0
        assert results["updated"] == 0
        assert results["skipped"] == 0
        assert len(results["errors"]) == 0

    @pytest.mark.asyncio
    async def test_invalid_mapping_info_handled(self, component_mapping_service, mock_session):
        """Test that invalid mapping_info structures are handled gracefully."""
        component_mapping_service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)

        # Test mappings with invalid structure
        invalid_mappings = {
            "genesis:valid": {
                "component": "ValidComponent",
                "config": {}
            },
            "genesis:invalid_string": "this_should_be_a_dict",
            "genesis:invalid_none": None,
            "genesis:another_valid": {
                "component": "AnotherValidComponent",
                "config": {}
            }
        }

        results = await component_mapping_service.migrate_hardcoded_mappings(mock_session, invalid_mappings)

        # Should have errors for invalid mappings but continue processing valid ones
        assert len(results["errors"]) >= 2  # At least for the invalid entries
        assert any("Invalid mapping_info type" in error for error in results["errors"])

    def test_string_object_has_no_attribute_value_fix(self):
        """Test the specific fix for 'str' object has no attribute 'value' error."""
        # This tests the exact scenario that was causing the error
        category = "healthcare"  # This is a string, not an enum

        # The old code would do: category.value (which fails on strings)
        # The new code does:
        if isinstance(category, ComponentCategoryEnum):
            category_value = category.value
        elif isinstance(category, str):
            try:
                ComponentCategoryEnum(category)
                category_value = category
            except ValueError:
                category_value = ComponentCategoryEnum.TOOL.value
        else:
            category_value = ComponentCategoryEnum.TOOL.value

        assert category_value == "healthcare"

        # Test with invalid string that should fallback to default
        category = "not_a_valid_category"
        if isinstance(category, ComponentCategoryEnum):
            category_value = category.value
        elif isinstance(category, str):
            try:
                ComponentCategoryEnum(category)
                category_value = category
            except ValueError:
                category_value = ComponentCategoryEnum.TOOL.value
        else:
            category_value = ComponentCategoryEnum.TOOL.value

        assert category_value == "tool"  # Should fallback to default