
from langflow import CustomComponent
from langchain.tools import SecretStr
from typing import Optional, Dict, Union, Callable
from langflow.field_typing import BaseLanguageModel

class ChatAnthropicComponent(CustomComponent):
    display_name = "ChatAnthropic"
    description = "`Anthropic` chat large language models."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/chat/integrations/anthropic"

    def build_config(self):
        return {
            "anthropic_api_key": {
                "display_name": "Anthropic API Key",
                "type": SecretStr,
            },
            "anthropic_api_url": {
                "display_name": "Anthropic API URL",
                "type": str,
            },
            "model_kwargs": {
                "display_name": "Model Kwargs",
                "type": Dict[str, Union[str, int, float, bool]],
                "advanced": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "type": float,
            },
        }

    def build(
        self,
        anthropic_api_key: Optional[SecretStr] = None,
        anthropic_api_url: Optional[str] = None,
        model_kwargs: Optional[Dict[str, Union[str, int, float, bool]]] = None,
        temperature: Optional[float] = None,
    ) -> Union[BaseLanguageModel, Callable]:
        from langchain.model_io.models.chat.integrations import ChatAnthropic  # Importing here due to potential local scope requirements

        return ChatAnthropic(
            anthropic_api_key=anthropic_api_key.get_secret_value() if anthropic_api_key else None,
            anthropic_api_url=anthropic_api_url,
            model_kwargs=model_kwargs,
            temperature=temperature,
        )
