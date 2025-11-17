# from lfx.field_typing import Data

# TODO: remove ignore once the google package is published with types
from google.ai.generativelanguage_v1beta.types import BatchEmbedContentsRequest
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai._common import GoogleGenerativeAIError

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput

MIN_DIMENSION_ERROR = "Output dimensionality must be at least 1"
MAX_DIMENSION_ERROR = (
    "Output dimensionality cannot exceed 768. Google's embedding models only support dimensions up to 768."
)
MAX_DIMENSION = 768
MIN_DIMENSION = 1


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
                output_dimensionality: int | None = 768,
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
                if output_dimensionality is not None and output_dimensionality < MIN_DIMENSION:
                    raise ValueError(MIN_DIMENSION_ERROR)
                if output_dimensionality is not None and output_dimensionality > MAX_DIMENSION:
                    error_msg = MAX_DIMENSION_ERROR.format(output_dimensionality)
                    raise ValueError(error_msg)

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
                    embeddings.extend([list(e.values) for e in result.embeddings])
                return embeddings

            def embed_query(
                self,
                text: str,
                task_type: str | None = None,
                title: str | None = None,
                output_dimensionality: int | None = 768,
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
                if output_dimensionality is not None and output_dimensionality < MIN_DIMENSION:
                    raise ValueError(MIN_DIMENSION_ERROR)
                if output_dimensionality is not None and output_dimensionality > MAX_DIMENSION:
                    error_msg = MAX_DIMENSION_ERROR.format(output_dimensionality)
                    raise ValueError(error_msg)

                task_type = task_type or "RETRIEVAL_QUERY"
                return self.embed_documents(
                    [text],
                    task_type=task_type,
                    titles=[title] if title else None,
                    output_dimensionality=output_dimensionality,
                )[0]

        return HotaGoogleGenerativeAIEmbeddings(model=self.model_name, google_api_key=self.api_key)
