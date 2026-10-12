"""Unit tests for the OpenAI Decisions component."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from lfx_openai.components.openai.openai_decisions import (
    OpenAIDecisionsComponent,
    decisions_url,
    normalize_decision_questions,
)

_API_KEY = "openai-test-key"  # pragma: allowlist secret
_POST = "lfx_openai.components.openai.openai_decisions.provider_safe_httpx_post"
_SLEEP = "lfx_openai.components.openai.openai_decisions.time.sleep"

_QUESTIONS = {
    "damaged": {"type": "predicate", "instructions": "Does the customer report damage?"},
    "queue": {
        "type": "choice",
        "instructions": "Which team should handle this ticket?",
        "choices": [
            {"value": "billing", "description": "Refunds and payments"},
            {"value": "shipping", "description": "Delivery and damaged items"},
        ],
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this ticket?",
        "levels": [{"label": "low"}, {"label": "medium"}, {"label": "high"}],
    },
}

_RESPONSE = {
    "model": "gpt-6-luna",
    "answers": [
        {"type": "predicate", "name": "damaged", "probability": 0.92},
        {
            "type": "choice",
            "name": "queue",
            "choice": "billing",
            "probabilities": {"billing": 0.8, "shipping": 0.2},
            "confidence": 0.7,
        },
        {"type": "score", "name": "urgency", "score": 1.2, "confidence": 0.4},
        {"type": "refusal", "name": "hidden", "refusal": "policy"},
    ],
}


def _response(status: int, payload: dict | None = None, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text or json.dumps(payload or {})
    response.json.return_value = {} if payload is None else payload
    return response


def _component(**overrides) -> OpenAIDecisionsComponent:
    values = {
        "api_key": _API_KEY,
        "openai_api_base": "https://api.openai.com/v1",
        "model_name": "gpt-6-luna",
        "input_text": "The package arrived with a broken screen.",
        "questions": _QUESTIONS,
        "timeout": 5,
        "max_attempts": 1,
    }
    values.update(overrides)
    return OpenAIDecisionsComponent(**values)


class TestQuestionNormalization:
    def test_converts_a_name_keyed_map_into_the_api_array(self):
        payload = normalize_decision_questions(_QUESTIONS)

        by_name = {item["name"]: item for item in payload}
        assert by_name["damaged"]["type"] == "predicate"
        assert by_name["queue"]["choices"][0]["value"] == "billing"
        assert by_name["urgency"]["levels"][2]["label"] == "high"

    def test_accepts_criteria_maps_and_lists(self):
        payload = normalize_decision_questions(
            {
                "queue": {
                    "type": "choice",
                    "instructions": "Which team?",
                    "criteria": {"billing": "Payments", "technical": "Bugs"},
                },
                "urgency": {
                    "type": "score",
                    "instructions": "How urgent?",
                    "criteria": ["low", "high"],
                },
            }
        )

        by_name = {item["name"]: item for item in payload}
        assert by_name["queue"]["choices"][0] == {"value": "billing", "description": "Payments"}
        assert by_name["urgency"]["levels"] == [{"label": "low"}, {"label": "high"}]

    def test_rejects_an_unknown_type(self):
        with pytest.raises(ValueError, match="predicate, choice, or score"):
            normalize_decision_questions({"q": {"type": "noul", "instructions": "Yes?"}})

    def test_rejects_a_score_with_one_level(self):
        with pytest.raises(ValueError, match="score levels"):
            normalize_decision_questions({"q": {"type": "score", "instructions": "Rate it", "levels": ["only"]}})


class TestRequest:
    def test_builds_the_decisions_path(self):
        assert decisions_url("https://api.openai.com/v1") == "https://api.openai.com/v1/decisions"
        assert decisions_url("https://api.openai.com") == "https://api.openai.com/v1/decisions"
        assert decisions_url("https://gateway.example/v1/decisions") == "https://gateway.example/v1/decisions"

    def test_sends_predicate_choice_and_score_questions(self):
        component = _component()

        with patch(_POST, return_value=_response(200, _RESPONSE)) as mock_post:
            data = component.get_answers()
            summary = component.get_summary()

        assert mock_post.call_count == 1
        assert mock_post.call_args.args[0] == "https://api.openai.com/v1/decisions"
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {_API_KEY}"
        body = mock_post.call_args.kwargs["json"]
        assert body["model"] == "gpt-6-luna"
        assert body["input"] == "The package arrived with a broken screen."
        assert [item["type"] for item in body["questions"]] == ["predicate", "choice", "score"]
        assert data.data["answers"]["damaged"]["probability"] == 0.92
        assert "damaged (predicate): 0.92" in summary.text
        assert "queue (choice): billing" in summary.text
        assert "urgency (score): 1.2" in summary.text
        assert "hidden (refusal): policy" in summary.text

    def test_retries_a_server_error(self):
        component = _component(max_attempts=2)

        with (
            patch(_POST, side_effect=[_response(503, text="unavailable"), _response(200, _RESPONSE)]) as mock_post,
            patch(_SLEEP) as mock_sleep,
        ):
            data = component.get_answers()

        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1)
        assert data.data["model"] == "gpt-6-luna"

    def test_does_not_retry_an_unauthorized_response(self):
        component = _component(max_attempts=3)

        with (
            patch(_POST, return_value=_response(401, text="bad key")) as mock_post,
            pytest.raises(RuntimeError, match="HTTP 401"),
        ):
            component.get_answers()

        assert mock_post.call_count == 1

    def test_requires_an_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        component = _component(api_key="")

        with patch(_POST) as mock_post, pytest.raises(ValueError, match="API key is required"):
            component.get_answers()

        mock_post.assert_not_called()

    def test_blocks_an_internal_base_url_before_the_request(self):
        component = _component(openai_api_base="http://169.254.169.254/latest")

        with patch(_POST) as mock_post, pytest.raises(ValueError, match="SSRF Protection"):
            component.get_answers()

        mock_post.assert_not_called()

    def test_refuses_to_send_an_environment_key_to_a_custom_host(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", _API_KEY)
        component = _component(openai_api_base="https://evil.example/v1")

        with patch(_POST) as mock_post, pytest.raises(ValueError, match="non-default endpoint"):
            component.get_answers()

        mock_post.assert_not_called()
