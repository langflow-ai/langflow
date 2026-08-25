"""Regression tests: the Top K input must reach models that support it, and only those."""

import pytest
from lfx_amazon.components.amazon.amazon_bedrock_converse import AmazonBedrockConverseComponent

_FAKE_AWS_ACCESS_KEY_ID = "AKIAFAKEFAKEFAKEFAKE"  # pragma: allowlist secret
_FAKE_AWS_SECRET_ACCESS_KEY = "fake-secret"  # noqa: S105  # pragma: allowlist secret


def _component(**overrides) -> AmazonBedrockConverseComponent:
    component = AmazonBedrockConverseComponent()
    component.model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    component.aws_access_key_id = _FAKE_AWS_ACCESS_KEY_ID
    component.aws_secret_access_key = _FAKE_AWS_SECRET_ACCESS_KEY
    component.region_name = "us-east-1"
    component.temperature = 0.7
    component.max_tokens = 4096
    component.top_p = 0.9
    component.top_k = 250
    component.disable_streaming = False
    component.additional_model_fields = []
    for name, value in overrides.items():
        setattr(component, name, value)
    return component


def test_top_k_reaches_additional_model_request_fields():
    model = _component(top_k=17).build_model()

    assert model.additional_model_request_fields == {"top_k": 17}


def test_user_supplied_additional_model_fields_can_override_top_k():
    model = _component(top_k=17, additional_model_fields=[{"top_k": 99}]).build_model()

    assert model.additional_model_request_fields == {"top_k": 99}


def test_top_k_omitted_when_unset():
    model = _component(top_k=None).build_model()

    assert not model.additional_model_request_fields


# Meta, Amazon Titan and AI21 document no top_k at all and Cohere spells it "k", so
# Bedrock rejects the whole Converse call when top_k is sent to them. The input carries
# a default of 250 that every saved flow persists, so an ungated send would break flows
# on those providers that work today.
@pytest.mark.parametrize(
    "model_id",
    [
        "meta.llama3-1-70b-instruct-v1:0",
        "amazon.titan-text-premier-v1:0",
        "cohere.command-r-plus-v1:0",
        "ai21.jamba-1-5-large-v1:0",
        # Mistral Large speaks the chat-completion schema, which has no top_k, and the
        # text-completion models cap it below this component's default of 250.
        "mistral.mistral-large-2407-v1:0",
        "mistral.mistral-7b-instruct-v0:2",
    ],
)
def test_top_k_not_sent_to_providers_without_it(model_id):
    model = _component(model_id=model_id, top_k=250).build_model()

    assert not model.additional_model_request_fields


@pytest.mark.parametrize(
    "model_id",
    [
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        # Cross-region and worldwide inference profiles prefix the provider segment.
        "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
        "eu.anthropic.claude-3-5-sonnet-20240620-v1:0",
        "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ],
)
def test_top_k_sent_to_providers_that_support_it(model_id):
    model = _component(model_id=model_id, top_k=42).build_model()

    assert model.additional_model_request_fields == {"top_k": 42}


def test_additional_model_fields_still_reach_unsupported_providers():
    """A user who knows their provider's own key can still pass it explicitly."""
    model = _component(
        model_id="meta.llama3-1-70b-instruct-v1:0",
        top_k=250,
        additional_model_fields=[{"max_gen_len": 512}],
    ).build_model()

    assert model.additional_model_request_fields == {"max_gen_len": 512}
