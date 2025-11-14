import pytest
from lfx.base.models.cometapi_constants import COMETAPI_MODELS, MODEL_NAMES


class TestCometAPIConstants:
    """Test CometAPI constants and model lists."""

    def test_cometapi_models_not_empty(self):
        """Test that COMETAPI_MODELS list is not empty."""
        assert len(COMETAPI_MODELS) > 0
        assert isinstance(COMETAPI_MODELS, list)

    def test_model_names_alias(self):
        """Test that MODEL_NAMES is an alias for COMETAPI_MODELS."""
        assert MODEL_NAMES == COMETAPI_MODELS
        assert MODEL_NAMES is COMETAPI_MODELS  # Should be the same object

    def test_models_are_strings(self):
        """Test that all models in the list are strings."""
        for model in COMETAPI_MODELS:
            assert isinstance(model, str)
            assert len(model) > 0

    def test_specific_models_present(self):
        """Test that specific expected models are present."""
        expected_models = ["gpt-4o-mini", "claude-3-5-haiku-latest", "gemini-2.5-flash", "deepseek-chat"]

        for expected_model in expected_models:
            assert expected_model in COMETAPI_MODELS

    def test_no_duplicate_models(self):
        """Test that there are no duplicate models in the list."""
        assert len(COMETAPI_MODELS) == len(set(COMETAPI_MODELS))

    @pytest.mark.parametrize(
        "model_name", ["gpt-4o-mini", "claude-3-5-haiku-latest", "gemini-2.5-flash", "deepseek-chat", "grok-3"]
    )
    def test_specific_model_in_list(self, model_name):
        """Parametrized test for specific models."""
        assert model_name in COMETAPI_MODELS
