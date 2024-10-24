from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import DropdownInput, FloatInput, IntInput, SecretStrInput
from langflow.inputs.inputs import HandleInput


class GoogleGenerativeAIComponent(LCModelComponent):
    display_name = "Google Generative AI"
    description = "Generate text using Google Generative AI."
    icon = "GoogleGenerativeAI"
    name = "GoogleGenerativeAIModel"

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_output_tokens", display_name="Max Output Tokens", info="The maximum number of tokens to generate."
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            info="The name of the model to use.",
            options=["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro", "gemini-1.0-pro-vision"],
            value="gemini-1.5-pro",
        ),
        SecretStrInput(
            name="google_api_key",
            display_name="Google API Key",
            info="The Google API Key to use for the Google Generative AI.",
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="The maximum cumulative probability of tokens to consider when sampling.",
            advanced=True,
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        IntInput(
            name="n",
            display_name="N",
            info="Number of chat completions to generate for each prompt. "
            "Note that the API may not return the full n completions if duplicates are generated.",
            advanced=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Decode using top-k sampling: consider the set of top_k most probable tokens. Must be positive.",
            advanced=True,
        ),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:
            msg = "The 'langchain_google_genai' package is required to use the Google Generative AI model."
            raise ImportError(msg) from e

        google_api_key = self.google_api_key
        model = self.model
        max_output_tokens = self.max_output_tokens
        temperature = self.temperature
        top_k = self.top_k
        top_p = self.top_p
        n = self.n

        return ChatGoogleGenerativeAI(
            model=model,
            max_output_tokens=max_output_tokens or None,
            temperature=temperature,
            top_k=top_k or None,
            top_p=top_p or None,
            n=n or 1,
            google_api_key=SecretStr(google_api_key).get_secret_value(),
        )
