"""Unit tests for template_search module using real templates."""

import tempfile

import pytest
from langflow.agentic.utils import (
    get_all_tags,
    get_template_by_id,
    get_templates_count,
    list_templates,
)


class TestListTemplates:
    """Test cases for list_templates function using real templates."""

    def test_list_all_templates(self):
        """Test listing all templates without filters."""
        templates = list_templates()

        assert len(templates) > 0
        assert all(isinstance(t, dict) for t in templates)
        assert get_templates_count() == len(templates)

    def test_list_with_field_selection(self):
        """Test listing templates with specific field selection."""
        templates = list_templates(fields=["id", "name"])

        assert len(templates) > 0
        for template in templates:
            assert "id" in template
            assert "name" in template
            # Should only have requested fields
            assert len(template) == 2

    def test_list_with_multiple_fields(self):
        """Test listing with multiple field selection."""
        templates = list_templates(fields=["id", "name", "description", "tags"])

        assert len(templates) > 0
        for template in templates:
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "tags" in template
            # Should not have data field
            assert "data" not in template

    def test_search_by_query_case_insensitive(self):
        """Test that search is case-insensitive."""
        # Search for "basic" in different cases
        results_lower = list_templates(query="basic")
        results_upper = list_templates(query="BASIC")
        results_mixed = list_templates(query="BaSiC")

        # All should return same number of results
        assert len(results_lower) == len(results_upper) == len(results_mixed)

    def test_search_by_query_matches_name(self):
        """Test searching templates by query string in name."""
        # Search for "agent" which should exist in template names
        results = list_templates(query="agent")

        # Should find at least one result
        assert len(results) > 0
        # Verify results contain the search term in name or description
        for result in results:
            name_match = "agent" in result.get("name", "").lower()
            desc_match = "agent" in result.get("description", "").lower()
            assert name_match or desc_match

    def test_search_by_query_matches_description(self):
        """Test searching templates by query string in description."""
        # Get all templates first
        all_templates = list_templates()
        assert len(all_templates) > 0

        # Pick a word from a description
        sample_desc = all_templates[0].get("description", "")
        if sample_desc:
            # Get first word that's reasonably long
            words = [w for w in sample_desc.lower().split() if len(w) > 4]
            if words:
                search_word = words[0]
                results = list_templates(query=search_word)
                assert len(results) > 0

    def test_filter_by_single_tag(self):
        """Test filtering templates by a single tag."""
        # Get all available tags first
        all_tags = get_all_tags()
        assert len(all_tags) > 0

        # Test with first available tag
        test_tag = all_tags[0]
        results = list_templates(tags=[test_tag])

        assert len(results) > 0
        # Verify all results have the requested tag
        for result in results:
            assert test_tag in result.get("tags", [])

    def test_filter_by_multiple_tags(self):
        """Test filtering by multiple tags (OR logic)."""
        all_tags = get_all_tags()
        if len(all_tags) >= 2:
            # Use first two tags
            test_tags = all_tags[:2]
            results = list_templates(tags=test_tags)

            assert len(results) > 0
            # Verify each result has at least one of the requested tags
            for result in results:
                result_tags = result.get("tags", [])
                assert any(tag in result_tags for tag in test_tags)

    def test_filter_by_tag_with_field_selection(self):
        """Test combining tag filter with field selection."""
        all_tags = get_all_tags()
        if len(all_tags) > 0:
            test_tag = all_tags[0]
            results = list_templates(tags=[test_tag], fields=["name", "tags"])

            assert len(results) > 0
            for result in results:
                assert "name" in result
                assert "tags" in result
                assert "description" not in result
                assert "data" not in result
                assert test_tag in result["tags"]

    def test_combined_query_and_tag_filter(self):
        """Test combining query search with tag filtering."""
        all_tags = get_all_tags()
        if "agents" in all_tags:
            # Combine query and tag filter
            results = list_templates(query="agent", tags=["agents"])

            # Should return results that match both criteria
            for result in results:
                # Must have the tag
                assert "agents" in result.get("tags", [])
                # Must match query in name or description
                name_match = "agent" in result.get("name", "").lower()
                desc_match = "agent" in result.get("description", "").lower()
                assert name_match or desc_match

    def test_no_matches_invalid_query(self):
        """Test that empty list is returned when no templates match query."""
        results = list_templates(query="xyznonexistentquery123")
        assert results == []

    def test_no_matches_invalid_tag(self):
        """Test that empty list is returned when no templates match tag."""
        results = list_templates(tags=["nonexistent-tag-xyz"])
        assert results == []

    def test_empty_fields_returns_all_fields(self):
        """Test that None fields returns all template data."""
        results = list_templates(fields=None)

        assert len(results) > 0
        # Check that multiple fields are present
        for result in results:
            assert "id" in result
            assert "name" in result
            assert "description" in result
            assert len(result) > 3  # Should have many fields

    def test_nonexistent_directory(self):
        """Test handling of nonexistent directory."""
        with pytest.raises(FileNotFoundError, match="Starter projects directory not found"):
            list_templates(starter_projects_path="/nonexistent/path")


class TestGetTemplateById:
    """Test cases for get_template_by_id function."""

    def test_get_existing_template(self):
        """Test retrieving an existing template by ID."""
        # Get first template ID
        templates = list_templates(fields=["id"])
        assert len(templates) > 0

        first_id = templates[0]["id"]
        template = get_template_by_id(first_id)

        assert template is not None
        assert template["id"] == first_id

    def test_get_template_with_field_selection(self):
        """Test retrieving template with specific fields."""
        templates = list_templates(fields=["id"])
        assert len(templates) > 0

        first_id = templates[0]["id"]
        template = get_template_by_id(first_id, fields=["name", "tags"])

        assert template is not None
        assert "name" in template
        assert "tags" in template
        assert "data" not in template

    def test_get_nonexistent_template(self):
        """Test that None is returned for nonexistent template ID."""
        template = get_template_by_id("00000000-0000-0000-0000-000000000000")
        assert template is None

    def test_get_all_fields(self):
        """Test retrieving template with all fields."""
        templates = list_templates(fields=["id"])
        assert len(templates) > 0

        first_id = templates[0]["id"]
        template = get_template_by_id(first_id, fields=None)

        assert template is not None
        # Should have multiple fields
        assert "id" in template
        assert "name" in template
        assert len(template) > 3

    def test_get_multiple_templates_by_id(self):
        """Test retrieving multiple templates by their IDs."""
        templates = list_templates(fields=["id"])
        assert len(templates) >= 2

        # Get first two templates
        for template_id in [t["id"] for t in templates[:2]]:
            result = get_template_by_id(template_id)
            assert result is not None
            assert result["id"] == template_id


class TestGetAllTags:
    """Test cases for get_all_tags function."""

    def test_get_all_unique_tags(self):
        """Test retrieving all unique tags from templates."""
        tags = get_all_tags()

        assert isinstance(tags, list)
        assert len(tags) > 0
        assert all(isinstance(tag, str) for tag in tags)

    def test_tags_are_sorted(self):
        """Test that returned tags are sorted alphabetically."""
        tags = get_all_tags()

        assert tags == sorted(tags)

    def test_tags_are_unique(self):
        """Test that returned tags have no duplicates."""
        tags = get_all_tags()

        assert len(tags) == len(set(tags))

    def test_tags_match_template_tags(self):
        """Test that returned tags match tags in templates."""
        all_tags = get_all_tags()
        templates = list_templates()

        # Collect all tags from templates
        template_tags = set()
        for template in templates:
            template_tags.update(template.get("tags", []))

        # Should match
        assert set(all_tags) == template_tags


class TestGetTemplatesCount:
    """Test cases for get_templates_count function."""

    def test_count_matches_list(self):
        """Test that count matches number of templates."""
        count = get_templates_count()
        templates = list_templates()

        assert count == len(templates)
        assert count > 0

    def test_count_empty_directory(self):
        """Test counting templates in an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            count = get_templates_count(starter_projects_path=tmpdir)
            assert count == 0


class TestTemplateStructure:
    """Test the structure and content of real templates."""

    def test_all_templates_have_required_fields(self):
        """Test that all templates have required fields."""
        templates = list_templates()

        required_fields = ["id", "name", "description"]
        for template in templates:
            for field in required_fields:
                assert field in template, f"Template {template.get('name')} missing {field}"

    def test_template_ids_are_unique(self):
        """Test that all template IDs are unique."""
        templates = list_templates(fields=["id"])

        ids = [t["id"] for t in templates]
        assert len(ids) == len(set(ids)), "Template IDs must be unique"

    def test_template_names_are_not_empty(self):
        """Test that template names are not empty."""
        templates = list_templates(fields=["name"])

        for template in templates:
            name = template.get("name", "")
            assert name.strip(), f"Template has empty name: {template}"

    def test_template_descriptions_exist(self):
        """Test that templates have descriptions."""
        templates = list_templates(fields=["name", "description"])

        for template in templates:
            desc = template.get("description", "")
            assert desc, f"Template {template.get('name')} has no description"

    def test_template_tags_are_lists(self):
        """Test that template tags are lists."""
        templates = list_templates(fields=["name", "tags"])

        for template in templates:
            tags = template.get("tags")
            if tags is not None:
                assert isinstance(tags, list), f"Tags in {template.get('name')} is not a list"

    def test_templates_have_data_field(self):
        """Test that templates have data field when requested."""
        templates = list_templates()

        for template in templates:
            assert "data" in template
            assert isinstance(template["data"], dict)


class TestSearchFunctionality:
    """Test search and filtering functionality with real data."""

    def test_search_common_terms(self):
        """Test searching for common terms."""
        common_terms = ["agent", "chat", "rag", "prompt"]

        for term in common_terms:
            results = list_templates(query=term)
            # At least some terms should have results
            if results:
                # Verify results actually contain the term
                for result in results:
                    name_lower = result.get("name", "").lower()
                    desc_lower = result.get("description", "").lower()
                    assert term in name_lower or term in desc_lower

    def test_search_partial_words(self):
        """Test that partial word search works."""
        # Get a template name
        templates = list_templates(fields=["name"])
        if templates:
            full_name = templates[0]["name"]
            # Search for part of the name
            partial = full_name[:5].lower()
            if len(partial) >= 3:
                results = list_templates(query=partial)
                assert len(results) > 0

    def test_filter_by_each_tag(self):
        """Test filtering by each available tag."""
        all_tags = get_all_tags()

        for tag in all_tags:
            results = list_templates(tags=[tag])
            assert len(results) > 0, f"No templates found for tag: {tag}"

            # Verify all results have the tag
            for result in results:
                assert tag in result.get("tags", []), f"Result missing tag {tag}"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_query_string(self):
        """Test that empty query string returns all templates."""
        results = list_templates(query="")
        all_templates = list_templates()

        # Empty string should return all templates
        assert len(results) == len(all_templates)

    def test_empty_tags_list(self):
        """Test that empty tags list returns all templates."""
        results = list_templates(tags=[])
        all_templates = list_templates()

        assert len(results) == len(all_templates)

    def test_whitespace_only_query(self):
        """Test handling of whitespace-only query."""
        results = list_templates(query="   ")
        # Whitespace-only should match nothing
        assert len(results) == 0

    def test_special_characters_in_query(self):
        """Test handling of special characters in query."""
        results = list_templates(query="@#$%^&*()")
        # Special chars unlikely to match
        assert len(results) == 0

    def test_very_long_query(self):
        """Test handling of very long query strings."""
        long_query = "a" * 10000
        results = list_templates(query=long_query)
        # Very long query unlikely to match
        assert len(results) == 0

    def test_field_selection_with_nonexistent_fields(self):
        """Test requesting fields that don't exist in templates."""
        results = list_templates(fields=["id", "nonexistent_field_xyz"])

        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert "nonexistent_field_xyz" not in result

    def test_none_query_treated_as_no_filter(self):
        """Test that None query is treated as no filter."""
        results_none = list_templates(query=None)
        results_all = list_templates()

        assert len(results_none) == len(results_all)

    def test_none_tags_treated_as_no_filter(self):
        """Test that None tags is treated as no filter."""
        results_none = list_templates(tags=None)
        results_all = list_templates()

        assert len(results_none) == len(results_all)


class TestPerformance:
    """Performance and stress tests with real data."""

    def test_large_field_list(self):
        """Test performance with large number of fields."""
        large_field_list = [f"field_{i}" for i in range(100)]
        large_field_list.extend(["id", "name", "description"])

        # Should not crash, just return available fields
        results = list_templates(fields=large_field_list)
        assert len(results) > 0

    def test_many_tags_filter(self):
        """Test filtering with many tags (most don't exist)."""
        many_tags = [f"tag_{i}" for i in range(100)]

        # Add one real tag
        real_tags = get_all_tags()
        if real_tags:
            many_tags.append(real_tags[0])

            results = list_templates(tags=many_tags)
            # Should return results for the one real tag
            assert len(results) > 0

    def test_repeated_calls_consistency(self):
        """Test that repeated calls return consistent results."""
        results1 = list_templates()
        results2 = list_templates()
        results3 = list_templates()

        # Should return same count
        assert len(results1) == len(results2) == len(results3)

        # Should have same IDs
        ids1 = {t["id"] for t in results1}
        ids2 = {t["id"] for t in results2}
        ids3 = {t["id"] for t in results3}

        assert ids1 == ids2 == ids3


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_discover_templates_workflow(self):
        """Test a complete workflow of discovering templates."""
        # Step 1: Get all available tags
        tags = get_all_tags()
        assert len(tags) > 0

        # Step 2: Get templates for a specific tag
        if tags:
            templates_for_tag = list_templates(tags=[tags[0]], fields=["id", "name"])
            assert len(templates_for_tag) > 0

            # Step 3: Get full details for one template
            if templates_for_tag:
                template_id = templates_for_tag[0]["id"]
                full_template = get_template_by_id(template_id)
                assert full_template is not None
                assert "data" in full_template

    def test_search_and_filter_workflow(self):
        """Test searching and then filtering results."""
        # Step 1: Search for templates
        search_results = list_templates(query="agent")

        if search_results:
            # Step 2: Get tags from results
            result_tags = set()
            for result in search_results:
                result_tags.update(result.get("tags", []))

            # Step 3: Filter by one of those tags
            if result_tags:
                filtered = list_templates(tags=[next(iter(result_tags))])
                assert len(filtered) > 0

    def test_pagination_simulation(self):
        """Test simulating pagination by limiting results."""
        all_templates = list_templates(fields=["id", "name"])

        if len(all_templates) > 5:
            # Simulate getting first page (first 5)
            page1 = all_templates[:5]
            # Simulate getting second page (next 5)
            page2 = all_templates[5:10]

            # Pages should not overlap
            page1_ids = {t["id"] for t in page1}
            page2_ids = {t["id"] for t in page2}
            assert page1_ids.isdisjoint(page2_ids)
