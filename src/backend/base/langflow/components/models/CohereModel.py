from typing import Optional

from langchain_community.chat_models.cohere import ChatCohere
from pydantic.v1 import SecretStr
from langflow.field_typing import Text
from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent


class CohereComponent(LCModelComponent):
    display_name = "Cohere"
    description = "Generate text using Cohere LLMs."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"

    icon = "Cohere"

    field_order = [
        "cohere_api_key",
        "max_tokens",
        "temperature",
        "input_value",
        "system_message",
        "stream",
    ]

    def build_config(self):
        return {
            "cohere_api_key": {
                "display_name": "Cohere API Key",
                "type": "password",
                "password": True,
                "required": True,
            },
            "max_tokens": {
                "display_name": "Max Tokens",
                "advanced": True,
                "default": 256,
                "type": "int",
                "show": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "default": 0.75,
                "type": "float",
                "show": True,
            },
            "input_value": {"display_name": "Input"},
            "stream": {
                "display_name": "Stream",
                "info": STREAM_INFO_TEXT,
                "advanced": True,
            },
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "advanced": True,
            },
        }

    def build(
        self,
        cohere_api_key: str,
        input_value: Text,
        temperature: float = 0.75,
        stream: bool = False,
        system_message: Optional[str] = None,
    ) -> Text:
        api_key = SecretStr(cohere_api_key)
        output = ChatCohere(  # type: ignore
            cohere_api_key=api_key,
            temperature=temperature,
        )
        return self.get_chat_result(output, stream, input_value, system_message)
