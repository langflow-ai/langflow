from typing import Dict, Optional

from langchain_community.llms.ctransformers import CTransformers

from langflow import CustomComponent


class CTransformersComponent(CustomComponent):
    display_name = "CTransformers"
    description = "C Transformers LLM models"
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
        }

    def build(self, model: str, model_file: str, model_type: str, config: Optional[Dict] = None) -> CTransformers:
        return CTransformers(model=model, model_file=model_file, model_type=model_type, config=config)  # type: ignore
