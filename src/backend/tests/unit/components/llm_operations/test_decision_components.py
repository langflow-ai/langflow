"""The Decision Model component runs end to end for every provider with only the HTTP boundary replaced."""

import httpx
import pytest
from lfx.base.models.unified_models import get_provider_secret_variable_key
from lfx.components.llm_operations.decision_model import DecisionModelComponent
from lfx.schema.properties import Usage

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


class TestDecisionModelComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return DecisionModelComponent

    @pytest.fixture(params=list(MODELS))
    def provider(self, request):
        return request.param

    @pytest.fixture
    def default_kwargs(self, provider):
        return {
            "model": [{"provider": provider, "name": MODELS[provider]}],
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
    def provider_http(self, monkeypatch, provider):
        monkeypatch.setenv(get_provider_secret_variable_key(provider), "tenant-key")  # pragma: allowlist secret
        sent = []

        def post(url, **kwargs):
            sent.append((url, kwargs))
            return httpx.Response(200, json=_choice_response(provider))

        monkeypatch.setattr("lfx.base.models.decisions.providers.provider_safe_httpx_post", post)
        return sent

    async def test_the_tokens_a_decision_used_are_reported(
        self, component_class, default_kwargs, provider, monkeypatch
    ):
        """Chat Output adds these to the Playground message, as it does a language model's."""
        response = {**_choice_response(provider), "usage": {"input_tokens": 52, "output_tokens": 1}}
        monkeypatch.setattr(
            "lfx.base.models.decisions.providers.provider_safe_httpx_post",
            lambda _url, **_kwargs: httpx.Response(200, json=response),
        )
        component = await self.component_setup(component_class, default_kwargs)
        component.evaluate()
        assert component._token_usage == Usage(input_tokens=52, output_tokens=1, total_tokens=53)

    async def test_choice_evidence_from_the_provider_response(
        self, component_class, default_kwargs, provider, provider_http
    ):
        component = await self.component_setup(component_class, default_kwargs)
        result = component.evaluate().data
        url, request = provider_http.pop()
        assert url == ENDPOINTS[provider]
        assert request["headers"]["Authorization"] == "Bearer tenant-key"
        assert request["follow_redirects"] is False
        assert result["provider"] == provider
        assert result["probabilities"] == {"a": 0.3, "b": 0.7}
        assert result["selected_option"] == "b"
        assert "context" not in result["request"]
