from langchain_community.embeddings import FakeEmbeddings

from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.field_typing import Embeddings
from langflow.io import IntInput


class FakeEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "Fake Embeddings"
    description = "Generate fake embeddings, useful for initial testing and connecting components."
    icon = "LangChain"
    name = "LangChainFakeEmbeddings"

    inputs = [
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have.",
            value=5,
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        return FakeEmbeddings(
            size=self.dimensions or 5,
        )
