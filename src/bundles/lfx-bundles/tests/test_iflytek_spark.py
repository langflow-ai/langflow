import pytest

from lfx_bundles.iflytek.iflytek_spark import (
    IFLYTEK_SPARK_MAX_OUTPUT_TOKENS,
    IFlytekSparkComponent,
)


@pytest.mark.parametrize(("model_name", "model_limit"), IFLYTEK_SPARK_MAX_OUTPUT_TOKENS.items())
def test_accepts_each_iflytek_model_output_limit(model_name, model_limit):
    component = IFlytekSparkComponent(model_name=model_name, max_tokens=model_limit)

    assert component._validated_max_tokens() == model_limit


@pytest.mark.parametrize(("model_name", "model_limit"), IFLYTEK_SPARK_MAX_OUTPUT_TOKENS.items())
def test_rejects_output_tokens_above_each_iflytek_model_limit(model_name, model_limit):
    component = IFlytekSparkComponent(model_name=model_name, max_tokens=model_limit + 1)

    with pytest.raises(
        ValueError,
        match=rf"^{model_name} supports at most {model_limit} output tokens\.$",
    ):
        component._validated_max_tokens()


def test_zero_output_tokens_uses_iflytek_model_default():
    component = IFlytekSparkComponent(model_name="4.0Ultra", max_tokens=0)

    assert component._validated_max_tokens() is None
