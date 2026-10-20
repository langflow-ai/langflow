"""Standalone decision evaluators run end to end with only the HTTP boundary replaced."""

import httpx
import pytest
from lfx.base.models.decisions.providers import API_KEY_VARIABLES
from lfx.components.llm_operations.openai_decision import OpenAIDecisionComponent
from lfx.components.llm_operations.perplexity_decision import PerplexityDecisionComponent
from lfx.components.llm_operations.typesafe_decision import TypeSafeDecisionComponent

from tests.base import ComponentTestBaseWithoutClient

MODELS = {"TypeSafe": "jev-latest", "Perplexity": "pplx-decider-latest", "OpenAI": "gpt-6-luna"}
ENDPOINTS = {
    "TypeSafe": "https://api.typesafe.ai/v1/systemone",
    "Perplexity": "https://api.perplexity.ai/v1/decisions",
    "OpenAI": "https://api.openai.com/v1/decisions",
}


def _choice_response(provider: str) -> dict:
    if provider == "OpenAI":
        answer = {
            "name": "decision",
            "type": "choice",
            "probabilities": [{"value": "a", "probability": 0.3}, {"value": "b", "probability": 0.7}],
            "choice": "b",
        }
        return {"model": MODELS[provider], "answers": [answer]}
    answer = {"type": "choice", "probabilities": {"a": 0.3, "b": 0.7}, "choice": "b", "confidence": 0.4}
    return {"model": MODELS[provider], "answers": {"decision": answer}}


class DecisionComponentContract(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def default_kwargs(self, component_class):
        return {
            "model": [{"provider": component_class.provider, "name": MODELS[component_class.provider]}],
            "kind": "Choice",
            "context": "The invoice was charged twice.",
            "question": "Which team handles this?",
            "candidates": [
                {"id": "a", "label": "Support", "description": ""},
                {"id": "b", "label": "Billing", "description": "Payments and invoices"},
            ],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.fixture(autouse=True)
    def provider_http(self, monkeypatch, component_class):
        monkeypatch.setenv(API_KEY_VARIABLES[component_class.provider], "tenant-key")  # pragma: allowlist secret
        sent = []

        def post(url, **kwargs):
            sent.append((url, kwargs))
            return httpx.Response(200, json=_choice_response(component_class.provider))

        monkeypatch.setattr("lfx.base.models.decisions.providers.provider_safe_httpx_post", post)
        return sent

    async def test_choice_evidence_from_the_provider_response(self, component_class, default_kwargs, provider_http):
        component = await self.component_setup(component_class, default_kwargs)
        result = component.evaluate().data
        url, request = provider_http.pop()
        assert url == ENDPOINTS[component_class.provider]
        assert request["headers"]["Authorization"] == "Bearer tenant-key"
        assert request["follow_redirects"] is False
        assert result["provider"] == component_class.provider
        assert result["probabilities"] == {"a": 0.3, "b": 0.7}
        assert result["selected_option"] == "b"
        assert "context" not in result["request"]


class TestTypeSafeDecisionComponent(DecisionComponentContract):
    @pytest.fixture
    def component_class(self):
        return TypeSafeDecisionComponent


class TestPerplexityDecisionComponent(DecisionComponentContract):
    @pytest.fixture
    def component_class(self):
        return PerplexityDecisionComponent


class TestOpenAIDecisionComponent(DecisionComponentContract):
    @pytest.fixture
    def component_class(self):
        return OpenAIDecisionComponent
