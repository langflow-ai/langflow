from langflow import CustomComponent
from typing import Optional, Union, Callable
from langflow.field_typing import BaseLanguageModel
from langchain_community.llms.replicate import Replicate
import os


class ReplicateComponent(CustomComponent):
    display_name = "Replicate"
    description = "`Replicate` large language models."
    documentation = "https://python.langchain.com/docs/integrations/llms/replicate"

    def build_config(self):
        return {
            "model": {
                "display_name": "Model name",
                "field_type": "str",
                "advanced": False,
                "required": True,
                "options": [
                    "meta/llama-2-70b",
                    "meta/llama-2-13b",
                    "meta/llama-2-7b",
                    "meta/llama-2-70b-chat",
                    "meta/llama-2-13b-chat",
                    "meta/llama-2-7b-chat",
                    "mistralai/mistral-7b-v0.1",
                    "mistralai/mistral-7b-instruct-v0.2",
                    "mistralai/mixtral-8x7b-instruct-v0.1",
                ],
            },
            "model_kwargs": {
                "display_name": "Model Keyword Arguments",
                "field_type": "dict",
                "advanced": True,
                "required": False,
            },
            "replicate_api_token": {
                "display_name": "Replicate API Token",
                "field_type": "str",
                "advanced": False,
                "required": True,
                "password": True,
            },
            "prompt_key": {
                "display_name": "Prompt Key",
                "field_type": "str",
                "advanced": True,
                "required": False,
            },
            "streaming": {
                "display_name": "Streaming",
                "field_type": "bool",
                "advanced": True,
                "required": False,
            },
            "stop": {
                "display_name": "Stop Sequences",
                "field_type": "list",
                "advanced": True,
                "required": False,
            },
        }

    def build(
        self,
        model: str,
        model_kwargs: Optional[dict] = {},
        replicate_api_token: Optional[str] = None,
        prompt_key: Optional[str] = None,
        streaming: bool = False,
        stop: Optional[list] = [],
    ) -> Union[BaseLanguageModel, Callable]:
        os.environ["REPLICATE_API_TOKEN"] = replicate_api_token
        try:
            import replicate as replicate_python
        except ImportError:
            raise ImportError(
                "Could not import replicate python package. "
                "Please install it with `pip install replicate`."
            )
        version_obj = replicate_python.models.get(model).versions.list()[0]
        return Replicate(
            model=model,
            model_kwargs=model_kwargs,
            replicate_api_token=replicate_api_token,
            prompt_key=prompt_key,
            streaming=streaming,
            stop=stop,
            version_obj=version_obj,
        )
