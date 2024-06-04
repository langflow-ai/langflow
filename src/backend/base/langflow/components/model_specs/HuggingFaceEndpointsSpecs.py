from typing import Optional

from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel


class HuggingFaceEndpointsComponent(CustomComponent):
    display_name: str = "Hugging Face Inference API"
    description: str = "LLM model from Hugging Face Inference API."
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
        }

    def build(
        self,
        endpoint_url: str,
        task: str = "text2text-generation",
        huggingfacehub_api_token: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
    ) -> BaseLanguageModel:
        try:
            output = HuggingFaceEndpoint(  # type: ignore
                endpoint_url=endpoint_url,
                task=task,
                huggingfacehub_api_token=huggingfacehub_api_token,
                model_kwargs=model_kwargs or {},
            )
        except Exception as e:
            raise ValueError("Could not connect to HuggingFace Endpoints API.") from e
        return output
