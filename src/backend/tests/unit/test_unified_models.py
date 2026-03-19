from unittest.mock import MagicMock

from lfx.base.models.unified_models import get_unified_models_detailed, update_model_options_in_build_config


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


def test_include_deprecated_parameter_returns_deprecated_models():
    # When explicitly requested, at least one deprecated model should be present.
    result = get_unified_models_detailed(include_deprecated=True)
    deprecated_models = [m for m in _flatten_models(result) if m["metadata"].get("deprecated", False)]
    assert deprecated_models, "Expected at least one deprecated model when include_deprecated=True"

    # Sanity check: restricting by provider that is known to have deprecated entries (e.g., Anthropic)
    result_anthropic = get_unified_models_detailed(providers=["Anthropic"], include_deprecated=True)
    anthropic_deprecated = [m for m in _flatten_models(result_anthropic) if m["metadata"].get("deprecated", False)]
    assert anthropic_deprecated, "Expected deprecated Anthropic models when include_deprecated=True"


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


def test_update_model_options_with_custom_field_name():
    """Test that update_model_options_in_build_config works with custom field names."""
    # Create mock component
    mock_component = MagicMock()
    mock_component.user_id = "test-user-123"
    mock_component.cache = {}
    mock_component.log = MagicMock()

    # Create build_config with custom field name
    build_config = {
        "embedding_model": {
            "options": [],
            "value": "",
            "input_types": ["Embeddings"],
        }
    }

    # Mock options function
    def mock_get_options(user_id):  # noqa: ARG001
        return [
            {"name": "text-embedding-ada-002", "provider": "OpenAI"},
            {"name": "embed-english-v3.0", "provider": "Cohere"},
        ]

    # Call with custom field name
    result = update_model_options_in_build_config(
        component=mock_component,
        build_config=build_config,
        cache_key_prefix="test_embedding_options",
        get_options_func=mock_get_options,
        field_name=None,
        field_value="",
        model_field_name="embedding_model",
    )

    # Verify options were populated in the custom field
    assert "embedding_model" in result
    assert len(result["embedding_model"]["options"]) == 2
    assert result["embedding_model"]["options"][0]["name"] == "text-embedding-ada-002"
    assert result["embedding_model"]["options"][1]["provider"] == "Cohere"

    # Verify default value was set
    assert result["embedding_model"]["value"] == [result["embedding_model"]["options"][0]]


def test_update_model_options_default_field_name():
    """Test that update_model_options_in_build_config uses 'model' as default field name."""
    # Create mock component
    mock_component = MagicMock()
    mock_component.user_id = "test-user-456"
    mock_component.cache = {}
    mock_component.log = MagicMock()

    # Create build_config with default field name
    build_config = {
        "model": {
            "options": [],
            "value": "",
            "input_types": ["LanguageModel"],
        }
    }

    # Mock options function
    def mock_get_options(user_id):  # noqa: ARG001
        return [{"name": "gpt-4", "provider": "OpenAI"}]

    # Call without specifying model_field_name (should default to "model")
    result = update_model_options_in_build_config(
        component=mock_component,
        build_config=build_config,
        cache_key_prefix="test_model_options",
        get_options_func=mock_get_options,
        field_name=None,
        field_value="",
    )

    # Verify options were populated in the default "model" field
    assert "model" in result
    assert len(result["model"]["options"]) == 1
    assert result["model"]["options"][0]["name"] == "gpt-4"
