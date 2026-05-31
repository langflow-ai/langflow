"""Tests for NVIDIAModelComponent lazy model loading.

Verifies that no network call is made at import/class-definition time,
and that model options are populated dynamically via update_build_config.
"""

import contextlib
from unittest.mock import MagicMock, patch


def _mock_model(model_id: str):
    model = MagicMock()
    model.id = model_id
    return model


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


class TestNVIDIAComponentModelSelection:
    def test_rerank_update_preserves_selected_model(self):
        from lfx.components.nvidia.nvidia_rerank import NvidiaRerankComponent
        from lfx.schema.dotdict import dotdict

        component = NvidiaRerankComponent()
        build_config = dotdict(
            {
                "model": {
                    "options": ["nv-rerank-qa-mistral-4b:1"],
                    "value": "nv-rerank-qa-mistral-4b:1",
                }
            }
        )
        compressor = MagicMock()
        compressor.available_models = [
            _mock_model("nvidia/llama-3.2-nv-rerankqa-1b-v1"),
            _mock_model("nv-rerank-qa-mistral-4b:1"),
        ]

        with patch.object(component, "build_compressor", return_value=compressor):
            result = component.update_build_config(
                build_config,
                "https://integrate.api.nvidia.com/v1",
                field_name="base_url",
            )

        assert result["model"]["options"] == [
            "nvidia/llama-3.2-nv-rerankqa-1b-v1",
            "nv-rerank-qa-mistral-4b:1",
        ]
        assert result["model"]["value"] == "nv-rerank-qa-mistral-4b:1"

    def test_embedding_update_preserves_selected_model(self):
        from lfx.components.nvidia.nvidia_embedding import NVIDIAEmbeddingsComponent
        from lfx.schema.dotdict import dotdict

        component = NVIDIAEmbeddingsComponent()
        build_config = dotdict(
            {
                "model": {
                    "options": ["snowflake/arctic-embed-I"],
                    "value": "snowflake/arctic-embed-I",
                }
            }
        )
        embeddings = MagicMock()
        embeddings.available_models = [
            _mock_model("nvidia/nv-embed-v1"),
            _mock_model("snowflake/arctic-embed-I"),
        ]

        with patch.object(component, "build_embeddings", return_value=embeddings):
            result = component.update_build_config(
                build_config,
                "https://integrate.api.nvidia.com/v1",
                field_name="base_url",
            )

        assert result["model"]["options"] == ["nvidia/nv-embed-v1", "snowflake/arctic-embed-I"]
        assert result["model"]["value"] == "snowflake/arctic-embed-I"

    def test_rerank_update_falls_back_when_selected_model_is_unavailable(self):
        from lfx.components.nvidia.nvidia_rerank import NvidiaRerankComponent
        from lfx.schema.dotdict import dotdict

        component = NvidiaRerankComponent()
        build_config = dotdict({"model": {"options": ["removed-model"], "value": "removed-model"}})
        compressor = MagicMock()
        compressor.available_models = [_mock_model("model-a"), _mock_model("model-b")]

        with patch.object(component, "build_compressor", return_value=compressor):
            result = component.update_build_config(
                build_config,
                "https://integrate.api.nvidia.com/v1",
                field_name="base_url",
            )

        assert result["model"]["options"] == ["model-a", "model-b"]
        assert result["model"]["value"] == "model-a"
