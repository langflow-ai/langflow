"""OpenAI Decisions component.

``POST /v1/decisions`` is called with httpx. The Decisions helper on the OpenAI
Python SDK (``client.decisions.create``) arrived in openai 3.26, and this bundle
still depends on ``openai>=1.68.2,<3``. The HTTP call uses the same pinned
provider client as the other credential-bearing integrations.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from lfx.base.models.provider_ssrf import (
    ensure_credential_endpoint_allowed,
    provider_safe_httpx_post,
    validate_provider_base_url,
)
from lfx.custom.custom_component.component import Component
from lfx.io import DictInput, DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.secrets import secret_value_to_str

from lfx_openai.components.openai.openai_chat_model import DEFAULT_OPENAI_API_BASE

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
DECISION_MODELS = ["gpt-6-luna"]
_QUESTION_TYPES = frozenset({"predicate", "choice", "score"})
_CHOICE_MAX_OPTIONS = 255
_SCORE_MIN_LEVELS = 2
_SCORE_MAX_LEVELS = 10
_CLIENT_ERROR = 400
_RATE_LIMITED = 429
_SERVER_ERROR = 500
_DEFAULT_TIMEOUT = 60.0
_DEFAULT_ATTEMPTS = 2
_BACKOFF_CAP_SECONDS = 5

_DEFAULT_QUESTIONS = {
    "label": {
        "type": "choice",
        "instructions": "Which category best matches the text?",
        "choices": [
            {"value": "bug", "description": "A report of something broken"},
            {"value": "question", "description": "A request for information"},
            {"value": "other", "description": "None of the other categories"},
        ],
    }
}


def decisions_url(base_url: str | None) -> str:
    """Build the Decisions URL from an OpenAI-compatible API base.

    Args:
        base_url: API base, usually ``https://api.openai.com/v1``.

    Returns:
        Absolute URL for ``POST /v1/decisions``.
    """
    base = (base_url or DEFAULT_OPENAI_API_BASE).strip().rstrip("/")
    if base.endswith("/decisions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/decisions"
    return f"{base}/v1/decisions"


def resolve_api_key(value: Any, env_var: str) -> str:
    """Return a bearer token, falling back to the provider environment variable.

    Args:
        value: Component secret field. The global-variable name is treated as unset.
        env_var: Environment variable that holds the API key.

    Returns:
        The API key to send.

    Raises:
        ValueError: If neither the field nor the environment variable has a key.
    """
    text = secret_value_to_str(value).strip()
    if not text or text == env_var:
        text = os.environ.get(env_var, "").strip()
    if not text:
        msg = f"API key is required. Set {env_var} or provide an API key."
        raise ValueError(msg)
    return text


def coerce_input(value: Any) -> str | dict | list:
    """Accept text, or JSON text that is an object or array, as Decisions input.

    Args:
        value: Component input field.

    Returns:
        The input payload. Image content is not constructed here.

    Raises:
        ValueError: If the input is empty.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        msg = "Input text is required."
        raise ValueError(msg)
    text = value.strip()
    if text[0] in "{[":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return value
        if isinstance(parsed, dict | list):
            return parsed
    return value


def _require_instructions(value: Any, *, question: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    msg = f"Question {question!r} needs instructions."
    raise ValueError(msg)


def _choice_list(spec: dict[str, Any], *, question: str) -> list[dict[str, str]]:
    raw = spec.get("choices")
    if raw is None and isinstance(spec.get("criteria"), dict):
        raw = [
            {"value": str(key), "description": item} if isinstance(item, str) and item else {"value": str(key)}
            for key, item in spec["criteria"].items()
        ]
    if not isinstance(raw, list) or not raw:
        msg = f"Question {question!r} needs a non-empty choices list."
        raise TypeError(msg)
    if len(raw) > _CHOICE_MAX_OPTIONS:
        msg = f"Question {question!r} has {len(raw)} choices; the maximum is {_CHOICE_MAX_OPTIONS}."
        raise ValueError(msg)
    choices: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            choices.append({"value": item})
            continue
        if isinstance(item, dict) and isinstance(item.get("value"), str) and item["value"].strip():
            choice = {"value": item["value"]}
            description = item.get("description")
            if isinstance(description, str) and description:
                choice["description"] = description
            choices.append(choice)
            continue
        msg = f"Question {question!r} has a choice without a value."
        raise TypeError(msg)
    return choices


def _level_list(spec: dict[str, Any], *, question: str) -> list[dict[str, str]]:
    raw = spec.get("levels")
    if raw is None and isinstance(spec.get("criteria"), list):
        raw = spec["criteria"]
    if not isinstance(raw, list):
        msg = f"Question {question!r} needs an ordered levels list."
        raise TypeError(msg)
    if len(raw) < _SCORE_MIN_LEVELS or len(raw) > _SCORE_MAX_LEVELS:
        msg = f"Question {question!r} needs between {_SCORE_MIN_LEVELS} and {_SCORE_MAX_LEVELS} score levels."
        raise ValueError(msg)
    levels: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            levels.append({"label": item})
            continue
        if isinstance(item, dict) and isinstance(item.get("label"), str) and item["label"].strip():
            level = {"label": item["label"]}
            description = item.get("description")
            if isinstance(description, str) and description:
                level["description"] = description
            levels.append(level)
            continue
        msg = f"Question {question!r} has a score level without a label."
        raise TypeError(msg)
    return levels


def normalize_decision_questions(questions: Any) -> list[dict[str, Any]]:
    """Validate a Decisions question map and convert it to the API array.

    Args:
        questions: Object keyed by question name. The key becomes each question's ``name``.

    Returns:
        The ``questions`` array expected by ``POST /v1/decisions``.

    Raises:
        TypeError: If the map or a question has the wrong shape.
        ValueError: If a required field is missing or a limit is exceeded.
    """
    if not isinstance(questions, dict) or not questions:
        msg = "Questions must be a non-empty object keyed by question name."
        raise TypeError(msg)
    payload: list[dict[str, Any]] = []
    for name, spec in questions.items():
        if not isinstance(name, str) or not name.strip():
            msg = "Each question key must be a non-empty name."
            raise ValueError(msg)
        if not isinstance(spec, dict):
            msg = f"Question {name!r} must be an object."
            raise TypeError(msg)
        question_type = spec.get("type")
        if question_type not in _QUESTION_TYPES:
            msg = f"Question {name!r} type must be predicate, choice, or score."
            raise ValueError(msg)
        item: dict[str, Any] = {
            "type": question_type,
            "name": name,
            "instructions": _require_instructions(spec.get("instructions"), question=name),
        }
        if question_type == "choice":
            item["choices"] = _choice_list(spec, question=name)
        elif question_type == "score":
            item["levels"] = _level_list(spec, question=name)
        payload.append(item)
    return payload


def format_answer_lines(answers: dict[str, Any]) -> str:
    """Render typed answers as plain text.

    Args:
        answers: Answer objects keyed by question name.

    Returns:
        A multiline summary.
    """
    lines: list[str] = []
    for name, answer in answers.items():
        if not isinstance(answer, dict):
            lines.append(f"{name}: {answer}")
            continue
        kind = answer.get("type", "unknown")
        if kind == "predicate":
            lines.append(f"{name} (predicate): {answer.get('probability')}")
        elif kind == "choice":
            confidence = answer.get("confidence")
            suffix = f" (confidence {confidence})" if confidence is not None else ""
            lines.append(f"{name} (choice): {answer.get('choice')}{suffix}")
            probabilities = answer.get("probabilities")
            if isinstance(probabilities, dict):
                lines.extend(f"  {option}: {probability}" for option, probability in probabilities.items())
        elif kind == "score":
            confidence = answer.get("confidence")
            suffix = f" (confidence {confidence})" if confidence is not None else ""
            lines.append(f"{name} (score): {answer.get('score')}{suffix}")
        elif kind == "refusal":
            reason = answer.get("refusal") or answer.get("message") or "refused"
            lines.append(f"{name} (refusal): {reason}")
        else:
            lines.append(f"{name} ({kind}): {json.dumps(answer, default=str)}")
    return "\n".join(lines)


def format_decisions_result(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Decisions response for Data and Message outputs.

    Args:
        body: Parsed JSON response.

    Returns:
        A dict that includes a ``text`` summary plus answers keyed by name.

    Raises:
        RuntimeError: If the response does not contain an answers array.
    """
    raw_answers = body.get("answers")
    if not isinstance(raw_answers, list) or not raw_answers:
        msg = "Decisions response is missing answers."
        raise RuntimeError(msg)
    answers: dict[str, Any] = {}
    for answer in raw_answers:
        if isinstance(answer, dict) and isinstance(answer.get("name"), str):
            answers[answer["name"]] = answer
    if not answers:
        msg = "Decisions response answers have no names."
        raise RuntimeError(msg)
    model = body.get("model", "")
    summary = format_answer_lines(answers)
    text = f"Model: {model}\n\n{summary}" if model else summary
    return {
        "text": text,
        "provider": "openai",
        "model": model,
        "answers": answers,
        "usage": body.get("usage"),
    }


def _error_text(response: httpx.Response) -> str:
    detail = response.text[:500]
    return f"OpenAI Decisions returned HTTP {response.status_code}: {detail}"


def post_decisions(
    *,
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: float,
    max_attempts: int,
) -> dict[str, Any]:
    """POST a Decisions request, retrying rate limits and server errors.

    Args:
        url: Decisions endpoint.
        api_key: Bearer token.
        payload: Request body.
        timeout: Per-attempt timeout in seconds.
        max_attempts: Total attempts, including the first.

    Returns:
        Parsed JSON object.

    Raises:
        RuntimeError: If the provider returns an error or a non-JSON body.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    attempts = max(max_attempts, 1)
    last_error = "Decisions request failed."
    for attempt in range(attempts):
        try:
            response = provider_safe_httpx_post(url, json=payload, headers=headers, timeout=timeout)
        except httpx.RequestError as exc:
            last_error = f"Decisions request failed: {exc}"
            if attempt + 1 >= attempts:
                break
            time.sleep(min(2**attempt, _BACKOFF_CAP_SECONDS))
            continue
        if response.status_code == _RATE_LIMITED or response.status_code >= _SERVER_ERROR:
            last_error = _error_text(response)
            if attempt + 1 >= attempts:
                break
            time.sleep(min(2**attempt, _BACKOFF_CAP_SECONDS))
            continue
        if response.status_code >= _CLIENT_ERROR:
            msg = _error_text(response)
            raise RuntimeError(msg)
        try:
            body = response.json()
        except ValueError as exc:
            msg = "Decisions returned a non-JSON response."
            raise RuntimeError(msg) from exc
        if not isinstance(body, dict):
            msg = "Decisions returned an unexpected response."
            raise TypeError(msg)
        return body
    msg = last_error
    raise RuntimeError(msg)


class OpenAIDecisionsComponent(Component):
    """Classify, route, or score text with the OpenAI Decisions API."""

    display_name = "OpenAI Decisions"
    description = "Classify, route, or score text with OpenAI Decisions models such as gpt-6-luna."
    documentation = "https://platform.openai.com/docs/guides/decisions"
    icon = "OpenAI"
    name = "OpenAIDecisions"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="OpenAI API key. Defaults to the OPENAI_API_KEY global variable.",
            value=OPENAI_API_KEY_ENV,
            required=True,
        ),
        MessageTextInput(
            name="openai_api_base",
            display_name="OpenAI API Base",
            info="API base, usually https://api.openai.com/v1. /decisions is appended when missing.",
            value=DEFAULT_OPENAI_API_BASE,
            advanced=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Decisions model. gpt-6-luna is the public model for this endpoint.",
            options=DECISION_MODELS,
            value="gpt-6-luna",
            combobox=True,
        ),
        MessageTextInput(
            name="input_text",
            display_name="Input",
            info="Text or JSON shared by every question. Image input is not sent by this component.",
            required=True,
            tool_mode=True,
        ),
        DictInput(
            name="questions",
            display_name="Questions",
            info=(
                "Object keyed by question name. Each value needs type (predicate, choice, or score) "
                "and instructions. Choice uses a choices list (or a criteria object). "
                "Score uses an ordered levels list of 2 to 10 labels (or a criteria list)."
            ),
            value=_DEFAULT_QUESTIONS,
            required=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout",
            value=_DEFAULT_TIMEOUT,
            advanced=True,
            info="Seconds to wait for each Decisions request.",
        ),
        IntInput(
            name="max_attempts",
            display_name="Max Attempts",
            value=_DEFAULT_ATTEMPTS,
            advanced=True,
            info="Attempts including the first. Rate limits and server errors are retried.",
        ),
    ]

    outputs = [
        Output(display_name="Answers", name="answers", method="get_answers"),
        Output(display_name="Summary", name="summary", method="get_summary"),
    ]

    def _pre_run_setup(self) -> None:
        self._decision_result: dict[str, Any] | None = None

    def _evaluate(self) -> dict[str, Any]:
        cached = getattr(self, "_decision_result", None)
        if cached is not None:
            return cached
        api_key = resolve_api_key(self.api_key, OPENAI_API_KEY_ENV)
        base_url = (self.openai_api_base or DEFAULT_OPENAI_API_BASE).strip()
        model_name = (self.model_name or "").strip()
        if not model_name:
            msg = "Model is required."
            raise ValueError(msg)
        questions = normalize_decision_questions(self.questions)
        decision_input = coerce_input(self.input_text)
        ensure_credential_endpoint_allowed(
            api_key,
            base_url,
            default_url=DEFAULT_OPENAI_API_BASE,
            sdk_env_fallback=OPENAI_API_KEY_ENV,
        )
        validate_provider_base_url(base_url, default_url=DEFAULT_OPENAI_API_BASE)
        timeout = self.timeout if isinstance(self.timeout, int | float) and self.timeout > 0 else _DEFAULT_TIMEOUT
        attempts = self.max_attempts if isinstance(self.max_attempts, int) and self.max_attempts > 0 else 1
        body = post_decisions(
            url=decisions_url(base_url),
            api_key=api_key,
            payload={"model": model_name, "input": decision_input, "questions": questions},
            timeout=float(timeout),
            max_attempts=attempts,
        )
        result = format_decisions_result(body)
        self._decision_result = result
        self.status = result["text"]
        return result

    def get_answers(self) -> Data:
        """Return the structured Decisions response."""
        result = self._evaluate()
        return Data(data=result)

    def get_summary(self) -> Message:
        """Return a readable summary of the Decisions answers."""
        result = self._evaluate()
        return Message(text=result["text"])
