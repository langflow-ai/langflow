from unittest.mock import MagicMock, patch

import pytest
from lfx.base.models.unified_models import (
    _get_all_provider_mapped_fields,
    get_embeddings,
    get_unified_models_detailed,
    handle_model_input_update,
    update_model_options_in_build_config,
)


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
    result = get_unified_models_detailed(providers=["Anthropic"])
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


def test_update_model_options_static_options_with_custom_field_name():
    """Static pre-populated options should be detected using the custom field name, not 'model'."""
    mock_component = MagicMock()
    mock_component.user_id = "test-user-static"
    mock_component.cache = {}
    mock_component.log = MagicMock()

    static_opts = [{"name": "embed-v1", "provider": "Custom"}]
    build_config = {
        "embedding_model": {
            "options": static_opts,
            "value": "",
            "input_types": ["Embeddings"],
        }
    }

    result = update_model_options_in_build_config(
        component=mock_component,
        build_config=build_config,
        cache_key_prefix="test_static_custom",
        get_options_func=lambda user_id=None: [],  # noqa: ARG005
        field_name=None,
        field_value="",
        model_field_name="embedding_model",
    )

    # Static options should be preserved, not overwritten by the empty get_options_func result
    assert result["embedding_model"]["options"] == static_opts


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


# ---------------------------------------------------------------------------
# Helpers shared by new tests
# ---------------------------------------------------------------------------


def _make_mock_component(user_id="test-user"):
    component = MagicMock()
    component.user_id = user_id
    component.cache = {}
    component.log = MagicMock()
    return component


def _make_model_field(value="", options=None, input_types=None):
    return {
        "value": value,
        "options": options or [],
        "input_types": input_types or ["LanguageModel"],
        "show": True,
    }


def _make_openai_embedding_model(name="text-embedding-3-small"):
    return {
        "name": name,
        "provider": "OpenAI",
        "metadata": {
            "embedding_class": "OpenAIEmbeddings",
            "param_mapping": {
                "model": "model",
                "api_key": "api_key",
                "api_base": "base_url",
                "dimensions": "dimensions",
                "chunk_size": "chunk_size",
                "request_timeout": "request_timeout",
                "max_retries": "max_retries",
                "show_progress_bar": "show_progress_bar",
                "model_kwargs": "model_kwargs",
            },
        },
    }


# ---------------------------------------------------------------------------
# _get_all_provider_mapped_fields tests
# ---------------------------------------------------------------------------


def test_get_all_provider_mapped_fields_returns_set():
    fields = _get_all_provider_mapped_fields()
    assert isinstance(fields, set)
    assert len(fields) > 0


def test_get_all_provider_mapped_fields_contains_expected_fields():
    fields = _get_all_provider_mapped_fields()
    expected = {"base_url_ibm_watsonx", "project_id", "ollama_base_url"}
    assert expected & fields, f"Expected at least one of {expected} to be in provider mapped fields"


def test_get_all_provider_mapped_fields_is_cached():
    """Calling twice returns the exact same object (lru_cache)."""
    fields1 = _get_all_provider_mapped_fields()
    fields2 = _get_all_provider_mapped_fields()
    assert fields1 is fields2


# ---------------------------------------------------------------------------
# get_embeddings tests
# ---------------------------------------------------------------------------


def test_get_embeddings_passthrough_embeddings_object():
    """An already-instantiated Embeddings object should be returned as-is."""
    from langchain_core.embeddings import Embeddings as BaseEmbeddings

    mock_emb = MagicMock(spec=BaseEmbeddings)
    result = get_embeddings(mock_emb, user_id=None)
    assert result is mock_emb


def test_get_embeddings_empty_list_raises():
    with pytest.raises(ValueError, match="An embedding model selection is required"):
        get_embeddings([], user_id=None)


def test_get_embeddings_none_raises():
    with pytest.raises(ValueError, match="An embedding model selection is required"):
        get_embeddings(None, user_id=None)


def test_get_embeddings_non_list_raises():
    with pytest.raises(ValueError, match="An embedding model selection is required"):
        get_embeddings("gpt-4", user_id=None)


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
def test_get_embeddings_missing_api_key_non_ollama_raises(mock_get_api_key):
    mock_get_api_key.return_value = None
    with pytest.raises(ValueError, match="OpenAI API key is required"):
        get_embeddings([_make_openai_embedding_model()], user_id=None, api_key=None)


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
def test_get_embeddings_missing_model_name_raises(mock_get_api_key):
    mock_get_api_key.return_value = "test-key"
    model_dict = {
        "name": None,
        "provider": "OpenAI",
        "metadata": {"embedding_class": "OpenAIEmbeddings", "param_mapping": {"model": "model"}},
    }
    with pytest.raises(ValueError, match="Embedding model name is required"):
        get_embeddings([model_dict], user_id=None)


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
def test_get_embeddings_missing_embedding_class_raises(mock_get_api_key):
    mock_get_api_key.return_value = "test-key"
    model_dict = {
        "name": "text-embedding-3-small",
        "provider": "OpenAI",
        "metadata": {"param_mapping": {"model": "model"}},
    }
    with pytest.raises(ValueError, match="No embedding class defined in metadata"):
        get_embeddings([model_dict], user_id=None)


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
def test_get_embeddings_empty_param_mapping_raises(mock_get_api_key):
    mock_get_api_key.return_value = "test-key"
    model_dict = {
        "name": "text-embedding-3-small",
        "provider": "OpenAI",
        "metadata": {"embedding_class": "OpenAIEmbeddings", "param_mapping": {}},
    }
    with pytest.raises(ValueError, match="Parameter mapping not found in metadata"):
        get_embeddings([model_dict], user_id=None)


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
@patch("lfx.base.models.unified_models.get_embedding_class")
def test_get_embeddings_openai_basic(mock_get_class, mock_get_api_key):
    mock_get_api_key.return_value = "sk-test"
    mock_embedding_class = MagicMock()
    mock_instance = MagicMock()
    mock_embedding_class.return_value = mock_instance
    mock_get_class.return_value = mock_embedding_class

    result = get_embeddings([_make_openai_embedding_model()], user_id=None, api_key="sk-test")

    assert result is mock_instance
    mock_get_class.assert_called_once_with("OpenAIEmbeddings")
    kwargs = mock_embedding_class.call_args.kwargs
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["api_key"] == "sk-test"


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
@patch("lfx.base.models.unified_models.get_embedding_class")
def test_get_embeddings_optional_params_only_added_when_mapped(mock_get_class, mock_get_api_key):
    """Parameters only appear in kwargs if their key is in param_mapping."""
    mock_get_api_key.return_value = "sk-test"
    mock_embedding_class = MagicMock()
    mock_get_class.return_value = mock_embedding_class

    get_embeddings(
        [_make_openai_embedding_model()],
        user_id=None,
        api_key="sk-test",
        chunk_size=500,
        max_retries=5,
        dimensions=None,
    )

    kwargs = mock_embedding_class.call_args.kwargs
    assert kwargs.get("chunk_size") == 500
    assert kwargs.get("max_retries") == 5
    # dimensions not provided - should not appear
    assert kwargs.get("dimensions") is None


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
@patch("lfx.base.models.unified_models.get_embedding_class")
def test_get_embeddings_google_timeout_wrapped_in_dict(mock_get_class, mock_get_api_key):
    """For Google Generative AI, request_timeout should be wrapped as {'timeout': value}."""
    mock_get_api_key.return_value = "google-key"
    mock_embedding_class = MagicMock()
    mock_get_class.return_value = mock_embedding_class

    google_model = {
        "name": "models/text-embedding-004",
        "provider": "Google Generative AI",
        "metadata": {
            "embedding_class": "GoogleGenerativeAIEmbeddings",
            "param_mapping": {
                "model": "model",
                "api_key": "google_api_key",
                "request_timeout": "request_options",
            },
        },
    }

    get_embeddings([google_model], user_id=None, api_key="google-key", request_timeout=30.0)

    kwargs = mock_embedding_class.call_args.kwargs
    assert kwargs.get("request_options") == {"timeout": 30.0}


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
@patch("lfx.base.models.unified_models.get_embedding_class")
@patch("lfx.base.models.unified_models.get_all_variables_for_provider")
def test_get_embeddings_ollama_defaults_to_localhost(mock_get_vars, mock_get_class, mock_get_api_key):
    mock_get_api_key.return_value = None  # Ollama doesn't need an API key
    mock_get_vars.return_value = {}
    mock_embedding_class = MagicMock()
    mock_get_class.return_value = mock_embedding_class

    ollama_model = {
        "name": "nomic-embed-text",
        "provider": "Ollama",
        "metadata": {
            "embedding_class": "OllamaEmbeddings",
            "param_mapping": {"model": "model", "base_url": "base_url"},
        },
    }

    get_embeddings([ollama_model], user_id=None)

    kwargs = mock_embedding_class.call_args.kwargs
    assert kwargs.get("base_url") == "http://localhost:11434"


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
@patch("lfx.base.models.unified_models.get_embedding_class")
@patch("lfx.base.models.unified_models.get_all_variables_for_provider")
def test_get_embeddings_ollama_custom_base_url(mock_get_vars, mock_get_class, mock_get_api_key):
    mock_get_api_key.return_value = None
    mock_get_vars.return_value = {}
    mock_embedding_class = MagicMock()
    mock_get_class.return_value = mock_embedding_class

    ollama_model = {
        "name": "nomic-embed-text",
        "provider": "Ollama",
        "metadata": {
            "embedding_class": "OllamaEmbeddings",
            "param_mapping": {"model": "model", "base_url": "base_url"},
        },
    }

    get_embeddings([ollama_model], user_id=None, ollama_base_url="http://custom-host:11434")

    kwargs = mock_embedding_class.call_args.kwargs
    assert kwargs.get("base_url") == "http://custom-host:11434"


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
@patch("lfx.base.models.unified_models.get_embedding_class")
@patch("lfx.base.models.unified_models.get_all_variables_for_provider")
def test_get_embeddings_watsonx_url_and_project_id(mock_get_vars, mock_get_class, mock_get_api_key):
    mock_get_api_key.return_value = "ibm-key"
    mock_get_vars.return_value = {}
    mock_embedding_class = MagicMock()
    mock_get_class.return_value = mock_embedding_class

    watsonx_model = {
        "name": "ibm/slate-125m-english-rtrvr",
        "provider": "IBM WatsonX",
        "metadata": {
            "embedding_class": "WatsonxEmbeddings",
            "param_mapping": {
                "model_id": "model_id",
                "api_key": "apikey",
                "url": "url",
                "project_id": "project_id",
            },
        },
    }

    get_embeddings(
        [watsonx_model],
        user_id=None,
        api_key="ibm-key",
        watsonx_url="https://us-south.ml.cloud.ibm.com",
        watsonx_project_id="proj-123",
    )

    kwargs = mock_embedding_class.call_args.kwargs
    assert kwargs.get("url") == "https://us-south.ml.cloud.ibm.com"
    assert kwargs.get("project_id") == "proj-123"


@patch("lfx.base.models.unified_models.get_api_key_for_provider")
@patch("lfx.base.models.unified_models.get_embedding_class")
@patch("lfx.base.models.unified_models.get_all_variables_for_provider")
def test_get_embeddings_watsonx_error_wraps_message(mock_get_vars, mock_get_class, mock_get_api_key):
    """IBM WatsonX instantiation errors mentioning url/project get wrapped in a friendlier ValueError."""
    mock_get_api_key.return_value = "ibm-key"
    mock_get_vars.return_value = {}
    mock_embedding_class = MagicMock()
    mock_embedding_class.side_effect = RuntimeError("missing project id")
    mock_get_class.return_value = mock_embedding_class

    watsonx_model = {
        "name": "ibm/slate-125m-english-rtrvr",
        "provider": "IBM WatsonX",
        "metadata": {
            "embedding_class": "WatsonxEmbeddings",
            "param_mapping": {"model_id": "model_id", "api_key": "apikey"},
        },
    }

    with pytest.raises(ValueError, match="IBM WatsonX requires additional configuration"):
        get_embeddings([watsonx_model], user_id=None, api_key="ibm-key")


# ---------------------------------------------------------------------------
# handle_model_input_update tests
# ---------------------------------------------------------------------------


def test_handle_model_input_update_hides_all_provider_fields_by_default():
    """Provider-specific fields should be hidden when no model is selected."""
    component = _make_mock_component()
    provider_fields = _get_all_provider_mapped_fields()

    build_config = {"model": _make_model_field()}
    for f in provider_fields:
        build_config[f] = {"show": True, "required": True}

    def get_options(user_id=None):  # noqa: ARG001
        return []

    result = handle_model_input_update(
        component, build_config, field_value="", field_name=None, get_options_func=get_options
    )

    for f in provider_fields:
        assert result[f]["show"] is False
        assert result[f]["required"] is False


def test_handle_model_input_update_uses_language_model_options_by_default():
    """When no get_options_func is provided, get_language_model_options is used."""
    component = _make_mock_component()
    build_config = {"model": _make_model_field()}

    with patch("lfx.base.models.unified_models.get_language_model_options") as mock_opts:
        mock_opts.return_value = []
        handle_model_input_update(component, build_config, field_value="", field_name=None)
        mock_opts.assert_called_once()


def test_handle_model_input_update_calls_apply_provider_config_when_model_selected():
    """Selecting a model should call apply_provider_variable_config_to_build_config."""
    component = _make_mock_component()
    selected_model = [{"name": "gpt-4", "provider": "OpenAI", "metadata": {}}]
    build_config = {"model": _make_model_field(value=selected_model)}

    with patch("lfx.base.models.unified_models.apply_provider_variable_config_to_build_config") as mock_apply:
        mock_apply.side_effect = lambda cfg, _: cfg

        def get_options(user_id=None):  # noqa: ARG001
            return []

        handle_model_input_update(
            component, build_config, field_value=selected_model, field_name="model", get_options_func=get_options
        )

        mock_apply.assert_called_once_with(build_config, "OpenAI")


def test_handle_model_input_update_watsonx_embedding_shows_special_fields():
    """IBM WatsonX + embedding prefix should show truncate_input_tokens and input_text."""
    component = _make_mock_component()
    selected_model = [{"name": "ibm/slate-125m-english-rtrvr", "provider": "IBM WatsonX", "metadata": {}}]
    build_config = {
        "model": _make_model_field(value=selected_model),
        "truncate_input_tokens": {"show": False},
        "input_text": {"show": False},
    }

    with patch("lfx.base.models.unified_models.apply_provider_variable_config_to_build_config") as mock_apply:
        mock_apply.side_effect = lambda cfg, _: cfg

        result = handle_model_input_update(
            component,
            build_config,
            field_value=selected_model,
            field_name="model",
            cache_key_prefix="embedding_model_options",
            get_options_func=lambda user_id=None: [],  # noqa: ARG005
        )

    assert result["truncate_input_tokens"]["show"] is True
    assert result["input_text"]["show"] is True


def test_handle_model_input_update_non_watsonx_embedding_hides_special_fields():
    """Non-WatsonX embedding should hide truncate_input_tokens and input_text."""
    component = _make_mock_component()
    selected_model = [{"name": "text-embedding-3-small", "provider": "OpenAI", "metadata": {}}]
    build_config = {
        "model": _make_model_field(value=selected_model),
        "truncate_input_tokens": {"show": True},
        "input_text": {"show": True},
    }

    with patch("lfx.base.models.unified_models.apply_provider_variable_config_to_build_config") as mock_apply:
        mock_apply.side_effect = lambda cfg, _: cfg

        result = handle_model_input_update(
            component,
            build_config,
            field_value=selected_model,
            field_name="model",
            cache_key_prefix="embedding_model_options",
            get_options_func=lambda user_id=None: [],  # noqa: ARG005
        )

    assert result["truncate_input_tokens"]["show"] is False
    assert result["input_text"]["show"] is False


def test_handle_model_input_update_language_model_prefix_skips_embedding_fields():
    """Language model updates should not toggle truncate_input_tokens/input_text."""
    component = _make_mock_component()
    selected_model = [{"name": "gpt-4", "provider": "OpenAI", "metadata": {}}]
    original_show = False
    build_config = {
        "model": _make_model_field(value=selected_model),
        "truncate_input_tokens": {"show": original_show},
        "input_text": {"show": original_show},
    }

    with patch("lfx.base.models.unified_models.apply_provider_variable_config_to_build_config") as mock_apply:
        mock_apply.side_effect = lambda cfg, _: cfg

        result = handle_model_input_update(
            component,
            build_config,
            field_value=selected_model,
            field_name="model",
            cache_key_prefix="language_model_options",
            get_options_func=lambda user_id=None: [],  # noqa: ARG005
        )

    # The embedding-specific block should not run for language_model_options
    assert result["truncate_input_tokens"]["show"] is original_show
    assert result["input_text"]["show"] is original_show


def test_handle_model_input_update_returns_dict():
    component = _make_mock_component()
    build_config = {"model": _make_model_field()}
    result = handle_model_input_update(
        component,
        build_config,
        field_value="",
        field_name=None,
        get_options_func=lambda user_id=None: [],  # noqa: ARG005
    )
    assert isinstance(result, dict)
