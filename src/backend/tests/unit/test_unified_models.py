from langflow.base.models.unified_models import get_model_providers, get_unified_models_detailed


def _flatten_models(result):
    """Helper to flatten result to list of model dicts."""
    for provider_dict in result:
        yield from provider_dict["models"]


def test_get_model_providers_present():
    providers = get_model_providers()
    assert "OpenAI" in providers
    assert "Anthropic" in providers
    assert "Google Generative AI" in providers


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


def test_filter_by_provider():
    result = get_unified_models_detailed(providers=["Anthropic"])
    # Only one provider should be returned
    assert len(result) == 1
    assert result[0]["provider"] == "Anthropic"
    # Ensure all models are from that provider
    for _model in _flatten_models(result):
        assert result[0]["provider"] == "Anthropic"


def test_filter_by_multiple_providers():
    result = get_unified_models_detailed(providers=["OpenAI", "Anthropic"])
    returned = {entry["provider"] for entry in result}
    assert "OpenAI" in returned
    assert "Anthropic" in returned
    assert "Google Generative AI" not in returned


def test_filter_by_multiple_providers_with_type():
    result = get_unified_models_detailed(providers=["OpenAI", "Anthropic"], model_type="llm")

    returned = {entry["provider"] for entry in result}
    assert result is not None
    assert "OpenAI" in returned
    assert "Anthropic" in returned
    assert "Google Generative AI" not in returned


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
