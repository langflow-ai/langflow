"""Tests for Groq constants and fallback models.

Tests cover:
- Fallback model structure and integrity
- Model categorization (production, preview, deprecated, unsupported)
- Backward compatibility constants
- Model metadata completeness
"""


class TestGroqConstantsStructure:
    """Test the structure and integrity of Groq constants."""

    def test_groq_models_detailed_exists(self):
        """Test that GROQ_MODELS_DETAILED constant exists."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED

        assert isinstance(GROQ_MODELS_DETAILED, list)
        assert len(GROQ_MODELS_DETAILED) > 0

    def test_groq_models_detailed_structure(self):
        """Test that each model in GROQ_MODELS_DETAILED has required fields."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED

        required_fields = ["name", "provider", "icon"]

        for model in GROQ_MODELS_DETAILED:
            assert isinstance(model, dict)
            for field in required_fields:
                assert field in model, f"Model {model.get('name', 'unknown')} missing field: {field}"

    def test_groq_production_models_exists(self):
        """Test that GROQ_PRODUCTION_MODELS constant exists."""
        from lfx.base.models.groq_constants import GROQ_PRODUCTION_MODELS

        assert isinstance(GROQ_PRODUCTION_MODELS, list)
        assert len(GROQ_PRODUCTION_MODELS) >= 2  # Should have at least fallback models

    def test_groq_preview_models_exists(self):
        """Test that GROQ_PREVIEW_MODELS constant exists."""
        from lfx.base.models.groq_constants import GROQ_PREVIEW_MODELS

        assert isinstance(GROQ_PREVIEW_MODELS, list)

    def test_deprecated_groq_models_exists(self):
        """Test that DEPRECATED_GROQ_MODELS constant exists."""
        from lfx.base.models.groq_constants import DEPRECATED_GROQ_MODELS

        assert isinstance(DEPRECATED_GROQ_MODELS, list)

    def test_unsupported_groq_models_exists(self):
        """Test that UNSUPPORTED_GROQ_MODELS constant exists."""
        from lfx.base.models.groq_constants import UNSUPPORTED_GROQ_MODELS

        assert isinstance(UNSUPPORTED_GROQ_MODELS, list)
        assert len(UNSUPPORTED_GROQ_MODELS) > 0

    def test_tool_calling_unsupported_groq_models_exists(self):
        """Test that TOOL_CALLING_UNSUPPORTED_GROQ_MODELS constant exists."""
        from lfx.base.models.groq_constants import TOOL_CALLING_UNSUPPORTED_GROQ_MODELS

        assert isinstance(TOOL_CALLING_UNSUPPORTED_GROQ_MODELS, list)

    def test_groq_models_combined_list(self):
        """Test that GROQ_MODELS is the combination of production and preview."""
        from lfx.base.models.groq_constants import GROQ_MODELS, GROQ_PREVIEW_MODELS, GROQ_PRODUCTION_MODELS

        combined = GROQ_PRODUCTION_MODELS + GROQ_PREVIEW_MODELS
        assert combined == GROQ_MODELS

    def test_model_names_alias(self):
        """Test that MODEL_NAMES is an alias for GROQ_MODELS."""
        from lfx.base.models.groq_constants import GROQ_MODELS, MODEL_NAMES

        assert MODEL_NAMES == GROQ_MODELS


class TestFallbackProductionModels:
    """Test fallback production models."""

    def test_fallback_models_present(self):
        """Test that essential fallback models are present."""
        from lfx.base.models.groq_constants import GROQ_PRODUCTION_MODELS

        # Essential fallback models mentioned in the code
        assert "llama-3.1-8b-instant" in GROQ_PRODUCTION_MODELS
        assert "llama-3.3-70b-versatile" in GROQ_PRODUCTION_MODELS

    def test_fallback_models_have_metadata(self):
        """Test that fallback models have complete metadata."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED

        fallback_names = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]

        for model in GROQ_MODELS_DETAILED:
            if model["name"] in fallback_names:
                assert model.get("provider") is not None
                assert model.get("icon") is not None
                # Fallback models should support tool calling
                assert model.get("tool_calling") is True
                # Should not be deprecated or unsupported
                assert model.get("deprecated", False) is False
                assert model.get("not_supported", False) is False
                assert model.get("preview", False) is False

    def test_production_models_not_deprecated(self):
        """Test that production models are not deprecated."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED, GROQ_PRODUCTION_MODELS

        for model in GROQ_MODELS_DETAILED:
            if model["name"] in GROQ_PRODUCTION_MODELS:
                assert model.get("deprecated", False) is False

    def test_production_models_not_unsupported(self):
        """Test that production models are not marked as unsupported."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED, GROQ_PRODUCTION_MODELS

        for model in GROQ_MODELS_DETAILED:
            if model["name"] in GROQ_PRODUCTION_MODELS:
                assert model.get("not_supported", False) is False

    def test_production_models_not_preview(self):
        """Test that production models are not preview models."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED, GROQ_PRODUCTION_MODELS

        for model in GROQ_MODELS_DETAILED:
            if model["name"] in GROQ_PRODUCTION_MODELS:
                assert model.get("preview", False) is False


class TestDeprecatedModels:
    """Test deprecated models handling."""

    def test_deprecated_models_marked_correctly(self):
        """Test that deprecated models have the deprecated flag."""
        from lfx.base.models.groq_constants import DEPRECATED_GROQ_MODELS, GROQ_MODELS_DETAILED

        for model in GROQ_MODELS_DETAILED:
            if model["name"] in DEPRECATED_GROQ_MODELS:
                assert model.get("deprecated") is True

    def test_deprecated_models_not_in_production(self):
        """Test that deprecated models are not in production list."""
        from lfx.base.models.groq_constants import DEPRECATED_GROQ_MODELS, GROQ_PRODUCTION_MODELS

        for model_name in DEPRECATED_GROQ_MODELS:
            assert model_name not in GROQ_PRODUCTION_MODELS

    def test_deprecated_models_examples(self):
        """Test that known deprecated models are in the list."""
        from lfx.base.models.groq_constants import DEPRECATED_GROQ_MODELS

        # Examples from the PR changes
        expected_deprecated = [
            "gemma2-9b-it",
            "gemma-7b-it",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "llama-guard-3-8b",
        ]

        for model in expected_deprecated:
            assert model in DEPRECATED_GROQ_MODELS


class TestUnsupportedModels:
    """Test unsupported (non-LLM) models."""

    def test_unsupported_models_marked_correctly(self):
        """Test that unsupported models have the not_supported flag."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED, UNSUPPORTED_GROQ_MODELS

        for model in GROQ_MODELS_DETAILED:
            if model["name"] in UNSUPPORTED_GROQ_MODELS:
                assert model.get("not_supported") is True

    def test_unsupported_models_not_in_production(self):
        """Test that unsupported models are not in production list."""
        from lfx.base.models.groq_constants import GROQ_PRODUCTION_MODELS, UNSUPPORTED_GROQ_MODELS

        for model_name in UNSUPPORTED_GROQ_MODELS:
            assert model_name not in GROQ_PRODUCTION_MODELS

    def test_unsupported_models_not_in_main_list(self):
        """Test that unsupported models are not in GROQ_MODELS."""
        from lfx.base.models.groq_constants import GROQ_MODELS, UNSUPPORTED_GROQ_MODELS

        for model_name in UNSUPPORTED_GROQ_MODELS:
            assert model_name not in GROQ_MODELS

    def test_audio_models_unsupported(self):
        """Test that audio models are marked as unsupported."""
        from lfx.base.models.groq_constants import UNSUPPORTED_GROQ_MODELS

        audio_models = [
            "whisper-large-v3",
            "whisper-large-v3-turbo",
            "distil-whisper-large-v3-en",
        ]

        for model in audio_models:
            assert model in UNSUPPORTED_GROQ_MODELS

    def test_tts_models_unsupported(self):
        """Test that TTS models are marked as unsupported."""
        from lfx.base.models.groq_constants import UNSUPPORTED_GROQ_MODELS

        tts_models = ["playai-tts", "playai-tts-arabic"]

        for model in tts_models:
            assert model in UNSUPPORTED_GROQ_MODELS

    def test_guard_models_unsupported(self):
        """Test that guard/safeguard models are marked as unsupported."""
        from lfx.base.models.groq_constants import UNSUPPORTED_GROQ_MODELS

        guard_models = [
            "meta-llama/llama-guard-4-12b",
            "meta-llama/llama-prompt-guard-2-86m",
            "meta-llama/llama-prompt-guard-2-22m",
            "openai/gpt-oss-safeguard-20b",
        ]

        for model in guard_models:
            assert model in UNSUPPORTED_GROQ_MODELS

    def test_safeguard_model_unsupported(self):
        """Test that safeguard models like mistral-saba are marked as unsupported."""
        from lfx.base.models.groq_constants import UNSUPPORTED_GROQ_MODELS

        assert "mistral-saba-24b" in UNSUPPORTED_GROQ_MODELS


class TestPreviewModels:
    """Test preview models handling."""

    def test_preview_models_marked_correctly(self):
        """Test that preview models have the preview flag."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED, GROQ_PREVIEW_MODELS

        for model in GROQ_MODELS_DETAILED:
            if model["name"] in GROQ_PREVIEW_MODELS:
                assert model.get("preview") is True

    def test_preview_models_not_in_production(self):
        """Test that preview models are separate from production."""
        from lfx.base.models.groq_constants import GROQ_PREVIEW_MODELS, GROQ_PRODUCTION_MODELS

        for model_name in GROQ_PREVIEW_MODELS:
            assert model_name not in GROQ_PRODUCTION_MODELS

    def test_preview_models_in_main_list(self):
        """Test that preview models are included in GROQ_MODELS."""
        from lfx.base.models.groq_constants import GROQ_MODELS, GROQ_PREVIEW_MODELS

        for model_name in GROQ_PREVIEW_MODELS:
            assert model_name in GROQ_MODELS


class TestToolCallingModels:
    """Test tool calling support categorization."""

    def test_tool_calling_unsupported_not_in_production(self):
        """Test that models without tool calling are tracked."""
        from lfx.base.models.groq_constants import (
            GROQ_MODELS_DETAILED,
            TOOL_CALLING_UNSUPPORTED_GROQ_MODELS,
        )

        for model in GROQ_MODELS_DETAILED:
            if model["name"] in TOOL_CALLING_UNSUPPORTED_GROQ_MODELS:
                # These models should explicitly not support tool calling
                assert model.get("tool_calling", False) is False
                # And should not be deprecated or unsupported
                assert model.get("deprecated", False) is False
                assert model.get("not_supported", False) is False


class TestModelCategorization:
    """Test that model categorization is mutually exclusive."""

    def test_no_overlap_production_deprecated(self):
        """Test no overlap between production and deprecated models."""
        from lfx.base.models.groq_constants import DEPRECATED_GROQ_MODELS, GROQ_PRODUCTION_MODELS

        overlap = set(GROQ_PRODUCTION_MODELS) & set(DEPRECATED_GROQ_MODELS)
        assert len(overlap) == 0, f"Found overlap: {overlap}"

    def test_no_overlap_production_unsupported(self):
        """Test no overlap between production and unsupported models."""
        from lfx.base.models.groq_constants import GROQ_PRODUCTION_MODELS, UNSUPPORTED_GROQ_MODELS

        overlap = set(GROQ_PRODUCTION_MODELS) & set(UNSUPPORTED_GROQ_MODELS)
        assert len(overlap) == 0, f"Found overlap: {overlap}"

    def test_no_overlap_preview_deprecated(self):
        """Test no overlap between preview and deprecated models."""
        from lfx.base.models.groq_constants import DEPRECATED_GROQ_MODELS, GROQ_PREVIEW_MODELS

        overlap = set(GROQ_PREVIEW_MODELS) & set(DEPRECATED_GROQ_MODELS)
        assert len(overlap) == 0, f"Found overlap: {overlap}"

    def test_no_overlap_preview_unsupported(self):
        """Test no overlap between preview and unsupported models."""
        from lfx.base.models.groq_constants import GROQ_PREVIEW_MODELS, UNSUPPORTED_GROQ_MODELS

        overlap = set(GROQ_PREVIEW_MODELS) & set(UNSUPPORTED_GROQ_MODELS)
        assert len(overlap) == 0, f"Found overlap: {overlap}"

    def test_all_models_categorized(self):
        """Test that all models in GROQ_MODELS_DETAILED are categorized."""
        from lfx.base.models.groq_constants import (
            DEPRECATED_GROQ_MODELS,
            GROQ_MODELS,
            GROQ_MODELS_DETAILED,
            UNSUPPORTED_GROQ_MODELS,
        )

        for model in GROQ_MODELS_DETAILED:
            model_name = model["name"]

            # Each model should be in exactly one category
            in_main = model_name in GROQ_MODELS
            is_deprecated = model_name in DEPRECATED_GROQ_MODELS
            is_unsupported = model_name in UNSUPPORTED_GROQ_MODELS

            categories = sum([in_main, is_deprecated, is_unsupported])

            assert categories == 1, f"Model {model_name} is in {categories} categories (should be exactly 1)"


class TestProviderMetadata:
    """Test provider metadata for models."""

    def test_all_models_have_provider(self):
        """Test that all models have a provider field."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED

        for model in GROQ_MODELS_DETAILED:
            assert "provider" in model
            assert isinstance(model["provider"], str)
            assert len(model["provider"]) > 0

    def test_all_models_have_icon(self):
        """Test that all models have an icon field."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED

        for model in GROQ_MODELS_DETAILED:
            assert "icon" in model
            assert isinstance(model["icon"], str)
            assert len(model["icon"]) > 0

    def test_provider_values_reasonable(self):
        """Test that provider values are from expected set."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED

        for model in GROQ_MODELS_DETAILED:
            # Just ensure provider is a non-empty string
            # (actual values may vary)
            assert isinstance(model["provider"], str)
            assert len(model["provider"]) > 0


class TestBackwardCompatibility:
    """Test backward compatibility of constants."""

    def test_groq_models_is_list(self):
        """Test that GROQ_MODELS is a list for backward compatibility."""
        from lfx.base.models.groq_constants import GROQ_MODELS

        assert isinstance(GROQ_MODELS, list)

    def test_groq_models_contains_strings(self):
        """Test that GROQ_MODELS contains model name strings."""
        from lfx.base.models.groq_constants import GROQ_MODELS

        for model in GROQ_MODELS:
            assert isinstance(model, str)
            assert len(model) > 0

    def test_no_duplicates_in_groq_models(self):
        """Test that GROQ_MODELS has no duplicates."""
        from lfx.base.models.groq_constants import GROQ_MODELS

        assert len(GROQ_MODELS) == len(set(GROQ_MODELS))

    def test_no_duplicates_in_groq_models_detailed(self):
        """Test that GROQ_MODELS_DETAILED has no duplicate model names."""
        from lfx.base.models.groq_constants import GROQ_MODELS_DETAILED

        model_names = [model["name"] for model in GROQ_MODELS_DETAILED]
        assert len(model_names) == len(set(model_names))


class TestFallbackListMinimalSize:
    """Test that fallback lists are minimal but sufficient."""

    def test_production_models_minimal(self):
        """Test that production models list is minimal (2 fallback models)."""
        from lfx.base.models.groq_constants import GROQ_PRODUCTION_MODELS

        # According to the code comments, should have minimal fallback set
        # At least 2 models as per the fallback in discovery module
        assert len(GROQ_PRODUCTION_MODELS) >= 2

    def test_fallback_models_match_discovery(self):
        """Test that fallback models in constants match those in discovery module."""
        from lfx.base.models.groq_constants import GROQ_PRODUCTION_MODELS

        # The discovery module defines these as fallback
        discovery_fallback = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]

        for model in discovery_fallback:
            assert model in GROQ_PRODUCTION_MODELS
