from typing import Optional
from langflow import CustomComponent
from langchain.llms.huggingface_endpoint import HuggingFaceEndpoint
from langchain_community.chat_models.huggingface import ChatHuggingFace
from langflow.field_typing import Text


class HuggingFaceEndpointsComponent(CustomComponent):
    display_name: str = "Hugging Face Inference API models"
    description: str = "Generate text using LLM model from Hugging Face Inference API."

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
            "inputs": {"display_name": "Input"},
        }

    def build(
        self,
        inputs: str,
        endpoint_url: str,
        task: str = "text2text-generation",
        huggingfacehub_api_token: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
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
        message = output.invoke(inputs)
        result = message.content if hasattr(message, "content") else message
        self.status = result
        return result

