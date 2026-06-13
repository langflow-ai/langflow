from lfx.base.models.empiriolabs_constants import EMPIRIOLABS_MODELS, MODEL_NAMES


class TestEmpirioLabsConstants:
    """Test EmpirioLabs constants and model lists."""

    def test_empiriolabs_models_not_empty(self):
        """Test that EMPIRIOLABS_MODELS list is not empty."""
        assert len(EMPIRIOLABS_MODELS) > 0
        assert isinstance(EMPIRIOLABS_MODELS, list)

    def test_model_names_alias(self):
        """Test that MODEL_NAMES is an alias for EMPIRIOLABS_MODELS."""
        assert MODEL_NAMES == EMPIRIOLABS_MODELS
        assert MODEL_NAMES is EMPIRIOLABS_MODELS  # Should be the same object

    def test_models_are_strings(self):
        """Test that all models in the list are strings."""
        for model in EMPIRIOLABS_MODELS:
            assert isinstance(model, str)
            assert len(model) > 0

    def test_specific_models_present(self):
        """Test that specific expected models are present."""
        expected_models = ["qwen3-7-plus", "deepseek-v4-pro", "glm-5-1", "minimax-m3"]

        for expected_model in expected_models:
            assert expected_model in EMPIRIOLABS_MODELS

    def test_no_duplicate_models(self):
        """Test that there are no duplicate models in the list."""
        assert len(EMPIRIOLABS_MODELS) == len(set(EMPIRIOLABS_MODELS))
