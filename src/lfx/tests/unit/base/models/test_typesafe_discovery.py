"""TypeSafe discovery is authenticated, credential-isolated and independent of execution."""

from unittest.mock import Mock

import httpx
import pytest
from lfx.base.models.decisions import providers, typesafe
from lfx.base.models.decisions.runtime import evaluate_decision
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest, DecisionResult
from lfx.base.models.model_utils import replace_with_live_models
from lfx.base.models.unified_models import credentials, get_decision_model_options
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
)


def policy():
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"typesafe"}),
        allowed_provider_ids=frozenset({"typesafe"}),
    )


@pytest.fixture
def catalog(monkeypatch):
    typesafe._catalog.cache_clear()
    handler = Mock(
        side_effect=lambda request: httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "jev-preview"
                        if request.headers["authorization"] == "Bearer first-key"
                        else "future-model",
                        "description": "Model",
                        "release_date": "2026-10-27",
                    }
                ]
            },
        )
    )
    monkeypatch.setattr(
        typesafe, "provider_httpx_client_kwargs", lambda _url: ({"transport": httpx.MockTransport(handler)}, {})
    )
    yield handler
    typesafe._catalog.cache_clear()


def test_list_uses_fixed_authenticated_endpoint_and_isolates_cached_credentials(catalog):
    first = typesafe.get_models("first-key")
    first[0]["capabilities"].clear()
    assert typesafe.get_models("first-key")[0]["capabilities"] == ["choice", "boolean", "score"]
    assert typesafe.get_models("second-key")[0]["name"] == "future-model"
    assert catalog.call_count == 2
    assert str(catalog.call_args.args[0].url) == "https://api.typesafe.ai/v1/models"
    assert "first-key" not in repr(typesafe._catalog.cache)
    assert "second-key" not in repr(typesafe._catalog.cache)


@pytest.mark.parametrize(("status", "body"), [(401, {}), (500, {}), (200, {}), (200, {"models": [None]})])
def test_failures_are_explicit_redacted_and_not_cached(catalog, status, body):
    catalog.side_effect = lambda _request: httpx.Response(status, json=body)
    for _ in range(2):
        with pytest.raises(DecisionConfigurationError, match="Could not load TypeSafe") as error:
            typesafe.get_models("first-key")
        assert "first-key" not in str(error.value)
    assert catalog.call_count == 2


def test_redirect_is_not_followed(catalog):
    catalog.side_effect = lambda _request: httpx.Response(302, headers={"Location": "https://attacker.invalid"})
    with pytest.raises(DecisionConfigurationError):
        typesafe.get_models("first-key")
    catalog.assert_called_once()


@pytest.mark.usefixtures("catalog")
def test_configured_catalog_replaces_seed_but_not_chat(monkeypatch):
    monkeypatch.setattr("lfx.base.models.model_utils.get_provider_variable_value", lambda *_: "first-key")
    groups = [
        {"provider": "TypeSafe", "models": [{"model_name": "jev-latest", "metadata": {"model_type": "decision"}}]}
    ]
    replace_with_live_models(groups, "user", {"TypeSafe"})
    assert [row["model_name"] for row in groups[0]["models"]] == ["jev-preview"]
    untouched = [{"provider": "TypeSafe", "models": []}]
    replace_with_live_models(untouched, "user", {"TypeSafe"}, "llm")
    assert untouched == [{"provider": "TypeSafe", "models": []}]


@pytest.mark.usefixtures("catalog")
def test_standalone_picker_discovers_env_configured_models(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "first-key")
    options = get_decision_model_options(provider_policy=policy())
    assert [o["name"] for o in options] == ["jev-preview"]


def test_default_validation_discovers_using_unsaved_key(monkeypatch, catalog):
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy())
    validate = Mock()
    monkeypatch.setattr(providers, "validate_decision_provider_key", validate)
    credentials.validate_model_provider_key("TypeSafe", {"TYPESAFE_API_KEY": "second-key"})
    assert validate.call_args.args[2] == "future-model"
    assert catalog.call_args.args[0].headers["authorization"] == "Bearer second-key"


def test_pinned_execution_uses_request_key_without_discovery(monkeypatch, catalog):
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy())
    transport = Mock(
        return_value=DecisionResult(kind="boolean", provider="TypeSafe", model="jev-1.14.0", probability_true=0.5)
    )
    monkeypatch.setattr(providers, "evaluate_provider", transport)
    request = DecisionRequest(kind="boolean", question="Relevant?", context="text")
    evaluate_decision(
        request,
        model={"provider": "TypeSafe", "name": "jev-1.14.0"},
        request_variables={"TYPESAFE_API_KEY": "request-key"},
    )
    assert transport.call_args.kwargs["api_key"] == "request-key"
    catalog.assert_not_called()


@pytest.mark.parametrize("name", ["future-model", "jev-1.14.0"])
def test_explicit_typesafe_ids_are_validated_by_system_one(monkeypatch, catalog, name):
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy())
    validate = Mock()
    monkeypatch.setattr(providers, "validate_decision_provider_key", validate)
    credentials.validate_model_provider_key("TypeSafe", {"TYPESAFE_API_KEY": "first-key"}, model_name=name)
    assert validate.call_args.args[2] == name
    catalog.assert_not_called()


def test_discovery_strips_surrounding_key_whitespace_but_rejects_embedded_controls(monkeypatch, catalog):
    from lfx.base.models.model_utils import get_live_models_for_provider

    monkeypatch.setenv("TYPESAFE_API_KEY", " first-key\n")
    assert get_live_models_for_provider(None, "TypeSafe", "decision")[0]["name"] == "jev-preview"
    assert catalog.call_args.args[0].headers["authorization"] == "Bearer first-key"
    monkeypatch.setenv("TYPESAFE_API_KEY", "first\nkey")
    with pytest.raises(DecisionConfigurationError, match="valid TypeSafe API key"):
        get_live_models_for_provider(None, "TypeSafe", "decision")
    assert catalog.call_count == 1
