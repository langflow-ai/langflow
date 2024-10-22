from langchain_community.chat_models.baidu_qianfan_endpoint import QianfanChatEndpoint
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing.constants import LanguageModel
from langflow.inputs.inputs import HandleInput
from langflow.io import DropdownInput, FloatInput, MessageTextInput, SecretStrInput


class QianfanChatEndpointComponent(LCModelComponent):
    display_name: str = "Qianfan"
    description: str = "Generate text using Baidu Qianfan LLMs."
    documentation: str = "https://python.langchain.com/docs/integrations/chat/baidu_qianfan_endpoint"
    icon = "BaiduQianfan"
    name = "BaiduQianfanChatModel"

    inputs = [
        *LCModelComponent._base_inputs,
        DropdownInput(
            name="model",
            display_name="Model Name",
            options=[
                "ERNIE-Bot",
                "ERNIE-Bot-turbo",
                "BLOOMZ-7B",
                "Llama-2-7b-chat",
                "Llama-2-13b-chat",
                "Llama-2-70b-chat",
                "Qianfan-BLOOMZ-7B-compressed",
                "Qianfan-Chinese-Llama-2-7B",
                "ChatGLM2-6B-32K",
                "AquilaChat-7B",
            ],
            info="https://python.langchain.com/docs/integrations/chat/baidu_qianfan_endpoint",
            value="ERNIE-Bot-turbo",
        ),
        SecretStrInput(
            name="qianfan_ak",
            display_name="Qianfan Ak",
            info="which you could get from  https://cloud.baidu.com/product/wenxinworkshop",
        ),
        SecretStrInput(
            name="qianfan_sk",
            display_name="Qianfan Sk",
            info="which you could get from  https://cloud.baidu.com/product/wenxinworkshop",
        ),
        FloatInput(
            name="top_p",
            display_name="Top p",
            info="Model params, only supported in ERNIE-Bot and ERNIE-Bot-turbo",
            value=0.8,
            advanced=True,
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            info="Model params, only supported in ERNIE-Bot and ERNIE-Bot-turbo",
            value=0.95,
        ),
        FloatInput(
            name="penalty_score",
            display_name="Penalty Score",
            info="Model params, only supported in ERNIE-Bot and ERNIE-Bot-turbo",
            value=1.0,
            advanced=True,
        ),
        MessageTextInput(
            name="endpoint", display_name="Endpoint", info="Endpoint of the Qianfan LLM, required if custom model used."
        ),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        model = self.model
        qianfan_ak = self.qianfan_ak
        qianfan_sk = self.qianfan_sk
        top_p = self.top_p
        temperature = self.temperature
        penalty_score = self.penalty_score
        endpoint = self.endpoint

        try:
            output = QianfanChatEndpoint(
                model=model,
                qianfan_ak=SecretStr(qianfan_ak).get_secret_value() if qianfan_ak else None,
                qianfan_sk=SecretStr(qianfan_sk).get_secret_value() if qianfan_sk else None,
                top_p=top_p,
                temperature=temperature,
                penalty_score=penalty_score,
                endpoint=endpoint,
            )
        except Exception as e:
            msg = "Could not connect to Baidu Qianfan API."
            raise ValueError(msg) from e

        return output
