
from langflow import CustomComponent
from langchain.llms import BaseLanguageModel
from typing import Optional

class CohereComponent(CustomComponent):
    display_name = "Cohere"
    description = "Cohere large language models."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"

    def build_config(self):
        return {
            "cohere_api_key": {
                "display_name": "Cohere API Key",
                "type": "password",
                "show": True
            },
            "max_tokens": {
                "display_name": "Max Tokens",
                "default": 256,
                "type": "int",
                "show": True
            },
            "temperature": {
                "display_name": "Temperature",
                "default": 0.75,
                "type": "float",
                "show": True
            },
        }

    def build(
        self,
        cohere_api_key: str,
        max_tokens: Optional[int] = 256,
        temperature: Optional[float] = 0.75,
    ) -> BaseLanguageModel:
        # Assuming there is a Cohere class that takes these parameters to initialize
        # Please replace `Cohere` with the actual class name that should be instantiated
        return Cohere(api_key=cohere_api_key, max_tokens=max_tokens, temperature=temperature)
