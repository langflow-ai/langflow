import pytest
from langflow.components.processing.regex import RegexExtractorComponent
from langflow.schema import Data
from langflow.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestRegexExtractorComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return RegexExtractorComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "input_text": "Contact us at test@example.com",
            "pattern": r"\b\w+@\w+\.\w+\b",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def test_successful_regex_extraction(self):
        # Test with email pattern
        component = RegexExtractorComponent(
            input_text="Contact us at test@example.com or support@test.com", pattern=r"\b\w+@\w+\.\w+\b"
        )

        result = component.extract_matches()
        assert isinstance(result, list)
        assert all(isinstance(item, Data) for item in result)
        assert len(result) == 2
        assert result[0].data["match"] == "test@example.com"
        assert result[1].data["match"] == "support@test.com"

    def test_no_matches_found(self):
        # Test with pattern that won't match
        component = RegexExtractorComponent(input_text="No email addresses here", pattern=r"\b\w+@\w+\.\w+\b")

        result = component.extract_matches()
        assert isinstance(result, list)
        assert len(result) == 0  # The implementation returns an empty list when no matches are found

    def test_invalid_regex_pattern(self):
        # Test with invalid regex pattern
        component = RegexExtractorComponent(
            input_text="Some text",
            pattern="[",  # Invalid regex pattern
        )

        result = component.extract_matches()
        assert isinstance(result, list)
        assert len(result) == 1
        assert "error" in result[0].data
        assert "Invalid regex pattern" in result[0].data["error"]

    def test_empty_input_text(self):
        # Test with empty input
        component = RegexExtractorComponent(input_text="", pattern=r"\b\w+@\w+\.\w+\b")

        result = component.extract_matches()
        assert isinstance(result, list)
        assert len(result) == 0  # The implementation returns an empty list when input is empty

    def test_get_matches_text_output(self):
        # Test the text output method
        component = RegexExtractorComponent(input_text="Contact: test@example.com", pattern=r"\b\w+@\w+\.\w+\b")

        result = component.get_matches_text()
        assert isinstance(result, Message)
        assert result.text == "test@example.com"

    def test_get_matches_text_no_matches(self):
        # Test text output with no matches
        component = RegexExtractorComponent(input_text="No email addresses", pattern=r"\b\w+@\w+\.\w+\b")

        result = component.get_matches_text()
        assert isinstance(result, Message)
        assert result.text == "No matches found"

    def test_get_matches_text_invalid_pattern(self):
        # Test text output with invalid pattern
        component = RegexExtractorComponent(
            input_text="Some text",
            pattern="[",  # Invalid regex pattern
        )

        result = component.get_matches_text()
        assert isinstance(result, Message)
        assert "Invalid regex pattern" in result.text
