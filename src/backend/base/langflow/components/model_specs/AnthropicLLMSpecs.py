from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseLanguageModel
from pydantic.v1 import SecretStr

from langflow.custom import CustomComponent


class ChatAntropicSpecsComponent(CustomComponent):
    display_name: str = "Anthropic"
    description: str = "Anthropic Chat&Completion large language models."
    icon = "Anthropic"

    def build_config(self):
        return {
            "model": {
                "display_name": "Model Name",
                "options": [
                    "claude-2.1",
                    "claude-2.0",
                    "claude-instant-1.2",
                    "claude-instant-1",
                    # Add more models as needed
                ],
                "info": "https://python.langchain.com/docs/integrations/chat/anthropic",
                "required": True,
                "value": "claude-2.1",
            },
            "anthropic_api_key": {
                "display_name": "Anthropic API Key",
                "required": True,
                "password": True,
                "info": "Your Anthropic API key.",
            },
            "max_tokens": {
                "display_name": "Max Tokens",
                "advanced": True,
                "info": "The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "value": 0.7,
            },
            "api_endpoint": {
                "display_name": "API Endpoint",
                "info": "Endpoint of the Anthropic API. Defaults to 'https://api.anthropic.com' if not specified.",
            },
            "code": {"show": False},
        }

    def build(
        self,
        model: str,
        anthropic_api_key: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        api_endpoint: Optional[str] = None,
    ) -> BaseLanguageModel:
        # Set default API endpoint if not provided
        if not api_endpoint:
            api_endpoint = "https://api.anthropic.com"

        try:
            output = ChatAnthropic(
                model_name=model,
                anthropic_api_key=SecretStr(anthropic_api_key) if anthropic_api_key else None,
                max_tokens_to_sample=max_tokens,  # type: ignore
                temperature=temperature,
                anthropic_api_url=api_endpoint,
            )
        except Exception as e:
            raise ValueError("Could not connect to Anthropic API.") from e
        return output
