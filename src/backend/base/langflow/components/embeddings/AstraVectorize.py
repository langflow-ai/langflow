from typing import Any
from langflow.custom import Component
from langflow.inputs.inputs import DictInput, SecretStrInput, MessageTextInput
from langflow.template.field.base import Output


class AstraVectorize(Component):
    display_name: str = "Astra Vectorize"
    description: str = "Configuration options for Astra Vectorize server-side embeddings."
    documentation: str = "https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html"
    icon = "AstraDB"

    inputs = [
        MessageTextInput(
            name="provider",
            display_name="Provider name",
            info="The embedding provider to use.",
        ),
        MessageTextInput(
            name="model_name",
            display_name="Model name",
            info="The embedding model to use.",
        ),
        DictInput(
            name="authentication",
            display_name="Authentication",
            info="Authentication parameters. Use the Astra Portal to add the embedding provider integration to your Astra organization.",
            is_list=True,
        ),
        SecretStrInput(
            name="provider_api_key",
            display_name="Provider API Key",
            info="An alternative to the Astra Authentication that let you use directly the API key of the provider.",
        ),
        DictInput(
            name="model_parameters",
            display_name="Model parameters",
            info="Additional model parameters.",
            advanced=True,
            is_list=True,
        ),
    ]
    outputs = [
        Output(display_name="Vectorize", name="config", method="build_options", types=["dict"]),
    ]

    def build_options(self) -> dict[str, Any]:
        return {
            # must match exactly astra CollectionVectorServiceOptions
            "collection_vector_service_options": {
                "provider": self.provider,
                "modelName": self.model_name,
                "authentication": self.authentication,
                "parameters": self.model_parameters,
            },
            "collection_embedding_api_key": self.provider_api_key,
        }
