"""Bug #1 (PR-12575): Gemini died with "Unknown model class: ChatGoogleGenerativeAI".

The agentic ``build_model_config`` hardcoded model-class names in a dict that
drifted from the central model registry: Google Generative AI mapped to
``ChatGoogleGenerativeAI``, but the registry only knows
``ChatGoogleGenerativeAIFixed`` — so selecting any Gemini model and sending a
prompt died at the run with ``ValueError: Unknown model class:
ChatGoogleGenerativeAI``. Groq / Azure OpenAI were latent variants of the same
gap (their class names were absent from the registry entirely).

These tests assert the EXACT failing contract: the model class
``build_model_config`` emits must be one the central registry can resolve.
"""

from __future__ import annotations

import pytest
from langflow.agentic.flows.model_config import build_model_config
from lfx.base.models.unified_models.class_registry import get_model_class


def _model_class_is_resolvable(class_name: str) -> None:
    """Fail only on the bug's exact error — ValueError('Unknown model class').

    A missing optional provider package raises ImportError (with an install
    hint), which is a different, acceptable failure mode — not the registry gap
    this bug is about.
    """
    try:
        get_model_class(class_name)
    except ValueError as exc:  # the exact bug: "Unknown model class: ..."
        pytest.fail(f"model class not registered: {exc}")
    except ImportError:
        pass


class TestBuildModelConfigUsesRegisteredClassNames:
    def test_should_use_registered_class_when_provider_is_google(self):
        config = build_model_config("Google Generative AI", "gemini-2.5-pro")
        # The stale alias "ChatGoogleGenerativeAI" is what broke Gemini.
        assert config[0]["metadata"]["model_class"] == "ChatGoogleGenerativeAIFixed"

    def test_should_emit_a_resolvable_class_when_provider_is_google(self):
        # Exact error path: the run resolved the class via get_model_class,
        # which raised "Unknown model class: ChatGoogleGenerativeAI".
        config = build_model_config("Google Generative AI", "gemini-2.5-pro")
        _model_class_is_resolvable(config[0]["metadata"]["model_class"])

    @pytest.mark.parametrize(
        ("provider", "expected"),
        [("OpenAI", "ChatOpenAI"), ("Anthropic", "ChatAnthropic")],
    )
    def test_should_keep_openai_and_anthropic_class_names(self, provider, expected):
        assert build_model_config(provider, "m")[0]["metadata"]["model_class"] == expected


class TestRegistryKnowsGroqAndAzure:
    """Latent variant of Bug #1 — Groq / Azure class names must be registered.

    Their class names were missing from the registry entirely, so selecting
    either provider raised "Unknown model class" the same way Gemini did.
    """

    @pytest.mark.parametrize("class_name", ["ChatGroq", "AzureChatOpenAI"])
    def test_should_resolve_groq_and_azure_without_unknown_class_error(self, class_name):
        _model_class_is_resolvable(class_name)
