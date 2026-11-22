"""Provider-neutral decision requests and evidence validated before consumption."""

from __future__ import annotations

import json
import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, field_validator, model_validator

DecisionKind = Literal["choice", "boolean", "score"]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonEmpty = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]
# Provider-reported model names are stored in evidence; anything longer is not a model name.
ModelName = Annotated[str, Field(strict=True, min_length=1, max_length=128, pattern=r"\S")]
MIN_CANDIDATES = 2
# Providers report rounded numbers: TypeSafe's probabilities only "roughly" sum to 1, and its answers
# come back to two decimals, so each reported probability and score can be off by up to 0.005.
REPORTED_ROUNDING = 0.005


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


def validation_summary(exc: ValidationError, *, field_only: bool = False) -> str:
    """Field paths and messages only; pydantic's input values may carry provider or user content.

    ``field_only`` keeps just the top-level field, for provider responses whose nested keys the
    provider chose and must never be echoed.
    """
    problems = []
    for error in exc.errors():
        path = ".".join(str(part) for part in error["loc"][: 1 if field_only else None])
        # A rule across the whole object has no path; pydantic prefixes its message with "Value error, ".
        problems.append(f"{path}: {error['msg']}" if path else error["msg"].removeprefix("Value error, "))
    return "; ".join(problems)


# What the component shows for each part of a decision request.
_ROWS = {"options": "Option", "levels": "Level"}
_CELLS = {"id": "ID", "label": "Label", "description": "Description"}
_REQUIRED_CELLS = {"id": "an ID", "label": "a Label"}
_FIELDS = {"question": "Question", "context": "Context"}
# A cell left empty, cleared to "", or holding only spaces.
_BLANK_ERRORS = {"string_type", "string_too_short", "string_pattern_mismatch"}


def configuration_summary(exc: ValidationError) -> str:
    """Name the option, level or field a flow must fix, in the component's words, never pydantic's paths."""
    missing: dict[str, list[str]] = {}
    problems: list[str] = []
    for error in exc.errors():
        loc = error["loc"]
        # A missing key reports the whole row as its input, so it is blank whatever that holds.
        blank = error["type"] == "missing" or (
            error["type"] in _BLANK_ERRORS and not str(error.get("input") or "").strip()
        )
        if len(loc) == 3 and loc[0] in _ROWS and isinstance(loc[1], int):  # noqa: PLR2004 - (table, row, column)
            row = f"{_ROWS[loc[0]]} {loc[1] + 1}"
            if error["type"] == "extra_forbidden":
                problems.append(f"{row} has an unexpected column {loc[2]!r}.")
            elif blank and loc[2] in _REQUIRED_CELLS:
                missing.setdefault(row, []).append(_REQUIRED_CELLS[loc[2]])
            else:
                problems.append(f"{row}'s {_CELLS.get(loc[2], loc[2])} must be text.")
        elif len(loc) == 1 and loc[0] in _FIELDS and blank:
            problems.append(f"{_FIELDS[loc[0]]} can't be empty.")
        elif loc and loc[0] == "context":
            # Only Structured Context can hold something other than text.
            problems.append(
                "Structured Context must be one JSON object, such as a single record, whose values are plain "
                "JSON: text, numbers, true or false, null, lists and objects."
            )
        elif not loc:
            # A rule across the whole request, such as unique IDs.
            problems.append(f"{error['msg'].removeprefix('Value error, ')}.")
        else:
            problems.append(f"{'.'.join(str(part) for part in loc)}: {error['msg']}.")
    # Union types report one error per branch; say each problem once.
    return " ".join(
        [f"{row} needs {' and '.join(cells)}." for row, cells in missing.items()] + list(dict.fromkeys(problems))
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
    options: tuple[DecisionOption, ...] = ()
    levels: tuple[DecisionOption, ...] = ()
    # Boolean only: what a Yes and a No answer mean.
    yes_description: str = ""
    no_description: str = ""

    @field_validator("yes_description", "no_description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        # A blank description is no description.
        return value.strip()

    @field_validator("context")
    @classmethod
    def validate_context(cls, value: str | dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        json.dumps(value, allow_nan=False)
        return value

    @model_validator(mode="after")
    def validate_candidates(self) -> DecisionRequest:
        candidates = self.options if self.kind == "choice" else self.levels
        noun = "Option" if self.kind == "choice" else "Level"
        if self.kind in {"choice", "score"} and len(candidates) < MIN_CANDIDATES:
            msg = f"Add at least two {noun.lower()}s"
            raise ValueError(msg)
        if (self.kind != "choice" and self.options) or (self.kind != "score" and self.levels):
            msg = "Options belong to Choice and ordered levels belong to Score"
            raise ValueError(msg)
        if self.kind != "boolean" and (self.yes_description or self.no_description):
            msg = "Yes and No descriptions belong to Boolean"
            raise ValueError(msg)
        ids = [c.id for c in candidates]
        labels = [c.label.strip().casefold() for c in candidates]
        for column, values in (("ID", ids), ("Label, ignoring case", labels)):
            for position, value in enumerate(values, start=1):
                if (first := values.index(value) + 1) < position:
                    msg = f"{noun}s {first} and {position} have the same {column}. Each needs a different one"
                    raise ValueError(msg)
        return self


def decision_request(**fields: Any) -> DecisionRequest:
    """Build a request from flow configuration, reporting invalid configuration as a clear error."""
    try:
        return DecisionRequest(**fields)
    except ValidationError as exc:
        raise DecisionConfigurationError(configuration_summary(exc)) from None


class DecisionResult(BaseModel):
    """Evidence fields retain their meanings; no implicit Boolean/route policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: DecisionKind
    provider: NonEmpty
    model: ModelName
    model_source: Literal["response", "request"] = "response"
    status: Literal["success", "refusal"] = "success"
    probabilities: dict[str, Probability] | None = None
    probability_true: Probability | None = None
    score: FiniteNumber | None = None
    selected_option: NonEmpty | None = None
    confidence: Probability | None = None
    refusal: NonEmpty | None = None
    usage: dict[str, JsonValue] | None = None
    # The provider's ID for this request, to quote when asking it about an answer.
    request_id: NonEmpty | None = None

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
            # Accept the providers' rounding, never normalize malformed provider evidence.
            rounding = REPORTED_ROUNDING * len(self.probabilities)
            if not math.isclose(sum(self.probabilities.values()), 1.0, rel_tol=0, abs_tol=rounding):
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
        if self.kind != request.kind:
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
            # The score was rounded once, and each probability's rounding error is weighted by its level.
            rounding = REPORTED_ROUNDING * (1 + sum(range(len(request.levels))))
            if not math.isclose(self.score, expected_score, rel_tol=0, abs_tol=rounding):
                msg = "Score disagrees with its ordered-level probability distribution"
                raise DecisionEvaluationError(msg)
        return self
