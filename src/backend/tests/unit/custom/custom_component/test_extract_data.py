"""Unit tests for Component.extract_data method."""

import pandas as pd
import pytest
from lfx.custom.custom_component.component import Component
from lfx.schema.message import Message


class TestExtractData:
    """Test suite for Component.extract_data method."""

    @pytest.fixture
    def component(self):
        """Create a basic component instance for testing."""
        return Component()

    def test_extract_data_with_dataframe(self, component):
        """Test that extract_data returns DataFrame unchanged."""
        # Arrange
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})

        # Act
        result = component.extract_data(df)

        # Assert
        assert isinstance(result, pd.DataFrame)
        assert result is df  # Should return the same object
        pd.testing.assert_frame_equal(result, df)

    def test_extract_data_with_series(self, component):
        """Test that extract_data returns Series unchanged."""
        # Arrange
        series = pd.Series([1, 2, 3, 4, 5], name="test_series")

        # Act
        result = component.extract_data(series)

        # Assert
        assert isinstance(result, pd.Series)
        assert result is series  # Should return the same object
        pd.testing.assert_series_equal(result, series)

    def test_extract_data_with_message(self, component):
        """Test that extract_data handles Message objects correctly."""
        # Arrange
        message = Message(text="Test message")

        # Act
        result = component.extract_data(message)

        # Assert
        assert result == "Test message"
        assert component.status == "Test message"

    def test_extract_data_with_message_no_text(self, component):
        """Test that extract_data handles Message with no text."""
        # Arrange
        message = Message(text=None)

        # Act
        result = component.extract_data(message)

        # Assert
        assert result == "No text available"

    def test_extract_data_with_dict(self, component):
        """Test that extract_data handles dict correctly."""
        # Arrange
        data = {"key1": "value1", "key2": "value2"}

        # Act
        result = component.extract_data(data)

        # Assert
        assert result == data

    def test_extract_data_with_string(self, component):
        """Test that extract_data handles string correctly."""
        # Arrange
        data = "test string"

        # Act
        result = component.extract_data(data)

        # Assert
        assert result == data

    def test_extract_data_dataframe_not_processed_by_hasattr(self, component):
        """Test that DataFrame bypasses hasattr checks.

        This is a regression test to ensure DataFrames are not incorrectly
        processed by downstream hasattr checks for .data or .model_dump attributes.
        """
        # Arrange
        df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})

        # Act
        result = component.extract_data(df)

        # Assert
        # The result should be the DataFrame itself, not processed further
        assert isinstance(result, pd.DataFrame)
        assert result is df
        # Verify it wasn't converted to dict or other format
        assert not isinstance(result, dict)
        assert not isinstance(result, str)

    def test_extract_data_series_not_processed_by_hasattr(self, component):
        """Test that Series bypasses hasattr checks.

        This is a regression test to ensure Series are not incorrectly
        processed by downstream hasattr checks for .data or .model_dump attributes.
        """
        # Arrange
        series = pd.Series([10, 20, 30])

        # Act
        result = component.extract_data(series)

        # Assert
        # The result should be the Series itself, not processed further
        assert isinstance(result, pd.Series)
        assert result is series
        # Verify it wasn't converted to dict or other format
        assert not isinstance(result, dict)
        assert not isinstance(result, str)


# Made with Bob
