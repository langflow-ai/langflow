from typing import List

from langchain_community.vectorstores.vectara import Vectara

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.Vectara import VectaraComponent
from langflow.field_typing import Text
from langflow.schema import Record


class VectaraSearchComponent(VectaraComponent, LCVectorStoreComponent):
    display_name: str = "Vectara Search"
    description: str = "Search a Vectara Vector Store for similar documents."
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/vectara"
    icon = "Vectara"

    field_config = {
        "search_type": {
            "display_name": "Search Type",
            "options": ["Similarity", "MMR"],
        },
        "input_value": {"display_name": "Input"},
        "vectara_customer_id": {
            "display_name": "Vectara Customer ID",
        },
        "vectara_corpus_id": {
            "display_name": "Vectara Corpus ID",
        },
        "vectara_api_key": {
            "display_name": "Vectara API Key",
            "password": True,
        },
        "files_url": {
            "display_name": "Files Url",
            "info": "Make vectara object using url of files (optional)",
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
        vectara_customer_id: str,
        vectara_corpus_id: str,
        vectara_api_key: str,
        number_of_results: int = 4,
    ) -> List[Record]:
        source = "Langflow"
        vector_store = Vectara(
            vectara_customer_id=vectara_customer_id,
            vectara_corpus_id=vectara_corpus_id,
            vectara_api_key=vectara_api_key,
            source=source,
        )

        if not vector_store:
            raise ValueError("Failed to create Vectara Vector Store")

        return self.search_with_vector_store(
            vector_store=vector_store, input_value=input_value, search_type=search_type, k=number_of_results
        )
