from typing import Dict, Optional

from langflow.field_typing import BaseLanguageModel
from langchain_community.llms.vertexai import VertexAI

from langflow.interface.custom.custom_component import CustomComponent


class VertexAIComponent(CustomComponent):
    display_name = "VertexAI"
    description = "Google Vertex AI large language models"
    icon = "VertexAI"

    def build_config(self):
        return {
            "credentials": {
                "display_name": "Credentials",
                "field_type": "file",
                "file_types": [".json"],
                "required": False,
                "value": None,
            },
            "location": {
                "display_name": "Location",
                "type": "str",
                "advanced": True,
                "value": "us-central1",
                "required": False,
            },
            "max_output_tokens": {
                "display_name": "Max Output Tokens",
                "field_type": "int",
                "value": 128,
                "required": False,
                "advanced": True,
            },
            "max_retries": {
                "display_name": "Max Retries",
                "type": "int",
                "value": 6,
                "required": False,
                "advanced": True,
            },
            "metadata": {
                "display_name": "Metadata",
                "field_type": "dict",
                "required": False,
                "default": {},
            },
            "model_name": {
                "display_name": "Model Name",
                "type": "str",
                "value": "text-bison",
                "required": False,
            },
            "n": {
                "advanced": True,
                "display_name": "N",
                "field_type": "int",
                "value": 1,
                "required": False,
            },
            "project": {
                "display_name": "Project",
                "type": "str",
                "required": False,
                "default": None,
            },
            "request_parallelism": {
                "display_name": "Request Parallelism",
                "field_type": "int",
                "value": 5,
                "required": False,
                "advanced": True,
            },
            "streaming": {
                "display_name": "Streaming",
                "field_type": "bool",
                "value": False,
                "required": False,
                "advanced": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "value": 0.0,
                "required": False,
                "advanced": True,
            },
            "top_k": {"display_name": "Top K", "type": "int", "default": 40, "required": False, "advanced": True},
            "top_p": {
                "display_name": "Top P",
                "field_type": "float",
                "value": 0.95,
                "required": False,
                "advanced": True,
            },
            "tuned_model_name": {
                "display_name": "Tuned Model Name",
                "type": "str",
                "required": False,
                "value": None,
                "advanced": True,
            },
            "verbose": {
                "display_name": "Verbose",
                "field_type": "bool",
                "value": False,
                "required": False,
            },
            "name": {"display_name": "Name", "field_type": "str"},
        }

    def build(
        self,
        credentials: Optional[str] = None,
        location: str = "us-central1",
        max_output_tokens: int = 128,
        max_retries: int = 6,
        metadata: Dict = {},
        model_name: str = "text-bison",
        n: int = 1,
        name: Optional[str] = None,
        project: Optional[str] = None,
        request_parallelism: int = 5,
        streaming: bool = False,
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        tuned_model_name: Optional[str] = None,
        verbose: bool = False,
    ) -> BaseLanguageModel:
        return VertexAI(
            credentials=credentials,
            location=location,
            max_output_tokens=max_output_tokens,
            max_retries=max_retries,
            metadata=metadata,
            model_name=model_name,
            n=n,
            name=name,
            project=project,
            request_parallelism=request_parallelism,
            streaming=streaming,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            tuned_model_name=tuned_model_name,
            verbose=verbose,
        )
