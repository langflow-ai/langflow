from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langflow.services.database.utils import validate_non_empty_string


class TestValidateNonEmptyString:
    """Tests for the validate_non_empty_string utility."""

    def _make_info(self, field_name: str) -> MagicMock:
        info = MagicMock()
        info.field_name = field_name
        return info

    def test_returns_stripped_value(self):
        assert validate_non_empty_string("  hello  ", self._make_info("name")) == "hello"

    def test_passthrough_clean_value(self):
        assert validate_non_empty_string("hello", self._make_info("name")) == "hello"

    def test_empty_string_raises_with_field_name(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            validate_non_empty_string("", self._make_info("name"))

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="provider_url must not be empty"):
            validate_non_empty_string("   ", self._make_info("provider_url"))

    def test_fallback_field_name_when_info_lacks_attribute(self):
        """When info has no field_name attribute, falls back to 'Field'."""
        info = object()  # no field_name attribute
        with pytest.raises(ValueError, match="Field must not be empty"):
            validate_non_empty_string("", info)
