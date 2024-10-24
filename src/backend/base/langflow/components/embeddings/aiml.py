from langflow.base.embeddings.aiml_embeddings import AIMLEmbeddingsImpl
from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.base.models.aiml_constants import AIML_EMBEDDING_MODELS
from langflow.field_typing import Embeddings
from langflow.inputs.inputs import DropdownInput
from langflow.io import SecretStrInput


class AIMLEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "AI/ML Embeddings"
    description = "Generate embeddings using the AI/ML API."
    icon = "AI/ML"
    name = "AIMLEmbeddings"

    inputs = [
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=AIML_EMBEDDING_MODELS,
            required=True,
        ),
        SecretStrInput(
            name="aiml_api_key",
            display_name="AI/ML API Key",
            value="AIML_API_KEY",
            required=True,
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        return AIMLEmbeddingsImpl(
            api_key=self.aiml_api_key,
            model=self.model_name,
        )
