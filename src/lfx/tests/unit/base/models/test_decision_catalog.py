from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.base.models.model_utils import replace_with_live_models
from lfx.base.models.unified_models import get_decision_model_options, get_unified_models_detailed, model_catalog
from lfx.base.models.unified_models.build_config import handle_model_input_update
from lfx.base.models.unified_models.credentials import model_status_contains, model_status_key, parse_model_status_key
from lfx.inputs.inputs import ModelInput
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
)


def policy(*, blocked=(), allowed=("typesafe", "perplexity", "openai")):
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id="user"),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"typesafe", "perplexity", "openai"}),
        allowed_provider_ids=frozenset(allowed),
        blocked_model_keys=frozenset(blocked),
    )


def test_all_mandatory_decision_models_have_capabilities():
    options = get_decision_model_options(provider_policy=policy())
    assert {(item["provider"], item["name"]) for item in options} == {
        ("TypeSafe", "jev-latest"),
        ("Perplexity", "pplx-decider-latest"),
        ("Perplexity", "pplx-decider-flash-latest"),
        ("OpenAI", "gpt-6-luna"),
    }
    assert all(item["metadata"]["capabilities"] == ["choice", "boolean", "score"] for item in options)


def test_typed_status_and_policy_isolate_decision_from_chat():
    key = model_status_key("OpenAI", "shared::name", "decision")
    assert parse_model_status_key(key) == ("OpenAI", "shared::name", "decision")
    assert model_status_contains({key}, "OpenAI", "shared::name", "decision")
    assert not model_status_contains({key}, "OpenAI", "shared::name", "llm")
    snapshot = policy(blocked={"openai::decision::shared::name"})
    assert not snapshot.allows_model("OpenAI", "shared::name", model_type="decision")
    assert snapshot.allows_model("OpenAI", "shared::name", model_type="llm")
    assert not snapshot.allows_model("OpenAI", "shared::name")


@pytest.fixture
def saved_settings(monkeypatch):
    """A Langflow backend, which keeps Model Providers settings; standalone lfx keeps none."""
    monkeypatch.setattr(model_catalog, "_keeps_model_settings", lambda: True)


@pytest.mark.usefixtures("saved_settings")
def test_decision_options_apply_enabled_typed_status_and_policy(monkeypatch):
    monkeypatch.setattr(
        model_catalog, "_get_model_status", AsyncMock(return_value=({"OpenAI::decision::gpt-6-luna"}, set()))
    )
    monkeypatch.setattr(
        model_catalog, "_fetch_enabled_providers_for_user", AsyncMock(return_value={"OpenAI", "TypeSafe"})
    )
    options = get_decision_model_options("user", provider_policy=policy())
    assert [(item["provider"], item["name"]) for item in options] == [("TypeSafe", "jev-latest")]
    assert get_decision_model_options("user", provider_policy=policy(allowed=())) == []


@pytest.mark.usefixtures("saved_settings")
def test_configuration_read_failure_is_not_catalog_allow_all(monkeypatch):
    monkeypatch.setattr(model_catalog, "_get_model_status", AsyncMock(side_effect=RuntimeError("database unavailable")))
    with pytest.raises(RuntimeError, match="database unavailable"):
        get_decision_model_options("user", provider_policy=policy())


@pytest.mark.usefixtures("saved_settings")
def test_unconfigured_provider_is_not_available(monkeypatch):
    monkeypatch.setattr(model_catalog, "_get_model_status", AsyncMock(return_value=(set(), set())))
    monkeypatch.setattr(model_catalog, "_fetch_enabled_providers_for_user", AsyncMock(return_value=set()))
    assert get_decision_model_options("user", provider_policy=policy()) == []


def test_live_chat_discovery_does_not_erase_decision_catalog(monkeypatch):
    monkeypatch.setattr(
        "lfx.base.models.model_utils.get_live_models_for_provider",
        lambda *_: [{"name": "live-chat", "model_type": "llm"}],
    )
    groups = get_unified_models_detailed(providers=["OpenAI"])
    replace_with_live_models(groups, "user", {"OpenAI"})
    assert any(row["metadata"]["model_type"] == "decision" for row in groups[0]["models"])


def test_decision_model_input_has_no_connection_handle_or_implicit_default(monkeypatch):
    from lfx.base.models import unified_models

    decision_input = ModelInput(name="decision_model", model_type="decision")
    assert decision_input.input_types == []
    assert decision_input.external_options == {}
    monkeypatch.setattr(
        unified_models, "get_decision_model_options", lambda **_: [{"name": "jev-latest", "provider": "TypeSafe"}]
    )
    component = SimpleNamespace(inputs=[decision_input], user_id=None)
    config = {"decision_model": {"value": None}}
    handle_model_input_update(component, config, None, model_field_name="decision_model")
    assert config["decision_model"]["value"] is None
    assert config["decision_model"]["input_types"] == []
    with pytest.raises(ValueError, match="connection handles"):
        ModelInput(name="decision_model", model_type="decision", value="connect_other_models")


@pytest.mark.usefixtures("saved_settings")
def test_component_credentials_still_honor_model_disable(monkeypatch):
    monkeypatch.setattr(
        model_catalog, "_get_model_status", AsyncMock(return_value=({"OpenAI::decision::gpt-6-luna"}, set()))
    )
    configured = AsyncMock(side_effect=AssertionError("runtime must not require a saved API key"))
    monkeypatch.setattr(model_catalog, "_fetch_enabled_providers_for_user", configured)
    options = get_decision_model_options("user", provider_policy=policy(), require_configured=False)
    assert all(item["provider"] != "OpenAI" for item in options)
    assert {item["provider"] for item in options} == {"TypeSafe", "Perplexity"}
    configured.assert_not_called()


def test_decision_build_config_honors_provider_specific_options():
    decision_input = ModelInput(name="decision_model", model_type="decision")
    component = SimpleNamespace(inputs=[decision_input], user_id=None)
    config = {"decision_model": {"value": None}}
    options = [{"name": "jev-latest", "provider": "TypeSafe"}]
    handle_model_input_update(
        component, config, None, model_field_name="decision_model", get_options_func=lambda **_: options
    )
    assert config["decision_model"]["options"] == options


async def test_standalone_lfx_represented_user_needs_no_backend_preferences(monkeypatch):
    import builtins

    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    original_import = builtins.__import__

    def without_backend(name, *args, **kwargs):
        if name == "langflow" or name.startswith("langflow."):
            msg = "Standalone LFX must not import langflow"
            raise AssertionError(msg)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(credentials, "get_variable_service", VariableService)
    monkeypatch.setattr(builtins, "__import__", without_backend)
    assert await credentials._get_model_status("represented-caller", strict=True) == (set(), set())


def test_lfx_run_generated_user_has_no_saved_settings_to_read(monkeypatch):
    """`lfx run` stamps a random user id and registers no variable service; decisions must still resolve."""
    from uuid import uuid4

    from lfx.base.models.unified_models import credentials

    monkeypatch.setattr(credentials, "get_variable_service", lambda: None)
    options = get_decision_model_options(user_id=uuid4().hex, provider_policy=policy(), require_configured=False)
    assert ("TypeSafe", "jev-latest") in {(item["provider"], item["name"]) for item in options}


def test_models_dev_chat_override_preserves_same_named_decision_capabilities():
    from lfx.base.models.decision_constants import DECISION_MODELS_DETAILED
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    static = [[{"provider": "OpenAI", "name": "gpt-6-luna", "model_type": "llm"}], DECISION_MODELS_DETAILED]
    result = apply_models_dev_overrides(
        static, {"openai": {"models": {"gpt-6-luna": {"id": "gpt-6-luna", "name": "Luna"}}}}
    )
    rows = [row for group in result for row in group]
    assert [row for row in rows if row.get("model_type") == "decision"] == DECISION_MODELS_DETAILED
    assert len([row for row in rows if row["name"] == "gpt-6-luna" and row["model_type"] == "llm"]) == 1


def test_placeholder_user_id_is_standalone_not_a_user(monkeypatch):
    """A component outside a graph reports user_id "None"; that must not trigger a saved-settings read."""

    async def no_saved_settings(*_args, **_kwargs):
        msg = "standalone lookup must not read saved model settings"
        raise AssertionError(msg)

    monkeypatch.setattr(model_catalog, "_get_model_status", no_saved_settings)
    options = get_decision_model_options(user_id="None", provider_policy=policy())
    assert ("TypeSafe", "jev-latest") in {(item["provider"], item["name"]) for item in options}


def test_untyped_validation_of_a_decision_only_model_sends_a_decision(monkeypatch):
    """A legacy untyped enable of gpt-6-luna must not be validated as a chat completion."""
    from unittest.mock import Mock

    from lfx.base.models.decisions import providers
    from lfx.base.models.unified_models import credentials

    decision = Mock()
    monkeypatch.setattr(providers, "validate_decision_provider_key", decision)
    variables = {"OPENAI_API_KEY": "tenant-key"}  # pragma: allowlist secret
    credentials.validate_model_provider_key("OpenAI", variables, "gpt-6-luna")
    decision.assert_called_once_with("OpenAI", variables, "gpt-6-luna")


@pytest.mark.parametrize("service", [None, "env"], ids=["lfx run", "lfx serve"])
def test_standalone_lfx_offers_every_catalog_decision_model(monkeypatch, service):
    """The lfx run and serve commands generate a user id but keep no Model Providers settings to read."""
    from lfx.base.models.unified_models import credentials
    from lfx.services.variable.service import VariableService

    monkeypatch.setattr(credentials, "get_variable_service", lambda: VariableService() if service else None)
    options = get_decision_model_options(user_id="00000000-0000-0000-0000-000000000001", provider_policy=policy())
    assert {("TypeSafe", "jev-latest"), ("OpenAI", "gpt-6-luna")} <= {(o["provider"], o["name"]) for o in options}
