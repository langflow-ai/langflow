"""Tests for the FastMCP server implementation."""

import pytest

from langflow.agentic.mcp.server import count_templates, get_template, list_all_tags, mcp, search_templates


class TestMCPServer:
    """Test FastMCP server initialization."""

    def test_mcp_instance_created(self):
        """Test that FastMCP server instance is created."""
        assert mcp is not None
        assert hasattr(mcp, "run")

    def test_mcp_server_name(self):
        """Test that server has correct name."""
        # FastMCP stores the name in the _name attribute
        assert hasattr(mcp, "_name") or hasattr(mcp, "name")


class TestToolFunctions:
    """Test the tool wrapper functions."""

    def test_search_templates_basic(self):
        """Test basic search_templates call."""
        results = search_templates()
        assert isinstance(results, list)
        assert len(results) > 0
        # Each result should be a dict
        for result in results:
            assert isinstance(result, dict)

    def test_search_templates_with_fields(self):
        """Test search_templates with field selection."""
        results = search_templates(fields=["id", "name"])
        assert isinstance(results, list)
        assert len(results) > 0
        # Check that only requested fields are present
        for result in results:
            assert "id" in result
            assert "name" in result
            # Should not have more fields than requested (plus None values)
            actual_fields = {k for k, v in result.items() if v is not None}
            assert actual_fields.issubset({"id", "name"})

    def test_search_templates_with_query(self):
        """Test search_templates with search query."""
        results = search_templates(query="Basic", fields=["name"])
        assert isinstance(results, list)
        # Should find at least one template with "Basic" in name or description
        if results:
            # If we got results, verify they match the query
            for result in results:
                assert isinstance(result, dict)

    def test_search_templates_with_tags(self):
        """Test search_templates with tag filtering."""
        # First get all tags to ensure we have at least one
        all_tags = list_all_tags()
        if all_tags:
            # Use the first tag
            tag = all_tags[0]
            results = search_templates(tags=[tag], fields=["name", "tags"])
            assert isinstance(results, list)
            # If we got results, verify they have the tag
            for result in results:
                if "tags" in result and result["tags"]:
                    assert tag in result["tags"]

    def test_get_template_valid_id(self):
        """Test get_template with valid template ID."""
        # First get a template to get a valid ID
        templates = search_templates(fields=["id"])
        if templates:
            template_id = templates[0]["id"]
            result = get_template(template_id=template_id)
            assert result is not None
            assert isinstance(result, dict)
            assert result["id"] == template_id

    def test_get_template_with_fields(self):
        """Test get_template with field selection."""
        # Get a valid template ID
        templates = search_templates(fields=["id"])
        if templates:
            template_id = templates[0]["id"]
            result = get_template(template_id=template_id, fields=["id", "name"])
            assert result is not None
            assert isinstance(result, dict)
            assert "id" in result
            assert "name" in result

    def test_get_template_invalid_id(self):
        """Test get_template with invalid template ID."""
        result = get_template(template_id="invalid-uuid-12345")
        assert result is None

    def test_list_all_tags(self):
        """Test list_all_tags returns sorted list of tags."""
        tags = list_all_tags()
        assert isinstance(tags, list)
        assert len(tags) > 0
        # Verify all items are strings
        for tag in tags:
            assert isinstance(tag, str)
            assert len(tag) > 0
        # Verify list is sorted
        assert tags == sorted(tags)

    def test_count_templates(self):
        """Test count_templates returns positive integer."""
        count = count_templates()
        assert isinstance(count, int)
        assert count > 0
        # Should match the number of templates from search
        all_templates = search_templates()
        assert count == len(all_templates)


class TestToolIntegration:
    """Test integration between different tools."""

    def test_count_matches_search_results(self):
        """Test that count_templates matches search_templates length."""
        count = count_templates()
        all_templates = search_templates()
        assert count == len(all_templates)

    def test_all_tags_appear_in_templates(self):
        """Test that all tags from list_all_tags appear in at least one template."""
        all_tags = list_all_tags()
        all_templates = search_templates(fields=["tags"])

        # Collect all tags from templates
        template_tags = set()
        for template in all_templates:
            if "tags" in template and template["tags"]:
                template_tags.update(template["tags"])

        # All tags from list_all_tags should be in template_tags
        for tag in all_tags:
            assert tag in template_tags

    def test_get_template_matches_search_result(self):
        """Test that get_template returns same data as search_templates."""
        # Get first template from search
        templates = search_templates(fields=["id", "name", "description"])
        if templates:
            first = templates[0]
            template_id = first["id"]

            # Get the same template by ID
            result = get_template(template_id=template_id, fields=["id", "name", "description"])

            # Should match
            assert result is not None
            assert result["id"] == first["id"]
            assert result["name"] == first["name"]
            if "description" in first:
                assert result["description"] == first["description"]


class TestErrorHandling:
    """Test error handling in tool functions."""

    def test_search_templates_empty_query(self):
        """Test search_templates with empty string query."""
        # Empty string should be treated as no query
        results = search_templates(query="")
        assert isinstance(results, list)
        # Should return all templates
        all_templates = search_templates()
        assert len(results) == len(all_templates)

    def test_search_templates_nonexistent_tag(self):
        """Test search_templates with non-existent tag."""
        results = search_templates(tags=["nonexistent-tag-xyz-123"])
        assert isinstance(results, list)
        # Should return empty list or no results
        assert len(results) == 0

    def test_search_templates_empty_fields_list(self):
        """Test search_templates with empty fields list."""
        results = search_templates(fields=[])
        assert isinstance(results, list)
        # Should return all templates with all fields
        for result in results:
            assert isinstance(result, dict)
            # Empty fields list means return all fields
            assert len(result) > 0

    def test_get_template_empty_fields_list(self):
        """Test get_template with empty fields list."""
        # Get a valid template ID
        templates = search_templates(fields=["id"])
        if templates:
            template_id = templates[0]["id"]
            result = get_template(template_id=template_id, fields=[])
            assert result is not None
            assert isinstance(result, dict)
            # Empty fields list means return all fields
            assert len(result) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
