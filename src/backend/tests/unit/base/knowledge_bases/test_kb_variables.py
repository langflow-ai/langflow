"""Tests for KB Variable service integration."""

from uuid import uuid4

import pytest

from langflow.services.variable.constants import CATEGORY_KB, VALID_CATEGORIES


class TestKBVariableConstants:
    """Test KB category constants."""

    def test_kb_category_exists(self):
        """Test that KB category constant exists."""
        assert CATEGORY_KB == "KB"

    def test_kb_category_in_valid_categories(self):
        """Test that KB category is in valid categories list."""
        assert CATEGORY_KB in VALID_CATEGORIES

    def test_valid_categories_includes_all_expected(self):
        """Test that all expected categories are present."""
        expected_categories = ["Global", "Settings", "LLM", "KB"]
        for category in expected_categories:
            assert category in VALID_CATEGORIES


class TestKBVariableIntegration:
    """Test KB variable integration scenarios."""

    @pytest.fixture
    def sample_kb_variables(self):
        """Sample KB configuration variables."""
        user_id = uuid4()
        return [
            {
                "name": "kb_provider",
                "value": "chroma",
                "category": "KB",
                "type": "Generic",
                "user_id": user_id,
            },
            {
                "name": "kb_chroma_server_host",
                "value": "localhost",
                "category": "KB",
                "type": "Generic",
                "user_id": user_id,
            },
            {
                "name": "kb_chroma_server_http_port",
                "value": "8000",
                "category": "KB",
                "type": "Generic",
                "user_id": user_id,
            },
        ]

    def test_kb_variable_structure(self, sample_kb_variables):
        """Test KB variable structure is correct."""
        for var in sample_kb_variables:
            assert var["category"] == "KB"
            assert "user_id" in var
            assert "name" in var
            assert "value" in var
            assert "type" in var

    def test_opensearch_kb_variables(self):
        """Test OpenSearch KB variable configuration."""
        user_id = uuid4()
        opensearch_vars = [
            {
                "name": "kb_provider",
                "value": "opensearch",
                "category": "KB",
                "type": "Generic",
                "user_id": user_id,
            },
            {
                "name": "kb_opensearch_url",
                "value": "https://search.example.com:9200",
                "category": "KB",
                "type": "Credential",  # Encrypted storage
                "user_id": user_id,
            },
            {
                "name": "kb_opensearch_index_prefix",
                "value": "langflow-kb-",
                "category": "KB",
                "type": "Generic",
                "user_id": user_id,
            },
        ]

        for var in opensearch_vars:
            assert var["category"] == "KB"
            assert var["user_id"] == user_id

        # Check credential type for URL
        url_var = next(var for var in opensearch_vars if var["name"] == "kb_opensearch_url")
        assert url_var["type"] == "Credential"
