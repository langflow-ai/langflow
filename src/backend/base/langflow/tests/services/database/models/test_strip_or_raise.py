from __future__ import annotations

import pytest
from langflow.services.database.utils import strip_or_raise


class TestStripOrRaise:
    """Tests for the strip_or_raise utility."""

    def test_returns_stripped_value(self):
        assert strip_or_raise("  hello  ", "field") == "hello"

    def test_passthrough_clean_value(self):
        assert strip_or_raise("hello", "field") == "hello"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="my_field must not be empty"):
            strip_or_raise("", "my_field")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="my_field must not be empty"):
            strip_or_raise("   ", "my_field")

    def test_field_name_appears_in_error(self):
        with pytest.raises(ValueError, match="provider_url"):
            strip_or_raise("", "provider_url")
