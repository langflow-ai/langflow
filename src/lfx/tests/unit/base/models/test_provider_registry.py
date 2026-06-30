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
    get_model_provider_metadata,
    get_model_provider_variable_mapping,
    get_model_providers,
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
    assert "FakeCo Embeddings" not in EMBEDDING_PARAM_MAPPINGS


def test_zero_registration_is_noop():
    before = set(MODEL_PROVIDER_METADATA)
    provider_registry.clear()
    assert set(MODEL_PROVIDER_METADATA) == before
    assert provider_registry.registered_provider_names() == frozenset()
