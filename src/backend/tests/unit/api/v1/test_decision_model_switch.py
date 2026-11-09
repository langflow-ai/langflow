"""A decision model switched off in Model Providers never reaches its provider (LE-3117 F4)."""

import asyncio
from unittest.mock import Mock

import pytest
from fastapi import status
from lfx.base.models.decisions import providers
from lfx.base.models.decisions.runtime import evaluate_decision
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest, DecisionResult

REQUEST = DecisionRequest(kind="boolean", question="Is this a complaint?", context="My payment failed.")
MODEL = {"provider": "OpenAI", "name": "gpt-6-luna"}
# The caller's own key, as an API run sends it; no provider is set up in Model Providers.
REQUEST_KEY = {"OPENAI_API_KEY": "sk-caller-key"}  # pragma: allowlist secret


@pytest.fixture
def transport(monkeypatch):
    for name in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "LANGFLOW_OPENAI_BASE_URL", "LANGFLOW_OPENAI_API_BASE"):
        monkeypatch.delenv(name, raising=False)
    # Enabling the model validates credentials before the mocked provider call.
    monkeypatch.setenv("OPENAI_API_KEY", REQUEST_KEY["OPENAI_API_KEY"])
    sent = Mock(
        return_value=DecisionResult(kind="boolean", provider="OpenAI", model="gpt-6-luna", probability_true=0.8)
    )
    monkeypatch.setattr(providers, "evaluate_provider", sent)
    return sent


async def _switch(client, headers, *, enabled: bool) -> None:
    response = await client.post(
        "api/v1/models/enabled_models",
        headers=headers,
        json=[{"provider": "OpenAI", "model_id": "gpt-6-luna", "enabled": enabled, "model_type": "decision"}],
    )
    assert response.status_code == status.HTTP_200_OK, response.text


def _evaluate(user_id):
    return evaluate_decision(REQUEST, model=MODEL, user_id=user_id, request_variables=REQUEST_KEY)


async def test_a_model_switched_off_in_model_providers_stops_the_run(client, logged_in_headers, active_user, transport):
    await _switch(client, logged_in_headers, enabled=False)

    with pytest.raises(DecisionConfigurationError, match=r"^gpt-6-luna is switched off in Model Providers\."):
        await asyncio.to_thread(_evaluate, active_user.id)
    transport.assert_not_called()


async def test_switching_it_back_on_lets_the_run_through(client, logged_in_headers, active_user, transport):
    await _switch(client, logged_in_headers, enabled=False)
    await _switch(client, logged_in_headers, enabled=True)
    transport.reset_mock()  # switching on can make its own key check

    result = await asyncio.to_thread(_evaluate, active_user.id)

    assert result.probability_true == 0.8
    transport.assert_called_once()


async def test_switching_off_the_chat_model_of_the_same_name_doesnt_stop_decisions(
    client, logged_in_headers, active_user, transport
):
    # gpt-6-luna is also an OpenAI chat model; that switch belongs to the language picker.
    response = await client.post(
        "api/v1/models/enabled_models",
        headers=logged_in_headers,
        json=[{"provider": "OpenAI", "model_id": "gpt-6-luna", "enabled": False, "model_type": "llm"}],
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    await asyncio.to_thread(_evaluate, active_user.id)

    transport.assert_called_once()
