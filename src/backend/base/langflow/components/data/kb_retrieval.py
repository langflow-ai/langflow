from pathlib import Path

import numpy as np
import pandas as pd

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame

KNOWLEDGE_BASES_DIR = "~/.langflow/knowledge_bases"
KNOWLEDGE_BASES_ROOT_PATH = Path(KNOWLEDGE_BASES_DIR).expanduser()


class KBRetrievalComponent(Component):
    display_name = "Retrieve KB"
    description = "Load a particular knowledge base."
    icon = "database"
    name = "KBRetrieval"

    inputs = [
        DropdownInput(
            name="knowledge_base",
            display_name="Knowledge Base",
            info="Select the knowledge base to load files from.",
            options=[
                str(d.name) for d in KNOWLEDGE_BASES_ROOT_PATH.iterdir() if not d.name.startswith(".") and d.is_dir()
            ]
            if KNOWLEDGE_BASES_ROOT_PATH.exists()
            else [],
            refresh_button=True,
        ),
        StrInput(
            name="kb_root_path",
            display_name="KB Root Path",
            info="Root directory for knowledge bases (defaults to ~/.langflow/knowledge_bases)",
            advanced=True,
            value=KNOWLEDGE_BASES_DIR,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Embedding Provider API Key",
            info="API key for the embedding provider to generate embeddings.",
            advanced=True,
            required=False,
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Optional search query to filter knowledge base data.",
        )
    ]

    outputs = [
        Output(
            name="kb_info",
            display_name="Knowledge Base Info",
            method="retrieve_kb_info",
            info="Returns basic metadata of the selected knowledge base.",
        ),
        Output(
            name="kb_data",
            display_name="Knowledge Base Data",
            method="get_kb_data",
            info="Returns the data from the selected knowledge base.",
        ),
    ]

    def _get_knowledge_bases(self) -> list[str]:
        """Retrieve a list of available knowledge bases.

        Returns:
            A list of knowledge base names.
        """
        # Return the list of directories in the knowledge base root path
        kb_root_path = Path(self.kb_root_path).expanduser()

        if not kb_root_path.exists():
            return []

        return [str(d.name) for d in kb_root_path.iterdir() if not d.name.startswith(".") and d.is_dir()]

    def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
        if field_name == "knowledge_base":
            # Update the knowledge base options dynamically
            build_config["knowledge_base"]["options"] = self._get_knowledge_bases()
            build_config["knowledge_base"]["value"] = None

        return build_config

    def retrieve_kb_info(self) -> DataFrame:
        """Retrieve basic metadata of the selected knowledge base.

        Returns:
            A DataFrame containing basic metadata of the knowledge base.
        """
        data = Data(
            name=self.knowledge_base,
            description=f"Metadata for {self.knowledge_base}",
            documents_count=0,
        )
        return DataFrame(data=[data])

    def get_kb_data(self) -> DataFrame:
        """Retrieve data from the selected knowledge base by reading the .parquet file in the knowledge base folder.

        Returns:
            A DataFrame containing the data rows from the knowledge base.
        """
        kb_root_path = Path(self.kb_root_path).expanduser()
        kb_path = kb_root_path / self.knowledge_base

        parquet_file = kb_path / "source.parquet"
        vectors_file = kb_path / "vectors.npy"

        if not vectors_file.exists():
            msg = f"Vectors file not found: {vectors_file}. Please ensure the knowledge base has been indexed."
            raise ValueError(msg)
        try:
            # Load the vectors from the .npy file
            vectors = np.load(vectors_file, allow_pickle=True)
        except Exception as e:
            msg = f"Failed to load vectors from '{vectors_file}': {e}"
            raise RuntimeError(msg) from e

        if not parquet_file.exists():
            msg = f"Parquet file not found: {parquet_file}"
            raise ValueError(msg)
        try:
            parquet_df = pd.read_parquet(parquet_file).to_dict(orient="records")

            # Append an embeddings column to the DataFrame
            for i, record in enumerate(parquet_df):
                record["embedding"] = vectors[i]

            # If a search query is provided, by using OpenAI to perform a vector search against the data
            if self.search_query:
                top_indices = self.vector_search(
                    df=pd.DataFrame(parquet_df),
                    query=self.search_query,
                    top_k=5
                )

                # Filter the DataFrame to only include the top results
                parquet_df = [parquet_df[i] for i in top_indices]

            # Convert each record (dict) to a Data object, then create a DataFrame from the list of Data
            data_list = [Data(**record) for record in parquet_df]

            # Return the DataFrame containing the data
            return DataFrame(data=data_list)

        except Exception as e:
            raise RuntimeError from e

    def get_client(self):  # TODO: This should select the embedding provider of the knowledge base
        """Get the OpenAI client for embedding generation."""
        from openai import OpenAI

        # Initialize the OpenAI client
        return OpenAI(api_key=self.api_key)

    def get_embedding(self, text, model="text-embedding-3-small"):
        """Get embedding for a single text."""
        client = self.get_client()
        response = client.embeddings.create(input=text, model=model)
        return response.data[0].embedding

    def cosine_similarity_np(self, a, b):
        """Lightweight cosine similarity using only numpy."""
        return np.dot(a, b.T) / (np.linalg.norm(a) * np.linalg.norm(b, axis=1))

    def vector_search(self, df, query, top_k=5):
        """Perform vector search on DataFrame."""
        # Get query embedding
        query_embedding = np.array(self.get_embedding(query))

        # Convert embeddings to matrix
        embeddings_matrix = np.vstack(df["embedding"].values)

        # Calculate similarities using lightweight numpy function
        similarities = self.cosine_similarity_np(query_embedding, embeddings_matrix)

        # Get top k results
        return np.argsort(similarities)[::-1][:top_k]

