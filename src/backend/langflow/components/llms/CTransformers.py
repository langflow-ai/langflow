
from langflow import CustomComponent
from langchain.llms import BaseLanguageModel
from typing import Optional, Dict

class CTransformersComponent(CustomComponent):
    display_name = "CTransformers"
    description = "C Transformers LLM models"
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/ctransformers"

    def build_config(self):
        return {
            "model": {"display_name": "Model", "required": True},
            "model_file": {"display_name": "Model File", "required": False},
            "model_type": {"display_name": "Model Type", "required": False},
            "config": {"display_name": "Config", "advanced": True, "required": False},
        }

    def build(
        self,
        model: str,
        model_file: Optional[str] = None,
        model_type: Optional[str] = None,
        config: Optional[Dict] = None
    ) -> BaseLanguageModel:
        # Default config values
        default_config = {
            "top_k": 40,
            "top_p": 0.95,
            "temperature": 0.8,
            "repetition_penalty": 1.1,
            "last_n_tokens": 64,
            "seed": -1,
            "max_new_tokens": 256,
            "stop": None,
            "stream": False,
            "reset": True,
            "batch_size": 8,
            "threads": -1,
            "context_length": -1,
            "gpu_layers": 0
        }

        # If there is a custom config, update the default config with it
        if config:
            default_config.update(config)

        # Assuming the import below is correct and CTransformers is a class within the langchain library
        # that inherits from BaseLanguageModel. The following import statement is required:
        # from langchain.llms.integration_module import CTransformers

        return CTransformers(model=model, model_file=model_file, model_type=model_type, config=default_config)

# Note: The actual CTransformers class needs to be imported from the correct module inside the langchain library.
# The `integration_module` in the import statement is just a placeholder and should be replaced with
# the actual module where the CTransformers class is located.
