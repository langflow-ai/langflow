from typing import Optional

from langchain_community.chat_models.vertexai import ChatVertexAI

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel


class ChatVertexAIComponent(CustomComponent):
    display_name = "ChatVertexAI"
    description = "`Vertex AI` Chat large language models API."
    icon = "VertexAI"

    def build_config(self):
        return {
            "credentials": {
                "display_name": "Credentials",
                "field_type": "file",
                "file_types": [".json"],
                "file_path": None,
            },
            "examples": {
                "display_name": "Examples",
                "multiline": True,
            },
            "location": {
                "display_name": "Location",
                "value": "us-central1",
            },
            "max_output_tokens": {
                "display_name": "Max Output Tokens",
                "value": 128,
                "advanced": True,
            },
            "model_name": {
                "display_name": "Model Name",
                "value": "chat-bison",
            },
            "project": {
                "display_name": "Project",
            },
            "temperature": {
                "display_name": "Temperature",
                "value": 0.0,
            },
            "top_k": {
                "display_name": "Top K",
                "value": 40,
                "advanced": True,
            },
            "top_p": {
                "display_name": "Top P",
                "value": 0.95,
                "advanced": True,
            },
            "verbose": {
                "display_name": "Verbose",
                "value": False,
                "advanced": True,
            },
        }

    def build(
        self,
        credentials: Optional[str],
        project: str,
        location: str = "us-central1",
        max_output_tokens: int = 128,
        model_name: str = "chat-bison",
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        verbose: bool = False,
    ) -> BaseLanguageModel:
        return ChatVertexAI(
            credentials=credentials,
            location=location,
            max_output_tokens=max_output_tokens,
            model_name=model_name,
            project=project,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            verbose=verbose,
        )
