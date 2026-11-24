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

    def test_should_not_expose_fictional_gpt53_ids_in_cometapi_models(self):
        """Bug: fictional gpt-5.3 ids in COMETAPI_MODELS cause 404 at runtime.

        gpt-5.3-instant is a ChatGPT product name, not an API model id; gpt-5.3 has no
        base variant — only gpt-5.3-chat-latest and gpt-5.3-codex exist. Selecting
        either of the removed entries causes 404 model_not_found at runtime.
        """
        fictional_ids = {"gpt-5.3", "gpt-5.3-instant"}
        leaked = fictional_ids & set(COMETAPI_MODELS)

        assert not leaked, (
            f"Fictional OpenAI model IDs exposed in COMETAPI_MODELS: {sorted(leaked)}. "
            f"These IDs are not real API models and trigger 404 model_not_found at runtime."
        )
