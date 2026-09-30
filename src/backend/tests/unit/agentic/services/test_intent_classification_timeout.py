"""I1 — classify_intent must bound the TranslationFlow LLM call.

A call to the intent classifier is a network call to a slow, unreliable
external model. Without an explicit timeout a hung provider stalls the whole
SSE request indefinitely. classify_intent must abort the call within a
budget and fall back to the safe "question" intent.
"""

from __future__ import annotations

import asyncio

import pytest
from langflow.agentic.services.helpers import intent_classification
from langflow.agentic.services.helpers.intent_classification import classify_intent


class TestClassifyIntentTimeout:
    async def test_should_fall_back_to_question_when_translation_flow_hangs(self, monkeypatch):
        # Arrange — the underlying LLM flow never returns.
        async def hanging_execute_flow_file(*_args, **_kwargs):
            await asyncio.sleep(30)
            msg = "should never get here — call must be timed out"
            raise AssertionError(msg)

        monkeypatch.setattr(intent_classification, "execute_flow_file", hanging_execute_flow_file)
        # Tight budget so the test is fast; constant may not exist yet (RED).
        monkeypatch.setattr(
            intent_classification,
            "INTENT_CLASSIFICATION_TIMEOUT_SECONDS",
            0.05,
            raising=False,
        )

        # Act — must return well within the 30s hang (outer guard = 3s).
        result = await asyncio.wait_for(
            classify_intent("bonjour, ça va?", global_variables={}),
            timeout=3.0,
        )

        # Assert — graceful degradation to the safe default.
        assert result.intent == "question"
        assert result.translation == "bonjour, ça va?"

    async def test_should_classify_normally_when_flow_responds_in_time(self, monkeypatch):
        async def fast_execute_flow_file(*_args, **_kwargs):
            payload = '{"translation": "hello", "intent": "question"}'
            return {"outputs": [{"outputs": [{"results": {"message": {"text": payload}}}]}]}

        monkeypatch.setattr(intent_classification, "execute_flow_file", fast_execute_flow_file)

        result = await asyncio.wait_for(
            classify_intent("olá", global_variables={}),
            timeout=3.0,
        )

        assert result.intent == "question"
        assert result.translation == "hello"


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
