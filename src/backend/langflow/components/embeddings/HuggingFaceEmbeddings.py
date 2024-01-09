from langflow import CustomComponent
from typing import Optional, Any, Dict
from langflow.field_typing import Embeddings


class HuggingFaceEmbeddingsComponent(CustomComponent):
    display_name = "HuggingFaceEmbeddings"
    description = "HuggingFace sentence_transformers embedding models."
    documentation = (
        "https://python.langchain.com/docs/modules/data_connection/text_embedding/integrations/sentence_transformers"
    )

    def build_config(self):
        return {
            "cache_folder": {"display_name": "Cache Folder", "advanced": True},
            "client": {"display_name": "Client", "advanced": True},
            "encode_kwargs": {"display_name": "Encode Kwargs", "advanced": True},
            "model_kwargs": {"display_name": "Model Kwargs", "advanced": True},
            "model_name": {"display_name": "Model Name"},
            "multi_process": {"display_name": "Multi Process", "advanced": True},
        }

    def build(
        self,
        cache_folder: Optional[str] = None,
        client: Optional[Any] = None,
        encode_kwargs: Optional[Dict] = None,
        model_kwargs: Optional[Dict] = None,
        model_name: str = "sentence-transformers/all-mpnet-base-v2",
        multi_process: bool = False,
    ) -> Embeddings:
        return Embeddings(
            cache_folder=cache_folder,
            client=client,
            encode_kwargs=encode_kwargs,
            model_kwargs=model_kwargs,
            model_name=model_name,
            multi_process=multi_process,
        )
