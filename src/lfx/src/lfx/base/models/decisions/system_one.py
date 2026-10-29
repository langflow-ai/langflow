"""Several typed questions about one state in a single TypeSafe System One call.

A decision component asks one question per request. Native consumers, such as an evaluation judge,
ask several about the same state at once: the state is read once, so the call costs and takes about
as much as one question. Only TypeSafe documents named questions in one request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.base.models.decisions.providers import post_decision, provider_token_usage
from lfx.base.models.decisions.runtime import authorize_decision_model
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionEvaluationError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

SYSTEM_ONE_PROVIDER = "TypeSafe"
# What each question type needs from the model's catalog capabilities.
_CAPABILITY = {"noul": "boolean", "choice": "choice"}


@dataclass(frozen=True)
class SystemOneAnswers:
    """``nouls`` holds each yes/no question's probability of yes; ``choices`` each choice's probabilities."""

    model: str
    nouls: dict[str, float]
    choices: dict[str, dict[str, float]]
    usage: dict[str, Any] | None
    request_id: str | None


def _probability(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if 0.0 <= number <= 1.0 else None


def _invalid(request_id: str | None) -> DecisionEvaluationError:
    ref = f" (request ID {request_id})" if request_id else ""
    return DecisionEvaluationError(
        f"{SYSTEM_ONE_PROVIDER} sent answers Langflow couldn't read{ref}. Try again.", category="invalid_response"
    )


def _read_choice(answer: dict[str, Any], question: Mapping[str, Any], request_id: str | None) -> dict[str, float]:
    probabilities = answer.get("probabilities")
    labels = set(question.get("criteria") or {})
    if not isinstance(probabilities, dict) or set(probabilities) != labels:
        raise _invalid(request_id)
    read = {label: _probability(value) for label, value in probabilities.items()}
    if any(value is None for value in read.values()):
        raise _invalid(request_id)
    return {label: float(value) for label, value in read.items() if value is not None}


def parse_answers(body: Any, questions: Mapping[str, Mapping[str, Any]], *, request_id: str | None) -> SystemOneAnswers:
    """Every requested question answered with its own type and probabilities in [0, 1], or an error."""
    answers = body.get("answers") if isinstance(body, dict) else None
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise _invalid(request_id)
    nouls: dict[str, float] = {}
    choices: dict[str, dict[str, float]] = {}
    for name, question in questions.items():
        answer = answers[name]
        if not isinstance(answer, dict) or answer.get("type") != question["type"]:
            raise _invalid(request_id)
        if question["type"] == "noul":
            probability = _probability(answer.get("noul"))
            if probability is None:
                raise _invalid(request_id)
            nouls[name] = probability
        else:
            choices[name] = _read_choice(answer, question, request_id)
    reported = body.get("model")
    model = reported if isinstance(reported, str) else ""
    return SystemOneAnswers(
        model=model, nouls=nouls, choices=choices, usage=provider_token_usage(body.get("usage")), request_id=request_id
    )


def evaluate_system_one(
    state: str | dict[str, Any],
    questions: Mapping[str, Mapping[str, Any]],
    *,
    model: list[dict[str, Any]] | dict[str, Any],
    user_id: UUID | str | None = None,
    request_variables: Mapping[str, Any] | None = None,
    timeout: float = 60,
) -> SystemOneAnswers:
    """Ask noul and choice questions about one state; policy and the provider's own key apply as for a decision."""
    if not questions:
        msg = "Ask at least one question."
        raise DecisionConfigurationError(msg)
    kinds = tuple(dict.fromkeys(_CAPABILITY.get(str(question.get("type")), "") for question in questions.values()))
    if "" in kinds:
        msg = "System One questions here are noul or choice."
        raise DecisionConfigurationError(msg)
    provider, model_name, api_key = authorize_decision_model(
        model, kinds=kinds, user_id=user_id, request_variables=request_variables
    )
    if provider != SYSTEM_ONE_PROVIDER:
        msg = f"Only {SYSTEM_ONE_PROVIDER} decision models answer several questions in one call."
        raise DecisionConfigurationError(msg)
    payload = {"model": model_name, "state": state, "questions": {name: dict(q) for name, q in questions.items()}}
    body, request_id = post_decision(provider, payload, api_key=api_key, timeout=timeout)
    return parse_answers(body, questions, request_id=request_id)
