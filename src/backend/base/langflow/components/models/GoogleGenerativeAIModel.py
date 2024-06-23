from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import BoolInput, DropdownInput, FloatInput, IntInput, MessageInput, Output, SecretStrInput, StrInput


class GoogleGenerativeAIComponent(LCModelComponent):
    display_name: str = "Google Generative AI"
    description: str = "Generate text using Google Generative AI."
    icon = "GoogleGenerativeAI"

    inputs = [
        SecretStrInput(
            name="google_api_key",
            display_name="Google API Key",
            info="The Google API Key to use for the Google Generative AI.",
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            info="The name of the model to use.",
            options=["gemini-1.5-pro", "gemini-1.5-flash"],
            value="gemini-1.5-pro",
        ),
        IntInput(
            name="max_output_tokens",
            display_name="Max Output Tokens",
            info="The maximum number of tokens to generate.",
            advanced=True,
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            info="Run inference with this temperature. Must by in the closed interval [0.0, 1.0].",
            value=0.1,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Decode using top-k sampling: consider the set of top_k most probable tokens. Must be positive.",
            advanced=True,
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="The maximum cumulative probability of tokens to consider when sampling.",
            advanced=True,
        ),
        IntInput(
            name="n",
            display_name="N",
            info="Number of chat completions to generate for each prompt. Note that the API may not return the full n completions if duplicates are generated.",
            advanced=True,
        ),
        MessageInput(
            name="input_value",
            display_name="Input",
            info="The input to the model.",
            input_types=["Text", "Data", "Prompt"],
        ),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def build_model(self) -> LanguageModel:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("The 'langchain_google_genai' package is required to use the Google Generative AI model.")

        google_api_key = self.google_api_key
        model = self.model
        max_output_tokens = self.max_output_tokens
        temperature = self.temperature
        top_k = self.top_k
        top_p = self.top_p
        n = self.n

        output = ChatGoogleGenerativeAI(  # type: ignore
            model=model,
            max_output_tokens=max_output_tokens or None,
            temperature=temperature,
            top_k=top_k or None,
            top_p=top_p or None,
            n=n or 1,
            google_api_key=SecretStr(google_api_key),
        )

        return output
