"""Unit tests for the bundle model-provider registry.

Covers:
  - register_provider merges a provider into the core tables in place and is
    visible through every existing accessor (get_model_providers,
    get_model_provider_metadata, the @lru_cache-d variable map).
  - Core providers win on name collision; duplicate bundle registration is a
    no-op.
  - api-key-optional, live-discovery, and credential-validation dispatch route
    to the registered provider.
  - Embedding wiring lands in the class/param tables.
  - clear() restores the byte-identical baseline (zero-bundle behavior).
  - Invalid specs raise.
"""

from __future__ import annotations

import pytest
from lfx.base.models import provider_registry
from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA
from lfx.base.models.model_utils import get_live_models_for_provider
from lfx.base.models.provider_registry import ProviderSpec, register_provider
from lfx.base.models.unified_models import (
    get_live_only_providers,
    get_model_provider_metadata,
    get_model_provider_variable_mapping,
    get_model_providers,
    get_models_detailed,
    validate_model_provider_key,
)
from lfx.base.models.unified_models.class_registry import (
    EMBEDDING_PARAM_MAPPINGS,
    EMBEDDING_PROVIDER_CLASS_MAPPING,
)

# ---------------------------------------------------------------------------
# Importable callables referenced by ProviderSpec dotted paths. Resolved via
# importlib against this module's name -- robust because the running test module
# is already in sys.modules, so import_module returns it from cache.
# ---------------------------------------------------------------------------

_validator_calls: list[tuple] = []


def fake_live_discovery(user_id, model_type):  # noqa: ARG001
    return [{"provider": "FakeCo", "name": f"fake-{model_type}", "icon": "FakeCo"}]


def fake_validator(provider, variables, model_name):
    _validator_calls.append((provider, dict(variables), model_name))
    if variables.get("FAKECO_API_KEY") == "bad":  # pragma: allowlist secret
        msg = "FakeCo credentials rejected"
        raise ValueError(msg)


_LIVE_DISCOVERY_PATH = f"{__name__}:fake_live_discovery"
_VALIDATOR_PATH = f"{__name__}:fake_validator"


def fake_catalog_loader():
    """Return rows whose provider ownership must be stamped by the registry."""
    return [
        {
            "provider": "Untrusted manifest value",
            "name": "fake-chat-1",
            "icon": "FakeCo",
            "default": True,
            "model_type": "llm",
        },
        {
            "name": "fake-embed-1",
            "icon": "FakeCo",
            "default": True,
            "model_type": "embeddings",
        },
    ]


def duplicate_whitespace_catalog_loader():
    """Return duplicate model identities after registry normalization."""
    return [
        {"name": "fake-chat-1", "model_type": "llm"},
        {"name": " fake-chat-1 ", "model_type": "llm"},
    ]


_CATALOG_LOADER_PATH = f"{__name__}:fake_catalog_loader"
_DUPLICATE_CATALOG_LOADER_PATH = f"{__name__}:duplicate_whitespace_catalog_loader"


def _fakeco_metadata() -> dict:
    return {
        "icon": "FakeCo",
        "max_tokens_field_name": "max_tokens",
        "variables": [
            {
                "variable_name": "FakeCo API Key",
                "variable_key": "FAKECO_API_KEY",
                "required": True,
                "is_secret": True,
                "is_list": False,
                "options": [],
                "langchain_param": "api_key",
            },
        ],
        "api_docs_url": "https://fakeco.example/docs",
        "mapping": {"model_class": "ChatOpenAI", "model_param": "model"},
    }


def _fakeco_spec(**overrides) -> ProviderSpec:
    kwargs: dict = {"name": "FakeCo", "metadata": _fakeco_metadata()}
    kwargs.update(overrides)
    return ProviderSpec(**kwargs)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Ensure no registration leaks across tests."""
    provider_registry.clear()
    _validator_calls.clear()
    yield
    provider_registry.clear()


# ---------------------------------------------------------------------------
# Registration + visibility
# ---------------------------------------------------------------------------


def test_register_adds_metadata_and_appears_in_accessors():
    assert "FakeCo" not in get_model_providers()

    assert register_provider(_fakeco_spec()) is True

    assert MODEL_PROVIDER_METADATA["FakeCo"]["icon"] == "FakeCo"
    assert "FakeCo" in get_model_provider_metadata()
    # Appears even though FakeCo ships no static model catalog.
    assert "FakeCo" in get_model_providers()


def test_register_exposes_stable_identity_display_name_and_aliases():
    register_provider(
        _fakeco_spec(
            provider_id="fakeco.enterprise",
            display_name="FakeCo Enterprise",
            aliases=("fake-co", "FakeCo Legacy"),
        )
    )

    assert provider_registry.provider_id_for("FakeCo") == "fakeco.enterprise"
    assert provider_registry.provider_id_for("fake-co") == "fakeco.enterprise"
    assert provider_registry.provider_id_for("FakeCo Legacy") == "fakeco.enterprise"
    assert provider_registry.provider_name_for_id("fakeco.enterprise") == "FakeCo"
    assert MODEL_PROVIDER_METADATA["FakeCo"]["provider_id"] == "fakeco.enterprise"
    assert MODEL_PROVIDER_METADATA["FakeCo"]["display_name"] == "FakeCo Enterprise"


def test_model_component_explicit_identity_wins_over_ambiguous_module_name():
    class AzureEmbeddingComponent:
        display_name = "Azure OpenAI Embeddings"
        model_provider_id = "azure-openai"

    assert provider_registry.model_component_provider_id(AzureEmbeddingComponent()) == "azure-openai"


def test_model_component_policy_mode_distinguishes_delegate_and_opt_out():
    class Component:
        model_provider_policy_mode = "delegate"

    assert provider_registry.uses_standalone_model_provider_policy(Component()) is False
    Component.model_provider_policy_mode = "none"
    assert provider_registry.uses_standalone_model_provider_policy(Component()) is False


def test_registry_snapshot_deep_freezes_descriptor_payloads():
    register_provider(_fakeco_spec(provider_id="fakeco"))

    descriptor = provider_registry.get_registry_snapshot().descriptors_by_id["fakeco"]

    with pytest.raises(TypeError):
        descriptor.metadata["icon"] = "Spoofed"  # type: ignore[index]
    variables = descriptor.metadata["variables"]
    with pytest.raises(TypeError):
        variables[0]["variable_key"] = "SPOOFED_KEY"  # type: ignore[index]

    assert MODEL_PROVIDER_METADATA["FakeCo"]["icon"] == "FakeCo"
    assert MODEL_PROVIDER_METADATA["FakeCo"]["variables"][0]["variable_key"] == "FAKECO_API_KEY"


def test_registered_catalog_loader_contributes_static_models():
    register_provider(
        _fakeco_spec(
            provider_id="fakeco",
            catalog_loader=_CATALOG_LOADER_PATH,
        )
    )

    fakeco_groups = [
        group for group in get_models_detailed() if group and all(row.get("provider") == "FakeCo" for row in group)
    ]

    assert len(fakeco_groups) == 1
    assert [row["name"] for row in fakeco_groups[0]] == ["fake-chat-1", "fake-embed-1"]
    assert {row["provider"] for row in fakeco_groups[0]} == {"FakeCo"}


def test_registered_catalog_rejects_duplicate_normalized_model_names():
    register_provider(
        _fakeco_spec(
            provider_id="fakeco",
            catalog_loader=_DUPLICATE_CATALOG_LOADER_PATH,
        )
    )

    with pytest.raises(ValueError, match="duplicate model identity"):
        provider_registry.validate_registered_provider_catalogs()


def test_duplicate_provider_id_is_rejected_even_when_names_differ():
    register_provider(_fakeco_spec(provider_id="fakeco"))

    with pytest.raises(ValueError, match="provider_id"):
        register_provider(
            ProviderSpec(
                name="OtherCo",
                provider_id="fakeco",
                metadata={**_fakeco_metadata(), "icon": "OtherCo"},
            )
        )


@pytest.mark.parametrize("reserved_key", ["provider", "models", "num_models", "provider_id", "aliases"])
def test_provider_metadata_cannot_override_identity_or_catalog_structure(reserved_key):
    with pytest.raises(ValueError, match="reserved keys"):
        register_provider(
            _fakeco_spec(
                metadata={**_fakeco_metadata(), reserved_key: "OpenAI"},
            )
        )


def test_variable_mapping_cache_refreshed_after_register():
    # Prime the lru_cache before registration.
    before = get_model_provider_variable_mapping()
    assert "FakeCo" not in before

    register_provider(_fakeco_spec())

    after = get_model_provider_variable_mapping()
    assert after.get("FakeCo") == "FAKECO_API_KEY"


def test_core_provider_name_is_not_overwritten():
    original = MODEL_PROVIDER_METADATA["OpenAI"]
    spoof = ProviderSpec(name="OpenAI", metadata=_fakeco_metadata())

    assert register_provider(spoof) is False
    assert MODEL_PROVIDER_METADATA["OpenAI"] is original
    assert not provider_registry.is_registered("OpenAI")


def test_duplicate_bundle_registration_is_ignored():
    assert register_provider(_fakeco_spec()) is True
    assert register_provider(_fakeco_spec(metadata={**_fakeco_metadata(), "icon": "Other"})) is False
    # First registration wins.
    assert MODEL_PROVIDER_METADATA["FakeCo"]["icon"] == "FakeCo"


# ---------------------------------------------------------------------------
# Live-only provider surface (feeds the /api/v1/models union)
# ---------------------------------------------------------------------------


def test_live_only_providers_empty_at_core_baseline():
    # Azure OpenAI / Groq carry metadata but no live gate and must not surface;
    # every live-capable core provider ships static catalog rows.
    assert get_live_only_providers() == []


def test_live_registration_appears_in_live_only_providers():
    register_provider(_fakeco_spec(live=True, live_discovery=_LIVE_DISCOVERY_PATH))
    assert get_live_only_providers() == ["FakeCo"]


def test_conditional_live_registration_appears_in_live_only_providers():
    register_provider(_fakeco_spec(conditional_live=True, live_discovery=_LIVE_DISCOVERY_PATH))
    assert get_live_only_providers() == ["FakeCo"]


def test_non_live_registration_excluded_from_live_only_providers():
    # Without a live gate the provider could never list models; excluding it
    # mirrors the deliberate absence of Azure OpenAI / Groq from the unified UI.
    register_provider(_fakeco_spec())
    assert get_live_only_providers() == []


# ---------------------------------------------------------------------------
# Behavior dispatch
# ---------------------------------------------------------------------------


def test_api_key_optional_flag():
    register_provider(_fakeco_spec(api_key_required=False))
    assert provider_registry.is_api_key_optional("FakeCo") is True


def test_api_key_required_by_default():
    register_provider(_fakeco_spec())
    assert provider_registry.is_api_key_optional("FakeCo") is False


def test_live_provider_added_to_live_list_and_dispatches():
    register_provider(_fakeco_spec(live=True, live_discovery=_LIVE_DISCOVERY_PATH))
    assert "FakeCo" in LIVE_MODEL_PROVIDERS

    models = get_live_models_for_provider("user-1", "FakeCo", "llm")
    assert [m["name"] for m in models] == ["fake-llm"]


def _boom_discovery(user_id, model_type):  # noqa: ARG001
    msg = "network down"
    raise RuntimeError(msg)


def test_live_discovery_failure_degrades_to_empty():
    # _boom_discovery imports fine but raises when called -> degrade to [].
    register_provider(_fakeco_spec(live=True, live_discovery=f"{__name__}:_boom_discovery"))
    assert get_live_models_for_provider("user-1", "FakeCo", "llm") == []


def test_unknown_live_discovery_path_degrades_to_empty():
    register_provider(_fakeco_spec(live=True, live_discovery=f"{__name__}:does_not_exist"))
    assert get_live_models_for_provider("user-1", "FakeCo", "llm") == []


def test_validator_dispatch_pass():
    register_provider(_fakeco_spec(validator=_VALIDATOR_PATH))
    validate_model_provider_key("FakeCo", {"FAKECO_API_KEY": "good"})  # pragma: allowlist secret
    assert _validator_calls
    assert _validator_calls[0][0] == "FakeCo"


def test_validator_dispatch_raises_on_bad_key():
    register_provider(_fakeco_spec(validator=_VALIDATOR_PATH))
    with pytest.raises(ValueError, match="FakeCo credentials rejected"):
        validate_model_provider_key("FakeCo", {"FAKECO_API_KEY": "bad"})  # pragma: allowlist secret


def test_registered_provider_without_validator_is_noop():
    register_provider(_fakeco_spec())
    # No validator configured -> generic pass, no exception.
    validate_model_provider_key("FakeCo", {"FAKECO_API_KEY": "anything"})  # pragma: allowlist secret


def _boom_validator(provider, variables, model_name):  # noqa: ARG001
    msg = "transport exploded"
    raise RuntimeError(msg)


def test_validator_non_value_error_is_normalized():
    # A bundle validator that raises a non-ValueError (e.g. a transport error)
    # is normalized to ValueError so it can't escape as an unhandled 500.
    register_provider(_fakeco_spec(validator=f"{__name__}:_boom_validator"))
    with pytest.raises(ValueError, match="Could not validate credentials"):
        validate_model_provider_key("FakeCo", {"FAKECO_API_BASE": "x"})


# ---------------------------------------------------------------------------
# Connection-variable application (get_llm / get_embeddings)
# ---------------------------------------------------------------------------


def _fakeco_metadata_with_base_url() -> dict:
    meta = _fakeco_metadata()
    meta["variables"] = [
        {
            "variable_name": "FakeCo Base URL",
            "variable_key": "FAKECO_API_BASE",
            "required": True,
            "is_secret": False,
            "is_list": False,
            "options": [],
            "langchain_param": "base_url",
        },
        *meta["variables"],
    ]
    return meta


def _fakeco_metadata_with_only_base_url() -> dict:
    """Provider metadata with required connection config but no secret variable."""
    meta = _fakeco_metadata()
    meta["variables"] = [
        {
            "variable_name": "FakeCo Base URL",
            "variable_key": "FAKECO_API_BASE",
            "required": True,
            "is_secret": False,
            "is_list": False,
            "options": [],
            "langchain_param": "base_url",
        }
    ]
    return meta


def test_get_llm_applies_registered_provider_base_url(monkeypatch):
    from lfx.base.models import unified_models as um
    from lfx.base.models.unified_models.instantiation import get_llm

    captured: dict = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    register_provider(_fakeco_spec(metadata=_fakeco_metadata_with_base_url(), api_key_required=False))
    monkeypatch.setattr(um, "get_api_key_for_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(um, "get_model_class", lambda _name: FakeChat)
    monkeypatch.setattr(
        um, "get_all_variables_for_provider", lambda *_a, **_k: {"FAKECO_API_BASE": "http://vllm.example:8000"}
    )

    model_selection = [
        {
            "name": "m1",
            "provider": "FakeCo",
            "metadata": {
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
            },
        }
    ]
    get_llm(model_selection, user_id=None)

    assert captured["model"] == "m1"
    assert captured["base_url"] == "http://vllm.example:8000"
    # api_key_optional provider with no configured key gets a non-empty placeholder.
    assert captured["api_key"] == "EMPTY"  # pragma: allowlist secret


def test_variable_mapping_prefers_secret_over_first_variable():
    # A provider whose first (required) variable is a non-secret base URL and
    # whose API key is an optional secret must map to the secret, not the base
    # URL -- otherwise get_api_key_for_provider would send the endpoint as the
    # bearer token.
    from lfx.base.models.unified_models import get_model_provider_variable_mapping

    register_provider(_fakeco_spec(metadata=_fakeco_metadata_with_base_url(), api_key_required=False))
    assert get_model_provider_variable_mapping()["FakeCo"] == "FAKECO_API_KEY"


def test_get_llm_real_resolver_uses_placeholder_not_base_url(monkeypatch):
    # Exercise the REAL get_api_key_for_provider path (not a patched stub): with
    # only the base URL configured, the api_key must resolve to the "EMPTY"
    # placeholder, never the base URL.
    from lfx.base.models import unified_models as um
    from lfx.base.models.unified_models.instantiation import get_llm

    captured: dict = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    register_provider(_fakeco_spec(metadata=_fakeco_metadata_with_only_base_url(), api_key_required=False))
    monkeypatch.setenv("FAKECO_API_BASE", "http://vllm.example:8000")
    monkeypatch.setattr(um, "get_model_class", lambda _name: FakeChat)
    # Base URL comes from the env via the connection handler; do NOT patch the
    # api-key resolver -- that is the path under test.
    monkeypatch.setattr(um, "get_all_variables_for_provider", lambda *_a, **_k: {})

    # The broad mapping remains available to provider enablement/UI callers,
    # but neither implicit nor explicit API-key lookup may consume it.
    assert um.get_model_provider_variable_mapping()["FakeCo"] == "FAKECO_API_BASE"
    assert um.get_api_key_for_provider(None, "FakeCo") is None
    assert um.get_api_key_for_provider(None, "FakeCo", "FAKECO_API_BASE") is None

    model_selection = [{"name": "m1", "provider": "FakeCo", "metadata": {"model_class": "ChatOpenAI"}}]
    get_llm(model_selection, user_id=None)

    assert captured["api_key"] == "EMPTY"  # pragma: allowlist secret
    assert captured["base_url"] == "http://vllm.example:8000"


def test_get_embeddings_applies_registered_provider_base_url_and_key(monkeypatch):
    from lfx.base.models import unified_models as um
    from lfx.base.models.unified_models.instantiation import get_embeddings

    captured: dict = {}

    class FakeEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    register_provider(
        _fakeco_spec(
            metadata=_fakeco_metadata_with_base_url(),
            api_key_required=False,
            embedding_class_name="OpenAIEmbeddings",
            embedding_param_key="FakeCo",
            embedding_param_mapping={"model": "model", "api_base": "base_url"},
        )
    )
    monkeypatch.setattr(um, "get_api_key_for_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(um, "get_embedding_class", lambda _name: FakeEmbeddings)
    monkeypatch.setattr(
        um, "get_all_variables_for_provider", lambda *_a, **_k: {"FAKECO_API_BASE": "http://vllm.example:8000"}
    )

    model_selection = [
        {
            "name": "emb-1",
            "provider": "FakeCo",
            "metadata": {
                "embedding_class": "OpenAIEmbeddings",
                "param_mapping": {"model": "model", "api_base": "base_url"},
            },
        }
    ]
    get_embeddings(model_selection, user_id=None)

    assert captured["model"] == "emb-1"
    assert captured["base_url"] == "http://vllm.example:8000"
    # No "api_key" slot in param_mapping -> the seam still passes the placeholder.
    assert captured["api_key"] == "EMPTY"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Embedding wiring
# ---------------------------------------------------------------------------


def test_embedding_wiring_registered():
    register_provider(
        _fakeco_spec(
            embedding_class_name="OpenAIEmbeddings",
            embedding_param_key="FakeCo Embeddings",
            embedding_param_mapping={"model": "model", "api_key": "api_key"},  # pragma: allowlist secret
        )
    )
    assert EMBEDDING_PROVIDER_CLASS_MAPPING["FakeCo"] == "OpenAIEmbeddings"
    assert EMBEDDING_PARAM_MAPPINGS["FakeCo"]["api_key"] == "api_key"  # pragma: allowlist secret
    assert EMBEDDING_PARAM_MAPPINGS["FakeCo Embeddings"]["api_key"] == "api_key"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Validation + baseline restoration
# ---------------------------------------------------------------------------


def test_invalid_spec_missing_model_class_raises():
    bad_meta = {"icon": "X", "variables": [], "mapping": {}}
    with pytest.raises(ValueError, match="model_class"):
        register_provider(ProviderSpec(name="BadCo", metadata=bad_meta))


def test_live_and_conditional_live_mutually_exclusive():
    with pytest.raises(ValueError, match="both live and conditional_live"):
        register_provider(_fakeco_spec(live=True, conditional_live=True))


def test_unknown_model_class_without_import_raises():
    meta = {**_fakeco_metadata(), "mapping": {"model_class": "NoSuchModelClass", "model_param": "model"}}
    with pytest.raises(ValueError, match="unknown model class"):
        register_provider(_fakeco_spec(metadata=meta))


def test_conflicting_model_class_import_raises():
    meta = {**_fakeco_metadata(), "mapping": {"model_class": "ChatOpenAI", "model_param": "model"}}
    # ChatOpenAI already maps to langchain_openai; a divergent import must be rejected.
    with pytest.raises(ValueError, match="conflicts with an existing import"):
        register_provider(_fakeco_spec(metadata=meta, model_class=("some_other_pkg", "ChatOpenAI", None)))


def test_embedding_param_key_conflict_raises():
    # "OpenAI" is a core EMBEDDING_PARAM_MAPPINGS key; reusing it would let clear()
    # later delete the core mapping, so registration must be rejected.
    with pytest.raises(ValueError, match="conflict with an existing mapping"):
        register_provider(
            _fakeco_spec(
                embedding_class_name="OpenAIEmbeddings",
                embedding_param_key="OpenAI",
                embedding_param_mapping={"model": "model"},
            )
        )


_NOT_CALLABLE = 42


def _non_list_discovery(user_id, model_type):  # noqa: ARG001
    return "not-a-list"


def test_non_callable_live_discovery_degrades_to_none():
    register_provider(_fakeco_spec(live=True, live_discovery=f"{__name__}:_NOT_CALLABLE"))
    assert provider_registry.live_discovery_for("FakeCo") is None
    assert get_live_models_for_provider("user-1", "FakeCo", "llm") == []


def test_non_list_live_discovery_return_is_normalized():
    register_provider(_fakeco_spec(live=True, live_discovery=f"{__name__}:_non_list_discovery"))
    assert get_live_models_for_provider("user-1", "FakeCo", "llm") == []


def test_clear_restores_baseline():
    baseline_providers = get_model_providers()
    baseline_meta_keys = set(MODEL_PROVIDER_METADATA)
    baseline_live = list(LIVE_MODEL_PROVIDERS)

    register_provider(
        _fakeco_spec(
            live=True,
            live_discovery=_LIVE_DISCOVERY_PATH,
            embedding_class_name="OpenAIEmbeddings",
            embedding_param_key="FakeCo Embeddings",
            embedding_param_mapping={"model": "model"},
        )
    )
    assert "FakeCo" in get_model_providers()

    provider_registry.clear()

    assert get_model_providers() == baseline_providers
    assert set(MODEL_PROVIDER_METADATA) == baseline_meta_keys
    assert list(LIVE_MODEL_PROVIDERS) == baseline_live
    assert "FakeCo" not in EMBEDDING_PROVIDER_CLASS_MAPPING
    assert "FakeCo" not in EMBEDDING_PARAM_MAPPINGS
    assert "FakeCo Embeddings" not in EMBEDDING_PARAM_MAPPINGS


def test_unregister_provider_removes_only_the_target_registration():
    register_provider(
        _fakeco_spec(
            provider_id="fakeco",
            aliases=("FakeCo Legacy",),
            live=True,
            live_discovery=_LIVE_DISCOVERY_PATH,
            catalog_loader=_CATALOG_LOADER_PATH,
            embedding_class_name="OpenAIEmbeddings",
            embedding_param_key="FakeCo Embeddings",
            embedding_param_mapping={"model": "model"},
        )
    )
    register_provider(_fakeco_spec(name="OtherCo", provider_id="otherco"))
    provider_registry.live_discovery_for("FakeCo")
    provider_registry.validate_registered_provider_catalogs(["FakeCo"])

    assert provider_registry.unregister_provider("FakeCo") is True

    assert provider_registry.is_registered("FakeCo") is False
    assert provider_registry.is_registered("OtherCo") is True
    assert provider_registry.provider_id_for("FakeCo Legacy") is None
    assert "FakeCo" not in MODEL_PROVIDER_METADATA
    assert "FakeCo" not in LIVE_MODEL_PROVIDERS
    assert "FakeCo" not in EMBEDDING_PROVIDER_CLASS_MAPPING
    assert "FakeCo" not in EMBEDDING_PARAM_MAPPINGS
    assert "FakeCo Embeddings" not in EMBEDDING_PARAM_MAPPINGS
    assert provider_registry.unregister_provider("FakeCo") is False


def test_zero_registration_is_noop():
    before = set(MODEL_PROVIDER_METADATA)
    provider_registry.clear()
    assert set(MODEL_PROVIDER_METADATA) == before
    assert provider_registry.registered_provider_names() == frozenset()
