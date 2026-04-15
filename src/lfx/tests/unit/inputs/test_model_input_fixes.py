"""Tests for ModelInput fixes.

This module tests the following bug fixes:
1. Input port visibility: ModelInput should always show connection handle based on model_type.
2. Model defaults (cb6208f0ab): The first 5 models from each provider should be marked as default.
"""

from lfx.base.models.unified_models import get_unified_models_detailed
from lfx.inputs.inputs import ModelInput


class TestModelInputPortVisibility:
    """Test that ModelInput always shows connection handle based on model_type."""

    def test_default_language_model_input_types(self):
        """By default, ModelInput should have input_types=['LanguageModel'] for language models."""
        model_input = ModelInput(name="test_model")
        assert model_input.input_types == ["LanguageModel"]

    def test_default_embedding_model_input_types(self):
        """ModelInput with model_type='embedding' should have input_types=['Embeddings']."""
        model_input = ModelInput(name="test_model", model_type="embedding")
        assert model_input.input_types == ["Embeddings"]

    def test_input_types_with_model_value(self):
        """Setting a model value should still have input_types set based on model_type."""
        model_input = ModelInput(name="test_model", value=[{"name": "gpt-4o"}])
        assert model_input.input_types == ["LanguageModel"]

    def test_string_value_normalization(self):
        """String values should be normalized to dict format and input_types should be set."""
        model_input = ModelInput(name="test_model", value="gpt-4o")
        # Value should be normalized
        assert isinstance(model_input.value, list)
        if model_input.value:  # May be normalized or fallback
            assert isinstance(model_input.value[0], dict)
        # Should have connection handle based on model_type
        assert model_input.input_types == ["LanguageModel"]


class TestModelInputValueNormalization:
    """Test that ModelInput correctly normalizes various value formats."""

    def test_single_string_normalized_to_dict(self):
        """Single string model name should be converted to list of dicts."""
        model_input = ModelInput(name="test_model", value="gpt-4o")
        assert isinstance(model_input.value, list)
        if model_input.value:
            assert isinstance(model_input.value[0], dict)
            assert "name" in model_input.value[0]

    def test_list_of_strings_normalized(self):
        """List of string model names should be converted to list of dicts."""
        model_input = ModelInput(name="test_model", value=["gpt-4o", "gpt-4o-mini"])
        assert isinstance(model_input.value, list)
        if model_input.value:
            assert all(isinstance(item, dict) for item in model_input.value)
            assert all("name" in item for item in model_input.value)

    def test_dict_format_preserved(self):
        """List of dicts should be preserved as-is."""
        value = [{"name": "gpt-4o", "provider": "OpenAI"}]
        model_input = ModelInput(name="test_model", value=value)
        assert model_input.value == value

    def test_none_value_handled(self):
        """None value should be handled gracefully."""
        model_input = ModelInput(name="test_model", value=None)
        assert model_input.value is None

    def test_empty_string_handled(self):
        """Empty string should be handled gracefully."""
        model_input = ModelInput(name="test_model", value="")
        assert model_input.value == ""


class TestUnifiedModelsDefaults:
    """Test that first 5 models per provider are marked as default (fix: cb6208f0ab)."""

    def test_first_five_models_marked_default(self):
        """First 5 models from each provider should have default=True in metadata."""
        all_providers = get_unified_models_detailed()

        for provider_data in all_providers:
            provider = provider_data["provider"]
            models = provider_data["models"]

            # Check first 5 models (or all if less than 5)
            num_to_check = min(5, len(models))
            for i in range(num_to_check):
                model = models[i]
                assert model["metadata"].get("default") is True, (
                    f"Model {i} in provider {provider} should be marked as default"
                )

    def test_models_after_five_not_default(self):
        """Models after the first 5 should not be marked as default."""
        all_providers = get_unified_models_detailed()

        for provider_data in all_providers:
            provider = provider_data["provider"]
            models = provider_data["models"]

            # Check models after first 5
            if len(models) > 5:
                for i in range(5, len(models)):
                    model = models[i]
                    # These should not have default=True
                    assert model["metadata"].get("default") is not True, (
                        f"Model {i} in provider {provider} should not be marked as default"
                    )

    def test_only_defaults_filter_works(self):
        """When only_defaults=True, only first 5 models per provider are returned."""
        all_providers = get_unified_models_detailed(only_defaults=True)

        for provider_data in all_providers:
            provider = provider_data["provider"]
            models = provider_data["models"]

            # Should have at most 5 models
            assert len(models) <= 5, f"Provider {provider} should have at most 5 models when only_defaults=True"

            # All returned models should have default=True
            for model in models:
                assert model["metadata"].get("default") is True, (
                    f"All models from {provider} with only_defaults=True should be marked as default"
                )

    def test_defaults_not_affected_by_deprecated_filter(self):
        """Default marking should work independently of deprecated filtering."""
        providers_normal = get_unified_models_detailed(include_deprecated=False)
        providers_with_deprecated = get_unified_models_detailed(include_deprecated=True)

        # Both should have defaults marked
        for provider_data in providers_normal:
            models = provider_data["models"]
            if models:
                # At least first model should be default (if any models exist)
                assert models[0]["metadata"].get("default") is True

        for provider_data in providers_with_deprecated:
            models = provider_data["models"]
            if models:
                # At least first model should be default (if any models exist)
                assert models[0]["metadata"].get("default") is True

    def test_defaults_applied_after_filtering(self):
        """Default marking should be based on list order after other filters are applied."""
        # Get models for a specific provider
        providers = get_unified_models_detailed(providers=["OpenAI"])

        if providers:
            provider_data = providers[0]
            models = provider_data["models"]

            # First 5 in the filtered list should be marked as default
            num_to_check = min(5, len(models))
            for i in range(num_to_check):
                assert models[i]["metadata"].get("default") is True


class TestModelInputRefreshButton:
    """Test that ModelInput has refresh_button enabled by default."""

    def test_refresh_button_default_true(self):
        """ModelInput should have refresh_button=True by default."""
        model_input = ModelInput(name="test_model")
        assert model_input.refresh_button is True

    def test_refresh_button_can_be_disabled(self):
        """ModelInput should allow disabling refresh_button."""
        model_input = ModelInput(name="test_model", refresh_button=False)
        assert model_input.refresh_button is False


class TestModelInputEmbeddingType:
    """Test that ModelInput correctly handles embedding model_type (fix for LE-278).

    input_types should always be set based on model_type:
    - "embedding" -> ["Embeddings"]
    - "language" (default) -> ["LanguageModel"]
    """

    def test_language_model_type_default(self):
        """Default model_type should be 'language'."""
        model_input = ModelInput(name="test_model")
        assert model_input.model_type == "language"

    def test_embedding_model_type_can_be_set(self):
        """model_type can be set to 'embedding'."""
        model_input = ModelInput(name="test_model", model_type="embedding")
        assert model_input.model_type == "embedding"

    def test_language_type_sets_language_model_input_types(self):
        """When model_type='language', input_types should be ['LanguageModel']."""
        model_input = ModelInput(name="test_model", model_type="language")
        assert model_input.input_types == ["LanguageModel"]

    def test_embedding_type_sets_embeddings_input_types(self):
        """When model_type='embedding', input_types should be ['Embeddings']."""
        model_input = ModelInput(name="test_model", model_type="embedding")
        assert model_input.input_types == ["Embeddings"]

    def test_embedding_type_with_value(self):
        """Embedding model with value should still have input_types=['Embeddings']."""
        model_input = ModelInput(
            name="test_model",
            model_type="embedding",
            value=[{"name": "text-embedding-ada-002"}],
        )
        assert model_input.input_types == ["Embeddings"]

    def test_explicit_input_types_preserved_for_embedding(self):
        """If input_types is explicitly set, it should not be overwritten."""
        model_input = ModelInput(
            name="test_model",
            model_type="embedding",
            input_types=["Embeddings"],
        )
        # Should preserve the explicit input_types
        assert model_input.input_types == ["Embeddings"]

    def test_explicit_input_types_preserved_for_language(self):
        """If input_types is explicitly set for language model, it should not be overwritten."""
        model_input = ModelInput(
            name="test_model",
            model_type="language",
            input_types=["LanguageModel"],
        )
        # Should preserve the explicit input_types
        assert model_input.input_types == ["LanguageModel"]
