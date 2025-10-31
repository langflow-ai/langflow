import pytest
from lfx.base.models.gigachat_constants import (
    GIGACHAT_CHAT_MODEL_NAMES,
    GIGACHAT_SCOPES,
    MODEL_NAMES,
)


class TestGigaChatConstants:
    """Test GigaChat constants and model lists."""

    def test_gigachat_models_not_empty(self):
        """Test that GIGACHAT_CHAT_MODEL_NAMES list is not empty."""
        assert len(GIGACHAT_CHAT_MODEL_NAMES) > 0
        assert isinstance(GIGACHAT_CHAT_MODEL_NAMES, list)

    def test_model_names_alias(self):
        """Test that MODEL_NAMES is an alias for GIGACHAT_CHAT_MODEL_NAMES."""
        assert MODEL_NAMES == GIGACHAT_CHAT_MODEL_NAMES
        assert MODEL_NAMES is GIGACHAT_CHAT_MODEL_NAMES

    def test_models_are_strings(self):
        """Test that all models in the list are strings."""
        for model in GIGACHAT_CHAT_MODEL_NAMES:
            assert isinstance(model, str)
            assert len(model) > 0

    def test_specific_models_present(self):
        """Test that specific expected models are present."""
        expected_models = ["GigaChat-2", "GigaChat-2-Pro", "GigaChat-2-Max"]

        for expected_model in expected_models:
            assert expected_model in GIGACHAT_CHAT_MODEL_NAMES

    def test_no_duplicate_models(self):
        """Test that there are no duplicate models in the list."""
        assert len(GIGACHAT_CHAT_MODEL_NAMES) == len(set(GIGACHAT_CHAT_MODEL_NAMES))

    @pytest.mark.parametrize("model_name", ["GigaChat-2", "GigaChat-2-Pro", "GigaChat-2-Max"])
    def test_specific_model_in_list(self, model_name):
        """Parametrized test for specific models."""
        assert model_name in GIGACHAT_CHAT_MODEL_NAMES

    def test_scopes_present(self):
        """Test that specific expected scopes are present."""
        expected_scopes = ["GIGACHAT_API_PERS", "GIGACHAT_API_CORP", "GIGACHAT_API_B2B"]

        for expected_model in expected_scopes:
            assert expected_model in GIGACHAT_SCOPES
