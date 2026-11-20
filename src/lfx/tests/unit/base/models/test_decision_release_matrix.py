"""v1.14 release matrix: every decision type through every mandatory provider, with only the network faked.

Each case runs the real Smart Router policy, catalog, provider policy, credential resolution, wire translation,
response parsing and evidence validation. Unit tests elsewhere pin each layer alone; this file pins that they
agree end to end for TypeSafe, Perplexity and OpenAI, so a release cannot silently drop one.
"""

from types import SimpleNamespace

import httpx
import pytest
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionEvaluationError
from lfx.base.models.provider_registry import resolve_provider_id
from lfx.components.llm_operations.decision_model import DecisionModelComponent
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
from lfx.schema.data import Data
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
)

from tests.unit.base.models import decision_wire
from tests.unit.base.models.decision_wire import (
    KEY_VARIABLES,
    PROVIDERS,
    SERVED_MODELS,
    candidate_ids,
    distribution,
    probability_true,
    raises,
    refusal,
    selected_model,
    status,
)

STOP, ELSE = "Stop with error", "Route to Else"
ROUTES = [
    {"route_category": "Billing", "route_description": "Invoices, refunds and charges"},
    {"route_category": "Technical", "route_description": "Errors and outages"},
    {"route_category": "Sales", "route_description": "Plans and pricing"},
]
LEVELS = [{"route_category": "Low"}, {"route_category": "Medium"}, {"route_category": "High"}]
ROUTE_IDS = ["category_1_result", "category_2_result", "category_3_result"]
QUESTIONS = {
    "choice": "Which team should handle this message?",
    "boolean": "Is the customer asking for a refund?",
    "score": "How urgent is this message?",
}


@pytest.fixture
def decision_endpoint(monkeypatch):
    return decision_wire.install(monkeypatch)


def _router(provider, kind, *, error_action=ELSE, minimum_probability=0.7, else_connected=True, **fields):
    router = SmartRouterComponent()
    tables = {"choice": {"routes": ROUTES}, "score": {"score_levels": LEVELS}, "boolean": {}}[kind]
    router.set(
        input_text="I was charged twice for my plan.",
        routing_mode="Decision Model",
        decision_model=selected_model(provider),
        decision_kind=kind.title(),
        decision_question=QUESTIONS[kind],
        minimum_probability=minimum_probability,
        evaluation_error_action=error_action,
        enable_else_output=True,
        **{**tables, **fields},
    )
    edges = [SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))] if else_connected else []
    router._vertex = SimpleNamespace(outgoing_edges=edges)
    router.log = lambda *_args, **_kwargs: None
    return router


def _route(provider, kind, **settings):
    """The label the router chose ("" is Else) and the evidence it logged."""
    router = _router(provider, kind, **settings)
    return router._get_categorization(), router._decision_evidence


def _accepting_reply(kind):
    return {
        "choice": distribution(0.1, 0.8, 0.1),
        "boolean": probability_true(0.9),
        # 0*0.1 + 1*0.2 + 2*0.7 = 1.6, which rounds to High.
        "score": distribution(0.1, 0.2, 0.7),
    }[kind]


each_provider = pytest.mark.parametrize("provider", PROVIDERS)
each_kind = pytest.mark.parametrize("kind", ["choice", "boolean", "score"])


@each_provider
@each_kind
def test_a_confident_answer_takes_its_route(decision_endpoint, provider, kind):
    decision_endpoint.answer(_accepting_reply(kind))

    label, evidence = _route(provider, kind)

    assert label == {"choice": "Technical", "boolean": "Yes", "score": "High"}[kind]
    assert evidence["reason"] == "accepted"
    assert (
        evidence["activated_branch"]
        == {"choice": ROUTE_IDS[1], "boolean": "yes_result", "score": "level_3_result"}[kind]
    )
    sent_to, authorization, _ = decision_endpoint.calls[0]
    assert sent_to == provider
    # Each provider only ever gets its own key, never another provider's or the Language Model's.
    assert authorization == f"Bearer {provider.lower()}-release-key"
    # The model version the provider reports is the evidence a run records.
    assert evidence["result"]["model"] == SERVED_MODELS[provider]
    assert evidence["result"]["provider"] == provider


@each_provider
def test_choice_routes_by_route_id_not_by_name(decision_endpoint, provider):
    """Renaming a route or reordering the table never changes which output a decision activates."""
    routes = [
        {"route_category": "Sales (renamed)", "route_id": "category_3_result"},
        {"route_category": "Billing", "route_id": "category_1_result"},
    ]
    decision_endpoint.answer(distribution(0.9, 0.1))

    label, evidence = _route(provider, "choice", routes=routes, last_route_number=3)

    sent_ids = candidate_ids(provider, decision_endpoint.payload)
    assert sent_ids == ["category_3_result", "category_1_result"]
    assert label == "Sales (renamed)"
    assert evidence["activated_branch"] == "category_3_result"


@each_provider
@pytest.mark.parametrize(
    ("kind", "reply"), [("choice", distribution(0.4, 0.4, 0.2)), ("boolean", probability_true(0.5))]
)
def test_a_tie_for_the_top_goes_to_else(decision_endpoint, provider, kind, reply):
    decision_endpoint.answer(reply)

    label, evidence = _route(provider, kind, minimum_probability=0)

    assert label == ""
    assert evidence["reason"] == "tied_top_probability"
    assert evidence["activated_branch"] == "default_result"


@each_provider
@pytest.mark.parametrize(
    ("kind", "reply", "expected"),
    [
        ("choice", distribution(0.7, 0.2, 0.1), "Billing"),
        ("choice", distribution(0.69, 0.21, 0.1), ""),
        ("boolean", probability_true(0.7), "Yes"),
        ("boolean", probability_true(0.69), ""),
        ("boolean", probability_true(0.3), "No"),
    ],
)
def test_the_minimum_probability_is_inclusive(decision_endpoint, provider, kind, reply, expected):
    decision_endpoint.answer(reply)

    label, evidence = _route(provider, kind, minimum_probability=0.7)

    assert label == expected
    assert evidence["reason"] == ("accepted" if expected else "below_minimum_probability")


@each_provider
def test_no_meets_a_minimum_float_error_would_put_it_under(decision_endpoint, provider):
    """1 - 0.33 is 0.6699999999999999 in floating point; P(no) must still meet a 0.67 minimum."""
    decision_endpoint.answer(probability_true(0.33))

    label, evidence = _route(provider, "boolean", minimum_probability=0.67)

    assert label == "No"
    assert evidence["route_probabilities"]["no_result"] == 0.67


@each_provider
def test_a_routes_own_minimum_overrides_the_routers(decision_endpoint, provider):
    routes = [
        {**ROUTES[0], "minimum_probability": 0.95},
        {**ROUTES[1], "minimum_probability": "0.5"},
        ROUTES[2],
    ]
    decision_endpoint.answer(distribution(0.9, 0.05, 0.05))
    label, evidence = _route(provider, "choice", routes=routes)
    assert (label, evidence["applied_threshold"]) == ("", 0.95)

    decision_endpoint.answer(distribution(0.05, 0.6, 0.35))
    label, evidence = _route(provider, "choice", routes=routes)
    assert (label, evidence["applied_threshold"]) == ("Technical", 0.5)


@each_provider
def test_yes_and_no_minimums_override_the_routers(decision_endpoint, provider):
    decision_endpoint.answer(probability_true(0.9))
    label, _ = _route(provider, "boolean", yes_minimum_probability=0.95)
    assert label == ""

    decision_endpoint.answer(probability_true(0.4))
    label, _ = _route(provider, "boolean", no_minimum_probability=0.5)
    assert label == "No"


@each_provider
def test_a_score_halfway_between_levels_takes_the_higher(decision_endpoint, provider):
    decision_endpoint.answer(distribution(0.5, 0.5, 0.0))

    label, evidence = _route(provider, "score")

    assert label == "Medium"
    assert evidence["result"]["score"] == 0.5


INVALID_ANSWERS = [
    pytest.param("choice", distribution(0.5, 0.3, 0.1), id="choice-does-not-sum-to-one"),
    pytest.param("choice", distribution(-0.1, 0.6, 0.5), id="choice-negative-probability"),
    pytest.param("boolean", probability_true(1.2), id="boolean-above-one"),
    pytest.param("score", distribution(0.1, 0.2, 0.7, score=2.5), id="score-outside-rubric"),
    pytest.param("score", distribution(0.1, 0.2, 0.7, score=0.2), id="score-disagrees-with-distribution"),
]


@each_provider
@pytest.mark.parametrize(("kind", "reply"), INVALID_ANSWERS)
def test_invalid_evidence_is_an_evaluation_error_never_uncertainty(decision_endpoint, provider, kind, reply):
    decision_endpoint.answer(reply)
    label, evidence = _route(provider, kind, error_action=ELSE)
    assert label == ""
    assert evidence["reason"] == "evaluation_error"
    assert evidence["error"]["category"] == "invalid_response"

    router = _router(provider, kind, error_action=STOP)
    with pytest.raises(DecisionEvaluationError) as stopped:
        router._get_categorization()
    assert stopped.value.category == "invalid_response"
    assert router._decision_evidence["activated_branch"] is None


OPERATIONAL_ERRORS = [
    pytest.param(raises(httpx.ReadTimeout("slow")), "timeout", id="timeout"),
    pytest.param(raises(httpx.ConnectError("down")), "transport", id="transport"),
    pytest.param(status(429), "http_error", id="rate-limited"),
    pytest.param(status(503), "http_error", id="server-error"),
    pytest.param(status(413), "input_too_large", id="input-too-large"),
]


@each_provider
@each_kind
@pytest.mark.parametrize(("reply", "category"), OPERATIONAL_ERRORS)
def test_both_error_actions_for_operational_errors(decision_endpoint, provider, kind, reply, category):
    decision_endpoint.answer(reply)
    label, evidence = _route(provider, kind, error_action=ELSE)
    assert label == ""
    assert evidence["error"]["category"] == category
    assert evidence["activated_branch"] == "default_result"

    with pytest.raises(DecisionEvaluationError) as stopped:
        _route(provider, kind, error_action=STOP)
    assert stopped.value.category == category


ALWAYS_STOP = [
    pytest.param(status(401), PermissionError, "permission_denied", id="rejected-key"),
    pytest.param(status(403), PermissionError, "permission_denied", id="key-without-access"),
    pytest.param(status(402), PermissionError, "permission_denied", id="out-of-credit"),
    pytest.param(status(429, "insufficient_quota"), PermissionError, "permission_denied", id="quota-exhausted"),
    pytest.param(status(404), DecisionConfigurationError, "configuration_error", id="model-not-offered"),
    pytest.param(status(422), DecisionConfigurationError, "configuration_error", id="request-not-accepted"),
]


@each_provider
@pytest.mark.parametrize(("reply", "error", "reason"), ALWAYS_STOP)
def test_access_and_configuration_failures_stop_even_with_route_to_else(
    decision_endpoint, provider, reply, error, reason
):
    decision_endpoint.answer(reply)
    router = _router(provider, "choice", error_action=ELSE)

    with pytest.raises(error):
        router._get_categorization()

    assert router._decision_evidence["reason"] == reason
    assert router._decision_evidence["activated_branch"] is None


@pytest.mark.parametrize("kind", ["choice", "boolean", "score"])
def test_an_openai_refusal_follows_the_error_action(decision_endpoint, kind):
    decision_endpoint.answer(refusal())
    label, evidence = _route("OpenAI", kind, error_action=ELSE)
    assert (label, evidence["reason"]) == ("", "refusal")

    with pytest.raises(DecisionEvaluationError, match="declined to answer") as stopped:
        _route("OpenAI", kind, error_action=STOP)
    assert stopped.value.category == "refusal"


@pytest.mark.parametrize("provider", ["TypeSafe", "Perplexity"])
def test_a_refusal_shape_from_other_providers_is_an_invalid_answer(decision_endpoint, provider):
    """Only OpenAI documents refusals; elsewhere the shape is malformed evidence, not a refusal."""
    decision_endpoint.answer(refusal())

    label, evidence = _route(provider, "choice", error_action=ELSE)

    assert label == ""
    assert evidence["error"]["category"] == "invalid_response"


def _blocking_policy(provider):
    provider_id = resolve_provider_id(provider)
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({provider_id}),
        allowed_provider_ids=frozenset(),
    )


@each_provider
def test_a_denied_provider_is_refused_before_any_inference(decision_endpoint, monkeypatch, provider):
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: _blocking_policy(provider)
    )

    with pytest.raises(ModelProviderPolicyError):
        _route(provider, "choice", error_action=ELSE)

    assert decision_endpoint.calls == []


@each_provider
def test_a_missing_key_is_refused_before_any_inference(decision_endpoint, monkeypatch, provider):
    monkeypatch.delenv(KEY_VARIABLES[provider])

    with pytest.raises(DecisionConfigurationError, match="API key"):
        _route(provider, "choice", error_action=ELSE)

    assert decision_endpoint.calls == []


def test_openai_with_a_custom_endpoint_is_refused_before_any_inference(decision_endpoint, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")

    with pytest.raises(DecisionConfigurationError, match="official OpenAI endpoint"):
        _route("OpenAI", "choice", error_action=ELSE)

    assert decision_endpoint.calls == []


@each_provider
@pytest.mark.parametrize(
    "settings",
    [pytest.param({"else_connected": False}, id="else-not-connected"), pytest.param({}, id="else-off")],
)
def test_else_is_required_before_any_inference(decision_endpoint, provider, settings):
    router = _router(provider, "choice", **settings)
    if not settings:
        router.set(enable_else_output=False)

    with pytest.raises(DecisionConfigurationError, match="Include Else Output"):
        router._get_categorization()

    assert decision_endpoint.calls == []


@each_provider
@pytest.mark.parametrize("bad", [-0.1, 1.5, "", float("nan")])
def test_an_invalid_minimum_probability_stops_before_any_inference(decision_endpoint, provider, bad):
    with pytest.raises(DecisionConfigurationError, match="Minimum Probability"):
        _route(provider, "choice", minimum_probability=bad)

    assert decision_endpoint.calls == []


CANDIDATES = [{"id": "refund", "label": "Refund"}, {"id": "other", "label": "Something else"}]


@each_provider
@each_kind
def test_the_standalone_component_returns_typed_evidence(decision_endpoint, provider, kind):
    replies = {"choice": distribution(0.8, 0.2), "boolean": probability_true(0.8), "score": distribution(0.2, 0.8)}
    decision_endpoint.answer(replies[kind])
    component = DecisionModelComponent()
    component.set(
        model=selected_model(provider),
        kind=kind.title(),
        context="I was charged twice for my plan.",
        question=QUESTIONS[kind],
        candidates=CANDIDATES,
    )

    result = component.evaluate()

    assert isinstance(result, Data)
    assert result.data["kind"] == kind
    assert result.data["provider"] == provider
    assert result.data["model"] == SERVED_MODELS[provider]
    assert result.data["status"] == "success"
    expected = {
        "choice": {"probabilities": {"refund": 0.8, "other": 0.2}},
        "boolean": {"probability_true": 0.8},
        "score": {"probabilities": {"refund": 0.2, "other": 0.8}, "score": 0.8},
    }[kind]
    assert {name: result.data.get(name) for name in expected} == expected
    # The request is echoed for inspection, never the context it judged.
    assert "context" not in result.data["request"]


@each_provider
def test_the_standalone_component_raises_operational_errors(decision_endpoint, provider):
    """The component has no Else: an operational error stops the run, for a flow to handle."""
    decision_endpoint.answer(status(503))
    component = DecisionModelComponent()
    component.set(model=selected_model(provider), kind="Boolean", context="Hi", question="Is this a refund?")

    with pytest.raises(DecisionEvaluationError) as stopped:
        component.evaluate()

    assert stopped.value.category == "http_error"
