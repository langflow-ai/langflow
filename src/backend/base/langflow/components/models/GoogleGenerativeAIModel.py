from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import RangeSpec, Text


class GoogleGenerativeAIComponent(LCModelComponent):
    display_name: str = "Google Generative AI"
    description: str = "Generate text using Google Generative AI to generate text."
    icon = "GoogleGenerativeAI"
    icon = "Google"

    def build_config(self):
        return {
            "google_api_key": {
                "display_name": "Google API Key",
                "info": "The Google API Key to use for the Google Generative AI.",
            },
            "max_output_tokens": {
                "display_name": "Max Output Tokens",
                "info": "The maximum number of tokens to generate.",
            },
            "temperature": {
                "display_name": "Temperature",
                "info": "Run inference with this temperature. Must by in the closed interval [0.0, 1.0].",
            },
            "top_k": {
                "display_name": "Top K",
                "info": "Decode using top-k sampling: consider the set of top_k most probable tokens. Must be positive.",
                "range_spec": RangeSpec(min=0, max=2, step=0.1),
                "advanced": True,
            },
            "top_p": {
                "display_name": "Top P",
                "info": "The maximum cumulative probability of tokens to consider when sampling.",
                "advanced": True,
            },
            "n": {
                "display_name": "N",
                "info": "Number of chat completions to generate for each prompt. Note that the API may not return the full n completions if duplicates are generated.",
                "advanced": True,
            },
            "model": {
                "display_name": "Model",
                "info": "The name of the model to use. Supported examples: gemini-pro",
                "options": ["gemini-pro", "gemini-pro-vision"],
            },
            "code": {
                "advanced": True,
            },
            "input_value": {"display_name": "Input", "info": "The input to the model."},
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
        google_api_key: str,
        model: str,
        input_value: Text,
        max_output_tokens: Optional[int] = None,
        temperature: float = 0.1,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = 1,
        stream: bool = False,
        system_message: Optional[str] = None,
    ) -> Text:
        output = ChatGoogleGenerativeAI(
            model=model,
            max_output_tokens=max_output_tokens or None,  # type: ignore
            temperature=temperature,
            top_k=top_k or None,
            top_p=top_p or None,  # type: ignore
            n=n or 1,
            google_api_key=SecretStr(google_api_key),
        )
        return self.get_chat_result(output, stream, input_value, system_message)
