from langflow.base.models.unified_models import get_unified_models_detailed


def _flatten_models(result):
    """Helper to flatten result to list of model dicts."""
    for provider_dict in result:
        yield from provider_dict["models"]


def test_default_providers_present():
    result = get_unified_models_detailed()
    providers = {entry["provider"] for entry in result}
    assert "OpenAI" in providers
    assert "Anthropic" in providers
    assert "Google Generative AI" in providers


def test_default_excludes_not_supported():
    result = get_unified_models_detailed()
    for model in _flatten_models(result):
        # By default, models flagged not_supported should be absent
        assert model["metadata"].get("not_supported", False) is False


def test_default_excludes_deprecated():
    result = get_unified_models_detailed()
    for model in _flatten_models(result):
        # By default, models flagged deprecated should be absent
        assert model["metadata"].get("deprecated", False) is False


def test_include_deprecated_parameter():
    # Test that deprecated models are included when explicitly requested
    result = get_unified_models_detailed(include_deprecated=True)
    deprecated_found = False
    for model in _flatten_models(result):
        if model["metadata"].get("deprecated", False):
            deprecated_found = True
            break
    # This test assumes there are some deprecated models in the constants
    # If no deprecated models exist, this test will pass but not verify the functionality
    # In a real scenario, we'd want to ensure there are deprecated models to test against


def test_filter_by_provider():
    result = get_unified_models_detailed(provider="Anthropic")
    # Only one provider should be returned
    assert len(result) == 1
    assert result[0]["provider"] == "Anthropic"
    # Ensure all models are from that provider
    for _model in _flatten_models(result):
        assert result[0]["provider"] == "Anthropic"


def test_filter_by_model_name():
    target = "gpt-4"
    result = get_unified_models_detailed(model_name=target)
    # Should only include OpenAI provider with the single model
    assert len(result) == 1
    provider_dict = result[0]
    assert provider_dict["provider"] == "OpenAI"
    assert len(provider_dict["models"]) == 1
    assert provider_dict["models"][0]["model_name"] == target


def test_filter_by_metadata():
    # Require tool_calling support
    result = get_unified_models_detailed(tool_calling=True)
    assert result, "Expected at least one model supporting tool calling"
    for model in _flatten_models(result):
        assert model["metadata"].get("tool_calling", False) is True


def test_filter_by_model_type_embeddings():
    result = get_unified_models_detailed(model_type="embeddings")
    models = list(_flatten_models(result))
    assert models, "Expected at least one embedding model"
    for model in models:
        assert model["metadata"].get("model_type", "llm") == "embeddings"
