from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    SecretStrInput,
    SliderInput,
    StrInput,
)
from lfx.utils.ssrf_httpx import ssrf_protected_openai_clients_for_url
from pydantic.v1 import SecretStr

# Models served by the iFlytek Spark OpenAI-compatible HTTP endpoint.
IFLYTEK_SPARK_MODELS = [
    "4.0Ultra",
    "generalv3.5",
    "max-32k",
    "generalv3",
    "pro-128k",
    "lite",
]
IFLYTEK_SPARK_MAX_OUTPUT_TOKENS = {
    "4.0Ultra": 32_768,
    "generalv3.5": 8_192,
    "max-32k": 32_768,
    "generalv3": 8_192,
    "pro-128k": 32_768,
    "lite": 4_096,
}
IFLYTEK_SPARK_BASE_URL = "https://spark-api-open.xf-yun.com/v1"


class IFlytekSparkComponent(LCModelComponent):
    """iFlytek Spark component for language models."""

    display_name = "IFlytek Spark"
    description = "Generate text using iFlytek Spark LLMs through the OpenAI-compatible HTTP API."
    icon = "IFlytek"
    name = "IFlytekSparkModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="Maximum number of tokens to generate. Set to 0 to use the model default.",
            range_spec=RangeSpec(min=0, max=max(IFLYTEK_SPARK_MAX_OUTPUT_TOKENS.values())),
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=IFLYTEK_SPARK_MODELS,
            value=IFLYTEK_SPARK_MODELS[0],
        ),
        StrInput(
            name="api_base",
            display_name="Spark API Base",
            advanced=True,
            info="Base URL for the OpenAI-compatible Spark HTTP endpoint.",
            value=IFLYTEK_SPARK_BASE_URL,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Spark API Password",
            info="The HTTP service API password, used as the Bearer token.",
            advanced=False,
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness in responses.",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
    ]

    def _validated_max_tokens(self) -> int | None:
        max_tokens = self.max_tokens or None
        if max_tokens is None:
            return None

        model_limit = IFLYTEK_SPARK_MAX_OUTPUT_TOKENS[self.model_name]
        if max_tokens > model_limit:
            msg = f"{self.model_name} supports at most {model_limit} output tokens."
            raise ValueError(msg)
        return max_tokens

    def build_model(self) -> LanguageModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            msg = "langchain-openai not installed. Please install with `pip install langchain-openai`"
            raise ImportError(msg) from e

        api_key = SecretStr(self.api_key).get_secret_value() if self.api_key else None
        ssrf_client_kwargs = ssrf_protected_openai_clients_for_url(self.api_base)

        output = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature if self.temperature is not None else 0.1,
            max_tokens=self._validated_max_tokens(),
            model_kwargs=self.model_kwargs or {},
            base_url=self.api_base,
            api_key=api_key,
            streaming=self.stream if hasattr(self, "stream") else False,
            **ssrf_client_kwargs,
        )

        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output
