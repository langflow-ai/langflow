from langflow import CustomComponent
from typing import Optional, Dict
from langchain_community.embeddings.huggingface import HuggingFaceEmbeddings


class HuggingFaceEmbeddingsComponent(CustomComponent):
    display_name = "HuggingFaceEmbeddings"
    description = "HuggingFace sentence_transformers embedding models."
    documentation = (
        "https://python.langchain.com/docs/modules/data_connection/text_embedding/integrations/sentence_transformers"
    )

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
