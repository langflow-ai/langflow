
from langflow import CustomComponent
from langchain.llms import BaseLLM
from typing import Optional, Dict, Union, Any
from langchain.field_typing import BaseLanguageModel

class ChatOpenAIComponent(CustomComponent):
    display_name = "ChatOpenAI"
    description = "`OpenAI` Chat large language models API."

    def build_config(self):
        return {
            "max_tokens": {
                "display_name": "Max Tokens",
                "type": "int",
                "advanced": False,
                "required": False,
            },
            "model_kwargs": {
                "display_name": "Model Kwargs",
                "type": "dict",
                "advanced": True,
                "required": False,
            },
            "model_name": {
                "display_name": "Model Name",
                "type": "str",
                "advanced": False,
                "required": False,
                "options": [
                    "gpt-4-1106-preview",
                    "gpt-4",
                    "gpt-4-32k",
                    "gpt-3.5-turbo",
                    "gpt-3.5-turbo-16k",
                ],
            },
            "openai_api_base": {
                "display_name": "OpenAI API Base",
                "type": "str",
                "advanced": False,
                "required": False,
                "info": (
                    "The base URL of the OpenAI API. Defaults to https://api.openai.com/v1.\n\n"
                    "You can change this to use other APIs like JinaChat, LocalAI and Prem."
                ),
            },
            "openai_api_key": {
                "display_name": "OpenAI API Key",
                "type": "str",
                "advanced": False,
                "required": False,
            },
            "temperature": {
                "display_name": "Temperature",
                "type": "float",
                "advanced": False,
                "required": False,
                "default": 0.7,
            },
        }

    def build(
        self,
        max_tokens: Optional[int] = None,
        model_kwargs: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = "gpt-4-1106-preview",
        openai_api_base: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Union[BaseLanguageModel, BaseLLM]:
        
        # Assuming there is a class `ChatOpenAI` that takes these parameters
        # The `ChatOpenAI` class must be imported or defined elsewhere in the actual implementation
        return ChatOpenAI(
            max_tokens=max_tokens,
            model_kwargs=model_kwargs,
            model_name=model_name,
            openai_api_base=openai_api_base,
            openai_api_key=openai_api_key,
            temperature=temperature,
        )
