"""Trust-boundary checks for semantic decision evidence."""

import pytest
from lfx.base.models.decisions.schema import (
    DecisionEvaluationError,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
)
from pydantic import ValidationError


@pytest.fixture
def options():
    return (DecisionOption(id="billing", label="Billing"), DecisionOption(id="support", label="Support"))


def test_choice_keeps_probabilities_separate_from_confidence(options):
    request = DecisionRequest(kind="choice", question="Which team?", context="Charged twice", options=options)
    result = DecisionResult(
        kind="choice",
        provider="TypeSafe",
        model="jev-latest",
        probabilities={"billing": 0.9, "support": 0.1},
        selected_option="billing",
        confidence=0.6,
    )
    assert result.validate_for(request) is result
    assert result.confidence == 0.6
    assert result.model_dump(mode="json")["probabilities"]["billing"] == 0.9


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), -0.01, 1.01, True, "0.5"])
def test_boolean_rejects_invalid_probability(probability):
    with pytest.raises(ValidationError):
        DecisionResult(kind="boolean", provider="TypeSafe", model="jev-latest", probability_true=probability)


@pytest.mark.parametrize("probability", [0, 0.5, 1])
def test_boolean_preserves_uncertainty_without_coercion(probability):
    result = DecisionResult(kind="boolean", provider="TypeSafe", model="jev-latest", probability_true=probability)
    request = DecisionRequest(kind="boolean", question="Contains a complaint?", context="Maybe")
    assert result.validate_for(request).probability_true == probability
    assert result.selected_option is None


@pytest.mark.parametrize("distribution", [{"billing": 0.3, "support": 0.3}, {"billing": 1.1, "support": -0.1}, {}])
def test_rejects_malformed_distributions(distribution):
    with pytest.raises(ValidationError):
        DecisionResult(kind="choice", provider="TypeSafe", model="jev-latest", probabilities=distribution)


@pytest.mark.parametrize("distribution", [{"billing": 1.0}, {"billing": 0.5, "other": 0.5}])
def test_distribution_requires_exact_requested_membership(options, distribution):
    request = DecisionRequest(kind="choice", question="Which?", context="x", options=options)
    result = DecisionResult(kind="choice", provider="TypeSafe", model="jev-latest", probabilities=distribution)
    with pytest.raises(DecisionEvaluationError, match="exactly"):
        result.validate_for(request)


@pytest.mark.parametrize("selected", ["unknown", "support"])
def test_selected_outcome_must_agree_with_distribution(options, selected):
    request = DecisionRequest(kind="choice", question="Which?", context="x", options=options)
    result = DecisionResult(
        kind="choice",
        provider="TypeSafe",
        model="jev-latest",
        probabilities={"billing": 0.9, "support": 0.1},
        selected_option=selected,
    )
    with pytest.raises(DecisionEvaluationError):
        result.validate_for(request)


def test_fractional_score_is_position_on_ordered_rubric(options):
    request = DecisionRequest(kind="score", question="How severe?", context="x", levels=options)
    result = DecisionResult(
        kind="score",
        provider="OpenAI",
        model="gpt-6-luna",
        probabilities={"billing": 0.25, "support": 0.75},
        score=0.75,
        confidence=0.2,
    )
    assert result.validate_for(request).score == 0.75


@pytest.mark.parametrize("score", [-0.5, 2, 0.3])
def test_score_must_match_scale_and_distribution(options, score):
    request = DecisionRequest(kind="score", question="How severe?", context="x", levels=options)
    result = DecisionResult(
        kind="score",
        provider="OpenAI",
        model="gpt-6-luna",
        probabilities={"billing": 0.25, "support": 0.75},
        score=score,
    )
    with pytest.raises(DecisionEvaluationError):
        result.validate_for(request)


def test_refusal_is_not_a_zero_probability():
    request = DecisionRequest(kind="boolean", question="Safe?", context="x")
    result = DecisionResult(kind="boolean", provider="OpenAI", model="gpt-6-luna", status="refusal", refusal="Declined")
    assert result.validate_for(request).probability_true is None
    with pytest.raises(ValidationError):
        DecisionResult(**{**result.model_dump(), "probability_true": 0})


def test_answer_of_a_different_kind_is_rejected():
    request = DecisionRequest(kind="boolean", question="Safe?", context="x")
    result = DecisionResult(kind="score", provider="OpenAI", model="gpt-6-luna", probabilities={"a": 1.0}, score=0.0)
    with pytest.raises(DecisionEvaluationError, match="different"):
        result.validate_for(request)


@pytest.mark.parametrize(("ids", "labels"), [(("x", "x"), ("A", "B")), (("x", "y"), ("A", " a "))])
def test_rejects_ambiguous_option_identities(ids, labels):
    options = tuple(DecisionOption(id=key, label=label) for key, label in zip(ids, labels, strict=True))
    with pytest.raises(ValidationError, match="unique"):
        DecisionRequest(kind="choice", question="Which?", context="x", options=options)


@pytest.mark.parametrize("kind", ["choice", "score"])
def test_requires_at_least_two_candidates(kind):
    with pytest.raises(ValidationError, match="at least two"):
        DecisionRequest(kind=kind, question="Which?", context="x")


def test_context_must_be_serializable_finite_json():
    with pytest.raises(ValidationError):
        DecisionRequest(kind="boolean", question="Safe?", context={"number": float("nan")})


@pytest.mark.parametrize("field", ["yes_description", "no_description"])
def test_yes_and_no_descriptions_belong_to_boolean(options, field):
    with pytest.raises(ValidationError, match="belong to Boolean"):
        DecisionRequest(kind="choice", question="Which team?", context="x", options=options, **{field: "Refund"})
