from typing import TYPE_CHECKING

from langchain_community.vectorstores import Vectara

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema.data import Data

if TYPE_CHECKING:
    from langflow.schema.dataframe import DataFrame


class VectaraVectorStoreComponent(LCVectorStoreComponent):
    """Vectara Vector Store with search capabilities."""

    display_name: str = "Vectara"
    description: str = "Vectara Vector Store with search capabilities"
    name = "Vectara"
    icon = "Vectara"

    inputs = [
        StrInput(name="vectara_customer_id", display_name="Vectara Customer ID", required=True),
        StrInput(name="vectara_corpus_id", display_name="Vectara Corpus ID", required=True),
        SecretStrInput(name="vectara_api_key", display_name="Vectara API Key", required=True),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
        ),
        *LCVectorStoreComponent.inputs,
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> Vectara:
        """Builds the Vectara object."""
        try:
            from langchain_community.vectorstores import Vectara
        except ImportError as e:
            msg = "Could not import Vectara. Please install it with `pip install langchain-community`."
            raise ImportError(msg) from e

        vectara = Vectara(
            vectara_customer_id=self.vectara_customer_id,
            vectara_corpus_id=self.vectara_corpus_id,
            vectara_api_key=self.vectara_api_key,
        )

        self._add_documents_to_vector_store(vectara)
        return vectara

    def _add_documents_to_vector_store(self, vector_store: Vectara) -> None:
        """Adds documents to the Vector Store."""
        ingest_data: list | Data | DataFrame = self.ingest_data
        if not ingest_data:
            self.status = "No documents to add to Vectara"
            return

        # Convert DataFrame to Data if needed using parent's method
        ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            self.log(f"Adding {len(documents)} documents to Vectara.")
            vector_store.add_documents(documents)
            self.status = f"Added {len(documents)} documents to Vectara"
        else:
            self.log("No documents to add to Vectara.")
            self.status = "No valid documents to add to Vectara"

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )

            data = docs_to_data(docs)
            self.status = f"Found {len(data)} results for the query: {self.search_query}"
            return data
        self.status = "No search query provided"
        return []
