import os
from typing import Any, Callable, Dict, Optional, Union

from langchain_community.chat_models.litellm import ChatLiteLLM, ChatLiteLLMException
from langflow import CustomComponent
from langflow.field_typing import BaseLanguageModel


class ChatLiteLLMComponent(CustomComponent):
    display_name = "ChatLiteLLM"
    description = "`LiteLLM` collection of large language models."
    documentation = "https://python.langchain.com/docs/integrations/chat/litellm"

    def build_config(self):
        return {
            "model": {
                "display_name": "Model name",
                "field_type": "str",
                "advanced": False,
                "required": True,
                "info": "The name of the model to use. For example, `gpt-3.5-turbo`.",
            },
            "api_key": {
                "display_name": "API key",
                "field_type": "str",
                "advanced": False,
                "required": False,
                "password": True,
            },
            "streaming": {
                "display_name": "Streaming",
                "field_type": "bool",
                "advanced": True,
                "required": False,
                "default": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "advanced": False,
                "required": False,
                "default": 0.7,
            },
            "model_kwargs": {
                "display_name": "Model kwargs",
                "field_type": "dict",
                "advanced": True,
                "required": False,
                "default": {},
            },
            "top_p": {
                "display_name": "Top p",
                "field_type": "float",
                "advanced": True,
                "required": False,
            },
            "top_k": {
                "display_name": "Top k",
                "field_type": "int",
                "advanced": True,
                "required": False,
            },
            "n": {
                "display_name": "N",
                "field_type": "int",
                "advanced": True,
                "required": False,
                "info": "Number of chat completions to generate for each prompt. "
                "Note that the API may not return the full n completions if duplicates are generated.",
                "default": 1,
            },
            "max_tokens": {
                "display_name": "Max tokens",
                "field_type": "int",
                "advanced": False,
                "required": False,
                "default": 256,
                "info": "The maximum number of tokens to generate for each chat completion.",
            },
            "max_retries": {
                "display_name": "Max retries",
                "field_type": "int",
                "advanced": True,
                "required": False,
                "default": 6,
            },
            "verbose": {
                "display_name": "Verbose",
                "field_type": "bool",
                "advanced": True,
                "required": False,
                "default": False,
            },
        }

    def build(
        self,
        model: str,
        api_key: str,
        streaming: bool = True,
        temperature: Optional[float] = 0.7,
        model_kwargs: Optional[Dict[str, Any]] = {},
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        n: int = 1,
        max_tokens: int = 256,
        max_retries: int = 6,
        verbose: bool = False,
    ) -> Union[BaseLanguageModel, Callable]:
        try:
            import litellm  # type: ignore

            litellm.drop_params = True
            litellm.set_verbose = verbose
        except ImportError:
            raise ChatLiteLLMException(
                "Could not import litellm python package. " "Please install it with `pip install litellm`"
            )
        if api_key:
            if "perplexity" in model:
                os.environ["PERPLEXITYAI_API_KEY"] = api_key
            elif "replicate" in model:
                os.environ["REPLICATE_API_KEY"] = api_key

        LLM = ChatLiteLLM(
            model=model,
            client=None,
            streaming=streaming,
            temperature=temperature,
            model_kwargs=model_kwargs if model_kwargs is not None else {},
            top_p=top_p,
            top_k=top_k,
            n=n,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )
        return LLM
