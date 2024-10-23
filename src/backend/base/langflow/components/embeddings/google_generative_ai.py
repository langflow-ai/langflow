# from langflow.field_typing import Data
import numpy as np

# TODO: remove ignore once the google package is published with types
from google.ai.generativelanguage_v1beta.types import BatchEmbedContentsRequest
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai._common import GoogleGenerativeAIError

from langflow.custom import Component
from langflow.io import MessageTextInput, Output, SecretStrInput


class GoogleGenerativeAIEmbeddingsComponent(Component):
    display_name = "Google Generative AI Embeddings"
    description = (
        "Connect to Google's generative AI embeddings service using the GoogleGenerativeAIEmbeddings class, "
        "found in the langchain-google-genai package."
    )
    documentation: str = "https://python.langchain.com/v0.2/docs/integrations/text_embedding/google_generative_ai/"
    icon = "Google"
    name = "Google Generative AI Embeddings"

    inputs = [
        SecretStrInput(name="api_key", display_name="API Key"),
        MessageTextInput(name="model_name", display_name="Model Name", value="models/text-embedding-004"),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        if not self.api_key:
            msg = "API Key is required"
            raise ValueError(msg)

        class HotaGoogleGenerativeAIEmbeddings(GoogleGenerativeAIEmbeddings):
            def __init__(self, *args, **kwargs) -> None:
                super(GoogleGenerativeAIEmbeddings, self).__init__(*args, **kwargs)

            def embed_documents(
                self,
                texts: list[str],
                *,
                batch_size: int = 100,
                task_type: str | None = None,
                titles: list[str] | None = None,
                output_dimensionality: int | None = 1536,
            ) -> list[list[float]]:
                """Embed a list of strings.

                Google Generative AI currently sets a max batch size of 100 strings.

                Args:
                    texts: List[str] The list of strings to embed.
                    batch_size: [int] The batch size of embeddings to send to the model
                    task_type: task_type (https://ai.google.dev/api/rest/v1/TaskType)
                    titles: An optional list of titles for texts provided.
                    Only applicable when TaskType is RETRIEVAL_DOCUMENT.
                    output_dimensionality: Optional reduced dimension for the output embedding.
                    https://ai.google.dev/api/rest/v1/models/batchEmbedContents#EmbedContentRequest
                Returns:
                    List of embeddings, one for each text.
                """
                embeddings: list[list[float]] = []
                batch_start_index = 0
                for batch in GoogleGenerativeAIEmbeddings._prepare_batches(texts, batch_size):
                    if titles:
                        titles_batch = titles[batch_start_index : batch_start_index + len(batch)]
                        batch_start_index += len(batch)
                    else:
                        titles_batch = [None] * len(batch)  # type: ignore[list-item]

                    requests = [
                        self._prepare_request(
                            text=text,
                            task_type=task_type,
                            title=title,
                            output_dimensionality=output_dimensionality,
                        )
                        for text, title in zip(batch, titles_batch, strict=True)
                    ]

                    try:
                        result = self.client.batch_embed_contents(
                            BatchEmbedContentsRequest(requests=requests, model=self.model)
                        )
                    except Exception as e:
                        msg = f"Error embedding content: {e}"
                        raise GoogleGenerativeAIError(msg) from e
                    embeddings.extend([list(np.pad(e.values, (0, 768), "constant")) for e in result.embeddings])
                return embeddings

            def embed_query(
                self,
                text: str,
                task_type: str | None = None,
                title: str | None = None,
                output_dimensionality: int | None = 1536,
            ) -> list[float]:
                """Embed a text.

                Args:
                    text: The text to embed.
                    task_type: task_type (https://ai.google.dev/api/rest/v1/TaskType)
                    title: An optional title for the text.
                    Only applicable when TaskType is RETRIEVAL_DOCUMENT.
                    output_dimensionality: Optional reduced dimension for the output embedding.
                    https://ai.google.dev/api/rest/v1/models/batchEmbedContents#EmbedContentRequest

                Returns:
                    Embedding for the text.
                """
                task_type = task_type or "RETRIEVAL_QUERY"
                return self.embed_documents(
                    [text],
                    task_type=task_type,
                    titles=[title] if title else None,
                    output_dimensionality=output_dimensionality,
                )[0]

        return HotaGoogleGenerativeAIEmbeddings(model=self.model_name, google_api_key=self.api_key)
