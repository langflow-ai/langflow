from typing import Optional

from langchain_community.chat_models.litellm import ChatLiteLLM, ChatLiteLLMException

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageInput,
    Output,
    SecretStrInput,
    StrInput,
)


class ChatLiteLLMModelComponent(LCModelComponent):
    display_name = "LiteLLM"
    description = "`LiteLLM` collection of large language models."
    documentation = "https://python.langchain.com/docs/integrations/chat/litellm"
    icon = "🚄"

    inputs = [
        MessageInput(name="input_value", display_name="Input"),
        StrInput(
            name="model",
            display_name="Model name",
            advanced=False,
            required=True,
            info="The name of the model to use. For example, `gpt-3.5-turbo`.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API key",
            advanced=False,
            required=False,
        ),
        DropdownInput(
            name="provider",
            display_name="Provider",
            info="The provider of the API key.",
            options=[
                "OpenAI",
                "Azure",
                "Anthropic",
                "Replicate",
                "Cohere",
                "OpenRouter",
            ],
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            advanced=False,
            required=False,
            value=0.7,
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model kwargs",
            advanced=True,
            required=False,
            value={},
        ),
        FloatInput(
            name="top_p",
            display_name="Top p",
            advanced=True,
            required=False,
        ),
        IntInput(
            name="top_k",
            display_name="Top k",
            advanced=True,
            required=False,
        ),
        IntInput(
            name="n",
            display_name="N",
            advanced=True,
            required=False,
            info="Number of chat completions to generate for each prompt. "
            "Note that the API may not return the full n completions if duplicates are generated.",
            value=1,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max tokens",
            advanced=False,
            value=256,
            info="The maximum number of tokens to generate for each chat completion.",
        ),
        IntInput(
            name="max_retries",
            display_name="Max retries",
            advanced=True,
            required=False,
            value=6,
        ),
        BoolInput(
            name="verbose",
            display_name="Verbose",
            advanced=True,
            required=False,
            value=False,
        ),
        BoolInput(
            name="stream",
            display_name="Stream",
            info=STREAM_INFO_TEXT,
            advanced=True,
        ),
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

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            import litellm  # type: ignore

            litellm.drop_params = True
            litellm.set_verbose = self.verbose
        except ImportError:
            raise ChatLiteLLMException(
                "Could not import litellm python package. " "Please install it with `pip install litellm`"
            )

        provider_map = {
            "OpenAI": "openai_api_key",
            "Azure": "azure_api_key",
            "Anthropic": "anthropic_api_key",
            "Replicate": "replicate_api_key",
            "Cohere": "cohere_api_key",
            "OpenRouter": "openrouter_api_key",
        }

        # Set the API key based on the provider
        api_keys: dict[str, Optional[str]] = {v: None for v in provider_map.values()}

        if variable_name := provider_map.get(self.provider):
            api_keys[variable_name] = self.api_key
        else:
            raise ChatLiteLLMException(
                f"Provider {self.provider} is not supported. Supported providers are: {', '.join(provider_map.keys())}"
            )

        output = ChatLiteLLM(
            model=self.model,
            client=None,
            streaming=self.stream,
            temperature=self.temperature,
            model_kwargs=self.model_kwargs if self.model_kwargs is not None else {},
            top_p=self.top_p,
            top_k=self.top_k,
            n=self.n,
            max_tokens=self.max_tokens,
            max_retries=self.max_retries,
            openai_api_key=api_keys["openai_api_key"],
            azure_api_key=api_keys["azure_api_key"],
            anthropic_api_key=api_keys["anthropic_api_key"],
            replicate_api_key=api_keys["replicate_api_key"],
            cohere_api_key=api_keys["cohere_api_key"],
            openrouter_api_key=api_keys["openrouter_api_key"],
        )

        return output  # type: ignore
