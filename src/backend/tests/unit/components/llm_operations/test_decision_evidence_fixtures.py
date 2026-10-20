"""Decision evidence fixtures for the inspection UI, regenerated from the real Smart Router.

Set UPDATE_DECISION_FIXTURES=1 to rewrite decision_evidence_fixtures.json after an intended change.
"""

import contextlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionEvaluationError, DecisionResult
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
from lfx.schema.message import Message

FIXTURES = Path(__file__).with_name("decision_evidence_fixtures.json")
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


def _choice(*probabilities: float, refusal: bool = False) -> DecisionResult:
    common = {"kind": "choice", "provider": "TypeSafe", "model": "jev-1.13.0", "usage": {"input_tokens": 312}}
    if refusal:
        return DecisionResult(**common, status="refusal", refusal="Provider declined this question.")
    ids = [f"category_{i + 1}_result" for i in range(len(probabilities))]
    return DecisionResult(**common, probabilities=dict(zip(ids, probabilities, strict=True)), confidence=0.6)


def _raise(error: Exception):
    def evaluate(*_args, **_kwargs):
        raise error

    return evaluate


SCENARIOS = {
    "accepted": ("Route to Else", lambda *_a, **_k: _choice(0.86, 0.1, 0.04)),
    "below_minimum_probability": ("Route to Else", lambda *_a, **_k: _choice(0.55, 0.3, 0.15)),
    "route_override_not_met": ("Route to Else", lambda *_a, **_k: _choice(0.05, 0.1, 0.85)),
    "tied_top_probability": ("Route to Else", lambda *_a, **_k: _choice(0.45, 0.45, 0.1)),
    "refusal_routed_to_else": ("Route to Else", lambda *_a, **_k: _choice(refusal=True)),
    "evaluation_error_routed_to_else": (
        "Route to Else",
        _raise(DecisionEvaluationError("TypeSafe decision request timed out.", category="timeout")),
    ),
    "evaluation_error_stopped": (
        "Stop with error",
        _raise(DecisionEvaluationError("TypeSafe decision request failed (HTTP 503).", category="http_error")),
    ),
    "permission_denied": ("Route to Else", _raise(PermissionError("TypeSafe denied the decision request (HTTP 401)."))),
    "configuration_error": (
        "Route to Else",
        _raise(DecisionConfigurationError("The selected decision model is disabled or unavailable.")),
    ),
}


def _evidence(monkeypatch, error_action: str, evaluate) -> dict:
    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    router = SmartRouterComponent()
    router.set(
        input_text="I was charged twice for my October invoice.",
        routes=ROUTES,
        routing_mode="Decision Model",
        decision_model=[{"provider": "TypeSafe", "name": "jev-latest"}],
        decision_question="Which team should handle this message?",
        minimum_probability=0.7,
        evaluation_error_action=error_action,
        enable_else_output=True,
    )
    router._vertex = SimpleNamespace(
        outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
    )
    router.log = lambda *_args, **_kwargs: None
    # Stopped evaluations still leave their evidence behind; that is what the fixture records.
    with contextlib.suppress(DecisionEvaluationError, DecisionConfigurationError, PermissionError):
        router._get_categorization()
    return router._build_artifact(Message(text="I was charged twice for my October invoice."))["raw"]["decision"]


class TestDecisionEvidenceFixtures:
    """Fixtures for the inspection UI match what the real router produces."""

    def test_decision_evidence_fixtures_match_the_router(self, monkeypatch):
        produced = {name: _evidence(monkeypatch, action, evaluate) for name, (action, evaluate) in SCENARIOS.items()}
        if os.environ.get("UPDATE_DECISION_FIXTURES") == "1":
            FIXTURES.write_text(json.dumps(produced, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        assert produced == json.loads(FIXTURES.read_text(encoding="utf-8"))

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
        ],
    )
    def test_each_fixture_has_the_expected_outcome(self, name, reason, branch):
        evidence = json.loads(FIXTURES.read_text(encoding="utf-8"))[name]
        assert evidence["reason"] == reason
        assert evidence["activated_branch"] == branch
