from langchain_community.embeddings.huggingface import HuggingFaceEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import BoolInput, DictInput, MessageTextInput, Output


class HuggingFaceEmbeddingsComponent(LCModelComponent):
    display_name = "Hugging Face Embeddings"
    description = "Generate embeddings using HuggingFace models."
    documentation = (
        "https://python.langchain.com/docs/modules/data_connection/text_embedding/integrations/sentence_transformers"
    )
    icon = "HuggingFace"
    name = "HuggingFaceEmbeddings"

    inputs = [
        MessageTextInput(name="cache_folder", display_name="Cache Folder", advanced=True),
        DictInput(name="encode_kwargs", display_name="Encode Kwargs", advanced=True),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        MessageTextInput(name="model_name", display_name="Model Name", value="sentence-transformers/all-mpnet-base-v2"),
        BoolInput(name="multi_process", display_name="Multi Process", advanced=True),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        return HuggingFaceEmbeddings(
            cache_folder=self.cache_folder,
            encode_kwargs=self.encode_kwargs,
            model_kwargs=self.model_kwargs,
            model_name=self.model_name,
            multi_process=self.multi_process,
        )
