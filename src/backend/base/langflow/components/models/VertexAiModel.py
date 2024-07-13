from langchain_google_vertexai import ChatVertexAI

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import BoolInput, FileInput, FloatInput, IntInput, MessageInput, MultilineInput, StrInput


class ChatVertexAIComponent(LCModelComponent):
    display_name = "Vertex AI"
    description = "Generate text using Vertex AI LLMs."
    icon = "VertexAI"
    name = "VertexAiModel"

    inputs = [
        MessageInput(name="input_value", display_name="Input"),
        FileInput(
            name="credentials",
            display_name="Credentials",
            info="Path to the JSON file containing the credentials.",
            file_types=["json"],
            advanced=True,
        ),
        StrInput(name="project", display_name="Project", info="The project ID."),
        MultilineInput(
            name="examples",
            display_name="Examples",
            info="Examples to pass to the model.",
            advanced=True,
        ),
        StrInput(name="location", display_name="Location", value="us-central1", advanced=True),
        IntInput(
            name="max_output_tokens",
            display_name="Max Output Tokens",
            value=128,
            advanced=True,
        ),
        StrInput(name="model_name", display_name="Model Name", value="gemini-1.5-pro"),
        FloatInput(name="temperature", display_name="Temperature", value=0.0),
        IntInput(name="top_k", display_name="Top K", value=40, advanced=True),
        FloatInput(name="top_p", display_name="Top P", value=0.95, advanced=True),
        BoolInput(name="verbose", display_name="Verbose", value=False, advanced=True),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        credentials = self.credentials
        location = self.location
        max_output_tokens = self.max_output_tokens
        model_name = self.model_name
        project = self.project
        temperature = self.temperature
        top_k = self.top_k
        top_p = self.top_p
        verbose = self.verbose

        output = ChatVertexAI(
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

        return output  # type: ignore
