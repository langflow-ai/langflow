"""Gateway discovery and explicit IDs share the existing policy and credential boundary."""

from unittest.mock import Mock

import httpx
import pytest
from lfx.base.models.decisions import openrouter, providers
from lfx.base.models.decisions.runtime import evaluate_decision
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest, DecisionResult
from lfx.base.models.model_utils import inject_custom_enabled_models, replace_with_live_models
from lfx.base.models.unified_models import credentials, get_decision_model_options, model_catalog
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
)


def policy(*, blocked=()):
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"openrouter"}),
        allowed_provider_ids=frozenset({"openrouter"}),
        blocked_model_keys=frozenset(blocked),
    )


@pytest.fixture(autouse=True)
def public_catalog(monkeypatch):
    openrouter._catalog.cache_clear()
    rows = [
        {"id": name, "architecture": {"output_modalities": ["decisions"]}}
        for name in ["new-author/new-model", "~typesafe/jev-latest", "baseten/mammoth-1:free"]
    ]
    get = Mock(
        return_value=httpx.Response(200, json={"data": rows}, request=httpx.Request("GET", "https://openrouter.ai"))
    )
    monkeypatch.setattr(openrouter, "ssrf_safe_httpx_get", get)
    yield get
    openrouter._catalog.cache_clear()


def test_catalog_accepts_new_authors_aliases_and_free_variants_without_credentials(public_catalog):
    rows = openrouter.get_models()
    assert {r["name"] for r in rows} == {"new-author/new-model", "~typesafe/jev-latest", "baseten/mammoth-1:free"}
    assert all(r["model_type"] == "decision" for r in rows)
    assert public_catalog.call_args.args == ("https://openrouter.ai/api/v1/models?output_modalities=decisions",)
    assert "headers" not in public_catalog.call_args.kwargs
    rows[0]["capabilities"].clear()
    assert openrouter.get_models()[0]["capabilities"] == ["choice", "boolean", "score"]
    public_catalog.assert_called_once()


@pytest.mark.parametrize("body", [{}, {"data": None}, {"data": [None]}, {"data": [{"id": 123}]}])
def test_bad_catalog_is_visible_and_not_cached(body, public_catalog):
    public_catalog.return_value = httpx.Response(200, json=body, request=httpx.Request("GET", "https://openrouter.ai"))
    for _ in range(2):
        with pytest.raises(DecisionConfigurationError, match="Could not load OpenRouter"):
            openrouter.get_models()
    assert public_catalog.call_count == 2


def test_discovery_does_not_mix_chat_and_decisions(monkeypatch):
    from lfx.base.models import model_utils

    monkeypatch.setattr(model_utils, "get_provider_variable_value", lambda *_: "key")
    monkeypatch.setattr(
        model_utils.httpx,
        "get",
        lambda *_a, **_k: httpx.Response(
            200, json={"data": [{"id": "chat-model"}]}, request=httpx.Request("GET", "https://openrouter.ai")
        ),
    )
    groups = []
    replace_with_live_models(groups, "user", {"OpenRouter"})
    assert {(r["model_name"], r["metadata"]["model_type"]) for r in groups[0]["models"]} == {
        ("chat-model", "llm"),
        ("new-author/new-model", "decision"),
        ("~typesafe/jev-latest", "decision"),
        ("baseten/mammoth-1:free", "decision"),
    }


def test_standalone_picker_lists_all_gateway_models():
    options = get_decision_model_options(provider_policy=policy())
    assert len(options) == 3
    assert all(o["provider"] == "OpenRouter" for o in options)


def test_saved_custom_model_survives_discovery_and_honors_disabled_state(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(model_catalog, "_keeps_model_settings", lambda: True)
    monkeypatch.setattr(model_catalog, "_fetch_enabled_providers_for_user", AsyncMock(return_value={"OpenRouter"}))
    monkeypatch.setattr(
        model_catalog,
        "_get_model_status",
        AsyncMock(
            return_value=(
                {"OpenRouter::decision::new-author/new-model"},
                {"OpenRouter::decision::author/new-version:exacto"},
            )
        ),
    )
    options = get_decision_model_options("user", provider_policy=policy())
    assert "author/new-version:exacto" in {o["name"] for o in options}
    assert "new-author/new-model" not in {o["name"] for o in options}


def test_custom_injection_is_decision_only():
    groups = []
    inject_custom_enabled_models(groups, {"OpenRouter::llm::unknown-chat", "OpenRouter::decision::new-id"})
    assert [r["model_name"] for r in groups[0]["models"]] == ["new-id"]


def test_explicit_model_runs_without_catalog_and_uses_only_openrouter_key(monkeypatch, public_catalog):
    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy())
    monkeypatch.setenv("OPENROUTER_API_KEY", "own-key")
    transport = Mock(
        return_value=DecisionResult(kind="boolean", provider="OpenRouter", model="new-id", probability_true=0.7)
    )
    monkeypatch.setattr(providers, "evaluate_provider", transport)
    request = DecisionRequest(kind="boolean", context="text", question="Relevant?")
    evaluate_decision(request, model={"provider": "OpenRouter", "name": "author/new-id:exacto"})
    transport.assert_called_once_with("OpenRouter", "author/new-id:exacto", request, api_key="own-key", timeout=60)
    public_catalog.assert_not_called()


def test_explicit_model_cannot_bypass_policy(monkeypatch, public_catalog):
    from lfx.services.model_provider_policy import ModelProviderPolicyError

    monkeypatch.setattr(
        "lfx.services.model_provider_policy.resolve_model_provider_policy",
        lambda **_: policy(blocked={"openrouter::decision::new-id"}),
    )
    with pytest.raises(ModelProviderPolicyError):
        evaluate_decision(
            DecisionRequest(kind="boolean", context="text", question="Relevant?"),
            model={"provider": "OpenRouter", "name": "new-id"},
        )
    public_catalog.assert_not_called()


def test_key_validation_for_new_model_uses_auth_not_chat_or_decision(monkeypatch, public_catalog):
    import requests

    monkeypatch.setattr("lfx.services.model_provider_policy.resolve_model_provider_policy", lambda **_: policy())
    get = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr(requests, "get", get)
    credentials.validate_model_provider_key(
        "OpenRouter", {"OPENROUTER_API_KEY": "own-key"}, model_name="new-id", model_type="decision"
    )
    assert get.call_args.args[0] == "https://openrouter.ai/api/v1/auth/key"
    public_catalog.assert_not_called()
