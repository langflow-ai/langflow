from typing import Dict, Optional

from langchain_community.llms.ctransformers import CTransformers

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text


class CTransformersComponent(LCModelComponent):
    display_name = "CTransformers"
    description = "Generate text using CTransformers LLM models"
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/ctransformers"

    def build_config(self):
        return {
            "model": {"display_name": "Model", "required": True},
            "model_file": {
                "display_name": "Model File",
                "required": False,
                "field_type": "file",
                "file_types": [".bin"],
            },
            "model_type": {"display_name": "Model Type", "required": True},
            "config": {
                "display_name": "Config",
                "advanced": True,
                "required": False,
                "field_type": "dict",
                "value": '{"top_k":40,"top_p":0.95,"temperature":0.8,"repetition_penalty":1.1,"last_n_tokens":64,"seed":-1,"max_new_tokens":256,"stop":"","stream":"False","reset":"True","batch_size":8,"threads":-1,"context_length":-1,"gpu_layers":0}',
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
        model: str,
        model_file: str,
        input_value: Text,
        model_type: str,
        stream: bool = False,
        config: Optional[Dict] = None,
    ) -> Text:
        output = CTransformers(
            client=None,
            model=model,
            model_file=model_file,
            model_type=model_type,
            config=config,  # noqa
        )

        return self.get_result(runnable=output, stream=stream, input_value=input_value)
