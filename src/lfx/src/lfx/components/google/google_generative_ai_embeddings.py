from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput


class GoogleGenerativeAIEmbeddingsComponent(Component):
    display_name = "Google Generative AI Embeddings"
    description = (
        "Connect to Google's generative AI embeddings service using the GoogleGenerativeAIEmbeddings class, "
        "found in the langchain-google-genai package."
    )
    documentation: str = "https://python.langchain.com/v0.2/docs/integrations/text_embedding/google_generative_ai/"
    icon = "GoogleGenerativeAI"
    name = "Google Generative AI Embeddings"

    inputs = [
        SecretStrInput(name="api_key", display_name="Google Generative AI API Key", required=True),
        MessageTextInput(name="model_name", display_name="Model Name", value="models/text-embedding-004"),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        if not self.api_key:
            msg = "API Key is required"
            raise ValueError(msg)

        return GoogleGenerativeAIEmbeddings(
            model=self.model_name,
            google_api_key=self.api_key,
        )
