import json
from pathlib import Path

import pytest
from lfx.base.models import provider_registry
from lfx.base.models.model_metadata import get_provider_param_mapping
from lfx.base.models.unified_models import get_model_providers, get_unified_models_detailed, instantiation
from lfx.extension import load_extension
from lfx_amazon.model_provider import EU_BEDROCK_INFERENCE_PROFILE_IDS, load_bedrock_models

_REASONING_PROFILES = {
    "eu.anthropic.claude-opus-4-8",
    "eu.anthropic.claude-sonnet-5",
    "eu.anthropic.claude-opus-4-7",
    "eu.anthropic.claude-sonnet-4-6",
    "eu.anthropic.claude-opus-4-6-v1",
    "eu.anthropic.claude-opus-4-5-20251101-v1:0",
    "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
    "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
}

_RETIRED_META_PROFILES = {
    "eu.meta.llama3-2-3b-instruct-v1:0",
    "eu.meta.llama3-2-1b-instruct-v1:0",
}


@pytest.fixture
def loaded_amazon_extension():
    """Load the Amazon extension with isolated provider-registry state."""
    provider_registry.clear()
    extension_root = Path(__file__).parents[1] / "src" / "lfx_amazon"
    result = load_extension(extension_root)
    assert result.ok, (result.errors, result.warnings)
    yield
    provider_registry.clear()


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_manifest_registers_iam_capable_bedrock_provider():
    """The extension registers Bedrock without requiring a stored API key."""
    assert "Amazon Bedrock" in get_model_providers()
    assert provider_registry.provider_id_for("Amazon Bedrock") == "amazon-bedrock"
    assert provider_registry.is_api_key_optional("Amazon Bedrock")
    assert get_provider_param_mapping("Amazon Bedrock")["api_key_param"] == "aws_access_key_id"


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_catalog_exposes_eu_inference_profiles():
    """The default catalog exposes every supported EU inference profile."""
    [provider] = get_unified_models_detailed(providers=["Amazon Bedrock"], only_defaults=True)

    assert [model["model_name"] for model in provider["models"]] == list(EU_BEDROCK_INFERENCE_PROFILE_IDS)
    assert "eu.anthropic.claude-opus-4-8" in EU_BEDROCK_INFERENCE_PROFILE_IDS
    assert all(model_id.startswith("eu.") for model_id in EU_BEDROCK_INFERENCE_PROFILE_IDS)


def test_catalog_capabilities_match_supported_models():
    """Reasoning and tool-calling flags match the independently maintained expectations."""
    models = {model["name"]: model for model in load_bedrock_models()}

    assert set(models) == set(EU_BEDROCK_INFERENCE_PROFILE_IDS)
    assert {name for name, model in models.items() if model["reasoning"]} == _REASONING_PROFILES
    assert all(model["tool_calling"] for model in models.values())
    assert models["eu.amazon.nova-2-lite-v1:0"]["reasoning"] is False


def test_catalog_excludes_retired_meta_profiles():
    """Models retired by AWS are not advertised as available defaults."""
    assert _RETIRED_META_PROFILES.isdisjoint(EU_BEDROCK_INFERENCE_PROFILE_IDS)


def test_manifest_credentials_are_optional():
    """All explicit AWS connection fields remain optional."""
    manifest_path = Path(__file__).parents[1] / "src" / "lfx_amazon" / "extension.json"
    provider = json.loads(manifest_path.read_text(encoding="utf-8"))["providers"][0]
    variables = provider["metadata"]["variables"]

    assert provider["api_key_required"] is False
    assert all(variable["required"] is False for variable in variables)
    assert {variable["variable_key"] for variable in variables} == {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_REGION",
    }


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_default_chain_omits_explicit_credentials(monkeypatch):
    """No explicit AWS arguments prevent the SDK from using its credential chain."""
    from lfx.base.models import unified_models as um

    captured = {}

    class FakeBedrock:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(um, "get_api_key_for_provider", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(um, "get_all_variables_for_provider", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(um, "get_model_class", lambda _name: FakeBedrock)
    aws_environment_variables = (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_REGION",
    )
    for variable_key in aws_environment_variables:
        monkeypatch.delenv(variable_key, raising=False)

    instantiation.get_llm(
        [{"name": "eu.anthropic.claude-opus-4-8", "provider": "Amazon Bedrock", "metadata": {}}],
        user_id=None,
    )

    assert captured["model"] == "eu.anthropic.claude-opus-4-8"
    assert "aws_access_key_id" not in captured
    assert "aws_secret_access_key" not in captured
    assert "aws_session_token" not in captured
    assert "credentials_profile_name" not in captured
    assert "region_name" not in captured


@pytest.mark.usefixtures("loaded_amazon_extension")
def test_explicit_compound_credentials_are_forwarded(monkeypatch):
    """Configured AWS credentials and connection settings reach the Bedrock client."""
    from lfx.base.models import unified_models as um

    captured = {}

    class FakeBedrock:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    variables = {
        "AWS_ACCESS_KEY_ID": "access-id",
        "AWS_SECRET_ACCESS_KEY": "secret-key",
        "AWS_SESSION_TOKEN": "session-token",
        "AWS_PROFILE": "development",
        "AWS_REGION": "eu-central-1",
    }
    monkeypatch.setattr(um, "get_api_key_for_provider", lambda *_args, **_kwargs: variables["AWS_ACCESS_KEY_ID"])
    monkeypatch.setattr(um, "get_all_variables_for_provider", lambda *_args, **_kwargs: variables)
    monkeypatch.setattr(um, "get_model_class", lambda _name: FakeBedrock)

    instantiation.get_llm(
        [{"name": "eu.anthropic.claude-opus-4-8", "provider": "Amazon Bedrock", "metadata": {}}],
        user_id=None,
    )

    assert captured["aws_access_key_id"] == variables["AWS_ACCESS_KEY_ID"]
    assert captured["aws_secret_access_key"] == variables["AWS_SECRET_ACCESS_KEY"]
    assert captured["aws_session_token"] == variables["AWS_SESSION_TOKEN"]
    assert captured["credentials_profile_name"] == variables["AWS_PROFILE"]
    assert captured["region_name"] == variables["AWS_REGION"]
