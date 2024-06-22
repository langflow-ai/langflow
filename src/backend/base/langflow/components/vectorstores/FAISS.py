from typing import List

from langchain_community.vectorstores import FAISS
from loguru import logger

from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.field_typing import Text
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, Output, StrInput
from langflow.schema import Data


class FaissVectorStoreComponent(LCVectorStoreComponent):
    """
    FAISS Vector Store with search capabilities
    """

    display_name: str = "FAISS"
    description: str = "FAISS Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/faiss"
    icon = "FAISS"

    inputs = [
        StrInput(
            name="folder_path",
            display_name="Folder Path",
            info="Path to save the FAISS index. It will be relative to where Langflow is running.",
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow_index",
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        StrInput(
            name="vector_store_inputs",
            display_name="Vector Store Inputs",
            input_types=["Document", "Data"],
            is_list=True,
        ),
        BoolInput(
            name="add_to_vector_store",
            display_name="Add to Vector Store",
            info="If true, the Vector Store Inputs will be added to the Vector Store.",
        ),
        BoolInput(
            name="allow_dangerous_deserialization",
            display_name="Allow Dangerous Deserialization",
            info="Set to True to allow loading pickle files from untrusted sources. Only enable this if you trust the source of the data.",
            advanced=True,
            value=False,
        ),
        StrInput(
            name="search_input",
            display_name="Search Input",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=4,
        ),
    ]

    outputs = [
        Output(
            display_name="Vector Store",
            name="vector_store",
            method="build_vector_store",
        ),
        Output(
            display_name="Base Retriever",
            name="base_retriever",
            method="build_base_retriever",
        ),
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
    ]

    def build_vector_store(self) -> FAISS:
        """
        Builds the FAISS object.
        """
        if not self.folder_path:
            raise ValueError("Folder path is required to save the FAISS index.")
        path = self.resolve_path(self.folder_path)

        if self.add_to_vector_store:
            documents = []
            for _input in self.vector_store_inputs or []:
                if isinstance(_input, Data):
                    documents.append(_input.to_lc_document())
                else:
                    documents.append(_input)

            faiss = FAISS.from_documents(documents=documents, embedding=self.embedding)
            faiss.save_local(Text(path), self.index_name)
        else:
            try:
                faiss = FAISS.load_local(
                    folder_path=Text(path),
                    embeddings=self.embedding,
                    index_name=self.index_name,
                    allow_dangerous_deserialization=self.allow_dangerous_deserialization,
                )
            except Exception as e:
                raise ValueError(
                    "Failed to load the FAISS index. Make sure the index was created with trusted data. "
                    "If you trust the data source, you can set `allow_dangerous_deserialization` to `True` "
                    "in the component's advanced settings to enable deserialization."
                ) from e

        return faiss

    def search_documents(self) -> List[Data]:
        """
        Search for documents in the FAISS vector store.
        """
        if not self.folder_path:
            raise ValueError("Folder path is required to load the FAISS index.")
        path = self.resolve_path(self.folder_path)

        try:
            vector_store = FAISS.load_local(
                folder_path=Text(path),
                embeddings=self.embedding,
                index_name=self.index_name,
                allow_dangerous_deserialization=self.allow_dangerous_deserialization,
            )
        except Exception as e:
            raise ValueError(
                "Failed to load the FAISS index. Make sure the index was created with trusted data. "
                "If you trust the data source, you can set `allow_dangerous_deserialization` to `True` "
                "in the component's advanced settings to enable deserialization."
            ) from e

        if not vector_store:
            raise ValueError("Failed to load the FAISS index.")

        logger.debug(f"Search input: {self.search_input}")
        logger.debug(f"Number of results: {self.number_of_results}")

        if self.search_input and isinstance(self.search_input, str) and self.search_input.strip():
            docs = vector_store.similarity_search(
                query=self.search_input,
                k=self.number_of_results,
            )

            logger.debug(f"Retrieved documents: {len(docs)}")

            data = docs_to_data(docs)
            logger.debug(f"Converted documents to data: {len(data)}")
            logger.debug(data)
            return data  # Return the search results data
        else:
            logger.debug("No search input provided. Skipping search.")
            return []
