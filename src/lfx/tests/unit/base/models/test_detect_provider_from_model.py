"""Provider attribution for the ``gen_ai.provider.name`` metric attribute.

This decides which provider an operator sees against outbound LLM latency and errors, so
getting it wrong is not cosmetic: an Azure outage reads as an OpenAI outage, and per-provider
cost and latency attribution is wrong for every deployment on Azure.

Detection is substring matching over the model name, which makes order significant. Azure
deployments are conventionally named after the model they serve (``azure-gpt-4``,
``gpt-4-azure``), so a name carries both hints and whichever branch runs first wins.
"""

from __future__ import annotations

import pytest
from lfx.base.models.llm_callback_utils import detect_provider_from_model


@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        # Azure deployments carrying the served model's name. These are the realistic ones:
        # the portal defaults a deployment name to the model, and teams prefix or suffix it.
        ("azure-gpt-4", "azure"),
        ("azure-gpt-35-turbo", "azure"),
        ("gpt-4-azure", "azure"),
        ("AZURE-GPT-4", "azure"),
        # Azure serves more than OpenAI models.
        ("azure-claude", "azure"),
        ("my-azure-deployment", "azure"),
    ],
)
def test_azure_wins_over_the_model_it_serves(model_name, expected):
    """The regression. Azure is who serves the call; the model name is not the provider."""
    assert detect_provider_from_model(model_name) == expected


@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        ("gpt-4", "openai"),
        ("gpt-4o-mini", "openai"),
        ("text-davinci-003", "openai"),
        ("claude-3-5-sonnet", "anthropic"),
        ("gemini-1.5-pro", "google"),
        ("llama-3.1-70b", "meta"),
        ("mistral-large", "mistral"),
        ("mixtral-8x7b", "mistral"),
        ("command-r-plus", "cohere"),
        ("amazon.titan-text-express-v1", "amazon"),
    ],
)
def test_direct_providers_are_unchanged(model_name, expected):
    """The control. Reordering must not move anything that was already right."""
    assert detect_provider_from_model(model_name) == expected


@pytest.mark.parametrize("model_name", [None, "", "some-internal-model"])
def test_an_unknown_model_is_none_rather_than_a_guess(model_name):
    """None becomes ``unknown`` at the call site, which is honest. A wrong provider is not."""
    assert detect_provider_from_model(model_name) is None
