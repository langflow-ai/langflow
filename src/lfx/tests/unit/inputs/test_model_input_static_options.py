"""Tests for ModelInput static options preservation.

This module tests that when a component specifies static options for a ModelInput,
those options remain static and are not overridden by global user settings.
"""

from unittest.mock import MagicMock

from lfx.base.models.unified_models import update_model_options_in_build_config


class TestModelInputStaticOptions:
    """Test that ModelInput with static options doesn't get refreshed from global settings."""

    def test_static_options_preserved_on_initial_load(self):
        """When options are provided, they should be preserved and not refreshed."""
        # Setup: Component with static options
        component = MagicMock()
        component.user_id = "test_user"
        component.cache = {}
        component.log = MagicMock()

        static_options = [
            {"name": "custom-model-1", "provider": "Custom"},
            {"name": "custom-model-2", "provider": "Custom"},
        ]

        build_config = {"model": {"options": static_options}}

        # Mock the get_options_func that would normally fetch from global settings
        def mock_get_options(user_id):  # noqa: ARG001
            return [
                {"name": "gpt-4o", "provider": "OpenAI"},
                {"name": "claude-3", "provider": "Anthropic"},
            ]

        # Call with initial load (field_name=None)
        result = update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=mock_get_options,
            field_name=None,
            field_value=None,
        )

        # Verify: Static options should be preserved, NOT replaced with global options
        assert result["model"]["options"] == static_options
        assert result["model"]["options"] != mock_get_options("test_user")

    def test_static_options_preserved_on_refresh(self):
        """When refresh button is clicked, static options should still be preserved."""
        # Setup: Component with static options
        component = MagicMock()
        component.user_id = "test_user"
        component.cache = {}
        component.log = MagicMock()

        static_options = [
            {"name": "custom-model-1", "provider": "Custom"},
            {"name": "custom-model-2", "provider": "Custom"},
        ]

        build_config = {"model": {"options": static_options}}

        def mock_get_options(user_id):  # noqa: ARG001
            return [
                {"name": "gpt-4o", "provider": "OpenAI"},
                {"name": "claude-3", "provider": "Anthropic"},
            ]

        # First call: initial load to detect static options
        update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=mock_get_options,
            field_name=None,
            field_value=None,
        )

        # Second call: simulate refresh button click (field_name="model")
        result = update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=mock_get_options,
            field_name="model",
            field_value=[{"name": "custom-model-1", "provider": "Custom"}],
        )

        # Verify: Static options should STILL be preserved after refresh
        assert result["model"]["options"] == static_options

    def test_dynamic_options_still_refresh(self):
        """When no options are provided, dynamic refresh should still work."""
        # Setup: Component WITHOUT static options
        component = MagicMock()
        component.user_id = "test_user"
        component.cache = {}
        component.log = MagicMock()

        # No options initially
        build_config = {"model": {}}

        global_options = [
            {"name": "gpt-4o", "provider": "OpenAI"},
            {"name": "claude-3", "provider": "Anthropic"},
        ]

        def mock_get_options(user_id):  # noqa: ARG001
            return global_options

        # Call with initial load
        result = update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=mock_get_options,
            field_name=None,
            field_value=None,
        )

        # Verify: Should use global options since no static options were provided
        assert result["model"]["options"] == global_options

    def test_static_options_with_connect_other_models(self):
        """Static options with 'connect_other_models' should show handle but keep options."""
        # Setup: Component with static options
        component = MagicMock()
        component.user_id = "test_user"
        component.cache = {}
        component.log = MagicMock()

        static_options = [
            {"name": "custom-model-1", "provider": "Custom"},
        ]

        build_config = {"model": {"options": static_options, "input_types": []}}

        def mock_get_options(user_id):  # noqa: ARG001
            return [{"name": "gpt-4o", "provider": "OpenAI"}]

        # First call: initial load to detect static options
        update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=mock_get_options,
            field_name=None,
            field_value=None,
        )

        # Second call: user selects "connect_other_models"
        result = update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=mock_get_options,
            field_name="model",
            field_value="connect_other_models",
        )

        # Verify: Static options preserved AND handle shown
        assert result["model"]["options"] == static_options
        assert result["model"]["input_types"] == ["LanguageModel"]

    def test_empty_static_options_list_treated_as_dynamic(self):
        """An empty options list should be treated as dynamic, not static."""
        # Setup: Component with empty options list
        component = MagicMock()
        component.user_id = "test_user"
        component.cache = {}
        component.log = MagicMock()

        # Empty options list
        build_config = {"model": {"options": []}}

        global_options = [
            {"name": "gpt-4o", "provider": "OpenAI"},
        ]

        def mock_get_options(user_id):  # noqa: ARG001
            return global_options

        # Call with initial load
        result = update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=mock_get_options,
            field_name=None,
            field_value=None,
        )

        # Verify: Should treat empty list as dynamic and fetch global options
        assert result["model"]["options"] == global_options
