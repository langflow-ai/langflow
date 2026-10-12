"""TypeSafe System One component.

Calls ``POST /v1/systemone`` with httpx. The TypeSafe Python SDK is not required:
the HTTP contract is small, and the shared provider client keeps the API key off
unapproved hosts.
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

DEFAULT_TYPESAFE_API_BASE = "https://api.typesafe.ai"
TYPESAFE_API_KEY_ENV = "TYPESAFE_API_KEY"
SYSTEMONE_MODELS = ["jev-latest", "jev-1.13.0"]
_QUESTION_TYPES = frozenset({"noul", "choice", "score"})
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
        "criteria": {
            "bug": "A report of something broken",
            "question": "A request for information",
            "other": "None of the other categories",
        },
    }
}


def systemone_url(base_url: str | None) -> str:
    """Build the System One evaluation URL from an API origin.

    Args:
        base_url: Provider origin, usually ``https://api.typesafe.ai``. A value that
            already ends in ``/v1`` or ``/v1/systemone`` is accepted.

    Returns:
        Absolute URL for ``POST /v1/systemone``.
    """
    base = (base_url or DEFAULT_TYPESAFE_API_BASE).strip().rstrip("/")
    if base.endswith("/v1/systemone"):
        return base
    if base.endswith("/v1"):
        return f"{base}/systemone"
    return f"{base}/v1/systemone"


def resolve_api_key(value: Any, env_var: str) -> str:
    """Return a bearer token, falling back to the provider environment variable.

    Args:
        value: Component secret field. The global-variable name is treated as unset.
        env_var: Environment variable that holds the operator or user API key.

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


def coerce_state(value: Any) -> str | dict | list:
    """Accept text, or JSON text that is an object or array, as System One state.

    Args:
        value: Component state field.

    Returns:
        The state payload.

    Raises:
        ValueError: If the state is empty.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        msg = "State is required."
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


def _require_instructions(value: Any, *, question: str) -> Any:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, dict) and value:
        return value
    if isinstance(value, list) and value:
        return value
    msg = f"Question {question!r} needs instructions."
    raise ValueError(msg)


def _rubric_value(value: Any, *, question: str, field: str) -> Any:
    if value is None or isinstance(value, str | dict | list):
        return value
    msg = f"Question {question!r} field {field!r} must be a string, object, array, or null."
    raise TypeError(msg)


def _noul_criteria(value: Any, *, question: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        msg = f"Question {question!r} noul criteria must be an object with true and false."
        raise TypeError(msg)
    unknown = set(value) - {"true", "false"}
    if unknown:
        msg = f"Question {question!r} noul criteria only accepts 'true' and 'false'."
        raise ValueError(msg)
    return {key: _rubric_value(item, question=question, field=key) for key, item in value.items()}


def _choice_criteria(value: Any, *, question: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        msg = f"Question {question!r} choice criteria must be a non-empty object of options."
        raise TypeError(msg)
    if len(value) > _CHOICE_MAX_OPTIONS:
        msg = f"Question {question!r} has {len(value)} options; the maximum is {_CHOICE_MAX_OPTIONS}."
        raise ValueError(msg)
    return {str(key): _rubric_value(item, question=question, field=str(key)) for key, item in value.items()}


def _score_criteria(value: Any, *, question: str) -> list[Any]:
    if not isinstance(value, list):
        msg = f"Question {question!r} score criteria must be an ordered list of levels."
        raise TypeError(msg)
    if len(value) < _SCORE_MIN_LEVELS or len(value) > _SCORE_MAX_LEVELS:
        msg = f"Question {question!r} needs between {_SCORE_MIN_LEVELS} and {_SCORE_MAX_LEVELS} score levels."
        raise ValueError(msg)
    return [_rubric_value(item, question=question, field="criteria") for item in value]


def normalize_typesafe_questions(questions: Any) -> dict[str, dict[str, Any]]:
    """Validate a System One question map.

    Args:
        questions: Object keyed by answer id. Values are noul, choice, or score questions.

    Returns:
        A payload safe to send as ``questions``.

    Raises:
        TypeError: If the map or a question has the wrong shape.
        ValueError: If a required field is missing or a limit is exceeded.
    """
    if not isinstance(questions, dict) or not questions:
        msg = "Questions must be a non-empty object keyed by question name."
        raise TypeError(msg)
    payload: dict[str, dict[str, Any]] = {}
    for name, spec in questions.items():
        if not isinstance(name, str) or not name.strip():
            msg = "Each question key must be a non-empty name."
            raise ValueError(msg)
        if not isinstance(spec, dict):
            msg = f"Question {name!r} must be an object."
            raise TypeError(msg)
        question_type = spec.get("type")
        if question_type not in _QUESTION_TYPES:
            msg = f"Question {name!r} type must be noul, choice, or score."
            raise ValueError(msg)
        item: dict[str, Any] = {
            "type": question_type,
            "instructions": _require_instructions(spec.get("instructions"), question=name),
        }
        if question_type == "noul":
            criteria = _noul_criteria(spec.get("criteria"), question=name)
            if criteria is not None:
                item["criteria"] = criteria
        elif question_type == "choice":
            item["criteria"] = _choice_criteria(spec.get("criteria"), question=name)
        else:
            item["criteria"] = _score_criteria(spec.get("criteria"), question=name)
        payload[name] = item
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
        if kind == "noul":
            lines.append(f"{name} (noul): {answer.get('noul')}")
        elif kind == "predicate":
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


def format_typesafe_result(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize a System One response for Data and Message outputs.

    Args:
        body: Parsed JSON response.

    Returns:
        A dict that includes a ``text`` summary plus the raw answers and usage.

    Raises:
        RuntimeError: If the response does not contain an answers object.
    """
    answers = body.get("answers")
    if not isinstance(answers, dict) or not answers:
        msg = "System One response is missing answers."
        raise RuntimeError(msg)
    model = body.get("model", "")
    summary = format_answer_lines(answers)
    text = f"Model: {model}\n\n{summary}" if model else summary
    return {
        "text": text,
        "provider": "typesafe",
        "model": model,
        "answers": answers,
        "usage": body.get("usage"),
    }


def _error_text(response: httpx.Response) -> str:
    detail = response.text[:500]
    return f"TypeSafe System One returned HTTP {response.status_code}: {detail}"


def post_systemone(
    *,
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: float,
    max_attempts: int,
) -> dict[str, Any]:
    """POST a System One request, retrying rate limits and server errors.

    Args:
        url: Evaluation endpoint.
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
    last_error = "System One request failed."
    for attempt in range(attempts):
        try:
            response = provider_safe_httpx_post(url, json=payload, headers=headers, timeout=timeout)
        except httpx.RequestError as exc:
            last_error = f"System One request failed: {exc}"
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
            msg = "System One returned a non-JSON response."
            raise RuntimeError(msg) from exc
        if not isinstance(body, dict):
            msg = "System One returned an unexpected response."
            raise TypeError(msg)
        return body
    msg = last_error
    raise RuntimeError(msg)


class TypeSafeSystemOneComponent(Component):
    """Evaluate text with a TypeSafe System One model such as Jev."""

    display_name = "TypeSafe System One"
    description = "Classify, route, or score text with TypeSafe System One models such as Jev."
    documentation = "https://docs.typesafe.ai/api"
    icon = "brain"
    name = "TypeSafeSystemOne"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="TypeSafe API Key",
            info="TypeSafe API key. Defaults to the TYPESAFE_API_KEY global variable.",
            value=TYPESAFE_API_KEY_ENV,
            required=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="API Base URL",
            info="TypeSafe API origin. Do not include /v1/systemone. Defaults to https://api.typesafe.ai.",
            value=DEFAULT_TYPESAFE_API_BASE,
            advanced=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="System One model id. jev-latest tracks the current stable Jev release.",
            options=SYSTEMONE_MODELS,
            value="jev-latest",
            combobox=True,
        ),
        MessageTextInput(
            name="state",
            display_name="State",
            info="Text or JSON (object or array) that every question evaluates.",
            required=True,
            tool_mode=True,
        ),
        DictInput(
            name="questions",
            display_name="Questions",
            info=(
                "Object keyed by answer id. Each value needs type (noul, choice, or score) "
                "and instructions. Choice uses a criteria object (max 255 options). "
                "Score uses an ordered criteria list of 2 to 10 levels."
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
            info="Seconds to wait for each System One request.",
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
        api_key = resolve_api_key(self.api_key, TYPESAFE_API_KEY_ENV)
        base_url = (self.base_url or DEFAULT_TYPESAFE_API_BASE).strip()
        model_name = (self.model_name or "").strip()
        if not model_name:
            msg = "Model is required."
            raise ValueError(msg)
        questions = normalize_typesafe_questions(self.questions)
        state = coerce_state(self.state)
        ensure_credential_endpoint_allowed(
            api_key,
            base_url,
            default_url=DEFAULT_TYPESAFE_API_BASE,
            sdk_env_fallback=TYPESAFE_API_KEY_ENV,
        )
        validate_provider_base_url(base_url, default_url=DEFAULT_TYPESAFE_API_BASE)
        timeout = self.timeout if isinstance(self.timeout, int | float) and self.timeout > 0 else _DEFAULT_TIMEOUT
        attempts = self.max_attempts if isinstance(self.max_attempts, int) and self.max_attempts > 0 else 1
        body = post_systemone(
            url=systemone_url(base_url),
            api_key=api_key,
            payload={"state": state, "model": model_name, "questions": questions},
            timeout=float(timeout),
            max_attempts=attempts,
        )
        result = format_typesafe_result(body)
        self._decision_result = result
        self.status = result["text"]
        return result

    def get_answers(self) -> Data:
        """Return the structured System One response."""
        result = self._evaluate()
        return Data(data=result)

    def get_summary(self) -> Message:
        """Return a readable summary of the System One answers."""
        result = self._evaluate()
        return Message(text=result["text"])
