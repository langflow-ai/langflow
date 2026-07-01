"""Tests for the lfx-azure-ai-foundry provider bundle and the models[] registry extension.

Covers:
  - ProviderSpec.models[] injects into _STATIC_MODELS_DETAILED and is reversed by clear().
  - End-to-end load through the real extension loader: provider appears in
    get_model_providers() and get_models_detailed() after load.
  - Validator callable is imported and invokes correctly (success + early-return paths).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Registry extension: models[] field
# ---------------------------------------------------------------------------


def test_register_provider_injects_static_models():
    """Static models declared in ProviderSpec.models[] must appear in get_models_detailed()."""
    from lfx.base.models import provider_registry
    from lfx.base.models.model_metadata import create_model_metadata
    from lfx.base.models.provider_registry import ProviderSpec, clear, register_provider
    from lfx.base.models.unified_models.provider_queries import get_models_detailed

    get_models_detailed.cache_clear()
    clear()
    try:
        seed = [create_model_metadata(provider="TestCloud", name="tc-model-1", icon="Azure")]
        spec = ProviderSpec(
            name="TestCloud",
            metadata={
                "icon": "Azure",
                "variables": [],
                "mapping": {"model_class": "ChatOpenAI", "model_param": "model"},
            },
            models=seed,
        )
        register_provider(spec)
        get_models_detailed.cache_clear()
        all_models = [m for group in get_models_detailed() for m in group]
        names = {m["name"] for m in all_models}
        assert "tc-model-1" in names
    finally:
        clear()
        get_models_detailed.cache_clear()
        provider_registry._CORE_PROVIDER_NAMES  # noqa: B018 - trigger re-capture guard check


def test_clear_removes_static_models():
    """clear() must remove models[] entries from _STATIC_MODELS_DETAILED."""
    from lfx.base.models.model_metadata import create_model_metadata
    from lfx.base.models.provider_registry import ProviderSpec, clear, register_provider
    from lfx.base.models.unified_models.provider_queries import _STATIC_MODELS_DETAILED, get_models_detailed

    get_models_detailed.cache_clear()
    clear()
    seed = [create_model_metadata(provider="TestCloud2", name="tc-model-2", icon="Azure")]
    spec = ProviderSpec(
        name="TestCloud2",
        metadata={
            "icon": "Azure",
            "variables": [],
            "mapping": {"model_class": "ChatOpenAI", "model_param": "model"},
        },
        models=seed,
    )
    register_provider(spec)
    assert seed in _STATIC_MODELS_DETAILED

    clear()
    assert seed not in _STATIC_MODELS_DETAILED
    get_models_detailed.cache_clear()


# ---------------------------------------------------------------------------
# End-to-end: load through the real extension loader
# ---------------------------------------------------------------------------


def _bundle_root() -> Path:
    """Return the path to the azure-ai-foundry bundle root (contains extension.json)."""
    return Path(__file__).parent.parent / "src" / "lfx_azure_ai_foundry"


def test_bundle_root_exists():
    """Sanity-check that the bundle root and extension.json are present."""
    root = _bundle_root()
    assert root.exists(), f"Bundle root not found: {root}"
    assert (root / "extension.json").exists()


# ---------------------------------------------------------------------------
# Manifest validation: models[] structural checks
# ---------------------------------------------------------------------------


def _minimal_provider_entry(**overrides):
    """Return a minimal valid ProviderManifestEntry dict, with optional overrides."""
    base = {
        "name": "TestCloud",
        "metadata": {
            "icon": "Azure",
            "variables": [],
            "mapping": {"model_class": "ChatOpenAI", "model_param": "model"},
        },
    }
    base.update(overrides)
    return base


def test_manifest_rejects_model_entry_without_name():
    """ProviderManifestEntry must reject models[] entries that have no 'name' key."""
    import pytest
    from lfx.extension.manifest import ProviderManifestEntry
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="non-empty 'name'"):
        ProviderManifestEntry(**_minimal_provider_entry(models=[{"provider": "TestCloud"}]))


def test_manifest_rejects_model_entry_with_mismatched_provider():
    """ProviderManifestEntry must reject models[] entries whose 'provider' key differs from the provider name."""
    import pytest
    from lfx.extension.manifest import ProviderManifestEntry
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="mismatched provider"):
        ProviderManifestEntry(
            **_minimal_provider_entry(models=[{"name": "gpt-4o", "provider": "WrongCloud"}])
        )


def test_manifest_accepts_model_entry_without_provider_key():
    """ProviderManifestEntry must accept models[] entries that omit the optional 'provider' key."""
    from lfx.extension.manifest import ProviderManifestEntry

    entry = ProviderManifestEntry(**_minimal_provider_entry(models=[{"name": "gpt-4o"}]))
    assert entry.models[0]["name"] == "gpt-4o"


def test_manifest_accepts_model_entry_with_matching_provider():
    """ProviderManifestEntry must accept models[] entries where 'provider' matches the provider name."""
    from lfx.extension.manifest import ProviderManifestEntry

    entry = ProviderManifestEntry(
        **_minimal_provider_entry(models=[{"name": "gpt-4o", "provider": "TestCloud"}])
    )
    assert entry.models[0]["name"] == "gpt-4o"


def test_azure_ai_foundry_appears_in_get_model_providers_after_load():
    """After loading the bundle, Azure AI Foundry must appear in get_model_providers()."""
    from lfx.base.models.provider_registry import clear
    from lfx.base.models.unified_models import get_model_providers
    from lfx.base.models.unified_models.provider_queries import get_models_detailed
    from lfx.extension.loader._orchestrator import load_extension

    get_models_detailed.cache_clear()
    clear()
    try:
        result = load_extension(str(_bundle_root()), slot="extra")
        assert not result.errors, f"Bundle load errors: {result.errors}"
        assert "Azure AI Foundry" in get_model_providers()
    finally:
        clear()
        get_models_detailed.cache_clear()


def test_azure_ai_foundry_seed_models_appear_after_load():
    """After loading the bundle, the seed catalog must appear in get_models_detailed()."""
    from lfx.base.models.provider_registry import clear
    from lfx.base.models.unified_models.provider_queries import get_models_detailed
    from lfx.extension.loader._orchestrator import load_extension

    get_models_detailed.cache_clear()
    clear()
    try:
        load_extension(str(_bundle_root()), slot="extra")
        get_models_detailed.cache_clear()
        all_models = [m for group in get_models_detailed() for m in group]
        foundry_names = {m["name"] for m in all_models if m.get("provider") == "Azure AI Foundry"}
        assert "gpt-4o" in foundry_names
        assert "gpt-4o-mini" in foundry_names
    finally:
        clear()
        get_models_detailed.cache_clear()


# ---------------------------------------------------------------------------
# Validator callable
# ---------------------------------------------------------------------------


def test_validator_returns_early_without_model_name():
    """Validator must return silently when model_name is not supplied."""
    from lfx_azure_ai_foundry.validator import validate_azure_ai_foundry_credentials

    validate_azure_ai_foundry_credentials(
        "Azure AI Foundry",
        {"AZURE_AI_FOUNDRY_API_KEY": "key", "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.com"},
        model_name=None,
    )


def test_validator_returns_early_without_api_key():
    """Validator must return silently when API key is absent."""
    from lfx_azure_ai_foundry.validator import validate_azure_ai_foundry_credentials

    validate_azure_ai_foundry_credentials(
        "Azure AI Foundry",
        {"AZURE_AI_FOUNDRY_ENDPOINT": "https://example.com"},
        model_name="gpt-4o",
    )


def test_validator_returns_early_without_endpoint():
    """Validator must return silently when endpoint is absent."""
    from lfx_azure_ai_foundry.validator import validate_azure_ai_foundry_credentials

    validate_azure_ai_foundry_credentials(
        "Azure AI Foundry",
        {"AZURE_AI_FOUNDRY_API_KEY": "key"},
        model_name="gpt-4o",
    )


def test_validator_invokes_chat_model_on_success():
    """Validator must construct AzureAIOpenAIApiChatModel and call invoke() when all fields present."""
    from lfx_azure_ai_foundry.validator import validate_azure_ai_foundry_credentials

    calls: list[dict] = []

    class FakeModel:
        """Stub that records constructor kwargs and returns a successful invoke result."""

        def __init__(self, **kwargs):
            """Record kwargs for post-call assertions."""
            calls.append(kwargs)

        def invoke(self, _prompt):
            """Return a fixed success response."""
            return "ok"

    fake_module = SimpleNamespace(AzureAIOpenAIApiChatModel=FakeModel)
    with patch.dict("sys.modules", {"langchain_azure_ai": fake_module, "langchain_azure_ai.chat_models": fake_module}):
        validate_azure_ai_foundry_credentials(
            "Azure AI Foundry",
            {"AZURE_AI_FOUNDRY_API_KEY": "k", "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.com"},
            model_name="gpt-4o",
        )

    assert calls[0]["credential"] == "k"
    assert calls[0]["endpoint"] == "https://example.com"
    assert calls[0]["model"] == "gpt-4o"


def test_validator_raises_on_invoke_failure():
    """Validator must raise ValueError when invoke() throws."""
    from lfx_azure_ai_foundry.validator import validate_azure_ai_foundry_credentials

    class FakeModel:
        """Stub whose invoke() always raises to exercise the validator error path."""

        def __init__(self, **kwargs):
            """Accept and discard constructor kwargs."""

        def invoke(self, _prompt):
            """Raise RuntimeError to simulate a rejected credential."""
            msg = "auth failed"
            raise RuntimeError(msg)

    fake_module = SimpleNamespace(AzureAIOpenAIApiChatModel=FakeModel)
    with (
        patch.dict("sys.modules", {"langchain_azure_ai": fake_module, "langchain_azure_ai.chat_models": fake_module}),
        pytest.raises(ValueError, match="auth failed"),
    ):
        validate_azure_ai_foundry_credentials(
            "Azure AI Foundry",
            {"AZURE_AI_FOUNDRY_API_KEY": "k", "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.com"},
            model_name="gpt-4o",
        )


def test_validator_raises_on_construction_failure():
    """Validator must raise ValueError when AzureAIOpenAIApiChatModel construction fails."""
    from lfx_azure_ai_foundry.validator import validate_azure_ai_foundry_credentials

    class BrokenModel:
        """Stub whose constructor always raises to exercise the construction error path."""

        def __init__(self, **_kwargs):
            """Raise immediately to simulate a broken/misconfigured client."""
            msg = "bad endpoint"
            raise ValueError(msg)

    fake_module = SimpleNamespace(AzureAIOpenAIApiChatModel=BrokenModel)
    with (
        patch.dict("sys.modules", {"langchain_azure_ai": fake_module, "langchain_azure_ai.chat_models": fake_module}),
        pytest.raises(ValueError, match="bad endpoint"),
    ):
        validate_azure_ai_foundry_credentials(
            "Azure AI Foundry",
            {"AZURE_AI_FOUNDRY_API_KEY": "k", "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.com"},
            model_name="gpt-4o",
        )
