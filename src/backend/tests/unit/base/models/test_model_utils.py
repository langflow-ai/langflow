"""Tests for lfx.base.models.model_utils.

Regression tests for the LLM Selector "Custom" fallback bug reported on Slack
by Akash Joshi / Anderson Filho: ``get_model_name`` returns ``"Custom"`` for
``AzureChatOpenAI`` and ``ChatWatsonx`` instances even though the model name
is set on a different attribute than the one ``next()`` happens to find first.
"""

# langchain-ibm / ibm-watsonx-ai are core langflow-base deps importable on every
# supported Python version (3.10-3.14), so import directly: a hard failure here
# surfaces a real import regression instead of silently skipping the suite.
# (ibm-watsonx-ai 1.5.13 fixed the Python 3.14 StrEnum initialization
# incompatibility that previously forced the upstream <3.14 cap.)
from langchain_ibm import ChatWatsonx
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from lfx.base.models.model_metadata import create_model_metadata
from lfx.base.models.model_utils import fetch_live_watsonx_models, get_model_name


class _AttrBag:
    """Minimal stand-in LLM with arbitrary attributes for unit testing."""

    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)


class TestGetModelName:
    """get_model_name must return the first non-empty model identifier."""

    def test_should_return_deployment_name_when_model_name_is_none_azure_shape(self):
        """Azure-shaped object: model_name=None must fall through to deployment_name."""
        llm = _AttrBag(model_name=None, deployment_name="my-gpt-4o-deployment")
        assert get_model_name(llm) == "my-gpt-4o-deployment"

    def test_should_return_model_id_when_model_is_none_watsonx_shape(self):
        """Watsonx-shaped object: model=None must fall through to model_id."""
        llm = _AttrBag(model=None, model_id="meta-llama/llama-3-3-70b-instruct")
        assert get_model_name(llm) == "meta-llama/llama-3-3-70b-instruct"

    def test_should_skip_empty_string_attribute_and_return_next_truthy_one(self):
        """An empty string attribute must be treated as missing, not returned."""
        llm = _AttrBag(model_name="", model_id="actual-id")
        assert get_model_name(llm) == "actual-id"

    def test_should_return_first_set_attribute_in_priority_order(self):
        """When multiple attrs are set, the first one in the priority list wins."""
        llm = _AttrBag(model_name="primary-name", model_id="secondary-id")
        assert get_model_name(llm) == "primary-name"

    def test_should_return_display_name_when_all_known_attributes_are_none(self):
        """All four attrs None ⇒ falls back to default display_name."""
        llm = _AttrBag(model_name=None, model=None, model_id=None, deployment_name=None)
        assert get_model_name(llm) == "Custom"

    def test_should_return_custom_display_name_when_caller_overrides_default(self):
        """Caller-provided display_name must be used as the fallback."""
        llm = _AttrBag()
        assert get_model_name(llm, display_name="MyFallback") == "MyFallback"

    def test_should_return_display_name_when_object_has_no_known_attributes(self):
        """Object with none of the four checked attrs ⇒ returns display_name."""

        class _Bare:
            unrelated_field = "ignored"

        assert get_model_name(_Bare()) == "Custom"

    def test_should_skip_other_falsy_values_and_return_next_truthy_one(self):
        """Falsy values like 0, empty list, empty dict must be skipped, not returned."""
        # Defensive: even though attribute values "should" be strings, a buggy
        # provider class could ship a default of 0 or [] — skip and try next.
        llm_zero = _AttrBag(model_name=0, model_id="real-id")
        assert get_model_name(llm_zero) == "real-id"

        llm_empty_list = _AttrBag(model_name=[], model_id="real-id")
        assert get_model_name(llm_empty_list) == "real-id"

    # ──────────────────────────────────────────────────────────────────────
    # Integration tests against real LangChain classes — no network calls.
    # ──────────────────────────────────────────────────────────────────────

    def test_should_resolve_model_name_for_real_chat_openai(self):
        """Control case: ChatOpenAI(model='gpt-4o') exposes model_name correctly."""
        llm = ChatOpenAI(model="gpt-4o", api_key="sk-fake")
        assert get_model_name(llm) == "gpt-4o"

    def test_should_resolve_deployment_name_for_real_azure_chat_openai(self):
        """AzureChatOpenAI exposes model_name=None and deployment_name=<actual>."""
        llm = AzureChatOpenAI(
            azure_deployment="my-gpt-4o-deployment",
            api_version="2024-02-01",
            azure_endpoint="https://example.openai.azure.com",
            api_key="fake",
        )
        assert get_model_name(llm) == "my-gpt-4o-deployment"

    def test_should_resolve_model_id_for_real_chat_watsonx(self):
        """ChatWatsonx exposes model=None and model_id=<actual>; built via model_construct to skip auth."""
        llm = ChatWatsonx.model_construct(
            model_id="meta-llama/llama-3-3-70b-instruct",
            url="https://us-south.ml.cloud.ibm.com",
            apikey="fake",
            project_id="fake",
        )
        assert get_model_name(llm) == "meta-llama/llama-3-3-70b-instruct"


class TestFetchLiveWatsonxModelsRespectsStaticToolCalling:
    """Live-fetched WatsonX models must honor static tool_calling metadata.

    Regression: ``fetch_live_watsonx_models`` blanket-sets ``tool_calling=True``
    for every LLM returned from the WatsonX foundation_model_specs endpoint,
    even when the static catalog declares the model as ``tool_calling=False``
    (e.g. code-instruct or guardian variants). The Agent dropdown filters on
    ``tool_calling=True`` and consequently surfaces models that will fail at
    runtime when bound with tools.
    """

    NON_TOOL_MODEL = "ibm/granite-3b-code-instruct"

    @staticmethod
    def _fake_static_llm_metadata():
        """Static catalog entry declaring the model as non-tool-calling."""
        return [
            create_model_metadata(
                provider="IBM WatsonX",
                name=TestFetchLiveWatsonxModelsRespectsStaticToolCalling.NON_TOOL_MODEL,
                icon="IBM",
                model_type="llm",
                tool_calling=False,
            ),
        ]

    def test_live_fetch_preserves_static_tool_calling_false(self, monkeypatch):
        """A model whose static metadata says tool_calling=False must come back as False."""
        # Force the live API to return the model name we declared as non-tool-calling.
        monkeypatch.setattr(
            "lfx.base.models.model_utils.get_provider_variable_value",
            lambda *_args, **_kwargs: "https://us-south.ml.cloud.ibm.com",
        )
        monkeypatch.setattr(
            "lfx.base.models.model_utils.get_watsonx_llm_models",
            lambda *_args, **_kwargs: [self.NON_TOOL_MODEL],
        )
        # Static catalog: the model is known and explicitly marked non-tool-calling.
        monkeypatch.setattr(
            "lfx.base.models.model_utils.WATSONX_LLM_METADATA",
            self._fake_static_llm_metadata(),
        )

        models = fetch_live_watsonx_models(user_id="test-user", model_type="llm")

        assert models, "Expected the live fetch to return the mocked model"
        match = next((m for m in models if m["name"] == self.NON_TOOL_MODEL), None)
        assert match is not None, f"{self.NON_TOOL_MODEL} missing from live results"
        assert match["tool_calling"] is False, (
            f"{self.NON_TOOL_MODEL} is declared tool_calling=False in static metadata "
            "but fetch_live_watsonx_models returned tool_calling=True. The live-fetch "
            "path is overriding static capability flags and will surface non-tool-capable "
            "models in the Agent dropdown."
        )

    def test_live_fetch_defaults_unknown_models_to_tool_calling_true(self, monkeypatch):
        """Models not in the static catalog default to tool_calling=True (current behavior)."""
        unknown_model = "ibm/some-future-model-xyz"
        monkeypatch.setattr(
            "lfx.base.models.model_utils.get_provider_variable_value",
            lambda *_args, **_kwargs: "https://us-south.ml.cloud.ibm.com",
        )
        monkeypatch.setattr(
            "lfx.base.models.model_utils.get_watsonx_llm_models",
            lambda *_args, **_kwargs: [unknown_model],
        )
        monkeypatch.setattr(
            "lfx.base.models.model_utils.WATSONX_LLM_METADATA",
            self._fake_static_llm_metadata(),  # does not contain unknown_model
        )

        models = fetch_live_watsonx_models(user_id="test-user", model_type="llm")

        match = next((m for m in models if m["name"] == unknown_model), None)
        assert match is not None
        assert match["tool_calling"] is True, (
            "Unknown models (not present in static catalog) should default to "
            "tool_calling=True to preserve current behavior for unenumerated models."
        )
