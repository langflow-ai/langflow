import json
from pathlib import Path

import pytest
from lfx.base.models import provider_registry
from lfx.base.models.model_metadata import get_provider_param_mapping
from lfx.base.models.unified_models import (
    get_model_class,
    get_model_providers,
    get_models_detailed,
    get_unified_models_detailed,
)
from lfx.extension import load_extension
from lfx_amazon.model_provider import EU_BEDROCK_INFERENCE_PROFILE_IDS, load_bedrock_models

# Independently maintained expectations for every EU Bedrock inference profile.
# This map is deliberately not derived from the implementation's constants so
# the tests fail if a profile's provider, tool-calling, or reasoning metadata
# drifts. Each value is (tool_calling, reasoning).
EXPECTED_EU_PROFILES: dict[str, tuple[bool, bool]] = {
    # Anthropic Claude 4.6+/5 profiles: tool calling and extended reasoning.
    "eu.anthropic.claude-opus-4-8": (True, True),
    "eu.anthropic.claude-sonnet-5": (True, True),
    "eu.anthropic.claude-opus-4-7": (True, True),
    "eu.anthropic.claude-sonnet-4-6": (True, True),
    "eu.anthropic.claude-opus-4-6-v1": (True, True),
    # Anthropic Claude 4.5 / legacy 3.x profiles: tool calling, no reasoning.
    "eu.anthropic.claude-opus-4-5-20251101-v1:0": (True, False),
    "eu.anthropic.claude-sonnet-4-5-20250929-v1:0": (True, False),
    "eu.anthropic.claude-haiku-4-5-20251001-v1:0": (True, False),
    "eu.anthropic.claude-3-7-sonnet-20250219-v1:0": (True, False),
    "eu.anthropic.claude-3-5-sonnet-20241022-v2:0": (True, False),
    "eu.anthropic.claude-3-haiku-20240307-v1:0": (True, False),
    # Amazon Nova profiles: tool calling, no reasoning.
    "eu.amazon.nova-2-lite-v1:0": (True, False),
    "eu.amazon.nova-pro-v1:0": (True, False),
    "eu.amazon.nova-lite-v1:0": (True, False),
    "eu.amazon.nova-micro-v1:0": (True, False),
    # Meta Llama legacy profiles: no tool calling, no reasoning.
    "eu.meta.llama3-2-3b-instruct-v1:0": (False, False),
    "eu.meta.llama3-2-1b-instruct-v1:0": (False, False),
}


@pytest.fixture
def loaded_amazon_extension():
    """Load the real Amazon extension into an isolated provider registry."""
    provider_registry.clear()
    extension_root = Path(__file__).parents[1] / "src" / "lfx_amazon"
    result = load_extension(extension_root)
    assert result.ok, (result.errors, result.warnings)
    yield
    provider_registry.clear()


def test_bedrock_catalog_contains_hardcoded_eu_inference_profiles():
    """The catalog exposes exactly the declared EU inference profiles as LLMs."""
    models = load_bedrock_models()

    assert [model["name"] for model in models] == list(EU_BEDROCK_INFERENCE_PROFILE_IDS)
    assert all(model["model_type"] == "llm" for model in models)
    assert all(model["name"].startswith("eu.") for model in models)
    assert "eu.anthropic.claude-opus-4-8" in EU_BEDROCK_INFERENCE_PROFILE_IDS
    assert "eu.amazon.nova-2-lite-v1:0" in EU_BEDROCK_INFERENCE_PROFILE_IDS
    assert "eu.meta.llama3-2-3b-instruct-v1:0" in EU_BEDROCK_INFERENCE_PROFILE_IDS


def test_catalog_matches_independent_expected_metadata():
    """Every catalog entry matches an independently maintained expectation.

    Asserts the provider, model type, tool-calling flag, and reasoning flag for
    each EU profile against ``EXPECTED_EU_PROFILES`` (which is not derived from
    the implementation's constants), so any metadata drift is caught.
    """
    models = {model["name"]: model for model in load_bedrock_models()}

    # No profile is present or missing relative to the independent expectation.
    assert set(models) == set(EXPECTED_EU_PROFILES)

    for name, (expected_tool_calling, expected_reasoning) in EXPECTED_EU_PROFILES.items():
        model = models[name]
        assert model["provider"] == "Amazon Bedrock", name
        assert model["icon"] == "Amazon", name
        assert model["model_type"] == "llm", name
        assert model["tool_calling"] is expected_tool_calling, name
        assert model["reasoning"] is expected_reasoning, name


def test_legacy_meta_profiles_do_not_advertise_tool_calling():
    """Meta Llama EU profiles never advertise tool calling."""
    meta_models = [model for model in load_bedrock_models() if model["name"].startswith("eu.meta.")]

    assert meta_models
    assert all(not model["tool_calling"] for model in meta_models)


def test_reasoning_flag_is_set_per_model_not_by_substring():
    """Reasoning is set per-model, not by an ``anthropic.claude`` substring match."""
    models = {model["name"]: model for model in load_bedrock_models()}

    # Current Claude 4.6+/5 profiles expose extended reasoning.
    assert models["eu.anthropic.claude-opus-4-8"]["reasoning"] is True
    assert models["eu.anthropic.claude-sonnet-4-6"]["reasoning"] is True

    # Legacy Claude 3.x profiles must not be advertised as reasoning models,
    # even though their IDs contain "anthropic.claude".
    assert models["eu.anthropic.claude-3-7-sonnet-20250219-v1:0"]["reasoning"] is False
    assert models["eu.anthropic.claude-3-haiku-20240307-v1:0"]["reasoning"] is False


def test_expired_claude_3_5_haiku_profile_is_not_advertised():
    """The end-of-life Claude 3.5 Haiku profile is excluded from the catalog."""
    # eu.anthropic.claude-3-5-haiku-20241022-v1:0 reached AWS end-of-life on
    # 2026-06-19 and must not be offered as an active/default model.
    expired_profile = "eu.anthropic.claude-3-5-haiku-20241022-v1:0"

    assert expired_profile not in EU_BEDROCK_INFERENCE_PROFILE_IDS
    assert expired_profile not in {model["name"] for model in load_bedrock_models()}


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_amazon_extension_manifest_registers_bedrock_provider():
    """Loading the extension registers Amazon Bedrock and publishes its models."""
    assert "Amazon Bedrock" in get_model_providers()
    assert provider_registry.provider_id_for("Amazon Bedrock") == "amazon-bedrock"

    bedrock_models = [
        row for group in get_models_detailed() for row in group if row.get("provider") == "Amazon Bedrock"
    ]
    assert bedrock_models


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_all_hardcoded_bedrock_models_are_visible_by_default():
    """Every EU profile is a default option, with no duplicate rows in the unified catalog."""
    [provider] = get_unified_models_detailed(providers=["Amazon Bedrock"], only_defaults=True)

    model_names = [model["model_name"] for model in provider["models"]]
    assert model_names == list(EU_BEDROCK_INFERENCE_PROFILE_IDS)
    # The static AWS_MODELS_DETAILED catalog and the extension catalog must not
    # both contribute a row for the same profile.
    assert len(model_names) == len(set(model_names))


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_bedrock_provider_maps_api_key_and_model_parameters():
    """The provider maps to ChatBedrockConverse with the expected parameter names."""
    mapping = get_provider_param_mapping("Amazon Bedrock")

    assert mapping["model_class"] == "ChatBedrockConverse"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "api_key"
    assert get_model_class("ChatBedrockConverse").__name__ == "ChatBedrockConverse"


def test_bedrock_provider_declares_api_key_and_region_without_live_discovery():
    """The manifest declares the API key and region variables and no live discovery."""
    manifest_path = Path(__file__).parents[1] / "src" / "lfx_amazon" / "extension.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provider = manifest["providers"][0]
    variables = provider["metadata"]["variables"]

    assert {variable["variable_key"] for variable in variables} == {
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_REGION",
    }
    assert "live_discovery" not in provider
    assert "conditional_live" not in provider
