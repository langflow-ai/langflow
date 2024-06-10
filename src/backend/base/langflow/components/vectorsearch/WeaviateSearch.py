from typing import List, Optional

from langchain_core.embeddings import Embeddings

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.Weaviate import WeaviateVectorStoreComponent
from langflow.field_typing import Text
from langflow.schema import Record


class WeaviateSearchVectorStore(WeaviateVectorStoreComponent, LCVectorStoreComponent):
    display_name: str = "Weaviate Search"
    description: str = "Search a Weaviate Vector Store for similar documents."
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/weaviate"
    icon = "Weaviate"

    field_config = {
        "search_type": {
            "display_name": "Search Type",
            "options": ["Similarity", "MMR"],
        },
        "input_value": {"display_name": "Input"},
        "url": {"display_name": "Weaviate URL", "value": "http://localhost:8080"},
        "api_key": {
            "display_name": "API Key",
            "password": True,
            "required": False,
        },
        "index_name": {
            "display_name": "Index name",
            "required": False,
        },
        "text_key": {
            "display_name": "Text Key",
            "required": False,
            "advanced": True,
            "value": "text",
        },
        "embedding": {"display_name": "Embedding"},
        "attributes": {
            "display_name": "Attributes",
            "required": False,
            "is_list": True,
            "field_type": "str",
            "advanced": True,
        },
        "search_by_text": {
            "display_name": "Search By Text",
            "field_type": "bool",
            "advanced": True,
        },
        "number_of_results": {
            "display_name": "Number of Results",
            "info": "Number of results to return.",
            "advanced": True,
        },
    }

    def build(  # type: ignore[override]
        self,
        input_value: Text,
        search_type: str,
        url: str,
        index_name: str,
        number_of_results: int = 4,
        search_by_text: bool = False,
        api_key: Optional[str] = None,
        text_key: str = "text",
        embedding: Optional[Embeddings] = None,
        attributes: Optional[list] = None,
    ) -> List[Record]:
        vector_store = super().build(
            url=url,
            api_key=api_key,
            index_name=index_name,
            text_key=text_key,
            embedding=embedding,
            attributes=attributes,
            search_by_text=search_by_text,
        )
        if not vector_store:
            raise ValueError("Failed to load the Weaviate index.")

        return self.search_with_vector_store(
            vector_store=vector_store, input_value=input_value, search_type=search_type, k=number_of_results
        )
