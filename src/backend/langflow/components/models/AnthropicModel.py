from typing import Optional

from langchain_community.chat_models.anthropic import ChatAnthropic
from pydantic.v1 import SecretStr

from langflow import CustomComponent
from langflow.field_typing import Text


class AnthropicLLM(CustomComponent):
    display_name: str = "AnthropicModel"
    description: str = (
        "Generate text using Anthropic Chat&Completion large language models."
    )

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
                "field_type": "int",
                "value": 256,
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
            "input_value": {"display_name": "Input"},
            "stream": {
                "display_name": "Stream",
                "info": "Stream the response from the model.",
            },
        }

    def build(
        self,
        model: str,
        input_value: str,
        anthropic_api_key: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        api_endpoint: Optional[str] = None,
        stream: bool = False,
    ) -> Text:
        # Set default API endpoint if not provided
        if not api_endpoint:
            api_endpoint = "https://api.anthropic.com"

        try:
            output = ChatAnthropic(
                model_name=model,
                anthropic_api_key=(
                    SecretStr(anthropic_api_key) if anthropic_api_key else None
                ),
                max_tokens_to_sample=max_tokens,  # type: ignore
                temperature=temperature,
                anthropic_api_url=api_endpoint,
            )
        except Exception as e:
            raise ValueError("Could not connect to Anthropic API.") from e
        if stream:
            result = output.stream(input_value)
        else:
            message = output.invoke(input_value)
            result = message.content if hasattr(message, "content") else message
            self.status = result
        return result
