"""Bug (PR-12575): user asks for gpt-5.4, canvas shows the assistant's gpt-5.5.

Fix part 1 — the TranslationFlow extracts the model the user explicitly named
and ``classify_intent`` carries it on ``IntentResult.requested_model`` /
``requested_provider`` so a deterministic downstream step can ENFORCE it on the
Agent nodes (never the assistant's own runtime model).

These tests cover the PARSER contract: given the TranslationFlow's JSON output,
the requested model/provider are surfaced (and stay ``None`` when absent).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

MODULE = "langflow.agentic.services.helpers.intent_classification"


async def _classify(response_json: str):
    from langflow.agentic.services.helpers.intent_classification import classify_intent

    with (
        patch(f"{MODULE}.execute_flow_file", new_callable=AsyncMock, return_value={"result": response_json}),
        patch(f"{MODULE}.extract_response_text", return_value=response_json),
    ):
        return await classify_intent("create a flow with an agent using the OpenAI gpt-5.4 model", {})


@pytest.mark.asyncio
async def test_should_extract_requested_model_and_provider_from_translation_json():
    result = await _classify(
        '{"translation": "create a flow with an agent using the OpenAI gpt-5.4 model", '
        '"intent": "build_flow", "requested_model": "gpt-5.4", "requested_provider": "OpenAI"}'
    )

    assert result.requested_model == "gpt-5.4"
    assert result.requested_provider == "OpenAI"


@pytest.mark.asyncio
async def test_should_leave_requested_model_none_when_user_named_no_model():
    result = await _classify('{"translation": "build me a chatbot flow", "intent": "build_flow"}')

    assert result.requested_model is None
    assert result.requested_provider is None


@pytest.mark.asyncio
async def test_should_treat_empty_requested_model_as_none():
    # The prompt emits empty strings when no model is named; normalize to None.
    result = await _classify(
        '{"translation": "build me a chatbot flow", "intent": "build_flow", '
        '"requested_model": "", "requested_provider": ""}'
    )

    assert result.requested_model is None
    assert result.requested_provider is None
