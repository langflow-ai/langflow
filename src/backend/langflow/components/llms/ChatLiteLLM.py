from typing import Any, Dict, Optional
from langflow import CustomComponent
import litellm
from langchain.chat_models.litellm import ChatLiteLLM
from loguru import logger
import orjson
from langchain.schema.language_model import BaseLanguageModel


class ChatLiteLLMComponent(CustomComponent):
    display_name = "Chat LiteLLM"
    description = "Chat with a LiteLLM model. All specific options are available in the advanced section."

    def build_config(self):
        return {
            "model": {
                "options": litellm.model_list,
                "info": (
                    "The model to use. Don't forget to"
                    " pick the correct API key to use with the model."
                ),
            },
            # all other options should be "advanced": True
            "model_name": {"advanced": True},
            "openai_api_key": {"advanced": True},
            "azure_api_key": {"advanced": True},
            "anthropic_api_key": {"advanced": True},
            "replicate_api_key": {"advanced": True},
            "cohere_api_key": {"advanced": True},
            "openrouter_api_key": {"advanced": True},
            "api_base": {"advanced": True},
            "organization": {"advanced": True},
            "custom_llm_provider": {"advanced": True},
            "request_timeout": {"advanced": True},
            "model_kwargs": {"advanced": True, "field_type": "code"},
            "max_tokens": {"advanced": True},
            "max_retries": {"advanced": True},
        }

    def check_api_key_exlusivity(self, **kwargs):
        # Only one api key can be provided
        if sum(1 if key is not None else 0 for key in kwargs.values()) > 1:
            raise ValueError(
                "Only one api key can be provided. Please, provide only one of the following: openai_api_key, azure_api_key, anthropic_api_key, replicate_api_key, cohere_api_key, openrouter_api_key"
            )

    def build(
        self,
        model: str,
        model_name: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        azure_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        replicate_api_key: Optional[str] = None,
        cohere_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        organization: Optional[str] = None,
        custom_llm_provider: Optional[str] = None,
        request_timeout: Optional[float] = None,
        model_kwargs: Dict[str, Any] = {},
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        temperature: float = 1,
        max_tokens: int = 256,
        max_retries: int = 6,
    ) -> BaseLanguageModel:
        # The api keys are exlusive and may come as an empty string
        # so we need to None them out if they are empty strings
        if openai_api_key == "":
            openai_api_key = None
        if azure_api_key == "":
            azure_api_key = None
        if anthropic_api_key == "":
            anthropic_api_key = None
        if replicate_api_key == "":
            replicate_api_key = None
        if cohere_api_key == "":
            cohere_api_key = None
        if openrouter_api_key == "":
            openrouter_api_key = None

        self.check_api_key_exlusivity(
            openai_api_key=openai_api_key,
            azure_api_key=azure_api_key,
            anthropic_api_key=anthropic_api_key,
            replicate_api_key=replicate_api_key,
            cohere_api_key=cohere_api_key,
            openrouter_api_key=openrouter_api_key,
        )
        if isinstance(model_kwargs, str):
            try:
                model_kwargs = orjson.loads(model_kwargs)
            except orjson.JSONDecodeError as e:
                model_kwargs = {}
                logger.warning(
                    f"Error decoding model_kwargs: {e}. Using default model_kwargs."
                )

        return ChatLiteLLM(
            model=model,
            model_name=model_name,
            openai_api_key=openai_api_key,
            azure_api_key=azure_api_key,
            anthropic_api_key=anthropic_api_key,
            replicate_api_key=replicate_api_key,
            cohere_api_key=cohere_api_key,
            openrouter_api_key=openrouter_api_key,
            api_base=api_base,
            organization=organization,
            custom_llm_provider=custom_llm_provider,
            request_timeout=request_timeout,
            model_kwargs=model_kwargs,
            top_p=top_p,
            top_k=top_k,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )
