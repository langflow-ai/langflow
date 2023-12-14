from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore

from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel, RangeSpec, TemplateField


class GoogleGenerativeAIComponent(CustomComponent):
    display_name: str = "Google Generative AI"
    description: str = "A component that uses Google Generative AI to generate text."
    documentation: str = "http://docs.langflow.org/components/custom"

    def build_config(self):
        return {
            "google_api_key": TemplateField(
                display_name="Google API Key",
                info="The Google API Key to use for the Google Generative AI.",
            ),
            "max_output_tokens": TemplateField(
                display_name="Max Output Tokens",
                info="The maximum number of tokens to generate.",
            ),
            "temperature": TemplateField(
                display_name="Temperature",
                info="Run inference with this temperature. Must by in the closed interval [0.0, 1.0].",
            ),
            "top_k": TemplateField(
                display_name="Top K",
                info="Decode using top-k sampling: consider the set of top_k most probable tokens. Must be positive.",
                range_spec=RangeSpec(min=0, max=2, step=0.1),
                advanced=True,
            ),
            "top_p": TemplateField(
                display_name="Top P",
                info="The maximum cumulative probability of tokens to consider when sampling.",
                advanced=True,
            ),
            "n": TemplateField(
                display_name="N",
                info="Number of chat completions to generate for each prompt. Note that the API may not return the full n completions if duplicates are generated.",
                advanced=True,
            ),
            "model": TemplateField(
                display_name="Model",
                info="The name of the model to use. Supported examples: gemini-pro",
                options=["gemini-pro", "gemini-pro-vision"],
            ),
            "code": TemplateField(
                advanced=True,
            ),
        }

    def build(
        self,
        google_api_key: str,
        model: str,
        max_output_tokens: Optional[int] = None,
        temperature: float = 0.1,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = 1,
    ) -> BaseLanguageModel:
        return ChatGoogleGenerativeAI(
            model=model,
            max_output_tokens=max_output_tokens or None,
            temperature=temperature,
            top_k=top_k or None,
            top_p=top_p or None,
            n=n or 1,
            google_api_key=google_api_key,
        )
