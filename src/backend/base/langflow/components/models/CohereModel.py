from typing import Optional


from langchain_community.chat_models.cohere import ChatCohere
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text


class CohereComponent(LCModelComponent):
    display_name = "Cohere"
    description = "Generate text using Cohere large language models."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"

    icon = "Cohere"

    def build_config(self):
        return {
            "cohere_api_key": {
                "display_name": "Cohere API Key",
                "type": "password",
                "password": True,
            },
            "max_tokens": {
                "display_name": "Max Tokens",
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
                "info": "Stream the response from the model.",
            },
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
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
