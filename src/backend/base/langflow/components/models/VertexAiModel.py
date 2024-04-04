from typing import List, Optional

from langchain_core.messages.base import BaseMessage

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text


class ChatVertexAIComponent(LCModelComponent):
    display_name = "Vertex AI"
    description = "Generate text using Vertex AI LLMs."
    icon = "VertexAI"

    field_order = [
        "credentials",
        "project",
        "examples",
        "location",
        "max_output_tokens",
        "model_name",
        "temperature",
        "top_k",
        "top_p",
        "verbose",
        "input_value",
        "system_message",
        "stream",
    ]

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
            "input_value": {"display_name": "Input"},
            "stream": {
                "display_name": "Stream",
                "info": STREAM_INFO_TEXT,
                "advanced": True,
            },
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "advanced": True,
            },
        }

    def build(
        self,
        input_value: Text,
        credentials: Optional[str],
        project: str,
        examples: Optional[List[BaseMessage]] = [],
        location: str = "us-central1",
        max_output_tokens: int = 128,
        model_name: str = "chat-bison",
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        verbose: bool = False,
        stream: bool = False,
        system_message: Optional[str] = None,
    ) -> Text:
        try:
            from langchain_google_vertexai import ChatVertexAI  # type: ignore
        except ImportError:
            raise ImportError(
                "To use the ChatVertexAI model, you need to install the langchain-google-vertexai package."
            )
        output = ChatVertexAI(
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

        return self.get_chat_result(output, stream, input_value, system_message)
