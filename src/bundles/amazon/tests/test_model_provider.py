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


@pytest.fixture
def loaded_amazon_extension():
    provider_registry.clear()
    extension_root = Path(__file__).parents[1] / "src" / "lfx_amazon"
    result = load_extension(extension_root)
    assert result.ok, (result.errors, result.warnings)
    yield
    provider_registry.clear()


def test_bedrock_catalog_contains_hardcoded_eu_inference_profiles():
    models = load_bedrock_models()

    assert [model["name"] for model in models] == list(EU_BEDROCK_INFERENCE_PROFILE_IDS)
    assert all(model["model_type"] == "llm" for model in models)
    assert all(model["name"].startswith("eu.") for model in models)
    assert "eu.anthropic.claude-opus-4-8" in EU_BEDROCK_INFERENCE_PROFILE_IDS
    assert "eu.amazon.nova-2-lite-v1:0" in EU_BEDROCK_INFERENCE_PROFILE_IDS
    assert "eu.meta.llama3-2-3b-instruct-v1:0" in EU_BEDROCK_INFERENCE_PROFILE_IDS


def test_legacy_meta_profiles_do_not_advertise_tool_calling():
    meta_models = [model for model in load_bedrock_models() if model["name"].startswith("eu.meta.")]

    assert meta_models
    assert all(not model["tool_calling"] for model in meta_models)


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_amazon_extension_manifest_registers_bedrock_provider():
    assert "Amazon Bedrock" in get_model_providers()
    assert provider_registry.provider_id_for("Amazon Bedrock") == "amazon-bedrock"

    bedrock_models = [
        row for group in get_models_detailed() for row in group if row.get("provider") == "Amazon Bedrock"
    ]
    assert bedrock_models


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_all_hardcoded_bedrock_models_are_visible_by_default():
    [provider] = get_unified_models_detailed(providers=["Amazon Bedrock"], only_defaults=True)

    assert [model["model_name"] for model in provider["models"]] == list(EU_BEDROCK_INFERENCE_PROFILE_IDS)


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_bedrock_provider_maps_api_key_and_model_parameters():
    mapping = get_provider_param_mapping("Amazon Bedrock")

    assert mapping["model_class"] == "ChatBedrockConverse"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "api_key"
    assert get_model_class("ChatBedrockConverse").__name__ == "ChatBedrockConverse"


def test_bedrock_provider_declares_api_key_and_region_without_live_discovery():
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
