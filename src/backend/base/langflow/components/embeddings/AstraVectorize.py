from typing import Optional, Dict, Any

from langflow.custom import CustomComponent

from langflow.custom import Component
from base.langflow.inputs import TextInput
from base.langflow.template.field.base import Output
#
#
# class AstraVectorize(Component):
#     display_name = "Astra Vectorize"
#     description = "Configuration options for Astra Vectorize server-side embeddings."
#     documentation = "..."
#     icon = "AstraDB" # TODO: New icon?
#
#     inputs = [
#         TextInput(
#             name="provider",
#             display_name="Provider",
#         )
#     ]
#     outputs = [
#         Output(display_name="Vectorize_configuration", name="embeddings", method="build"),
#     ]
#
#     def build(
#         self,
#     ) -> Dict[str, Any]:
#         return {
#             "provider": self.provider
#         }


from langflow.custom import Component
from langflow.inputs.inputs import DataInput, IntInput, TextInput, DictInput
from langflow.schema import Data
from langflow.template.field.base import Output
from langflow.utils.util import build_loader_repr_from_data, unescape_string


class AstraVectorize(Component):
    display_name: str = "Astra Vectorize"
    description: str = "Configuration options for Astra Vectorize server-side embeddings."
    documentation: str = "https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html"
    icon = "AstraDB"

    inputs = [
        TextInput(
            name="provider",
            display_name="Provider name",
            info='The provider to use.',
        ),
        TextInput(
            name="model_name",
            display_name="Model name",
            info='The model to use.',
        ),
        DictInput(
            name="authentication",
            display_name="Authentication",
            info='Authentication parameters. Use the Astra Portal to add the embedding provider integration to your Astra organization.',
            is_list=True
        ),
        DictInput(
            name="authentication2",
            display_name="Authentication",
            info='Authentication parameters. Use the Astra Portal to add the embedding provider integration to your Astra organization.',
            is_list=False
        ),
        TextInput(
            name="provider_api_key",
            display_name="Provider API Key to authenticate to the external service",
            info='An alternative to the Astra Authentication that let you use directly the API key of the provider.',
            advanced=True
        ),
        DictInput(
            name="parameters",
            display_name="Additional model parameters",
            info='Additional model parameters.',
            advanced=True,
            is_list=True
        ),
    ]
    outputs = [
        Output(display_name="Configuration", name="config", method="build", types=["dict"]),
    ]

    def build(self) -> dict[str, Any]:
        return {
            "collection_vector_service_options": {
                "provider": self.provider,
                "model_name": self.model_name,
                "authentication": self.authentication,
                "parameters": self.parameters
            },
            "collection_embedding_api_key": self.provider_api_key
        }
