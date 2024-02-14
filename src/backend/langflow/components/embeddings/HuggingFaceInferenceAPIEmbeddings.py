from langflow import CustomComponent
from typing import Optional, Dict
from langchain_community.embeddings.huggingface import HuggingFaceInferenceAPIEmbeddings


class HuggingFaceInferenceAPIEmbeddingsComponent(CustomComponent):
    display_name = "HuggingFaceInferenceAPIEmbeddings"
    description = "HuggingFace sentence_transformers embedding models, API version."
    documentation = (
        "https://github.com/huggingface/text-embeddings-inference"
    )

    def build_config(self):
        return {
            "api_key": {"display_name": "API Key", "password": True, "advanced": True},
            "api_url": {"display_name": "API URL", "advanced": True},
            "model_name": {"display_name": "Model Name"},
            "cache_folder": {"display_name": "Cache Folder", "advanced": True},
            "encode_kwargs": {"display_name": "Encode Kwargs", "advanced": True, "field_type": "dict"},
            "model_kwargs": {"display_name": "Model Kwargs", "field_type": "dict", "advanced": True},
            "multi_process": {"display_name": "Multi Process", "advanced": True},
        }

    def build(
        self,
        api_key: Optional[str] = "",
        api_url: str = "http://localhost:8080",
        model_name: str = "BAAI/bge-large-en-v1.5",
        cache_folder: Optional[str] = None,
        encode_kwargs: Optional[Dict] = {},
        model_kwargs: Optional[Dict] = {},
        multi_process: bool = False,
    ) -> HuggingFaceInferenceAPIEmbeddings:
        return HuggingFaceInferenceAPIEmbeddings(
            api_key=api_key,
            api_url=api_url,
            model_name=model_name,
            cache_folder=cache_folder,
            encode_kwargs=encode_kwargs,
            model_kwargs=model_kwargs,
            multi_process=multi_process,
        )
