from __future__ import annotations

from unittest.mock import patch


def _openai_language_selection() -> list[dict]:
    return [
        {
            "name": "gpt-4o",
            "provider": "OpenAI",
            "metadata": {
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
            },
        }
    ]


def _openai_embedding_selection() -> list[dict]:
    return [
        {
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
            "metadata": {
                "embedding_class": "OpenAIEmbeddings",
                "param_mapping": {
                    "model": "model",
                },
                "model_type": "embeddings",
            },
        }
    ]


def test_language_model_override_fields_accept_literals_by_default() -> None:
    from lfx.components.models_and_agents.language_model import LanguageModelComponent

    inputs = {component_input.name: component_input for component_input in LanguageModelComponent.inputs}

    assert inputs["model"].field_type.value == "model"
    assert inputs["model_name"].field_type.value == "str"
    assert inputs["model_name"].load_from_db is False
    assert inputs["provider"].field_type.value == "str"
    assert inputs["provider"].load_from_db is False


def test_language_model_uses_model_name_override_before_building_llm() -> None:
    from lfx.components.models_and_agents import language_model as language_model_module
    from lfx.components.models_and_agents.language_model import LanguageModelComponent

    component = LanguageModelComponent()
    component.set_attributes(
        {
            "model": _openai_language_selection(),
            "model_name": "gpt-4o-mini",
            "provider": "",
            "api_key": "test-key",  # pragma: allowlist secret
            "temperature": 0.1,
            "stream": False,
            "max_tokens": None,
            "base_url_ibm_watsonx": None,
            "project_id": None,
            "ollama_base_url": None,
        }
    )

    override_option = {
        **_openai_language_selection()[0],
        "name": "gpt-4o-mini",
    }
    with (
        patch.object(
            language_model_module, "get_language_model_options", return_value=[override_option]
        ) as mock_get_options,
        patch.object(language_model_module, "get_llm", return_value=object()) as mock_get_llm,
    ):
        component.build_model()

    mock_get_options.assert_called_once_with(user_id=component.user_id)
    model_arg = mock_get_llm.call_args.kwargs["model"]
    assert model_arg == [override_option]


def test_language_model_provider_override_drops_stale_metadata_when_option_lookup_misses() -> None:
    from lfx.components.models_and_agents import language_model as language_model_module
    from lfx.components.models_and_agents.language_model import LanguageModelComponent

    component = LanguageModelComponent()
    component.set_attributes(
        {
            "model": _openai_language_selection(),
            "model_name": "claude-3-5-sonnet-latest",
            "provider": "Anthropic",
            "api_key": "test-key",  # pragma: allowlist secret
            "temperature": 0.1,
            "stream": False,
            "max_tokens": None,
            "base_url_ibm_watsonx": None,
            "project_id": None,
            "ollama_base_url": None,
        }
    )

    with (
        patch.object(language_model_module, "get_language_model_options", return_value=[]) as mock_get_options,
        patch.object(language_model_module, "get_llm", return_value=object()) as mock_get_llm,
    ):
        component.build_model()

    mock_get_options.assert_called_once_with(user_id=component.user_id)
    model_arg = mock_get_llm.call_args.kwargs["model"]
    assert model_arg == [
        {
            "metadata": {},
            "name": "claude-3-5-sonnet-latest",
            "provider": "Anthropic",
            "category": "Anthropic",
        }
    ]


def test_embedding_model_override_fields_accept_literals_by_default() -> None:
    from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent

    inputs = {component_input.name: component_input for component_input in EmbeddingModelComponent.inputs}

    assert inputs["model"].field_type.value == "model"
    assert inputs["model_name"].field_type.value == "str"
    assert inputs["model_name"].load_from_db is False
    assert inputs["provider"].field_type.value == "str"
    assert inputs["provider"].load_from_db is False


def test_embedding_model_uses_model_name_override_before_building_embeddings() -> None:
    from lfx.components.models_and_agents import embedding_model as embedding_model_module
    from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent

    component = EmbeddingModelComponent()
    component.set_attributes(
        {
            "model": _openai_embedding_selection(),
            "model_name": "text-embedding-3-large",
            "provider": "",
            "api_key": "test-key",  # pragma: allowlist secret
            "api_base": "",
            "dimensions": None,
            "chunk_size": 1000,
            "request_timeout": None,
            "max_retries": 3,
            "show_progress_bar": False,
            "model_kwargs": {},
            "base_url_ibm_watsonx": None,
            "project_id": "",
            "truncate_input_tokens": None,
            "input_text": True,
            "ollama_base_url": None,
        }
    )

    override_option = {
        **_openai_embedding_selection()[0],
        "name": "text-embedding-3-large",
    }
    with (
        patch.object(
            embedding_model_module, "get_embedding_model_options", return_value=[override_option]
        ) as mock_get_options,
        patch.object(embedding_model_module, "get_embeddings", return_value=object()) as mock_get_embeddings,
    ):
        component.build_embeddings()

    mock_get_options.assert_called_once_with(user_id=component.user_id)
    model_arg = mock_get_embeddings.call_args.kwargs["model"]
    assert model_arg == [override_option]
