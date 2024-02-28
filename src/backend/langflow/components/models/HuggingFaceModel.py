from typing import Optional

from langchain_community.chat_models.huggingface import ChatHuggingFace
from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint

from langflow.components.models.base.model import LCModelComponent
from langflow.field_typing import Text


class HuggingFaceEndpointsComponent(LCModelComponent):
    display_name: str = "Hugging Face Inference API models"
    description: str = "Generate text using LLM model from Hugging Face Inference API."
    icon = "HuggingFace"

    def build_config(self):
        return {
            "endpoint_url": {"display_name": "Endpoint URL", "password": True},
            "task": {
                "display_name": "Task",
                "options": ["text2text-generation", "text-generation", "summarization"],
            },
            "huggingfacehub_api_token": {"display_name": "API token", "password": True},
            "model_kwargs": {
                "display_name": "Model Keyword Arguments",
                "field_type": "code",
            },
            "code": {"show": False},
            "input_value": {"display_name": "Input"},
            "stream": {
                "display_name": "Stream",
                "info": "Stream the response from the model.",
            },
        }

    def build(
        self,
        input_value: str,
        endpoint_url: str,
        task: str = "text2text-generation",
        huggingfacehub_api_token: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
        stream: bool = False,
    ) -> Text:
        try:
            llm = HuggingFaceEndpoint(
                endpoint_url=endpoint_url,
                task=task,
                huggingfacehub_api_token=huggingfacehub_api_token,
                model_kwargs=model_kwargs,
            )
        except Exception as e:
            raise ValueError("Could not connect to HuggingFace Endpoints API.") from e
        output = ChatHuggingFace(llm=llm)
        return self.get_result(output=output, stream=stream, input_value=input_value)
