"""Optional OPENAI_BASE_URL — point the OpenAI provider at a compatible server.

User report (Discord, 2026-06-11): "i can't set up custom provider or add
base url to openai for langflow assistant." Verified live (2026-06-12):
the OpenAI provider declares only OPENAI_API_KEY, a saved OPENAI_BASE_URL
global variable is ignored everywhere, and key validation always hits
api.openai.com — so a key for a local OpenAI-compatible server (vLLM,
LM Studio, Ollama's /v1) cannot even be saved.

Design: OPENAI_BASE_URL is OPTIONAL — the existing experience (paste an
API key, static catalog) is byte-identical when it is not set. With it
set, ChatOpenAI targets the custom server, validation validates against
it, and the model list comes live from ``{base}/models``.

Mock boundaries: ChatOpenAI construction, variable lookups, and the HTTP
fetch — external servers CI cannot reproduce.
"""

from unittest.mock import MagicMock, patch

from lfx.base.models.model_metadata import (
    CONDITIONAL_LIVE_MODEL_PROVIDERS,
    LIVE_MODEL_PROVIDERS,
)
from lfx.base.models.model_utils import (
    fetch_live_openai_compatible_models,
    replace_with_live_models,
)
from lfx.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_provider_all_variables,
    get_provider_required_variable_keys,
    validate_model_provider_key,
)
from lfx.base.models.unified_models.instantiation import get_llm
from lfx.utils.util import transform_localhost_url

USER_ID = "00000000-0000-0000-0000-000000000001"
CUSTOM_BASE_URL = "http://localhost:11434/v1"

OPENAI_MODEL_SPEC = [
    {
        "name": "gpt-oss:20b",
        "provider": "OpenAI",
        "metadata": {},
    }
]


class TestProviderMetadata:
    def test_should_declare_openai_base_url_as_optional_variable(self):
        variables = get_provider_all_variables("OpenAI")
        base_url_var = next((v for v in variables if v["variable_key"] == "OPENAI_BASE_URL"), None)

        assert base_url_var is not None, "OpenAI must declare an OPENAI_BASE_URL variable"
        assert base_url_var["required"] is False, "Base URL must be optional — key-only setup stays valid"
        assert base_url_var["is_secret"] is False

    def test_should_keep_openai_required_keys_unchanged(self):
        assert get_provider_required_variable_keys("OpenAI") == ["OPENAI_API_KEY"]

    def test_should_keep_openai_primary_variable_as_the_api_key(self):
        assert get_model_provider_variable_mapping()["OpenAI"] == "OPENAI_API_KEY"


class TestGetLlmBaseUrl:
    def test_should_pass_base_url_to_chat_openai_when_variable_is_set(self):
        with patch(
            "lfx.base.models.unified_models.get_all_variables_for_provider",
            return_value={"OPENAI_API_KEY": "sk-test", "OPENAI_BASE_URL": CUSTOM_BASE_URL},
        ):
            llm = get_llm(OPENAI_MODEL_SPEC, USER_ID, api_key="sk-test")

        assert llm.openai_api_base == transform_localhost_url(CUSTOM_BASE_URL)

    def test_should_not_set_base_url_when_variable_is_absent(self):
        with patch(
            "lfx.base.models.unified_models.get_all_variables_for_provider",
            return_value={"OPENAI_API_KEY": "sk-test"},
        ):
            llm = get_llm(OPENAI_MODEL_SPEC, USER_ID, api_key="sk-test")

        assert llm.openai_api_base is None


class TestKeyValidationWithBaseUrl:
    def test_should_validate_against_the_custom_endpoint_when_base_url_is_set(self):
        chat_openai = MagicMock()
        with patch("langchain_openai.ChatOpenAI", chat_openai):
            validate_model_provider_key(
                "OpenAI",
                {"OPENAI_API_KEY": "anything", "OPENAI_BASE_URL": CUSTOM_BASE_URL},
                model_name="gpt-oss:20b",
            )

        assert chat_openai.call_args.kwargs.get("base_url") == transform_localhost_url(CUSTOM_BASE_URL)

    def test_should_not_pass_base_url_when_not_configured(self):
        chat_openai = MagicMock()
        with patch("langchain_openai.ChatOpenAI", chat_openai):
            validate_model_provider_key("OpenAI", {"OPENAI_API_KEY": "sk-test"}, model_name="gpt-4o-mini")

        assert "base_url" not in chat_openai.call_args.kwargs


class TestLiveOpenAICompatibleModels:
    def test_should_return_empty_when_no_base_url_is_configured(self):
        with patch(
            "lfx.base.models.model_utils.get_provider_variable_value",
            return_value=None,
        ):
            assert fetch_live_openai_compatible_models(USER_ID, "llm") == []

    def test_should_list_models_from_the_custom_server(self):
        response = MagicMock()
        response.json.return_value = {"data": [{"id": "gpt-oss:20b"}, {"id": "llama3.2:latest"}]}
        response.raise_for_status.return_value = None
        with (
            patch(
                "lfx.base.models.model_utils.get_provider_variable_value",
                side_effect=lambda _uid, key: CUSTOM_BASE_URL if key == "OPENAI_BASE_URL" else "sk-test",
            ),
            patch("requests.get", return_value=response) as http_get,
        ):
            models = fetch_live_openai_compatible_models(USER_ID, "llm")

        assert [m["name"] for m in models] == ["gpt-oss:20b", "llama3.2:latest"]
        assert all(m["tool_calling"] for m in models)
        assert http_get.call_args.args[0] == f"{CUSTOM_BASE_URL}/models"

    def test_should_not_list_embeddings_from_the_custom_server(self):
        with patch(
            "lfx.base.models.model_utils.get_provider_variable_value",
            return_value=CUSTOM_BASE_URL,
        ):
            assert fetch_live_openai_compatible_models(USER_ID, "embeddings") == []


class TestConditionalLiveReplacement:
    """OpenAI is live ONLY when a base URL is configured.

    A normal OpenAI user (key only) must keep the curated static catalog —
    an empty live fetch must NOT wipe it (that wipe is the existing,
    intentional behavior for always-live providers like Ollama).
    """

    def test_should_declare_openai_as_conditional_live_provider(self):
        assert "OpenAI" in CONDITIONAL_LIVE_MODEL_PROVIDERS
        assert "OpenAI" not in LIVE_MODEL_PROVIDERS

    def test_should_keep_static_catalog_when_openai_live_fetch_is_empty(self):
        catalog = [{"provider": "OpenAI", "models": [{"model_name": "gpt-4o-mini", "metadata": {}}]}]
        with patch(
            "lfx.base.models.model_utils.get_live_models_for_provider",
            return_value=[],
        ):
            replace_with_live_models(catalog, USER_ID, ["OpenAI"], model_type="llm")

        assert [m["model_name"] for m in catalog[0]["models"]] == ["gpt-4o-mini"]

    def test_should_replace_catalog_with_server_models_when_base_url_is_configured(self):
        catalog = [{"provider": "OpenAI", "models": [{"model_name": "gpt-4o-mini", "metadata": {}}]}]
        live = [{"name": "gpt-oss:20b", "provider": "OpenAI", "tool_calling": True}]
        with patch(
            "lfx.base.models.model_utils.get_live_models_for_provider",
            return_value=live,
        ):
            replace_with_live_models(catalog, USER_ID, ["OpenAI"], model_type="llm")

        assert [m["model_name"] for m in catalog[0]["models"]] == ["gpt-oss:20b"]


class TestMalformedModelsPayload:
    """C7: a non-conforming /models payload from an arbitrary server degrades to [], not raises."""

    def _fetch(self, payload):
        from lfx.base.models import model_utils

        class FakeResp:
            def raise_for_status(self):
                return None

            def json(self):
                return payload

        with (
            patch.object(
                model_utils,
                "get_provider_variable_value",
                side_effect=lambda _uid, key: CUSTOM_BASE_URL if key == "OPENAI_BASE_URL" else "sk-x",
            ),
            patch("requests.get", return_value=FakeResp()),
        ):
            return fetch_live_openai_compatible_models(USER_ID, "llm")

    def test_should_return_empty_when_payload_is_a_list_not_a_dict(self):
        assert self._fetch(["gpt-4", "gpt-3.5"]) == []

    def test_should_return_empty_when_data_is_a_list_of_strings(self):
        assert self._fetch({"data": ["gpt-4"]}) == []

    def test_should_skip_non_dict_entries_but_keep_valid_ones(self):
        models = self._fetch({"data": ["junk", {"id": "gpt-oss:20b"}]})
        assert [m["name"] for m in models] == ["gpt-oss:20b"]


class TestBaseUrlNormalizationParity:
    """C8/C5: validation normalizes OPENAI_BASE_URL like runtime (Docker localhost parity)."""

    TRANSFORMED = "http://host.docker.internal:11434/v1"

    def test_validation_normalizes_base_url_like_runtime(self):
        chat_openai = MagicMock()
        with (
            patch("langchain_openai.ChatOpenAI", chat_openai),
            patch("lfx.utils.util.transform_localhost_url", return_value=self.TRANSFORMED),
        ):
            validate_model_provider_key(
                "OpenAI",
                {"OPENAI_API_KEY": "sk-x", "OPENAI_BASE_URL": "http://localhost:11434/v1"},
                model_name="gpt-oss:20b",
            )

        assert chat_openai.call_args.kwargs.get("base_url") == self.TRANSFORMED

    def test_get_llm_normalizes_base_url(self):
        with patch(
            "lfx.base.models.unified_models.get_all_variables_for_provider",
            return_value={"OPENAI_API_KEY": "sk-test", "OPENAI_BASE_URL": CUSTOM_BASE_URL},
        ):
            llm = get_llm(OPENAI_MODEL_SPEC, USER_ID, api_key="sk-test")

        assert llm.openai_api_base == transform_localhost_url(CUSTOM_BASE_URL)
