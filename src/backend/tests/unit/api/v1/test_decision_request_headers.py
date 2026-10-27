"""X-LANGFLOW-GLOBAL-VAR-* headers reach the decision runtime under the names header extraction gives them."""

from unittest.mock import Mock

import pytest
from langflow.api.utils.core import extract_global_variables_from_headers
from lfx.base.models.decisions import providers
from lfx.base.models.decisions.runtime import evaluate_decision
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest, DecisionResult

REQUEST = DecisionRequest(kind="boolean", question="Is this a complaint?", context="My payment failed.")
MODEL = {"provider": "OpenAI", "name": "gpt-6-luna"}


@pytest.fixture
def transport(monkeypatch):
    for name in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "LANGFLOW_OPENAI_BASE_URL", "LANGFLOW_OPENAI_API_BASE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ambient-key")  # pragma: allowlist secret
    sent = Mock(
        return_value=DecisionResult(kind="boolean", provider="OpenAI", model="gpt-6-luna", probability_true=0.8)
    )
    monkeypatch.setattr(providers, "evaluate_provider", sent)
    return sent


@pytest.mark.parametrize("header", ["X-LANGFLOW-GLOBAL-VAR-OPENAI-BASE-URL", "X-LANGFLOW-GLOBAL-VAR-OPENAI-API-BASE"])
def test_a_proxy_endpoint_header_refuses_the_hosted_api(transport, header):
    headers = {header: "https://proxy.example/v1", "X-LANGFLOW-GLOBAL-VAR-OPENAI_API_KEY": "sk-proxy-key"}
    with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
        evaluate_decision(REQUEST, model=MODEL, request_variables=extract_global_variables_from_headers(headers))
    transport.assert_not_called()


def test_a_dashed_key_header_beats_the_ambient_key(transport):
    headers = {"X-LANGFLOW-GLOBAL-VAR-OPENAI-API-KEY": "sk-caller-key"}
    evaluate_decision(REQUEST, model=MODEL, request_variables=extract_global_variables_from_headers(headers))
    assert transport.call_args.kwargs["api_key"] == "sk-caller-key"
