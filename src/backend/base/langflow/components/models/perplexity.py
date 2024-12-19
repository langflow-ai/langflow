from langchain_community.chat_models import ChatPerplexity
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import DropdownInput, FloatInput, IntInput, SecretStrInput


class PerplexityComponent(LCModelComponent):
    display_name = "Perplexity"
    description = "Generate text using Perplexity LLMs."
    documentation = "https://python.langchain.com/v0.2/docs/integrations/chat/perplexity/"
    icon = "Perplexity"
    name = "PerplexityModel"

    inputs = [
        *LCModelComponent._base_inputs,
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=[
                "llama-3.1-sonar-small-128k-online",
                "llama-3.1-sonar-large-128k-online",
                "llama-3.1-sonar-huge-128k-online",
                "llama-3.1-sonar-small-128k-chat",
                "llama-3.1-sonar-large-128k-chat",
                "llama-3.1-8b-instruct",
                "llama-3.1-70b-instruct",
            ],
            value="llama-3.1-sonar-small-128k-online",
        ),
        IntInput(
            name="max_output_tokens", display_name="Max Output Tokens", info="The maximum number of tokens to generate."
        ),
        SecretStrInput(
            name="api_key",
            display_name="Perplexity API Key",
            info="The Perplexity API Key to use for the Perplexity model.",
            advanced=False,
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.75),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="The maximum cumulative probability of tokens to consider when sampling.",
            advanced=True,
        ),
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
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        api_key = SecretStr(self.api_key).get_secret_value()
        temperature = self.temperature
        model = self.model_name
        max_output_tokens = self.max_output_tokens
        top_k = self.top_k
        top_p = self.top_p
        n = self.n

        return ChatPerplexity(
            model=model,
            temperature=temperature or 0.75,
            pplx_api_key=api_key,
            top_k=top_k or None,
            top_p=top_p or None,
            n=n or 1,
            max_output_tokens=max_output_tokens,
        )
