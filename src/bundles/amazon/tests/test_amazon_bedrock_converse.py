"""Regression test: the Top K input must reach the constructed ChatBedrockConverse model."""

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
