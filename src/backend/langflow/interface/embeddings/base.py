from typing import Dict, List, Optional

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.custom_lists import embedding_type_to_cls_dict
from langflow.settings import settings
from langflow.utils.util import build_template_from_class


class EmbeddingCreator(LangChainTypeCreator):
    type_name: str = "embeddings"

    @property
    def type_to_loader_dict(self) -> Dict:
        return embedding_type_to_cls_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of an embedding."""
        try:
            return build_template_from_class(name, embedding_type_to_cls_dict)
        except ValueError as exc:
            raise ValueError(f"Embedding {name} not found") from exc

    def to_list(self) -> List[str]:
        return [
            embedding.__name__
            for embedding in self.type_to_loader_dict.values()
            if embedding.__name__ in settings.embeddings or settings.dev
        ]


embedding_creator = EmbeddingCreator()
