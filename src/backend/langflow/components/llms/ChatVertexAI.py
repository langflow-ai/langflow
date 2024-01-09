
from langflow import CustomComponent
from typing import List
from langchain.messages import BaseMessage

class ChatVertexAIComponent(CustomComponent):
    display_name = "ChatVertexAI"
    description = "`Vertex AI` Chat large language models API."

    def build_config(self):
        return {
            "credentials": {
                "display_name": "Credentials",
                "type": "file",
                "fileTypes": ["json"],
                "file_path": None,
            },
            "examples": {
                "display_name": "Examples",
                "multiline": True,
            },
            "location": {
                "display_name": "Location",
                "default": "us-central1",
            },
            "max_output_tokens": {
                "display_name": "Max Output Tokens",
                "default": 128,
                "advanced": True,
            },
            "model_name": {
                "display_name": "Model Name",
                "default": "chat-bison",
            },
            "project": {
                "display_name": "Project",
            },
            "temperature": {
                "display_name": "Temperature",
                "default": 0.0,
            },
            "top_k": {
                "display_name": "Top K",
                "default": 40,
                "advanced": True,
            },
            "top_p": {
                "display_name": "Top P",
                "default": 0.95,
                "advanced": True,
            },
            "verbose": {
                "display_name": "Verbose",
                "default": False,
                "advanced": True,
            },
        }

    def build(
        self,
        credentials: str,
        examples: List[BaseMessage],
        project: str,
        location: str = "us-central1",
        max_output_tokens: int = 128,
        model_name: str = "chat-bison",
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        verbose: bool = False,
    ):
        # Assuming there is a ChatVertexAI class that takes these parameters
        return ChatVertexAI(
            credentials=credentials,
            examples=examples,
            location=location,
            max_output_tokens=max_output_tokens,
            model_name=model_name,
            project=project,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            verbose=verbose,
        )
