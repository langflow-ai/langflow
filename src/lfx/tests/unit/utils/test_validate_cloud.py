"""Unit tests for the validate_cloud module."""

import os
from unittest.mock import patch

import pytest
from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component


class TestRaiseErrorIfAstraCloudDisableComponent:
    """Test suite for the raise_error_if_astra_cloud_disable_component function."""

    def test_raises_error_when_env_var_is_true(self):
        """Test that ValueError is raised when ASTRA_CLOUD_DISABLE_COMPONENT is 'true'."""
        with (
            patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}),
            pytest.raises(ValueError, match="Component disabled in cloud"),
        ):
            raise_error_if_astra_cloud_disable_component("Component disabled in cloud")

    def test_raises_error_when_env_var_is_true_uppercase(self):
        """Test that ValueError is raised when ASTRA_CLOUD_DISABLE_COMPONENT is 'TRUE'."""
        with (
            patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "TRUE"}),
            pytest.raises(ValueError, match="Test error message"),
        ):
            raise_error_if_astra_cloud_disable_component("Test error message")

    def test_raises_error_when_env_var_is_true_with_whitespace(self):
        """Test that ValueError is raised when ASTRA_CLOUD_DISABLE_COMPONENT is 'true' with whitespace."""
        with (
            patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "  true  "}),
            pytest.raises(ValueError, match="Whitespace test"),
        ):
            raise_error_if_astra_cloud_disable_component("Whitespace test")

    def test_no_error_when_env_var_is_false(self):
        """Test that no error is raised when ASTRA_CLOUD_DISABLE_COMPONENT is 'false'."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "false"}):
            # Should not raise any exception
            raise_error_if_astra_cloud_disable_component("This should not be raised")

    def test_no_error_when_env_var_is_not_set(self):
        """Test that no error is raised when ASTRA_CLOUD_DISABLE_COMPONENT is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise any exception
            raise_error_if_astra_cloud_disable_component("This should not be raised")

    def test_no_error_when_env_var_is_empty_string(self):
        """Test that no error is raised when ASTRA_CLOUD_DISABLE_COMPONENT is empty."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": ""}):
            # Should not raise any exception
            raise_error_if_astra_cloud_disable_component("This should not be raised")

    def test_no_error_when_env_var_has_invalid_value(self):
        """Test that no error is raised when ASTRA_CLOUD_DISABLE_COMPONENT has an invalid value."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "invalid"}):
            # Should not raise any exception
            raise_error_if_astra_cloud_disable_component("This should not be raised")

    def test_no_error_when_env_var_is_1(self):
        """Test that no error is raised when ASTRA_CLOUD_DISABLE_COMPONENT is '1'."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "1"}):
            # Should not raise any exception (only "true" string should trigger)
            raise_error_if_astra_cloud_disable_component("This should not be raised")

    def test_custom_error_message(self):
        """Test that the custom error message is properly raised."""
        custom_msg = "Custom error: This component cannot be used in Astra Cloud environment"
        with (
            patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}),
            pytest.raises(ValueError, match=custom_msg),
        ):
            raise_error_if_astra_cloud_disable_component(custom_msg)

    def test_error_message_with_special_characters(self):
        """Test that error messages with special characters are handled correctly."""
        special_msg = "Error: Component [LocalDB] cannot be used! Contact support@example.com"
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            with pytest.raises(ValueError, match="Error: Component") as exc_info:
                raise_error_if_astra_cloud_disable_component(special_msg)
            assert str(exc_info.value) == special_msg

    @pytest.mark.parametrize(
        ("env_value", "should_raise"),
        [
            ("true", True),
            ("TRUE", True),
            ("True", True),
            ("TrUe", True),
            ("  true  ", True),
            ("\ttrue\n", True),
            ("false", False),
            ("FALSE", False),
            ("False", False),
            ("0", False),
            ("1", False),
            ("yes", False),
            ("no", False),
            ("", False),
            ("random", False),
        ],
    )
    def test_various_env_var_values(self, env_value: str, *, should_raise: bool):
        """Test the function with various environment variable values."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": env_value}):
            if should_raise:
                with pytest.raises(ValueError, match="Test message"):
                    raise_error_if_astra_cloud_disable_component("Test message")
            else:
                # Should not raise
                raise_error_if_astra_cloud_disable_component("Test message")
