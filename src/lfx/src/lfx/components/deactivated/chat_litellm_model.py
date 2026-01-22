from langchain_community.chat_models.litellm import ChatLiteLLM, ChatLiteLLMException

from lfx.base.constants import STREAM_INFO_TEXT
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageInput,
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
            display_name="Chat LiteLLM API Key",
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
            name="kwargs",
            display_name="Kwargs",
            advanced=True,
            required=False,
            is_list=True,
            value={},
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model kwargs",
            advanced=True,
            required=False,
            is_list=True,
            value={},
        ),
        FloatInput(name="top_p", display_name="Top p", advanced=True, required=False, value=0.5),
        IntInput(name="top_k", display_name="Top k", advanced=True, required=False, value=35),
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

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            import litellm

            litellm.drop_params = True
            litellm.set_verbose = self.verbose
        except ImportError as e:
            msg = "Could not import litellm python package. Please install it with `pip install litellm`"
            raise ChatLiteLLMException(msg) from e
        # Remove empty keys
        if "" in self.kwargs:
            del self.kwargs[""]
        if "" in self.model_kwargs:
            del self.model_kwargs[""]
        # Report missing fields for Azure provider
        if self.provider == "Azure":
            if "api_base" not in self.kwargs:
                msg = "Missing api_base on kwargs"
                raise ValueError(msg)
            if "api_version" not in self.model_kwargs:
                msg = "Missing api_version on model_kwargs"
                raise ValueError(msg)
        output = ChatLiteLLM(
            model=f"{self.provider.lower()}/{self.model}",
            client=None,
            streaming=self.stream,
            temperature=self.temperature,
            model_kwargs=self.model_kwargs if self.model_kwargs is not None else {},
            top_p=self.top_p,
            top_k=self.top_k,
            n=self.n,
            max_tokens=self.max_tokens,
            max_retries=self.max_retries,
            **self.kwargs,
        )
        output.client.api_key = self.api_key

        return output
