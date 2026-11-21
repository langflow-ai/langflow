"""Decision fixtures for the inspection UI, regenerated from the real Smart Router and Decision Model.

decision_evidence_fixtures.json holds Smart Router evidence for each decision type;
decision_result_fixtures.json holds the
Decision Model component's result for each decision type. Set UPDATE_DECISION_FIXTURES=1 to rewrite
both after an intended change.
"""

import contextlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

import httpx
import pytest
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionEvaluationError, DecisionResult
from lfx.base.models.unified_models import get_provider_secret_variable_key
from lfx.components.llm_operations.decision_model import DecisionModelComponent
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
from lfx.schema.message import Message

FIXTURES = Path(__file__).with_name("decision_evidence_fixtures.json")
RESULT_FIXTURES = Path(__file__).with_name("decision_result_fixtures.json")
ROUTES = [
    {"route_category": "Billing", "route_description": "Payments and invoices", "output_value": ""},
    {"route_category": "Technical Support", "route_description": "Bugs and outages", "output_value": ""},
    {
        "route_category": "Sales",
        "route_description": "Pricing and plans",
        "output_value": "",
        "minimum_probability": 0.9,
    },
]


COMMON = {"provider": "TypeSafe", "model": "jev-1.13.0", "usage": {"input_tokens": 312}}


def _choice(*probabilities: float, refusal: bool = False) -> DecisionResult:
    common = {"kind": "choice", **COMMON}
    if refusal:
        return DecisionResult(**common, status="refusal", refusal="Provider declined this question.")
    ids = [f"category_{i + 1}_result" for i in range(len(probabilities))]
    return DecisionResult(**common, probabilities=dict(zip(ids, probabilities, strict=True)), confidence=0.6)


def _boolean(probability_true: float) -> DecisionResult:
    return DecisionResult(kind="boolean", **COMMON, probability_true=probability_true)


def _score(*probabilities: float) -> DecisionResult:
    ids = [f"level_{i + 1}_result" for i in range(len(probabilities))]
    score = sum(i * p for i, p in enumerate(probabilities))
    return DecisionResult(kind="score", **COMMON, probabilities=dict(zip(ids, probabilities, strict=True)), score=score)


def _raise(error: Exception):
    def evaluate(*_args, **_kwargs):
        raise error

    return evaluate


def _adapter_error(outcome: httpx.Response | Exception) -> Exception:
    """The error TypeSafe's adapter raises for this transport outcome, so the fixtures carry real messages."""
    from lfx.base.models.decisions import providers
    from lfx.base.models.decisions.schema import DecisionRequest

    def post(*_args, **_kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    request = DecisionRequest(kind="boolean", question="Is this a refund?", context="x")
    original = providers.provider_safe_httpx_post
    providers.provider_safe_httpx_post = post
    try:
        providers.evaluate_provider("TypeSafe", "jev-latest", request, api_key="fixture-key")
    except Exception as exc:  # The adapter's own error is the fixture.
        return exc
    finally:
        providers.provider_safe_httpx_post = original
    msg = "the adapter accepted a failure"
    raise AssertionError(msg)


SCENARIOS = {
    "accepted": ("Route to Else", lambda *_a, **_k: _choice(0.86, 0.1, 0.04)),
    "below_minimum_probability": ("Route to Else", lambda *_a, **_k: _choice(0.55, 0.3, 0.15)),
    "route_override_not_met": ("Route to Else", lambda *_a, **_k: _choice(0.05, 0.1, 0.85)),
    "tied_top_probability": ("Route to Else", lambda *_a, **_k: _choice(0.45, 0.45, 0.1)),
    "refusal_routed_to_else": ("Route to Else", lambda *_a, **_k: _choice(refusal=True)),
    "evaluation_error_routed_to_else": (
        "Route to Else",
        _raise(_adapter_error(httpx.ReadTimeout("timed out", request=httpx.Request("POST", "https://typesafe.test")))),
    ),
    "evaluation_error_stopped": (
        "Stop with error",
        _raise(_adapter_error(httpx.Response(503, json={}))),
    ),
    "permission_denied": ("Route to Else", _raise(_adapter_error(httpx.Response(401, json={})))),
    "configuration_error": (
        "Route to Else",
        _raise(
            DecisionConfigurationError("The selected Decision Model is no longer offered. Pick another Decision Model.")
        ),
    ),
}


# Boolean and Score routers. Boolean answers through its Yes and No outputs, not the routes.
BOOLEAN = {
    "decision_kind": "Boolean",
    "decision_question": "Is the customer asking for a refund?",
    "yes_description": "Asks for money back",
    "no_description": "Anything else",
}
SCORE = {
    "decision_kind": "Score",
    "decision_question": "How urgent is this message?",
    "minimum_probability": None,
    "score_levels": [
        {"route_category": "Low", "route_description": "Can wait", "output_value": ""},
        {"route_category": "Medium", "route_description": "Today", "output_value": ""},
        {"route_category": "High", "route_description": "Now", "output_value": ""},
    ],
}
TYPE_SCENARIOS = {
    "boolean_accepted": (BOOLEAN, lambda *_a, **_k: _boolean(0.88)),
    "boolean_unsure": (BOOLEAN, lambda *_a, **_k: _boolean(0.55)),
    # A score of 1.4 rounds to Medium; 0.5, halfway between Low and Medium, takes the higher level.
    "score_accepted": (SCORE, lambda *_a, **_k: _score(0.1, 0.4, 0.5)),
    "score_rounds_up_at_halfway": (SCORE, lambda *_a, **_k: _score(0.5, 0.5, 0.0)),
}


def _evidence(monkeypatch, error_action: str, evaluate, **settings) -> dict:
    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    router = SmartRouterComponent()
    router.set(
        **{
            "input_text": "I was charged twice for my October invoice.",
            "routes": ROUTES,
            "routing_mode": "Decision Model",
            "decision_model": [{"provider": "TypeSafe", "name": "jev-latest"}],
            "decision_question": "Which team should handle this message?",
            "minimum_probability": 0.7,
            "evaluation_error_action": error_action,
            "enable_else_output": True,
            **settings,
        }
    )
    router._vertex = SimpleNamespace(
        outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
    )
    router.log = lambda *_args, **_kwargs: None
    # Stopped evaluations still leave their evidence behind; that is what the fixture records.
    with contextlib.suppress(DecisionEvaluationError, DecisionConfigurationError, PermissionError):
        router._get_categorization()
    return router._build_artifact(Message(text="I was charged twice for my October invoice."))["raw"]["decision"]


TEAMS = [
    {"id": "billing", "label": "Billing", "description": "Payments and invoices"},
    {"id": "technical", "label": "Technical Support", "description": "Bugs and outages"},
    {"id": "sales", "label": "Sales", "description": "Pricing and plans"},
]
SATISFACTION = [
    {"id": "upset", "label": "Upset", "description": ""},
    {"id": "neutral", "label": "Neutral", "description": ""},
    {"id": "satisfied", "label": "Satisfied", "description": ""},
    {"id": "delighted", "label": "Delighted", "description": ""},
]
USAGE = {"input_tokens": 296, "output_tokens": 0, "total_tokens": 296}


class ResultScenario(NamedTuple):
    provider: str
    model: str
    kind: str
    question: str
    candidates: list[dict]
    response: dict  # the provider's documented response shape, translated by the real adapter


RESULT_SCENARIOS = {
    "choice": ResultScenario(
        "Perplexity",
        "pplx-decider-latest",
        "Choice",
        "Which team should handle this message?",
        TEAMS,
        {
            "model": "pplx-decider-latest",
            "answers": {
                "decision": {
                    "type": "choice",
                    "probabilities": {"billing": 0.82, "technical": 0.12, "sales": 0.06},
                    "choice": "billing",
                    "confidence": 0.71,
                }
            },
            "usage": USAGE,
        },
    ),
    "boolean": ResultScenario(
        "OpenAI",
        "gpt-6-luna",
        "Boolean",
        "Is the customer asking for a refund?",
        [],
        {
            "model": "gpt-6-luna",
            "answers": [{"name": "decision", "type": "predicate", "probability": 0.88}],
            "usage": USAGE,
        },
    ),
    "score": ResultScenario(
        "TypeSafe",
        "jev-latest",
        "Score",
        "How satisfied is the customer?",
        SATISFACTION,
        {
            "model": "jev-1.13.0",
            "answers": {
                "decision": {
                    "type": "score",
                    "probabilities": {"0": 0.05, "1": 0.15, "2": 0.5, "3": 0.3},
                    "legend": {"0": "Upset", "1": "Neutral", "2": "Satisfied", "3": "Delighted"},
                    "score": 2.05,
                    "confidence": 0.4,
                }
            },
            "usage": USAGE,
        },
    ),
    "refusal": ResultScenario(
        "OpenAI",
        "gpt-6-luna",
        "Boolean",
        "Is the customer asking for a refund?",
        [],
        {
            "model": "gpt-6-luna",
            "answers": [{"name": "decision", "type": "refusal", "refusal": "I can't evaluate this request."}],
        },
    ),
}


def _component_result(monkeypatch, scenario: ResultScenario) -> dict:
    monkeypatch.setenv(get_provider_secret_variable_key(scenario.provider), "fixture-key")  # pragma: allowlist secret
    monkeypatch.setattr(
        "lfx.base.models.decisions.providers.provider_safe_httpx_post",
        # Only Perplexity documents a request ID header.
        lambda *_args, **_kwargs: httpx.Response(
            200,
            json=scenario.response,
            headers={"x-request-id": "req_5f0c9a"} if scenario.provider == "Perplexity" else {},
        ),
    )
    component = DecisionModelComponent()
    component.set(
        model=[{"provider": scenario.provider, "name": scenario.model}],
        kind=scenario.kind,
        context="I was charged twice for my October invoice. Support fixed it quickly, thanks!",
        question=scenario.question,
        candidates=scenario.candidates,
    )
    return component.evaluate().data


def _check_fixture(path: Path, produced: dict) -> None:
    """Compare with the saved fixture, rewriting it first when UPDATE_DECISION_FIXTURES=1."""
    if os.environ.get("UPDATE_DECISION_FIXTURES") == "1":
        path.write_text(json.dumps(produced, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert produced == json.loads(path.read_text(encoding="utf-8"))


class TestDecisionEvidenceFixtures:
    """Fixtures for the inspection UI match what the real router produces."""

    def test_decision_evidence_fixtures_match_the_router(self, monkeypatch):
        produced = {name: _evidence(monkeypatch, action, evaluate) for name, (action, evaluate) in SCENARIOS.items()}
        for name, (settings, evaluate) in TYPE_SCENARIOS.items():
            produced[name] = _evidence(monkeypatch, "Route to Else", evaluate, **settings)
        _check_fixture(FIXTURES, produced)

    def test_decision_result_fixtures_match_the_component(self, monkeypatch):
        produced = {name: _component_result(monkeypatch, scenario) for name, scenario in RESULT_SCENARIOS.items()}
        _check_fixture(RESULT_FIXTURES, produced)

    def test_a_route_below_its_threshold_is_the_top_outcome_not_a_selection(self):
        evidence = json.loads(FIXTURES.read_text(encoding="utf-8"))["below_minimum_probability"]
        assert evidence["top_outcome"] == "category_1_result"
        assert evidence["activated_branch"] == "default_result"
        assert "selected_outcome" not in evidence

    def test_score_names_no_top_outcome(self):
        # Score has no threshold to check a top outcome against; activated_branch names the level.
        fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
        for name in ("score_accepted", "score_rounds_up_at_halfway"):
            assert "top_outcome" not in fixtures[name], name
            assert fixtures[name]["activated_branch"] == "level_2_result"

    def test_probabilities_are_keyed_by_the_fixtures_own_options(self):
        # The evidence view reads each probability by option ID, so a Score keyed by route IDs breaks it.
        for name, evidence in json.loads(FIXTURES.read_text(encoding="utf-8")).items():
            probabilities = (evidence.get("result") or {}).get("probabilities")
            if probabilities:
                assert list(probabilities) == [option["id"] for option in evidence["options"]], name

    def test_result_fixtures_keep_each_kind_of_evidence_distinct(self):
        results = json.loads(RESULT_FIXTURES.read_text(encoding="utf-8"))
        assert results["boolean"]["probability_true"] == 0.88
        assert "probabilities" not in results["boolean"]
        assert results["score"]["score"] == 2.05
        assert [level["id"] for level in results["score"]["request"]["levels"]] == [r["id"] for r in SATISFACTION]
        assert results["score"]["probabilities"]["satisfied"] == 0.5
        assert results["choice"]["selected_option"] == "billing"
        assert results["choice"]["confidence"] == 0.71
        assert results["choice"]["request_id"] == "req_5f0c9a"
        assert "request_id" not in results["score"]
        assert results["refusal"]["status"] == "refusal"
        assert "probability_true" not in results["refusal"]
        assert results["refusal"]["refusal"] == "I can't evaluate this request."

    @pytest.mark.parametrize(
        ("name", "reason", "branch"),
        [
            ("accepted", "accepted", "category_1_result"),
            ("below_minimum_probability", "below_minimum_probability", "default_result"),
            ("route_override_not_met", "below_minimum_probability", "default_result"),
            ("tied_top_probability", "tied_top_probability", "default_result"),
            ("refusal_routed_to_else", "refusal", "default_result"),
            ("evaluation_error_routed_to_else", "evaluation_error", "default_result"),
            ("evaluation_error_stopped", "evaluation_error", None),
            ("permission_denied", "permission_denied", None),
            ("configuration_error", "configuration_error", None),
            ("boolean_accepted", "accepted", "yes_result"),
            ("boolean_unsure", "below_minimum_probability", "default_result"),
            ("score_accepted", "accepted", "level_2_result"),
            ("score_rounds_up_at_halfway", "accepted", "level_2_result"),
        ],
    )
    def test_each_fixture_has_the_expected_outcome(self, name, reason, branch):
        evidence = json.loads(FIXTURES.read_text(encoding="utf-8"))[name]
        assert evidence["reason"] == reason
        assert evidence["activated_branch"] == branch
