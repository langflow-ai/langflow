from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.v1 import models as models_api
from langflow.api.v1.models import (
    ModelStatusUpdate,
    _build_model_default_flags,
    _update_model_sets,
    build_model_providers_by_name,
    normalize_model_status_entries,
)
from langflow.api.v1.variable import _cleanup_model_list_variable
from lfx.base.models.model_utils import inject_custom_enabled_models
from lfx.base.models.unified_models.credentials import model_status_contains, model_status_key

pytestmark = pytest.mark.no_blockbuster


CATALOG_WITH_SHARED_ALIAS = [
    {
        "provider": "OpenAI",
        "models": [{"model_name": "gpt-4o-mini", "metadata": {"default": False}}],
    },
    {
        "provider": "Azure AI Foundry",
        "models": [{"model_name": "gpt-4o-mini", "metadata": {"default": True}}],
    },
]


def test_model_defaults_and_updates_are_provider_qualified():
    default_flags = _build_model_default_flags(CATALOG_WITH_SHARED_ALIAS)
    providers_by_name = build_model_providers_by_name(CATALOG_WITH_SHARED_ALIAS)

    assert default_flags == {
        "OpenAI::gpt-4o-mini": False,
        "OpenAI::llm::gpt-4o-mini": False,
        "Azure AI Foundry::gpt-4o-mini": True,
        "Azure AI Foundry::llm::gpt-4o-mini": True,
    }

    # A pre-upgrade bare entry applied to both providers. On the next write it
    # is expanded before changing only the provider the user toggled.
    disabled_models = normalize_model_status_entries({"gpt-4o-mini"}, providers_by_name)
    explicitly_enabled_models: set[str] = set()
    _update_model_sets(
        [ModelStatusUpdate(provider="OpenAI", model_id="gpt-4o-mini", enabled=True)],
        disabled_models,
        explicitly_enabled_models,
        default_flags,
    )

    assert disabled_models == {"Azure AI Foundry::gpt-4o-mini"}
    assert explicitly_enabled_models == {"OpenAI::gpt-4o-mini"}


def test_foundry_seed_default_stays_explicitly_enabled():
    disabled_models = {"Azure AI Foundry::gpt-4o-mini"}
    explicitly_enabled_models: set[str] = set()

    _update_model_sets(
        [ModelStatusUpdate(provider="Azure AI Foundry", model_id="gpt-4o-mini", enabled=True)],
        disabled_models,
        explicitly_enabled_models,
        {"Azure AI Foundry::gpt-4o-mini": True},
    )

    assert disabled_models == set()
    assert explicitly_enabled_models == {"Azure AI Foundry::gpt-4o-mini"}


def test_typed_default_flags_do_not_cross_model_types():
    provider = "OpenAI"
    model_name = "shared-name"
    flags = _build_model_default_flags(
        [
            {
                "provider": provider,
                "models": [
                    {
                        "model_name": model_name,
                        "metadata": {"default": True, "model_type": "llm"},
                    },
                    {
                        "model_name": model_name,
                        "metadata": {"default": False, "model_type": "embeddings"},
                    },
                ],
            }
        ]
    )

    assert flags[model_status_key(provider, model_name)] is True
    assert flags[model_status_key(provider, model_name, model_type="llm")] is True
    assert flags[model_status_key(provider, model_name, model_type="embeddings")] is False

    llm_enabled: set[str] = set()
    _update_model_sets(
        [ModelStatusUpdate(provider=provider, model_id=model_name, enabled=True, model_type="llm")],
        set(),
        llm_enabled,
        flags,
    )
    embedding_enabled: set[str] = set()
    _update_model_sets(
        [ModelStatusUpdate(provider=provider, model_id=model_name, enabled=True, model_type="embeddings")],
        set(),
        embedding_enabled,
        flags,
    )

    assert llm_enabled == set()
    assert embedding_enabled == {model_status_key(provider, model_name, model_type="embeddings")}


def test_typed_model_statuses_are_independent():
    llm_update = ModelStatusUpdate(
        provider="Azure AI Foundry",
        model_id="portal-deploy",
        enabled=True,
        model_type="llm",
    )
    embedding_update = ModelStatusUpdate(
        provider="Azure AI Foundry",
        model_id="portal-deploy",
        enabled=True,
        model_type="embeddings",
    )
    llm_status = model_status_key("Azure AI Foundry", "portal-deploy", model_type="llm")
    embedding_status = model_status_key("Azure AI Foundry", "portal-deploy", model_type="embeddings")

    assert llm_update.model_type == "llm"
    assert embedding_update.model_type == "embeddings"
    assert llm_status != embedding_status

    llm_enabled: set[str] = set()
    _update_model_sets(
        [llm_update],
        set(),
        llm_enabled,
        {"Azure AI Foundry::portal-deploy": False},
    )
    embedding_enabled: set[str] = set()
    _update_model_sets(
        [embedding_update],
        set(),
        embedding_enabled,
        {"Azure AI Foundry::portal-deploy": False},
    )

    assert llm_enabled == {llm_status}
    assert embedding_enabled == {embedding_status}
    assert model_status_contains(
        {llm_status},
        "Azure AI Foundry",
        "portal-deploy",
        model_type="llm",
    )
    assert not model_status_contains(
        {llm_status},
        "Azure AI Foundry",
        "portal-deploy",
        model_type="embeddings",
    )
    assert model_status_contains(
        {embedding_status},
        "Azure AI Foundry",
        "portal-deploy",
        model_type="embeddings",
    )
    assert not model_status_contains(
        {embedding_status},
        "Azure AI Foundry",
        "portal-deploy",
        model_type="llm",
    )


@pytest.mark.parametrize(
    ("update_enabled", "initial_disabled", "initial_enabled", "expected_disabled", "expected_enabled"),
    [
        (
            False,
            set(),
            {"Azure AI Foundry::shared-deploy"},
            {"Azure AI Foundry::llm::shared-deploy"},
            {"Azure AI Foundry::embeddings::shared-deploy"},
        ),
        (
            True,
            {"Azure AI Foundry::shared-deploy"},
            set(),
            {"Azure AI Foundry::embeddings::shared-deploy"},
            {"Azure AI Foundry::llm::shared-deploy"},
        ),
    ],
)
def test_typed_update_migrates_matching_legacy_state(
    update_enabled,
    initial_disabled,
    initial_enabled,
    expected_disabled,
    expected_enabled,
):
    identity = "Azure AI Foundry::shared-deploy"

    _update_model_sets(
        [
            ModelStatusUpdate(
                provider="Azure AI Foundry",
                model_id="shared-deploy",
                enabled=update_enabled,
                model_type="llm",
            )
        ],
        initial_disabled,
        initial_enabled,
        {identity: False},
        model_types_by_identity={identity: {"llm", "embeddings"}},
    )

    assert initial_disabled == expected_disabled
    assert initial_enabled == expected_enabled


async def test_get_enabled_models_returns_type_map_and_flat_union(monkeypatch):
    provider = "Azure AI Foundry"
    shared_name = "shared-deploy"
    catalog = [
        {
            "provider": provider,
            "models": [
                {
                    "model_name": shared_name,
                    "metadata": {"default": False, "model_type": "llm"},
                },
                {
                    "model_name": shared_name,
                    "metadata": {"default": False, "model_type": "embeddings"},
                },
                {
                    "model_name": "filtered-out",
                    "metadata": {"default": False, "model_type": "llm"},
                },
            ],
        }
    ]

    monkeypatch.setattr(models_api, "get_unified_models_detailed", lambda **_kwargs: catalog)
    monkeypatch.setattr(
        models_api,
        "_get_enabled_providers_result",
        AsyncMock(return_value={"provider_status": {provider: True}}),
    )
    monkeypatch.setattr(
        models_api, "_get_disabled_models", AsyncMock(return_value={f"{provider}::embeddings::{shared_name}"})
    )
    monkeypatch.setattr(models_api, "_get_enabled_models", AsyncMock(return_value={f"{provider}::llm::{shared_name}"}))
    monkeypatch.setattr(models_api, "replace_with_live_models", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(models_api, "inject_custom_enabled_models", lambda *_args, **_kwargs: None)

    result = await models_api.get_enabled_models(
        session=SimpleNamespace(),
        current_user=SimpleNamespace(id=uuid4()),
        provider_policy_attributes={"is_superuser": False},
        model_names=[shared_name],
    )

    assert result["enabled_models"] == {provider: {shared_name: True}}
    assert result["enabled_models_by_type"] == {
        provider: {
            "llm": {shared_name: True},
            "embeddings": {shared_name: False},
        }
    }


def test_inject_custom_enabled_models_appends_missing_deployments():
    provider_models = [
        {
            "provider": "Azure AI Foundry",
            "models": [
                {
                    "model_name": "gpt-4o",
                    "metadata": {"default": True, "model_type": "llm"},
                }
            ],
            "num_models": 1,
        }
    ]

    inject_custom_enabled_models(
        provider_models,
        {"Azure AI Foundry::gpt-5-mini", "Azure AI Foundry::gpt-4o", "OpenAI::ignored"},
        model_type="llm",
    )

    names = [model["model_name"] for model in provider_models[0]["models"]]
    assert names == ["gpt-4o", "gpt-5-mini"]
    assert provider_models[0]["num_models"] == 2
    custom = provider_models[0]["models"][1]
    assert custom["metadata"]["model_type"] == "llm"
    assert custom["metadata"]["tool_calling"] is True


def test_inject_custom_enabled_models_respects_filters_and_stable_order():
    provider_models = [
        {
            "provider": "Azure AI Foundry",
            "models": [],
            "num_models": 0,
        }
    ]
    enabled = {
        "Azure AI Foundry::zeta-deploy",
        "Azure AI Foundry::alpha-deploy",
        "Azure AI Foundry::beta-deploy",
    }

    inject_custom_enabled_models(
        provider_models,
        enabled,
        model_type="llm",
        metadata_filters={"tool_calling": True},
    )
    names = [model["model_name"] for model in provider_models[0]["models"]]
    assert names == ["alpha-deploy", "beta-deploy", "zeta-deploy"]

    # model_name filter keeps a single match
    provider_models[0]["models"] = []
    inject_custom_enabled_models(
        provider_models,
        enabled,
        model_name="beta-deploy",
        model_type="llm",
    )
    assert [m["model_name"] for m in provider_models[0]["models"]] == ["beta-deploy"]

    # embeddings type + tool_calling=True must not inject (custom embeddings are not tools)
    provider_models[0]["models"] = []
    inject_custom_enabled_models(
        provider_models,
        enabled,
        model_type="embeddings",
        metadata_filters={"tool_calling": True},
    )
    assert provider_models[0]["models"] == []

    provider_models[0]["models"] = []
    inject_custom_enabled_models(
        provider_models,
        {model_status_key("Azure AI Foundry", "text-embed", model_type="embeddings")},
        model_type="embeddings",
    )
    custom = provider_models[0]["models"][0]
    assert custom["model_name"] == "text-embed"
    assert custom["metadata"]["model_type"] == "embeddings"
    assert custom["metadata"]["tool_calling"] is False


def test_inject_custom_enabled_models_creates_provider_stub_for_embeddings():
    """Foundry has no seed embeddings; inject must still create a provider row."""
    provider_models: list[dict] = []
    inject_custom_enabled_models(
        provider_models,
        {model_status_key("Azure AI Foundry", "my-embed-deploy", model_type="embeddings")},
        model_type="embeddings",
    )

    assert len(provider_models) == 1
    assert provider_models[0]["provider"] == "Azure AI Foundry"
    models = provider_models[0]["models"]
    assert len(models) == 1
    assert models[0]["model_name"] == "my-embed-deploy"
    assert models[0]["metadata"]["model_type"] == "embeddings"


def test_inject_custom_enabled_models_uses_persisted_type():
    provider_models = [
        {
            "provider": "Azure AI Foundry",
            "models": [],
            "num_models": 0,
        }
    ]
    inject_custom_enabled_models(
        provider_models,
        {
            model_status_key("Azure AI Foundry", "team-chat", model_type="llm"),
            model_status_key("Azure AI Foundry", "vector-prod", model_type="embeddings"),
        },
    )

    models = provider_models[0]["models"]
    assert {(model["model_name"], model["metadata"]["model_type"]) for model in models} == {
        ("team-chat", "llm"),
        ("vector-prod", "embeddings"),
    }


def test_inject_legacy_custom_enabled_model_defaults_to_llm():
    provider_models = [
        {
            "provider": "Azure AI Foundry",
            "models": [],
            "num_models": 0,
        }
    ]

    inject_custom_enabled_models(
        provider_models,
        {"Azure AI Foundry::legacy-deploy"},
    )

    models = provider_models[0]["models"]
    assert [(model["model_name"], model["metadata"]["model_type"]) for model in models] == [("legacy-deploy", "llm")]


def test_inject_custom_enabled_models_does_not_synthesize_non_custom_provider():
    provider_models = [
        {
            "provider": "OpenAI",
            "models": [],
            "num_models": 0,
        }
    ]

    inject_custom_enabled_models(
        provider_models,
        {"OpenAI::gpt-5-chat-latest"},
        model_type="llm",
        metadata_filters={"tool_calling": True},
    )

    assert provider_models[0]["models"] == []


async def test_provider_cleanup_migrates_legacy_entries_before_removing_target_provider():
    variable_id = uuid4()
    variable_service = SimpleNamespace(
        get_variable_object=AsyncMock(
            return_value=SimpleNamespace(
                id=variable_id,
                value=json.dumps(
                    [
                        "gpt-4o-mini",
                        "OpenAI::custom-deployment",
                        "Azure AI Foundry::gpt-4o-mini",
                        "Anthropic::claude-3-5-sonnet-latest",
                        "unknown-legacy-model",
                    ]
                ),
            )
        ),
        update_variable_fields=AsyncMock(),
        delete_variable=AsyncMock(),
    )
    providers_by_name = build_model_providers_by_name(CATALOG_WITH_SHARED_ALIAS)

    await _cleanup_model_list_variable(
        variable_service,
        uuid4(),
        "__disabled_models__",
        "OpenAI",
        providers_by_name,
        session=SimpleNamespace(),
    )

    variable_service.delete_variable.assert_not_awaited()
    update = variable_service.update_variable_fields.await_args.kwargs["variable"]
    assert set(json.loads(update.value)) == {
        "Azure AI Foundry::gpt-4o-mini",
        "Anthropic::claude-3-5-sonnet-latest",
        "unknown-legacy-model",
    }


async def test_provider_cleanup_ignores_non_string_model_entries():
    variable_id = uuid4()
    variable_service = SimpleNamespace(
        get_variable_object=AsyncMock(
            return_value=SimpleNamespace(
                id=variable_id,
                value=json.dumps(
                    [
                        "OpenAI::custom-deployment",
                        7,
                        "Anthropic::claude-3-5-sonnet-latest",
                    ]
                ),
            )
        ),
        update_variable_fields=AsyncMock(),
        delete_variable=AsyncMock(),
    )

    await _cleanup_model_list_variable(
        variable_service,
        uuid4(),
        "__disabled_models__",
        "OpenAI",
        build_model_providers_by_name(CATALOG_WITH_SHARED_ALIAS),
        session=SimpleNamespace(),
    )

    variable_service.delete_variable.assert_not_awaited()
    update = variable_service.update_variable_fields.await_args.kwargs["variable"]
    assert json.loads(update.value) == ["Anthropic::claude-3-5-sonnet-latest"]


def test_decision_enablement_does_not_enable_same_named_chat():
    rows = [
        {
            "provider": "OpenAI",
            "models": [
                {"model_name": "shared", "metadata": {"model_type": "llm", "default": True}},
                {"model_name": "shared", "metadata": {"model_type": "decision", "default": False}},
            ],
        }
    ]
    flags = _build_model_default_flags(rows)
    disabled = {"OpenAI::shared"}
    enabled = set()
    _update_model_sets(
        [ModelStatusUpdate(provider="OpenAI", model_id="shared", model_type="decision", enabled=True)],
        disabled,
        enabled,
        flags,
        models_api._build_model_types_by_identity(rows),
    )
    assert disabled == {"OpenAI::llm::shared"}
    assert enabled == {"OpenAI::decision::shared"}


async def test_decision_validation_request_uses_decision_endpoint(monkeypatch):
    from unittest.mock import Mock

    from lfx.base.models import unified_models

    monkeypatch.setattr(models_api, "_require_provider", AsyncMock())
    validate = Mock()
    monkeypatch.setattr(unified_models, "validate_model_provider_key", validate)
    user = SimpleNamespace(id=uuid4())
    result = await models_api.validate_provider(
        models_api.ValidateProviderRequest(
            provider="OpenAI",
            variables={"OPENAI_API_KEY": "test-value"},
            model_type="decision",
            model_name="gpt-6-luna",
        ),
        current_user=user,
        provider_policy_attributes={},
    )
    assert result.valid
    validate.assert_called_once_with(
        "OpenAI",
        {"OPENAI_API_KEY": "test-value"},
        "gpt-6-luna",
        model_type="decision",
        user_id=user.id,
        policy_attributes={},
    )


@pytest.mark.parametrize(
    ("provider", "model_type", "model_name", "effective_model"),
    [
        ("OpenAI", "decision", "gpt-6-luna", "gpt-6-luna"),
        ("TypeSafe", None, None, "jev-latest"),
        ("Perplexity", None, None, "pplx-decider-latest"),
    ],
)
async def test_decision_credential_validation_never_invokes_denied_model(
    monkeypatch, provider, model_type, model_name, effective_model
):
    from unittest.mock import Mock

    from fastapi import HTTPException
    from lfx.base.models.decisions import providers
    from lfx.services import model_provider_policy
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicyPurpose,
        ModelProviderPolicySnapshot,
    )

    provider_id = provider.lower()
    policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id="caller"),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({provider_id}),
        allowed_provider_ids=frozenset({provider_id}),
        blocked_model_keys=frozenset({f"{provider_id}::decision::{effective_model}"}),
    )
    monkeypatch.setattr(models_api, "_require_provider", AsyncMock())
    resolver = Mock(return_value=policy)
    monkeypatch.setattr(model_provider_policy, "resolve_model_provider_policy", resolver)
    validate = Mock()
    monkeypatch.setattr(providers, "validate_decision_provider_key", validate)
    user = SimpleNamespace(id=uuid4())
    with pytest.raises(HTTPException) as error:
        await models_api.validate_provider(
            models_api.ValidateProviderRequest(
                provider=provider, variables={}, model_type=model_type, model_name=model_name
            ),
            current_user=user,
            provider_policy_attributes={"workspace_id": "workspace"},
        )
    assert error.value.status_code == 404
    validate.assert_not_called()
    assert resolver.call_args.kwargs["user_id"] == user.id
    assert resolver.call_args.kwargs["attributes"] == {"workspace_id": "workspace"}


async def test_narrowing_read_purpose_preserves_both_typed_model_denials(monkeypatch):
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicyPurpose,
        ModelProviderPolicySnapshot,
    )

    def snapshot(purpose, model):
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id="caller"),
            purpose=purpose,
            candidate_provider_ids=frozenset({"openai"}),
            allowed_provider_ids=frozenset({"openai"}),
            blocked_model_keys=frozenset({f"openai::decision::{model}"}),
        )

    monkeypatch.setattr(
        models_api,
        "_aresolve_policy_for_providers",
        AsyncMock(
            side_effect=[
                snapshot(ModelProviderPolicyPurpose.DISCOVER, "gpt-6-luna"),
                snapshot(ModelProviderPolicyPurpose.USE, "other-judge"),
            ]
        ),
    )
    policy = await models_api._aresolve_read_policy(
        SimpleNamespace(id=uuid4()),
        "use",
        default=ModelProviderPolicyPurpose.DISCOVER,
        attributes={},
        providers=["OpenAI"],
    )
    assert not policy.allows_model("OpenAI", "gpt-6-luna", model_type="decision")
    assert not policy.allows_model("OpenAI", "other-judge", model_type="decision")
    assert policy.allows_model("OpenAI", "gpt-6-luna", model_type="llm")


async def test_enable_decision_uses_typed_validation_despite_same_named_deprecated_chat(monkeypatch):
    from unittest.mock import MagicMock, Mock

    from lfx.base.models import unified_models
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicyPurpose,
        ModelProviderPolicySnapshot,
    )

    user = SimpleNamespace(id=uuid4())
    service = MagicMock(spec=models_api.DatabaseVariableService)
    policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id=user.id),
        purpose=ModelProviderPolicyPurpose.CONFIGURE,
        candidate_provider_ids=frozenset({"openai"}),
        allowed_provider_ids=frozenset({"openai"}),
    )
    monkeypatch.setattr(models_api, "ensure_variable_permission", AsyncMock())
    monkeypatch.setattr(models_api, "get_variable_service", lambda: service)
    monkeypatch.setattr(models_api, "_aresolve_policy", AsyncMock(return_value=policy))
    monkeypatch.setattr(models_api, "_get_disabled_models", AsyncMock(return_value=set()))
    monkeypatch.setattr(models_api, "_get_enabled_models", AsyncMock(return_value=set()))
    monkeypatch.setattr(models_api, "_save_model_list_variable", AsyncMock())
    monkeypatch.setattr(
        models_api,
        "get_unified_models_detailed",
        lambda **_: [
            {
                "provider": "OpenAI",
                "models": [
                    {"model_name": "shared", "metadata": {"model_type": "llm", "deprecated": True}},
                    {"model_name": "shared", "metadata": {"model_type": "decision"}},
                ],
            }
        ],
    )
    monkeypatch.setattr(unified_models, "get_all_variables_for_provider", lambda *_: {})
    validate = Mock()
    monkeypatch.setattr(unified_models, "validate_model_provider_key", validate)
    result = await models_api.update_enabled_models(
        session=object(),
        current_user=user,
        provider_policy_attributes={},
        updates=[ModelStatusUpdate(provider="OpenAI", model_id="shared", model_type="decision", enabled=True)],
    )
    validate.assert_called_once_with(
        "OpenAI", {}, model_name="shared", model_type="decision", user_id=user.id, policy_attributes={}
    )
    assert result["enabled_models"] == ["OpenAI::decision::shared"]


@pytest.mark.parametrize("denied", [False, True])
@pytest.mark.parametrize("operation", ["create", "update"])
async def test_openai_decision_credential_save_checks_model_policy_before_persistence(monkeypatch, denied, operation):
    from unittest.mock import MagicMock, Mock

    from fastapi import HTTPException
    from langflow.api.v1 import variable as variable_api
    from lfx.base.models.decisions import providers
    from lfx.services import model_provider_policy
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicyPurpose,
        ModelProviderPolicySnapshot,
    )

    user = SimpleNamespace(id=uuid4())
    variable = variable_api.VariableCreate(name="OPENAI_API_KEY", value="test-value", default_fields=[])
    stored = variable_api.Variable(name=variable.name, value=variable.value, default_fields=[], user_id=user.id)
    service = MagicMock(spec=variable_api.DatabaseVariableService)
    service.list_variables = AsyncMock(return_value=[])
    service.create_variable = AsyncMock(return_value=stored)
    service.update_variable_fields = AsyncMock(return_value=stored)
    monkeypatch.setattr(variable_api, "authorized_or_owner_scoped", AsyncMock(return_value=stored))
    monkeypatch.setattr(variable_api, "get_variable_service", lambda: service)
    monkeypatch.setattr(variable_api, "ensure_variable_permission", AsyncMock())
    monkeypatch.setattr(variable_api, "_require_provider", AsyncMock())
    monkeypatch.setattr(variable_api, "get_all_variables_for_provider", lambda *_: {})
    policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id=user.id),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"openai"}),
        allowed_provider_ids=frozenset({"openai"}),
        blocked_model_keys=frozenset({"openai::decision::gpt-6-luna"}) if denied else frozenset(),
    )
    resolver = Mock(return_value=policy)
    monkeypatch.setattr(model_provider_policy, "resolve_model_provider_policy", resolver)
    validate = Mock()
    monkeypatch.setattr(providers, "validate_decision_provider_key", validate)
    args = {
        "session": object(),
        "variable": variable,
        "current_user": user,
        "provider_policy_attributes": {"workspace_id": "workspace"},
        "validation_model_type": "decision",
    }
    save = variable_api.create_variable
    persistence = service.create_variable
    if operation == "update":
        args["variable"] = variable_api.VariableUpdate(id=stored.id, value="test-value")
        args["variable_id"] = stored.id
        save = variable_api.update_variable
        persistence = service.update_variable_fields
    if denied:
        with pytest.raises(HTTPException) as error:
            await save(**args)
        assert error.value.status_code == 404
        persistence.assert_not_called()
        validate.assert_not_called()
    else:
        result = await save(**args)
        assert result.id == stored.id
        validate.assert_called_once_with("OpenAI", {"OPENAI_API_KEY": "test-value"}, "gpt-6-luna")
        persistence.assert_awaited_once()
    assert resolver.call_args.kwargs["user_id"] == user.id
    assert resolver.call_args.kwargs["attributes"] == {"workspace_id": "workspace"}


DECISION_CATALOG = {
    ("TypeSafe", "jev-latest"),
    ("Perplexity", "pplx-decider-latest"),
    ("Perplexity", "pplx-decider-flash-latest"),
    ("OpenAI", "gpt-6-luna"),
}


def _decision_rows(response):
    return {
        (provider["provider"], model["model_name"]): model["metadata"]
        for provider in response.json()
        for model in provider["models"]
    }


@pytest.mark.usefixtures("active_user")
async def test_list_decision_models_returns_only_typed_decision_rows(client, logged_in_headers):
    response = await client.get("api/v1/models", params={"model_type": "decision"}, headers=logged_in_headers)
    assert response.status_code == 200
    rows = _decision_rows(response)
    assert set(rows) == DECISION_CATALOG
    assert all(meta["model_type"] == "decision" for meta in rows.values())
    assert all(meta["capabilities"] == ["choice", "boolean", "score"] for meta in rows.values())


@pytest.mark.usefixtures("active_user")
@pytest.mark.parametrize("params", [{"model_type": "decision"}, {}])
async def test_list_decision_models_hides_policy_denied_model(client, logged_in_headers, monkeypatch, params):
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicyPurpose,
        ModelProviderPolicySnapshot,
    )

    providers = frozenset({"openai", "typesafe", "perplexity"})
    snapshot = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id="caller"),
        purpose=ModelProviderPolicyPurpose.DISCOVER,
        candidate_provider_ids=providers,
        allowed_provider_ids=providers,
        blocked_model_keys=frozenset({"openai::decision::gpt-6-luna"}),
    )
    monkeypatch.setattr(models_api, "_aresolve_read_policy", AsyncMock(return_value=snapshot))
    response = await client.get("api/v1/models", params=params, headers=logged_in_headers)
    assert response.status_code == 200
    rows = {
        (provider["provider"], model["model_name"], model["metadata"].get("model_type"))
        for provider in response.json()
        for model in provider["models"]
    }
    assert {(p, m) for p, m, kind in rows if kind == "decision"} == DECISION_CATALOG - {("OpenAI", "gpt-6-luna")}
    if not params:
        # Only decision rows are filtered; OpenAI's chat models stay listed.
        assert any(provider == "OpenAI" and kind == "llm" for provider, _, kind in rows)


@pytest.mark.parametrize(("validation_model_type", "validated"), [(None, False), ("decision", True)])
async def test_perplexity_key_save_runs_a_decision_check_only_when_asked(monkeypatch, validation_model_type, validated):
    """The Perplexity chat bundle shares PERPLEXITY_API_KEY; its keys may lack Decisions access."""
    from unittest.mock import MagicMock, Mock

    from langflow.api.v1 import variable as variable_api

    user = SimpleNamespace(id=uuid4())
    variable = variable_api.VariableCreate(name="PERPLEXITY_API_KEY", value="test-value", default_fields=[])
    stored = variable_api.Variable(name=variable.name, value=variable.value, default_fields=[], user_id=user.id)
    service = MagicMock(spec=variable_api.DatabaseVariableService)
    service.list_variables = AsyncMock(return_value=[])
    service.create_variable = AsyncMock(return_value=stored)
    monkeypatch.setattr(variable_api, "get_variable_service", lambda: service)
    monkeypatch.setattr(variable_api, "ensure_variable_permission", AsyncMock())
    monkeypatch.setattr(variable_api, "_require_provider", AsyncMock())
    monkeypatch.setattr(variable_api, "get_all_variables_for_provider", lambda *_: {})
    validate = Mock()
    monkeypatch.setattr(variable_api, "validate_model_provider_key", validate)
    result = await variable_api.create_variable(
        session=object(),
        variable=variable,
        current_user=user,
        provider_policy_attributes={},
        validation_model_type=validation_model_type,
    )
    assert result.id == stored.id
    assert validate.called is validated
    service.create_variable.assert_awaited_once()
