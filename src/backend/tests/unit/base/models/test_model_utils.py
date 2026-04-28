"""Tests for lfx.base.models.model_utils.

Regression tests for the LLM Selector "Custom" fallback bug reported on Slack
by Akash Joshi / Anderson Filho: ``get_model_name`` returns ``"Custom"`` for
``AzureChatOpenAI`` and ``ChatWatsonx`` instances even though the model name
is set on a different attribute than the one ``next()`` happens to find first.
"""

from langchain_ibm import ChatWatsonx
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from lfx.base.models.model_utils import get_model_name


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
