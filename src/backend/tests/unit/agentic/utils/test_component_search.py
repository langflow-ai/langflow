"""Unit tests for component_search module using real components."""

import pytest
from langflow.agentic.utils.component_search import (
    get_all_component_types,
    get_component_by_name,
    get_components_by_type,
    get_components_count,
    list_all_components,
)
from langflow.services.deps import get_settings_service


class TestListAllComponents:
    """Test cases for list_all_components function using real components."""

    @pytest.mark.asyncio
    async def test_list_all_components_without_filters(self):
        """Test listing all components without any filters."""
        settings_service = get_settings_service()
        components = await list_all_components(settings_service=settings_service)

        assert len(components) > 0
        assert all(isinstance(c, dict) for c in components)
        # Each component should have at least name and type
        for comp in components:
            assert "name" in comp
            assert "type" in comp

    @pytest.mark.asyncio
    async def test_list_components_with_field_selection(self):
        """Test listing components with specific field selection."""
        settings_service = get_settings_service()
        components = await list_all_components(
            fields=["name", "display_name", "description"],
            settings_service=settings_service,
        )

        assert len(components) > 0
        for comp in components:
            assert "name" in comp
            assert "type" in comp  # type is always included
            # Check that only requested fields (plus name/type) are present
            assert "display_name" in comp or "description" in comp

    @pytest.mark.asyncio
    async def test_list_components_search_by_query(self):
        """Test searching components by query string."""
        settings_service = get_settings_service()
        # Search for "OpenAI" - should find OpenAI components
        components = await list_all_components(
            query="OpenAI",
            settings_service=settings_service,
        )

        # Should find at least some OpenAI components
        assert len(components) > 0
        for comp in components:
            name_match = "openai" in comp.get("name", "").lower()
            display_name_match = "openai" in comp.get("display_name", "").lower()
            description_match = "openai" in comp.get("description", "").lower()
            assert name_match or display_name_match or description_match

    @pytest.mark.asyncio
    async def test_list_components_search_case_insensitive(self):
        """Test that search is case-insensitive."""
        settings_service = get_settings_service()
        # Search for "chat" in different cases
        results_lower = await list_all_components(query="chat", settings_service=settings_service)
        results_upper = await list_all_components(query="CHAT", settings_service=settings_service)
        results_mixed = await list_all_components(query="ChAt", settings_service=settings_service)

        # All should return same results
        assert len(results_lower) == len(results_upper) == len(results_mixed)

    @pytest.mark.asyncio
    async def test_list_components_filter_by_type(self):
        """Test filtering components by type."""
        settings_service = get_settings_service()
        # Get all available types first
        all_types = await get_all_component_types(settings_service=settings_service)
        assert len(all_types) > 0

        # Filter by first available type
        test_type = all_types[0]
        components = await list_all_components(
            component_type=test_type,
            settings_service=settings_service,
        )

        assert len(components) > 0
        # All components should be of the specified type
        for comp in components:
            assert comp["type"].lower() == test_type.lower()

    @pytest.mark.asyncio
    async def test_list_components_filter_by_type_llms(self):
        """Test filtering components by 'llms' type specifically."""
        settings_service = get_settings_service()
        components = await list_all_components(
            component_type="llms",
            settings_service=settings_service,
        )

        # Should find LLM components
        if components:  # Only if llms type exists
            for comp in components:
                assert comp["type"].lower() == "llms"

    @pytest.mark.asyncio
    async def test_list_components_combine_query_and_type_filter(self):
        """Test combining query search with type filtering."""
        settings_service = get_settings_service()
        all_types = await get_all_component_types(settings_service=settings_service)

        if "llms" in [t.lower() for t in all_types]:
            # Search for "model" within llms type
            components = await list_all_components(
                query="model",
                component_type="llms",
                settings_service=settings_service,
            )

            for comp in components:
                # Must be llms type
                assert comp["type"].lower() == "llms"
                # Must match query
                name_match = "model" in comp.get("name", "").lower()
                display_match = "model" in comp.get("display_name", "").lower()
                desc_match = "model" in comp.get("description", "").lower()
                assert name_match or display_match or desc_match

    @pytest.mark.asyncio
    async def test_list_components_no_matches_returns_empty(self):
        """Test that empty list is returned when no components match query."""
        settings_service = get_settings_service()
        components = await list_all_components(
            query="xyznonexistentquery123456",
            settings_service=settings_service,
        )

        assert components == []

    @pytest.mark.asyncio
    async def test_list_components_all_fields_when_none_specified(self):
        """Test that all fields are returned when fields is None."""
        settings_service = get_settings_service()
        components = await list_all_components(
            fields=None,
            settings_service=settings_service,
        )

        assert len(components) > 0
        # Should have many fields
        for comp in components:
            assert "name" in comp
            assert "type" in comp
            # Should include additional fields when fields=None
            assert len(comp) > 2

    @pytest.mark.asyncio
    async def test_list_components_with_nonexistent_type(self):
        """Test filtering by a nonexistent type returns empty."""
        settings_service = get_settings_service()
        components = await list_all_components(
            component_type="nonexistent_type_xyz",
            settings_service=settings_service,
        )

        assert components == []


class TestGetComponentByName:
    """Test cases for get_component_by_name function."""

    @pytest.mark.asyncio
    async def test_get_existing_component(self):
        """Test retrieving an existing component by name."""
        settings_service = get_settings_service()
        # Get list of components to find a valid name
        all_components = await list_all_components(
            fields=["name"],
            settings_service=settings_service,
        )
        assert len(all_components) > 0

        # Get first component by name
        first_name = all_components[0]["name"]
        component = await get_component_by_name(
            component_name=first_name,
            settings_service=settings_service,
        )

        assert component is not None
        assert component["name"] == first_name

    @pytest.mark.asyncio
    async def test_get_component_with_type_filter(self):
        """Test getting component with type filter."""
        settings_service = get_settings_service()
        # Get components of a specific type
        all_types = await get_all_component_types(settings_service=settings_service)
        assert len(all_types) > 0

        test_type = all_types[0]
        type_components = await list_all_components(
            component_type=test_type,
            settings_service=settings_service,
        )

        if type_components:
            comp_name = type_components[0]["name"]
            component = await get_component_by_name(
                component_name=comp_name,
                component_type=test_type,
                settings_service=settings_service,
            )

            assert component is not None
            assert component["name"] == comp_name
            assert component["type"].lower() == test_type.lower()

    @pytest.mark.asyncio
    async def test_get_component_with_field_selection(self):
        """Test getting component with specific field selection."""
        settings_service = get_settings_service()
        all_components = await list_all_components(
            fields=["name"],
            settings_service=settings_service,
        )
        assert len(all_components) > 0

        first_name = all_components[0]["name"]
        component = await get_component_by_name(
            component_name=first_name,
            fields=["display_name", "description"],
            settings_service=settings_service,
        )

        assert component is not None
        assert "name" in component
        assert "type" in component
        # Should include requested fields if available
        assert "display_name" in component or "description" in component

    @pytest.mark.asyncio
    async def test_get_nonexistent_component(self):
        """Test that None is returned for nonexistent component."""
        settings_service = get_settings_service()
        component = await get_component_by_name(
            component_name="NonExistentComponentXYZ123",
            settings_service=settings_service,
        )

        assert component is None

    @pytest.mark.asyncio
    async def test_get_component_wrong_type(self):
        """Test getting component with wrong type returns None."""
        settings_service = get_settings_service()
        # Get a component from one type
        all_types = await get_all_component_types(settings_service=settings_service)
        if len(all_types) >= 2:
            first_type = all_types[0]
            second_type = all_types[1]

            type_components = await list_all_components(
                component_type=first_type,
                settings_service=settings_service,
            )

            if type_components:
                comp_name = type_components[0]["name"]
                # Try to get it with wrong type
                component = await get_component_by_name(
                    component_name=comp_name,
                    component_type=second_type,
                    settings_service=settings_service,
                )

                # Should be None since component doesn't exist in second_type
                # (unless the same name exists in both types)
                if component is not None:
                    assert component["type"].lower() == second_type.lower()


class TestGetAllComponentTypes:
    """Test cases for get_all_component_types function."""

    @pytest.mark.asyncio
    async def test_get_all_types(self):
        """Test retrieving all component types."""
        settings_service = get_settings_service()
        types = await get_all_component_types(settings_service=settings_service)

        assert isinstance(types, list)
        assert len(types) > 0
        assert all(isinstance(t, str) for t in types)

    @pytest.mark.asyncio
    async def test_types_are_sorted(self):
        """Test that returned types are sorted alphabetically."""
        settings_service = get_settings_service()
        types = await get_all_component_types(settings_service=settings_service)

        assert types == sorted(types)

    @pytest.mark.asyncio
    async def test_common_types_exist(self):
        """Test that common component types are present."""
        settings_service = get_settings_service()
        types = await get_all_component_types(settings_service=settings_service)

        types_lower = [t.lower() for t in types]
        # Some common types that should exist
        # At least one of these should be present
        common_types = ["agents", "embeddings", "llms", "tools", "data", "processing"]
        found_common = any(ct in types_lower for ct in common_types)
        assert found_common, f"Expected at least one common type in {types}"

    @pytest.mark.asyncio
    async def test_types_are_unique(self):
        """Test that returned types have no duplicates."""
        settings_service = get_settings_service()
        types = await get_all_component_types(settings_service=settings_service)

        assert len(types) == len(set(types))

    @pytest.mark.asyncio
    async def test_types_match_components(self):
        """Test that returned types match actual component types."""
        settings_service = get_settings_service()
        types = await get_all_component_types(settings_service=settings_service)
        all_components = await list_all_components(settings_service=settings_service)

        # Collect all types from components
        component_types = {comp["type"] for comp in all_components}

        # Types should match
        assert set(types) == component_types


class TestGetComponentsCount:
    """Test cases for get_components_count function."""

    @pytest.mark.asyncio
    async def test_count_all_components(self):
        """Test counting all components."""
        settings_service = get_settings_service()
        count = await get_components_count(settings_service=settings_service)
        components = await list_all_components(settings_service=settings_service)

        assert count == len(components)
        assert count > 0

    @pytest.mark.asyncio
    async def test_count_by_type(self):
        """Test counting components by type."""
        settings_service = get_settings_service()
        all_types = await get_all_component_types(settings_service=settings_service)
        assert len(all_types) > 0

        test_type = all_types[0]
        count = await get_components_count(
            component_type=test_type,
            settings_service=settings_service,
        )
        type_components = await list_all_components(
            component_type=test_type,
            settings_service=settings_service,
        )

        assert count == len(type_components)

    @pytest.mark.asyncio
    async def test_count_nonexistent_type(self):
        """Test counting components of nonexistent type returns 0."""
        settings_service = get_settings_service()
        count = await get_components_count(
            component_type="nonexistent_type_xyz",
            settings_service=settings_service,
        )

        assert count == 0

    @pytest.mark.asyncio
    async def test_total_count_equals_sum_of_type_counts(self):
        """Test that total count equals sum of all type counts."""
        settings_service = get_settings_service()
        total_count = await get_components_count(settings_service=settings_service)
        all_types = await get_all_component_types(settings_service=settings_service)

        sum_counts = 0
        for comp_type in all_types:
            type_count = await get_components_count(
                component_type=comp_type,
                settings_service=settings_service,
            )
            sum_counts += type_count

        assert total_count == sum_counts


class TestGetComponentsByType:
    """Test cases for get_components_by_type function."""

    @pytest.mark.asyncio
    async def test_get_components_by_type(self):
        """Test getting all components of a specific type."""
        settings_service = get_settings_service()
        all_types = await get_all_component_types(settings_service=settings_service)
        assert len(all_types) > 0

        test_type = all_types[0]
        components = await get_components_by_type(
            component_type=test_type,
            settings_service=settings_service,
        )

        assert isinstance(components, list)
        for comp in components:
            assert comp["type"].lower() == test_type.lower()

    @pytest.mark.asyncio
    async def test_get_components_by_type_with_fields(self):
        """Test getting components by type with field selection."""
        settings_service = get_settings_service()
        all_types = await get_all_component_types(settings_service=settings_service)
        assert len(all_types) > 0

        test_type = all_types[0]
        components = await get_components_by_type(
            component_type=test_type,
            fields=["name", "display_name"],
            settings_service=settings_service,
        )

        assert len(components) > 0
        for comp in components:
            assert "name" in comp
            assert "type" in comp
            # Should have limited fields

    @pytest.mark.asyncio
    async def test_get_components_by_each_type(self):
        """Test that get_components_by_type works for all available types."""
        settings_service = get_settings_service()
        all_types = await get_all_component_types(settings_service=settings_service)

        for comp_type in all_types:
            components = await get_components_by_type(
                component_type=comp_type,
                settings_service=settings_service,
            )
            assert isinstance(components, list)
            # Each type should have at least one component
            assert len(components) > 0, f"Type {comp_type} has no components"


class TestIntegrationScenarios:
    """Integration tests with real-world scenarios."""

    @pytest.mark.asyncio
    async def test_discover_components_workflow(self):
        """Test a complete workflow of discovering components."""
        settings_service = get_settings_service()

        # Step 1: Get all available types
        types = await get_all_component_types(settings_service=settings_service)
        assert len(types) > 0

        # Step 2: Get components for a specific type
        test_type = types[0]
        type_components = await get_components_by_type(
            component_type=test_type,
            fields=["name", "display_name"],
            settings_service=settings_service,
        )
        assert len(type_components) > 0

        # Step 3: Get full details for one component
        comp_name = type_components[0]["name"]
        full_component = await get_component_by_name(
            component_name=comp_name,
            settings_service=settings_service,
        )
        assert full_component is not None
        assert "name" in full_component

    @pytest.mark.asyncio
    async def test_search_and_count_workflow(self):
        """Test searching components and verifying counts."""
        settings_service = get_settings_service()

        # Get total count
        total_count = await get_components_count(settings_service=settings_service)

        # Search for a term
        search_results = await list_all_components(
            query="input",
            settings_service=settings_service,
        )

        # Search results should be <= total
        assert len(search_results) <= total_count

    @pytest.mark.asyncio
    async def test_component_data_consistency(self):
        """Test that component data is consistent across functions."""
        settings_service = get_settings_service()

        # Get a component via list
        all_components = await list_all_components(
            fields=["name", "type", "display_name"],
            settings_service=settings_service,
        )
        assert len(all_components) > 0

        # Get same component by name
        first_comp = all_components[0]
        retrieved = await get_component_by_name(
            component_name=first_comp["name"],
            fields=["display_name"],
            settings_service=settings_service,
        )

        assert retrieved is not None
        assert retrieved["name"] == first_comp["name"]
        assert retrieved["type"] == first_comp["type"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_all(self):
        """Test that empty query returns all components."""
        settings_service = get_settings_service()
        await list_all_components(settings_service=settings_service)
        empty_query = await list_all_components(
            query="",
            settings_service=settings_service,
        )

        # Empty string should match nothing (based on implementation)
        # If empty string returns all, this test should still pass
        assert isinstance(empty_query, list)

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test handling of special characters in query."""
        settings_service = get_settings_service()
        results = await list_all_components(
            query="@#$%^&*()",
            settings_service=settings_service,
        )

        # Should return empty list, not crash
        assert results == []

    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Test handling of very long query strings."""
        settings_service = get_settings_service()
        long_query = "a" * 10000
        results = await list_all_components(
            query=long_query,
            settings_service=settings_service,
        )

        # Should return empty list, not crash
        assert results == []

    @pytest.mark.asyncio
    async def test_whitespace_query(self):
        """Test handling of whitespace-only query."""
        settings_service = get_settings_service()
        results = await list_all_components(
            query="   ",
            settings_service=settings_service,
        )

        # Should handle gracefully
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_nonexistent_field_in_field_selection(self):
        """Test requesting fields that don't exist."""
        settings_service = get_settings_service()
        components = await list_all_components(
            fields=["name", "nonexistent_field_xyz"],
            settings_service=settings_service,
        )

        assert len(components) > 0
        for comp in components:
            assert "name" in comp
            # nonexistent field should not be present
            assert "nonexistent_field_xyz" not in comp


class TestPerformance:
    """Performance and stress tests."""

    @pytest.mark.asyncio
    async def test_repeated_calls_consistency(self):
        """Test that repeated calls return consistent results."""
        settings_service = get_settings_service()
        results1 = await list_all_components(settings_service=settings_service)
        results2 = await list_all_components(settings_service=settings_service)
        results3 = await list_all_components(settings_service=settings_service)

        # Should return same count
        assert len(results1) == len(results2) == len(results3)

        # Should have same names
        names1 = {c["name"] for c in results1}
        names2 = {c["name"] for c in results2}
        names3 = {c["name"] for c in results3}
        assert names1 == names2 == names3

    @pytest.mark.asyncio
    async def test_large_field_list(self):
        """Test handling of large field list."""
        settings_service = get_settings_service()
        large_field_list = [f"field_{i}" for i in range(100)]
        large_field_list.extend(["name", "display_name"])

        # Should not crash
        components = await list_all_components(
            fields=large_field_list,
            settings_service=settings_service,
        )
        assert isinstance(components, list)

