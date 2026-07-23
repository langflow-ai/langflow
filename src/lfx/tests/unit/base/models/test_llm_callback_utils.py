"""Unit tests for provider detection in lfx.base.models.llm_callback_utils."""

from lfx.base.models.llm_callback_utils import detect_provider_from_model


def test_azure_openai_not_mislabeled_openai():
    # LE-1993: "azure/gpt-4" contains "gpt"; azure must win over the openai branch.
    assert detect_provider_from_model("azure/gpt-4") == "azure"
    assert detect_provider_from_model("gpt-4o") == "openai"


def test_known_providers():
    assert detect_provider_from_model("claude-3-5-sonnet") == "anthropic"
    assert detect_provider_from_model("gemini-1.5-pro") == "google"
    assert detect_provider_from_model("llama-3-70b") == "meta"
    assert detect_provider_from_model("mistral-large") == "mistral"
    assert detect_provider_from_model("command-r") == "cohere"
    assert detect_provider_from_model("titan-text") == "amazon"


def test_none_and_unknown():
    assert detect_provider_from_model(None) is None
    assert detect_provider_from_model("some-unknown-model") is None
