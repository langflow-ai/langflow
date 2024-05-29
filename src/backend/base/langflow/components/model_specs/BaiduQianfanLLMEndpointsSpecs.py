from typing import Optional

from langchain_community.llms.baidu_qianfan_endpoint import QianfanLLMEndpoint

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel


class QianfanLLMEndpointComponent(CustomComponent):
    display_name: str = "QianfanLLMEndpoint"
    description: str = (
        "Baidu Qianfan hosted open source or customized models. "
        "Get more detail from https://python.langchain.com/docs/integrations/chat/baidu_qianfan_endpoint"
    )

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
        }

    def build(
        self,
        model: str = "ERNIE-Bot-turbo",
        qianfan_ak: Optional[str] = None,
        qianfan_sk: Optional[str] = None,
        top_p: Optional[float] = None,
        temperature: Optional[float] = None,
        penalty_score: Optional[float] = None,
        endpoint: Optional[str] = None,
    ) -> BaseLanguageModel:
        try:
            output = QianfanLLMEndpoint(  # type: ignore
                model=model,
                qianfan_ak=qianfan_ak,
                qianfan_sk=qianfan_sk,
                top_p=top_p,
                temperature=temperature,
                penalty_score=penalty_score,
                endpoint=endpoint,
            )
        except Exception as e:
            raise ValueError("Could not connect to Baidu Qianfan API.") from e
        return output  # type: ignore
