from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import BoolInput, DictInput, FileInput, FloatInput, IntInput, MessageTextInput, Output


class VertexAIEmbeddingsComponent(LCModelComponent):
    display_name = "VertexAI Embeddings"
    description = "Generate embeddings using Google Cloud VertexAI models."
    icon = "VertexAI"
    name = "VertexAIEmbeddings"

    inputs = [
        FileInput(
            name="credentials",
            display_name="Credentials",
            value="",
            file_types=["json"],  # Removed the dot
        ),
        DictInput(
            name="instance",
            display_name="Instance",
            advanced=True,
        ),
        MessageTextInput(
            name="location",
            display_name="Location",
            value="us-central1",
            advanced=True,
        ),
        IntInput(
            name="max_output_tokens",
            display_name="Max Output Tokens",
            value=128,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            value=6,
            advanced=True,
        ),
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            value="textembedding-gecko",
        ),
        IntInput(
            name="n",
            display_name="N",
            value=1,
            advanced=True,
        ),
        MessageTextInput(
            name="project",
            display_name="Project",
            advanced=True,
        ),
        IntInput(
            name="request_parallelism",
            display_name="Request Parallelism",
            value=5,
            advanced=True,
        ),
        MessageTextInput(
            name="stop",
            display_name="Stop",
            advanced=True,
        ),
        BoolInput(
            name="streaming",
            display_name="Streaming",
            value=False,
            advanced=True,
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            value=0.0,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            value=40,
            advanced=True,
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            value=0.95,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            from langchain_google_vertexai import VertexAIEmbeddings
        except ImportError:
            raise ImportError(
                "Please install the langchain-google-vertexai package to use the VertexAIEmbeddings component."
            )

        return VertexAIEmbeddings(
            instance=self.instance,
            credentials=self.credentials,
            location=self.location,
            max_output_tokens=self.max_output_tokens,
            max_retries=self.max_retries,
            model_name=self.model_name,
            n=self.n,
            project=self.project,
            request_parallelism=self.request_parallelism,
            stop=self.stop,
            streaming=self.streaming,
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
        )
