"""Provider-neutral decision requests and evidence validated before consumption."""

from __future__ import annotations

import json
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, field_validator, model_validator

DecisionKind = Literal["choice", "boolean", "score"]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonEmpty = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]
MIN_CANDIDATES = 2


class DecisionConfigurationError(ValueError):
    """An invalid configuration must stop execution, including Else mode."""


class DecisionEvaluationError(RuntimeError):
    """An operational or malformed-response failure; never valid uncertainty.

    ``category`` names the failure for diagnostics: timeout, transport, http_error,
    input_too_large, invalid_response or refusal.
    """

    def __init__(self, message: str, *, category: str = "invalid_response") -> None:
        super().__init__(message)
        self.category = category


def validation_summary(exc: ValidationError) -> str:
    """Field paths and messages only; pydantic's input values may carry provider or user content."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'value'}: {error['msg']}" for error in exc.errors()
    )


class DecisionOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonEmpty
    label: NonEmpty
    description: str = ""


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: DecisionKind
    question: NonEmpty
    context: str | dict[str, JsonValue]
    question_id: NonEmpty = "decision"
    options: tuple[DecisionOption, ...] = ()
    levels: tuple[DecisionOption, ...] = ()

    @field_validator("context")
    @classmethod
    def validate_context(cls, value: str | dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        json.dumps(value, allow_nan=False)
        return value

    @model_validator(mode="after")
    def validate_candidates(self) -> DecisionRequest:
        candidates = self.options if self.kind == "choice" else self.levels
        if self.kind in {"choice", "score"} and len(candidates) < MIN_CANDIDATES:
            msg = "Choice and Score require at least two described candidates"
            raise ValueError(msg)
        if (self.kind != "choice" and self.options) or (self.kind != "score" and self.levels):
            msg = "Options belong to Choice and ordered levels belong to Score"
            raise ValueError(msg)
        if len({candidate.id for candidate in candidates}) != len(candidates):
            msg = "Decision candidate IDs must be unique"
            raise ValueError(msg)
        if len({candidate.label.strip().casefold() for candidate in candidates}) != len(candidates):
            msg = "Decision candidate labels must be unique"
            raise ValueError(msg)
        return self


class DecisionResult(BaseModel):
    """Evidence fields retain their meanings; no implicit Boolean/route policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: DecisionKind
    question_id: NonEmpty = "decision"
    provider: NonEmpty
    model: NonEmpty
    model_source: Literal["response", "request"] = "response"
    status: Literal["success", "refusal"] = "success"
    probabilities: dict[str, Probability] | None = None
    probability_true: Probability | None = None
    score: FiniteNumber | None = None
    selected_option: NonEmpty | None = None
    confidence: Probability | None = None
    refusal: NonEmpty | None = None
    usage: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> DecisionResult:
        if self.status == "refusal":
            # The provider's reason is kept when given and never invented when absent.
            if any(
                value is not None
                for value in (
                    self.probabilities,
                    self.probability_true,
                    self.score,
                    self.selected_option,
                    self.confidence,
                )
            ):
                msg = "Refusal cannot contain successful judgment evidence"
                raise ValueError(msg)
            return self
        if self.refusal is not None:
            msg = "Successful judgments cannot contain a refusal"
            raise ValueError(msg)
        if self.kind == "boolean":
            if self.probability_true is None or any(
                value is not None for value in (self.probabilities, self.score, self.selected_option)
            ):
                msg = "Boolean results require P(true), without a distribution, score or derived Boolean"
                raise ValueError(msg)
        else:
            if not self.probabilities or self.probability_true is not None:
                msg = "Choice and Score results require a probability distribution"
                raise ValueError(msg)
            # Accept serialization rounding, never normalize malformed provider evidence.
            if not math.isclose(sum(self.probabilities.values()), 1.0, rel_tol=0, abs_tol=1e-5):
                msg = "Decision probabilities must sum to one"
                raise ValueError(msg)
            if self.kind == "choice" and self.score is not None:
                msg = "Choice results cannot contain a numeric score"
                raise ValueError(msg)
            if self.kind == "score" and (self.score is None or self.selected_option is not None):
                msg = "Score results require a numeric score, without a selected option"
                raise ValueError(msg)
        return self

    def validate_for(self, request: DecisionRequest) -> DecisionResult:
        """Reject mismatched or incomplete evidence against the original question."""
        if self.kind != request.kind or self.question_id != request.question_id:
            msg = "Provider answered a different decision question"
            raise DecisionEvaluationError(msg)
        if self.status == "refusal":
            return self
        candidates = request.options if request.kind == "choice" else request.levels
        if candidates:
            expected_ids = {candidate.id for candidate in candidates}
            if set(self.probabilities or {}) != expected_ids:
                msg = "Decision distribution must contain exactly the requested candidate IDs"
                raise DecisionEvaluationError(msg)
            if self.selected_option is not None:
                if self.selected_option not in expected_ids:
                    msg = "Selected outcome is not a requested option"
                    raise DecisionEvaluationError(msg)
                if self.probabilities[self.selected_option] != max(self.probabilities.values()):
                    msg = "Selected outcome disagrees with the probability distribution"
                    raise DecisionEvaluationError(msg)
        if request.kind == "score":
            if not 0 <= self.score <= len(request.levels) - 1:
                msg = "Score is outside the requested zero-based rubric"
                raise DecisionEvaluationError(msg)
            expected_score = sum(index * self.probabilities[level.id] for index, level in enumerate(request.levels))
            if not math.isclose(self.score, expected_score, rel_tol=0, abs_tol=1e-4):
                msg = "Score disagrees with its ordered-level probability distribution"
                raise DecisionEvaluationError(msg)
        return self
