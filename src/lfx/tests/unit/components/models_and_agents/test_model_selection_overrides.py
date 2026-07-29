from __future__ import annotations

from unittest.mock import MagicMock, patch


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
                    "api_key": "api_key",  # pragma: allowlist secret
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
    assert inputs["provider"].real_time_refresh is True


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


def test_language_model_blank_api_key_uses_effective_override_provider(monkeypatch) -> None:
    from lfx.components.models_and_agents import language_model as language_model_module
    from lfx.components.models_and_agents.language_model import LanguageModelComponent

    component = LanguageModelComponent()
    component.set_attributes(
        {
            "model": _openai_language_selection(),
            "model_name": "claude-test",
            "provider": "Anthropic",
            "api_key": "",
            "temperature": 0.1,
            "stream": False,
            "max_tokens": None,
            "base_url_ibm_watsonx": None,
            "project_id": None,
            "ollama_base_url": None,
        }
    )
    override_option = {
        "name": "claude-test",
        "provider": "Anthropic",
        "metadata": {
            "model_class": "ChatAnthropic",
            "model_name_param": "model",
            "api_key_param": "api_key",  # pragma: allowlist secret
        },
    }
    monkeypatch.setenv("OPENAI_API_KEY", "openai-sentinel")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-sentinel")
    model_constructor = MagicMock(return_value=object())

    with (
        patch.object(language_model_module, "get_language_model_options", return_value=[override_option]),
        patch(
            "lfx.base.models.unified_models.get_model_class",
            return_value=model_constructor,
        ) as mock_get_model_class,
    ):
        component.build_model()

    mock_get_model_class.assert_called_once_with("ChatAnthropic")
    assert model_constructor.call_args.kwargs["api_key"] == "anthropic-sentinel"  # pragma: allowlist secret
    assert model_constructor.call_args.kwargs["api_key"] != "openai-sentinel"  # pragma: allowlist secret


def test_embedding_model_override_fields_accept_literals_by_default() -> None:
    from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent

    inputs = {component_input.name: component_input for component_input in EmbeddingModelComponent.inputs}

    assert inputs["model"].field_type.value == "model"
    assert inputs["model_name"].field_type.value == "str"
    assert inputs["model_name"].load_from_db is False
    assert inputs["provider"].field_type.value == "str"
    assert inputs["provider"].load_from_db is False
    assert inputs["provider"].real_time_refresh is True


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


def test_embedding_model_blank_api_key_uses_effective_override_provider(monkeypatch) -> None:
    from lfx.components.models_and_agents import embedding_model as embedding_model_module
    from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent

    component = EmbeddingModelComponent()
    component.set_attributes(
        {
            "model": [
                {
                    "name": "ibm/slate-125m-english-rtrvr",
                    "provider": "IBM WatsonX",
                    "metadata": {},
                }
            ],
            "model_name": "text-embedding-3-small",
            "provider": "OpenAI",
            "api_key": "",
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
    override_option = _openai_embedding_selection()[0]
    monkeypatch.setenv("WATSONX_APIKEY", "watsonx-sentinel")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-sentinel")
    embedding_constructor = MagicMock(return_value=object())

    with (
        patch.object(embedding_model_module, "get_embedding_model_options", return_value=[override_option]),
        patch(
            "lfx.base.models.unified_models.get_embedding_class",
            return_value=embedding_constructor,
        ) as mock_get_embedding_class,
        patch(
            "lfx.base.models.unified_models.instantiation._get_provider_embedding_model_names",
            return_value=[],
        ),
    ):
        component.build_embeddings()

    mock_get_embedding_class.assert_called_once_with("OpenAIEmbeddings")
    assert embedding_constructor.call_args.kwargs["api_key"] == "openai-sentinel"  # pragma: allowlist secret
    assert embedding_constructor.call_args.kwargs["api_key"] != "watsonx-sentinel"  # pragma: allowlist secret
