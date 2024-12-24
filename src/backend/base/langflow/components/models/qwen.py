from typing import Optional

from langflow.base.models.model import LCModelComponent
from langflow.io import (
    IntInput,
    Output,
    SecretStrInput,
    FloatInput,
    StrInput,
    DropdownInput,
    SliderInput
)
from langflow.field_typing import LanguageModel
from langflow.base.models.qwen_constants import QWEN_MODEL_NAMES
from langflow.field_typing.range_spec import RangeSpec

from langchain_community.llms.tongyi import Tongyi


class QwenModelComponent(LCModelComponent):
    """Qwen (Tongyi) model component."""

    display_name: str = "Qwen"
    description: str = "This component generates text using Alibaba's Qwen (Tongyi) model."
    documentation: str = "https://help.aliyun.com/zh/dashscope/developer-reference/api-details"
    icon = "Qwen"
    name = "QwenModel"


    inputs = [
        *LCModelComponent._base_inputs,
        StrInput(
            name="qwen_url",
            display_name="Qwen Cloud Base Url",
            advanced=True,
            value="https://dashscope.aliyuncs.com/compatible-mode/v1",
            info="The base URL of the Qwen Cloud API. "
            "Defaults to https://dashscope.aliyuncs.com/compatible-mode/v1.",
        ),

        SecretStrInput(
            name="qwen_api_key",
            display_name="Qwen API Key",
            required=True,
            password=True,
        ),

         DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=QWEN_MODEL_NAMES,
            value=QWEN_MODEL_NAMES[0],
        ),

        # IntInput(
        #     name="max_tokens",
        #     display_name="Max Tokens",
        #     advanced=True,
        #     info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        #     range_spec=RangeSpec(min=0, max=128000),
        # ),
        # FloatInput(
        #     name="temperature",
        #     display_name="Temperature",
        #     default=0.7,
        #     info="Sampling temperature between 0 and 2",
        # ),

        # SliderInput(
        #     name="temperature", display_name="Temperature", value=0.1, range_spec=RangeSpec(min=0, max=2, step=0.01)
        # ),
        # IntInput(
        #     name="seed",
        #     display_name="Seed",
        #     info="The seed controls the reproducibility of the job.",
        #     advanced=True,
        #     value=1,
        # ),
    ]


    def build_model(self) -> LanguageModel:
        """Build the Qwen model."""
        qwen_url = self.qwen_url
        qwen_api_key = self.qwen_api_key
        model_name = self.model_name
        # max_tokens = self.max_tokens
        # temperature = self.temperature


        self.model = Tongyi(
            base_url=qwen_url,
            api_key=qwen_api_key,
            model=model_name,
            # max_tokens=max_tokens,
            # temperature=temperature,
        )
        return self.model
            
