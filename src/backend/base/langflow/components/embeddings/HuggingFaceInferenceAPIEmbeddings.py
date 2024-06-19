from typing import Dict, Optional

from langchain_community.embeddings.huggingface import HuggingFaceInferenceAPIEmbeddings
from pydantic.v1.types import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import BoolInput, DictInput, FloatInput, Output, SecretStrInput, TextInput


class HuggingFaceInferenceAPIEmbeddingsComponent(LCModelComponent):
    display_name = "Hugging Face API Embeddings"
    description = "Generate embeddings using Hugging Face Inference API models."
    documentation = "https://github.com/huggingface/text-embeddings-inference"
    icon = "HuggingFace"

    inputs = [
        SecretStrInput(name="api_key", display_name="API Key", advanced=True),
        TextInput(name="api_url", display_name="API URL", advanced=True, value="http://localhost:8080"),
        TextInput(name="model_name", display_name="Model Name", value="BAAI/bge-large-en-v1.5"),
        TextInput(name="cache_folder", display_name="Cache Folder", advanced=True),
        DictInput(name="encode_kwargs", display_name="Encode Kwargs", advanced=True),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        BoolInput(name="multi_process", display_name="Multi Process", advanced=True),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        if not self.api_key:
            raise ValueError("API Key is required")

        api_key = SecretStr(self.api_key)

        return HuggingFaceInferenceAPIEmbeddings(
            api_key=api_key,
            api_url=self.api_url,
            model_name=self.model_name,
            cache_folder=self.cache_folder,
            encode_kwargs=self.encode_kwargs,
            model_kwargs=self.model_kwargs,
            multi_process=self.multi_process,
        )
