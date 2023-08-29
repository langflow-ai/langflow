from typing import Optional
from langflow import CustomComponent
from langchain.llms import HuggingFaceEndpoint

class HuggingFaceEndpointsComponent(CustomComponent):
    display_name: str = "Hugging Face Endpoints"
    description: str = "LLM model from Inference Hugging Face Endpoints."

    def build_config(self): 
        return {
            "endpoint_url": {"display_name": "Endpoint URL", "password": True},
            "task": {"display_name": "Task", "type": "select", "options": ["text2text-generation", "text-generation", "summarization"]},
            "code": {"show": False},
        }

    def build(
        self, endpoint_url: str, task="text2text-generation",
    ) -> HuggingFaceEndpoint:
        try:
            output = HuggingFaceEndpoint(endpoint_url=endpoint_url, task=task)
        except Exception as e:
            raise ValueError("Could not connect to HuggingFace Endpoints API.") from e
        return output
