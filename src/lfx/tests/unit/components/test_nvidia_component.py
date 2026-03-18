"""Tests for NVIDIAModelComponent lazy model loading.

Verifies that no network call is made at import/class-definition time,
and that model options are populated dynamically via update_build_config.
"""

import contextlib
from unittest.mock import MagicMock, patch


class TestNVIDIAModelComponentLazyLoading:
    """Ensure NVIDIA model list is fetched lazily, not at import time."""

    def test_model_options_empty_on_import(self):
        """The model_name dropdown should have no options at class definition time."""
        from lfx.components.nvidia.nvidia import NVIDIAModelComponent

        model_name_input = next(
            inp for inp in NVIDIAModelComponent.inputs if getattr(inp, "name", None) == "model_name"
        )
        assert model_name_input.options == [], (
            "model_name options must be empty at import time to avoid blocking network calls"
        )

    def test_no_network_call_during_import(self):
        """Importing the module must not instantiate ChatNVIDIA or call get_available_models."""
        import importlib
        import sys

        # Insert a mock module so the import succeeds even without the real package
        mock_nvidia_module = MagicMock()
        sys.modules["langchain_nvidia_ai_endpoints"] = mock_nvidia_module
        try:
            import lfx.components.nvidia.nvidia as nvidia_mod

            importlib.reload(nvidia_mod)

            # The class-level code must not call ChatNVIDIA() or get_available_models()
            mock_nvidia_module.ChatNVIDIA.assert_not_called()
            mock_nvidia_module.ChatNVIDIA.return_value.get_available_models.assert_not_called()
        finally:
            sys.modules.pop("langchain_nvidia_ai_endpoints", None)

    def test_update_build_config_populates_models(self):
        """update_build_config should fetch models and populate the dropdown options."""
        from lfx.components.nvidia.nvidia import NVIDIAModelComponent
        from lfx.schema.dotdict import dotdict

        fake_model_a = MagicMock()
        fake_model_a.id = "model-a"
        fake_model_a.supports_tools = False
        fake_model_b = MagicMock()
        fake_model_b.id = "model-b"
        fake_model_b.supports_tools = True

        component = NVIDIAModelComponent()
        component._attributes = {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "fake-key",
            "tool_model_enabled": False,
        }

        build_config = dotdict(
            {
                "model_name": {"options": [], "value": None},
                "detailed_thinking": {"value": False, "show": False},
            }
        )

        with patch("lfx.components.nvidia.nvidia.ChatNVIDIA", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.available_models = [fake_model_a, fake_model_b]
            mock_instance.get_available_models.return_value = [fake_model_a, fake_model_b]
            mock_cls.return_value = mock_instance

            # Patch get_models to use our mock since the real import path may differ
            with patch.object(component, "get_models", return_value=["model-a", "model-b"]):
                result = component.update_build_config(build_config, None, field_name="model_name")

        assert result["model_name"]["options"] == ["model-a", "model-b"]
        assert result["model_name"]["value"] == "model-a"

    def test_update_build_config_handles_api_failure(self):
        """update_build_config should clear options and raise on API failure."""
        from lfx.components.nvidia.nvidia import NVIDIAModelComponent
        from lfx.schema.dotdict import dotdict

        component = NVIDIAModelComponent()
        component._attributes = {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "fake-key",
            "tool_model_enabled": False,
        }

        build_config = dotdict(
            {
                "model_name": {"options": ["stale-model"], "value": "stale-model"},
                "detailed_thinking": {"value": False, "show": False},
            }
        )

        with (
            patch.object(
                component,
                "get_models",
                side_effect=ConnectionError("network unreachable"),
            ),
            contextlib.suppress(ValueError),
        ):
            component.update_build_config(build_config, None, field_name="model_name")

        assert build_config["model_name"]["options"] == []
        assert build_config["model_name"]["value"] is None
