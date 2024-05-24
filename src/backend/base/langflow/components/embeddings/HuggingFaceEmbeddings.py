from typing import Dict, Optional

from langchain_community.embeddings.huggingface import HuggingFaceEmbeddings

from langflow.custom import CustomComponent


class HuggingFaceEmbeddingsComponent(CustomComponent):
    display_name = "Hugging Face Embeddings"
    description = "Generate embeddings using HuggingFace models."
    documentation = (
        "https://python.langchain.com/docs/modules/data_connection/text_embedding/integrations/sentence_transformers"
    )
    icon = "HuggingFace"

    def build_config(self):
        return {
            "cache_folder": {"display_name": "Cache Folder", "advanced": True},
            "encode_kwargs": {"display_name": "Encode Kwargs", "advanced": True, "field_type": "dict"},
            "model_kwargs": {"display_name": "Model Kwargs", "field_type": "dict", "advanced": True},
            "model_name": {"display_name": "Model Name"},
            "multi_process": {"display_name": "Multi Process", "advanced": True},
        }

    def build(
        self,
        cache_folder: Optional[str] = None,
        encode_kwargs: Optional[Dict] = {},
        model_kwargs: Optional[Dict] = {},
        model_name: str = "sentence-transformers/all-mpnet-base-v2",
        multi_process: bool = False,
    ) -> HuggingFaceEmbeddings:
        return HuggingFaceEmbeddings(
            cache_folder=cache_folder,
            encode_kwargs=encode_kwargs,
            model_kwargs=model_kwargs,
            model_name=model_name,
            multi_process=multi_process,
        )
