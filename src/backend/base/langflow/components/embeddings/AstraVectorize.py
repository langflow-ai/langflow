from typing import Any
from langflow.custom import Component
from langflow.inputs.inputs import DictInput, SecretStrInput, StrInput
from langflow.template.field.base import Output


class AstraVectorize(Component):
    display_name: str = "Astra Vectorize"
    description: str = "Configuration options for Astra Vectorize server-side embeddings."
    documentation: str = "https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html"
    icon = "AstraDB"

    inputs = [
        StrInput(
            name="provider",
            display_name="Provider name",
            info='The embedding provider to use.',
        ),
        StrInput(
            name="model_name",
            display_name="Model name",
            info='The embedding model to use.',
        ),
        DictInput(
            name="authentication",
            display_name="Authentication",
            info='Authentication parameters. Use the Astra Portal to add the embedding provider integration to your Astra organization.',
            is_list=True
        ),
        SecretStrInput(
            name="provider_api_key",
            display_name="Provider API Key",
            info='An alternative to the Astra Authentication that let you use directly the API key of the provider.',
            advanced=True
        ),
        DictInput(
            name="parameters",
            display_name="Model parameters",
            info='Additional model parameters.',
            advanced=True,
            is_list=True
        ),
    ]
    outputs = [
        Output(display_name="Vectorize", name="config", method="build", types=["dict"]),
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
