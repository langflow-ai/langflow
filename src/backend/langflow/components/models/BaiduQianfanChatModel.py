from typing import Optional

from langchain_community.chat_models.baidu_qianfan_endpoint import QianfanChatEndpoint
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text


class QianfanChatEndpointComponent(LCModelComponent):
    display_name: str = "QianfanChat"
    description: str = (
        "Generate text using Baidu Qianfan chat models. Get more detail from "
        "https://python.langchain.com/docs/integrations/chat/baidu_qianfan_endpoint."
    )
    icon = "BaiduQianfan"

    def build_config(self):
        return {
            "model": {
                "display_name": "Model Name",
                "options": [
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
                "info": "https://python.langchain.com/docs/integrations/chat/baidu_qianfan_endpoint",
                "required": True,
            },
            "qianfan_ak": {
                "display_name": "Qianfan Ak",
                "required": True,
                "password": True,
                "info": "which you could get from  https://cloud.baidu.com/product/wenxinworkshop",
            },
            "qianfan_sk": {
                "display_name": "Qianfan Sk",
                "required": True,
                "password": True,
                "info": "which you could get from  https://cloud.baidu.com/product/wenxinworkshop",
            },
            "top_p": {
                "display_name": "Top p",
                "field_type": "float",
                "info": "Model params, only supported in ERNIE-Bot and ERNIE-Bot-turbo",
                "value": 0.8,
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "info": "Model params, only supported in ERNIE-Bot and ERNIE-Bot-turbo",
                "value": 0.95,
            },
            "penalty_score": {
                "display_name": "Penalty Score",
                "field_type": "float",
                "info": "Model params, only supported in ERNIE-Bot and ERNIE-Bot-turbo",
                "value": 1.0,
            },
            "endpoint": {
                "display_name": "Endpoint",
                "info": "Endpoint of the Qianfan LLM, required if custom model used.",
            },
            "code": {"show": False},
            "input_value": {"display_name": "Input"},
            "stream": {
                "display_name": "Stream",
                "info": "Stream the response from the model.",
            },
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
            },
        }

    def build(
        self,
        input_value: Text,
        model: str = "ERNIE-Bot-turbo",
        qianfan_ak: Optional[str] = None,
        qianfan_sk: Optional[str] = None,
        top_p: Optional[float] = None,
        temperature: Optional[float] = None,
        penalty_score: Optional[float] = None,
        endpoint: Optional[str] = None,
        stream: bool = False,
        system_message: Optional[str] = None,
    ) -> Text:
        try:
            output = QianfanChatEndpoint(  # type: ignore
                model=model,
                qianfan_ak=SecretStr(qianfan_ak) if qianfan_ak else None,
                qianfan_sk=SecretStr(qianfan_sk) if qianfan_sk else None,
                top_p=top_p,
                temperature=temperature,
                penalty_score=penalty_score,
                endpoint=endpoint,
            )
        except Exception as e:
            raise ValueError("Could not connect to Baidu Qianfan API.") from e

        return self.get_chat_result(output, stream, input_value, system_message)
