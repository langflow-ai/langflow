from typing import Optional

from langchain_community.chat_models.huggingface import ChatHuggingFace
from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text


class HuggingFaceEndpointsComponent(LCModelComponent):
    display_name: str = "Hugging Face API"
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
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
            },
        }

    def build(
        self,
        input_value: Text,
        endpoint_url: str,
        model: Optional[str] = None,
        task: str = "text2text-generation",
        huggingfacehub_api_token: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
        stream: bool = False,
        system_message: Optional[str] = None,
    ) -> Text:
        try:
            llm = HuggingFaceEndpoint(  # type: ignore
                endpoint_url=endpoint_url,
                task=task,
                huggingfacehub_api_token=huggingfacehub_api_token,
                model_kwargs=model_kwargs or {},
                model=model or "",
            )
        except Exception as e:
            raise ValueError("Could not connect to HuggingFace Endpoints API.") from e
        output = ChatHuggingFace(llm=llm)
        return self.get_chat_result(output, stream, input_value, system_message)
