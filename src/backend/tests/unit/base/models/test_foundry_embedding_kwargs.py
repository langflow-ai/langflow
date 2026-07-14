"""Regression: blank EmbeddingModelComponent api_base must not wipe Foundry endpoint."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from lfx.base.models.unified_models.instantiation import _compose_embedding_kwargs

pytestmark = pytest.mark.no_blockbuster

FOUNDRY_ENDPOINT = "https://example.services.ai.azure.com/openai/v1"


@pytest.fixture
def unified_models_module():
    module = SimpleNamespace()
    module.get_api_key_for_provider = MagicMock(return_value="test-key")
    module.get_embedding_class = MagicMock(return_value=object)
    module.get_all_variables_for_provider = MagicMock(return_value={"AZURE_AI_FOUNDRY_ENDPOINT": FOUNDRY_ENDPOINT})
    return module


def test_foundry_embedding_kwargs_use_endpoint_when_api_base_blank(unified_models_module):
    composed = _compose_embedding_kwargs(
        "Azure AI Foundry",
        "text-embedding-3-small",
        uuid4(),
        unified_models_module,
        selected_provider="Azure AI Foundry",
        api_base="",  # MessageTextInput default from EmbeddingModelComponent
    )

    assert composed is not None
    _, kwargs = composed
    assert kwargs["base_url"] == FOUNDRY_ENDPOINT
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["api_key"] == "test-key"  # pragma: allowlist secret


def test_foundry_embedding_kwargs_prefer_explicit_api_base(unified_models_module):
    override = "https://override.example/openai/v1"
    composed = _compose_embedding_kwargs(
        "Azure AI Foundry",
        "text-embedding-3-small",
        uuid4(),
        unified_models_module,
        selected_provider="Azure AI Foundry",
        api_base=override,
    )

    assert composed is not None
    _, kwargs = composed
    assert kwargs["base_url"] == override
