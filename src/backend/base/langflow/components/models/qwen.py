from langchain_community.llms.tongyi import Tongyi

from langflow.base.models.model import LCModelComponent
from langflow.base.models.qwen_constants import QWEN_MODEL_NAMES
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import DropdownInput, SecretStrInput, SliderInput, StrInput


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
        SliderInput(name="top_p", display_name="top_p", value=0.1, range_spec=RangeSpec(min=0, max=1, step=0.01)),
    ]

    def build_model(self) -> LanguageModel:
        """Build the Qwen model."""
        qwen_url = self.qwen_url
        qwen_api_key = self.qwen_api_key
        model_name = self.model_name
        top_p = self.top_p

        self.model = Tongyi(base_url=qwen_url, api_key=qwen_api_key, model=model_name, top_p=top_p)
        return self.model
