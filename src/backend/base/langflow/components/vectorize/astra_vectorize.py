from typing import Optional, Dict, Any

from langflow.custom import CustomComponent

class AstraVectorize(CustomComponent):
    display_name = "Astra Vectorize"
    description = "Configuration options for Astra Vectorize server-side embeddings."
    icon = "AstraDB" # TODO: New icon? 
    field_order = ["provider", "model_name", "authentication", "parameters"]

    def build_config(self):
        return {
            "provider": {
                "display_name": "Provider",
                "options": [], # TODO: List Options
            },
            "model_name": {
                "display_name": "Model",
                "options": [] # TODO:  - we'll want to dynamically update this list based on the provider...
            },
            "authentication": {
                "display_name": "Authentication",
                "info": "Authentication Token for Selected Provider"# TODO
            },
            "parameters": {
                "display_name": "Parameters",
                "info": "Optional parameters to pass.",
            },
        }
            

    def build(
        self,
        provider: str,
        model_name: Optional[str], # we may only support one for specific providers? 
        authentication: Optional[Dict[str, Any]], # nemo doesn't need auth now? 
        parameters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "provider": provider,
            "model_name": model_name,
            "authentication": authentication,
            "parameters": parameters,
        }


