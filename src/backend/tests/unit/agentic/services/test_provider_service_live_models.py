"""Live-provider model resolution for the assistant (Ollama et al.).

Reproduced live (2026-06-12, release-1.11.0): with only Ollama configured
the assistant resolves its default model and fallback candidates from the
STATIC catalog (``llama3.3``, ``qwq``, ...) even though the running Ollama
server reports a different set of installed models (``gpt-oss:20b``,
``llama3.2:latest``, ``qwen2.5:1.5b``). Every request without an explicit
(and exactly-matching) model name dies with ``Model not available``.

For providers in ``LIVE_MODEL_PROVIDERS`` the default model and the
fallback candidate walk must come from the live installed-model list when
a ``user_id`` is available to resolve credentials.

The live fetch boundary (``get_live_models_for_provider``) is mocked: it
hits an external Ollama server that CI cannot reproduce. Everything else
runs real.
"""

from unittest.mock import patch

from langflow.agentic.services.provider_service import (
    get_default_model,
    get_provider_model_candidates,
)

MODULE = "langflow.agentic.services.provider_service"

INSTALLED_OLLAMA_MODELS = [
    {"name": "gpt-oss:20b", "tool_calling": True},
    {"name": "llama3.2:latest", "tool_calling": True},
    {"name": "qwen2.5:1.5b", "tool_calling": True},
]


class TestGetDefaultModelLiveProviders:
    def test_should_return_installed_model_when_catalog_default_is_not_installed(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=INSTALLED_OLLAMA_MODELS,
            create=True,
        ):
            default = get_default_model("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert default == "gpt-oss:20b"

    def test_should_keep_catalog_default_when_it_is_installed(self):
        installed = [{"name": "llama3.3", "tool_calling": True}, *INSTALLED_OLLAMA_MODELS]
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=installed,
            create=True,
        ):
            default = get_default_model("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert default == "llama3.3"

    def test_should_fall_back_to_catalog_when_live_fetch_returns_nothing(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=[],
            create=True,
        ):
            default = get_default_model("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert default == "llama3.3"

    def test_should_use_catalog_when_no_user_id_is_available(self):
        assert get_default_model("Ollama") == "llama3.3"

    def test_should_not_fetch_live_models_for_static_providers(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            create=True,
        ) as live_fetch:
            get_default_model("Anthropic", user_id="00000000-0000-0000-0000-000000000001")

        live_fetch.assert_not_called()


class TestOpenAIConditionalLive:
    """OpenAI with OPENAI_BASE_URL behaves like a live provider for the assistant.

    Without a base URL the live fetch returns [] and the static catalog
    stays in charge — key-only OpenAI users see no behavior change.
    """

    SERVER_MODELS = [
        {"name": "gpt-oss:20b", "tool_calling": True},
        {"name": "llama3.2:latest", "tool_calling": True},
    ]

    def test_should_default_to_a_server_model_when_base_url_is_configured(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=self.SERVER_MODELS,
            create=True,
        ):
            default = get_default_model("OpenAI", user_id="00000000-0000-0000-0000-000000000001")

        assert default == "gpt-oss:20b"

    def test_should_walk_server_models_as_fallback_candidates(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=self.SERVER_MODELS,
            create=True,
        ):
            candidates = get_provider_model_candidates("OpenAI", user_id="00000000-0000-0000-0000-000000000001")

        assert candidates == ["gpt-oss:20b", "llama3.2:latest"]

    def test_should_keep_catalog_default_when_live_fetch_is_empty(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=[],
            create=True,
        ):
            default = get_default_model("OpenAI", user_id="00000000-0000-0000-0000-000000000001")

        assert default is not None
        assert default != "gpt-oss:20b"


class TestGetProviderModelCandidatesLiveProviders:
    def test_should_walk_installed_models_when_provider_is_live(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=INSTALLED_OLLAMA_MODELS,
            create=True,
        ):
            candidates = get_provider_model_candidates("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert candidates == ["gpt-oss:20b", "llama3.2:latest", "qwen2.5:1.5b"]

    def test_should_exclude_installed_models_without_tool_calling(self):
        installed = [
            {"name": "gpt-oss:20b", "tool_calling": True},
            {"name": "no-tools-model", "tool_calling": False},
        ]
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=installed,
            create=True,
        ):
            candidates = get_provider_model_candidates("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert candidates == ["gpt-oss:20b"]

    def test_should_fall_back_to_catalog_when_live_fetch_returns_nothing(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=[],
            create=True,
        ):
            candidates = get_provider_model_candidates("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert candidates
        assert candidates[0] == "llama3.3"

    def test_should_use_catalog_when_no_user_id_is_available(self):
        candidates = get_provider_model_candidates("Ollama")

        assert candidates
        assert candidates[0] == "llama3.3"


class TestCloudModelOrdering:
    """Ollama cloud models (``:cloud`` tag) may 403 without a subscription.

    Reproduced live (2026-06-12): ``glm-5:cloud`` listed FIRST by /api/tags
    became the assistant default and every request died with
    ``requires a subscription ... (status code: 403)``. Local models must
    come first; cloud models stay selectable but are tried last.
    """

    INSTALLED_WITH_CLOUD_FIRST = [
        {"name": "glm-5:cloud", "tool_calling": True},
        {"name": "gpt-oss:20b", "tool_calling": True},
        {"name": "llama3.2:latest", "tool_calling": True},
    ]

    def test_should_not_default_to_a_cloud_model_when_local_models_exist(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=self.INSTALLED_WITH_CLOUD_FIRST,
            create=True,
        ):
            default = get_default_model("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert default == "gpt-oss:20b"

    def test_should_order_candidates_local_first_cloud_last(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=self.INSTALLED_WITH_CLOUD_FIRST,
            create=True,
        ):
            candidates = get_provider_model_candidates("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert candidates == ["gpt-oss:20b", "llama3.2:latest", "glm-5:cloud"]

    def test_should_keep_cloud_models_when_they_are_the_only_option(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            return_value=[{"name": "glm-5:cloud", "tool_calling": True}],
            create=True,
        ):
            default = get_default_model("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert default == "glm-5:cloud"


class TestLiveFetchFailOpen:
    """C2/C9: any exception from the live-fetch boundary degrades to catalog behavior (fail-open)."""

    def test_should_return_empty_when_live_fetch_raises_unexpected_error(self):
        from langflow.agentic.services.provider_service import list_installed_tool_calling_models

        with patch(
            f"{MODULE}.get_live_models_for_provider",
            side_effect=RuntimeError("adapter blew up"),
            create=True,
        ):
            result = list_installed_tool_calling_models("Ollama", "00000000-0000-0000-0000-000000000001")

        assert result == []

    def test_should_fall_back_to_catalog_candidates_when_live_fetch_raises(self):
        with patch(
            f"{MODULE}.get_live_models_for_provider",
            side_effect=RuntimeError("adapter blew up"),
            create=True,
        ):
            candidates = get_provider_model_candidates("Ollama", user_id="00000000-0000-0000-0000-000000000001")
            default = get_default_model("Ollama", user_id="00000000-0000-0000-0000-000000000001")

        assert candidates
        assert candidates[0] == "llama3.3"
        assert default == "llama3.3"
