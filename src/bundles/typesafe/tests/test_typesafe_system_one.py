"""Unit tests for the TypeSafe System One component."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from lfx_typesafe.components.typesafe.typesafe_system_one import (
    TypeSafeSystemOneComponent,
    normalize_typesafe_questions,
    systemone_url,
)

_API_KEY = "typesafe-test-key"  # pragma: allowlist secret
_POST = "lfx_typesafe.components.typesafe.typesafe_system_one.provider_safe_httpx_post"
_SLEEP = "lfx_typesafe.components.typesafe.typesafe_system_one.time.sleep"

_QUESTIONS = {
    "is_urgent": {
        "type": "noul",
        "instructions": "Does this convey urgency?",
        "criteria": {"true": "Time-sensitive", "false": "No urgency"},
    },
    "department": {
        "type": "choice",
        "instructions": "Which team should handle this?",
        "criteria": {"billing": "Payments", "technical": "Bugs"},
    },
    "frustration": {
        "type": "score",
        "instructions": "How frustrated is the customer?",
        "criteria": ["Calm", "Frustrated", "Very angry"],
    },
}

_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "is_urgent": {"type": "noul", "noul": 0.95},
        "department": {
            "type": "choice",
            "choice": "billing",
            "probabilities": {"billing": 0.88, "technical": 0.12},
            "confidence": 0.81,
        },
        "frustration": {
            "type": "score",
            "score": 1.05,
            "confidence": 0.92,
        },
    },
    "usage": {"input_tokens": 296, "output_tokens": 20},
}


def _response(status: int, payload: dict | None = None, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text or json.dumps(payload or {})
    response.json.return_value = {} if payload is None else payload
    return response


def _component(**overrides) -> TypeSafeSystemOneComponent:
    values = {
        "api_key": _API_KEY,
        "base_url": "https://api.typesafe.ai",
        "model_name": "jev-latest",
        "state": "Help! My payouts have been failing for 3 days.",
        "questions": _QUESTIONS,
        "timeout": 5,
        "max_attempts": 1,
    }
    values.update(overrides)
    return TypeSafeSystemOneComponent(**values)


class TestQuestionNormalization:
    def test_accepts_noul_choice_and_score(self):
        payload = normalize_typesafe_questions(_QUESTIONS)

        assert set(payload) == {"is_urgent", "department", "frustration"}
        assert payload["department"]["criteria"]["billing"] == "Payments"
        assert payload["frustration"]["criteria"] == ["Calm", "Frustrated", "Very angry"]

    def test_rejects_an_empty_map(self):
        with pytest.raises(TypeError, match="non-empty object"):
            normalize_typesafe_questions({})

    def test_rejects_unknown_type(self):
        with pytest.raises(ValueError, match="noul, choice, or score"):
            normalize_typesafe_questions({"q": {"type": "predicate", "instructions": "Yes?"}})

    def test_rejects_choice_without_options(self):
        with pytest.raises(TypeError, match="choice criteria"):
            normalize_typesafe_questions({"q": {"type": "choice", "instructions": "Which?"}})

    def test_rejects_a_single_score_level(self):
        with pytest.raises(ValueError, match="score levels"):
            normalize_typesafe_questions({"q": {"type": "score", "instructions": "Rate it", "criteria": ["Only"]}})

    def test_rejects_more_than_255_choices(self):
        criteria = {f"option-{index}": None for index in range(256)}
        questions = {"q": {"type": "choice", "instructions": "Which?", "criteria": criteria}}

        with pytest.raises(ValueError, match="maximum is 255"):
            normalize_typesafe_questions(questions)


class TestRequest:
    def test_builds_the_systemone_path(self):
        assert systemone_url("https://api.typesafe.ai") == "https://api.typesafe.ai/v1/systemone"
        assert systemone_url("https://api.typesafe.ai/v1") == "https://api.typesafe.ai/v1/systemone"
        assert systemone_url("https://api.typesafe.ai/v1/systemone") == "https://api.typesafe.ai/v1/systemone"

    def test_sends_all_question_types_and_formats_answers(self):
        component = _component(state='{"ticket": "payouts"}')

        with patch(_POST, return_value=_response(200, _RESPONSE)) as mock_post:
            data = component.get_answers()
            summary = component.get_summary()

        assert mock_post.call_count == 1
        assert mock_post.call_args.args[0] == "https://api.typesafe.ai/v1/systemone"
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {_API_KEY}"
        assert mock_post.call_args.kwargs["json"]["state"] == {"ticket": "payouts"}
        assert mock_post.call_args.kwargs["json"]["model"] == "jev-latest"
        assert data.data["answers"]["department"]["choice"] == "billing"
        assert data.data["usage"]["input_tokens"] == 296
        assert "is_urgent (noul): 0.95" in summary.text
        assert "department (choice): billing" in summary.text
        assert "frustration (score): 1.05" in summary.text

    def test_retries_a_rate_limit_then_returns_the_answer(self):
        component = _component(max_attempts=2)

        with (
            patch(_POST, side_effect=[_response(429, text="slow down"), _response(200, _RESPONSE)]) as mock_post,
            patch(_SLEEP) as mock_sleep,
        ):
            summary = component.get_summary()

        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1)
        assert "billing" in summary.text

    def test_does_not_retry_a_validation_error(self):
        component = _component(max_attempts=3)

        with (
            patch(_POST, return_value=_response(422, text="missing field")) as mock_post,
            pytest.raises(RuntimeError, match="HTTP 422"),
        ):
            component.get_answers()

        assert mock_post.call_count == 1

    def test_rejects_a_non_json_success_body(self):
        component = _component()
        response = _response(200, text="not-json")
        response.json.side_effect = ValueError("not json")

        with patch(_POST, return_value=response), pytest.raises(RuntimeError, match="non-JSON"):
            component.get_answers()

    def test_requires_an_api_key(self, monkeypatch):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        component = _component(api_key="")

        with patch(_POST) as mock_post, pytest.raises(ValueError, match="API key is required"):
            component.get_answers()

        mock_post.assert_not_called()

    def test_blocks_an_internal_base_url_before_the_request(self):
        component = _component(base_url="http://127.0.0.1:8000")

        with patch(_POST) as mock_post, pytest.raises(ValueError, match="SSRF Protection"):
            component.get_answers()

        mock_post.assert_not_called()

    def test_refuses_to_send_an_environment_key_to_a_custom_host(self, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", _API_KEY)
        component = _component(base_url="https://evil.example")

        with patch(_POST) as mock_post, pytest.raises(ValueError, match="non-default endpoint"):
            component.get_answers()

        mock_post.assert_not_called()
