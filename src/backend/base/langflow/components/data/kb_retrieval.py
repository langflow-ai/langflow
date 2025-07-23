import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from cryptography.fernet import InvalidToken
from langchain_chroma import Chroma
from loguru import logger

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.services.auth.utils import decrypt_api_key
from langflow.services.deps import get_settings_service

KNOWLEDGE_BASES_DIR = "~/.langflow/knowledge_bases"
KNOWLEDGE_BASES_ROOT_PATH = Path(KNOWLEDGE_BASES_DIR).expanduser()


class KBRetrievalComponent(Component):
    display_name = "Load Knowledge"
    description = "Load and perform searches against a particular knowledge base."
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
        ),
    ]

    outputs = [
        Output(
            name="chroma_kb_data",
            display_name="Results",
            method="get_chroma_kb_data",
            info="Returns the data from the selected knowledge base.",
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

    def _get_kb_metadata(self, kb_path: Path) -> dict:
        """Load and process knowledge base metadata."""
        metadata: dict[str, Any] = {}
        metadata_file = kb_path / "embedding_metadata.json"
        if not metadata_file.exists():
            logger.warning(f"Embedding metadata file not found at {metadata_file}")
            return metadata

        try:
            with metadata_file.open("r", encoding="utf-8") as f:
                metadata = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {metadata_file}")
            return {}

        # Decrypt API key if it exists
        if "api_key" in metadata and metadata.get("api_key"):
            settings_service = get_settings_service()
            try:
                decrypted_key = decrypt_api_key(metadata["api_key"], settings_service)
                metadata["api_key"] = decrypted_key
            except (InvalidToken, TypeError, ValueError) as e:
                logger.error(f"Could not decrypt API key. Please provide it manually. Error: {e}")
                metadata["api_key"] = None
        return metadata

    def _build_embeddings(self, metadata: dict):
        """Build embedding model from metadata."""
        provider = metadata.get("embedding_provider")
        model = metadata.get("embedding_model")
        api_key = metadata.get("api_key")
        dimensions = metadata.get("dimensions")
        chunk_size = metadata.get("chunk_size")

        # If user provided a key in the input, it overrides the stored one.
        if self.api_key and self.api_key.get_secret_value():
            api_key = self.api_key.get_secret_value()

        # TODO: Support other embedding providers in the future
        if provider == "OpenAI":
            from langchain_openai import OpenAIEmbeddings

            if not api_key:
                msg = "OpenAI API key is required. Provide it in the component's advanced settings."
                raise ValueError(msg)
            return OpenAIEmbeddings(
                model=model,
                dimensions=dimensions or None,
                api_key=api_key,
                chunk_size=chunk_size or 1000,
            )
        # Add other providers here if they become supported in ingest
        msg = f"Embedding provider '{provider}' is not supported for retrieval."
        raise NotImplementedError(msg)

    def get_chroma_kb_data(self) -> DataFrame:
        """Retrieve data from the selected knowledge base by reading the .parquet file in the knowledge base folder.

        Returns:
            A DataFrame containing the data rows from the knowledge base.
        """
        kb_root_path = Path(self.kb_root_path).expanduser()
        kb_path = kb_root_path / self.knowledge_base

        metadata = self._get_kb_metadata(kb_path)
        if not metadata:
            msg = f"Metadata not found for knowledge base: {self.knowledge_base}. Ensure it has been indexed."
            raise ValueError(msg)

        # Build the embedder for the knowledge base
        embedding_function = self._build_embeddings(metadata)

        # Load vector store
        chroma = Chroma(
            persist_directory=str(kb_path),
            embedding_function=embedding_function,
            collection_name=self.knowledge_base,
        )

        # With scores
        results = chroma.similarity_search_with_score(
            query=self.search_query or "",
            k=5,
        )

        # Assuming Data class has fields like 'content' and other metadata fields
        data_list = [
            Data(
                content=doc[0].page_content,
                score=doc[1],
                **doc[0].metadata,  # spread the metadata as additional fields
            )
            for doc in results
        ]

        # Arrange data_list by the score in descending order
        data_list.sort(key=lambda x: x.score, reverse=True)

        # Return the DataFrame containing the data
        return DataFrame(data=data_list)

    def get_kb_data(self) -> DataFrame:
        """Retrieve data from the selected knowledge base by reading the .parquet file in the knowledge base folder.

        Returns:
            A DataFrame containing the data rows from the knowledge base.
        """
        kb_root_path = Path(self.kb_root_path).expanduser()
        kb_path = kb_root_path / self.knowledge_base

        metadata = self._get_kb_metadata(kb_path)

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

            # Append a embeddings column to the DataFrame
            for i, record in enumerate(parquet_df):
                record["_embedding"] = vectors[i].tolist() if i < len(vectors) else None

            # If a search query is provided, by using OpenAI to perform a vector search against the data
            if self.search_query:
                embedder = self._build_embeddings(metadata)
                logger.info(f"Embedder: {embedder}")
                top_indices, scores = self.vector_search(
                    df=pd.DataFrame(parquet_df), query=self.search_query, embedder=embedder, top_k=5
                )

                # Filter the DataFrame to only include the top results
                parquet_df = [parquet_df[i] for i in top_indices]
                logger.info("Top indices: {top_indices}")
                # Append a scores column to the DataFrame
                for i, record in enumerate(parquet_df):
                    record["_score"] = scores[i]

            # Convert each record (dict) to a Data object, then create a DataFrame from the list of Data
            data_list = [Data(**record) for record in parquet_df]

            # Return the DataFrame containing the data
            return DataFrame(data=data_list)

        except Exception as e:
            raise RuntimeError from e

    def cosine_similarity_np(self, a, b):
        """Lightweight cosine similarity using only numpy."""
        return np.dot(a, b.T) / (np.linalg.norm(a) * np.linalg.norm(b, axis=1))

    def vector_search(self, df, query, embedder, top_k=5):
        """Perform vector search on DataFrame."""
        # Get query embedding
        query_embedding = np.array(embedder.embed_query(query))

        # Convert embeddings to matrix
        embeddings_matrix = np.vstack(df["_embedding"].values)

        # Calculate similarities using lightweight numpy function
        similarities = self.cosine_similarity_np(query_embedding, embeddings_matrix)

        # Get top k results
        return np.argsort(similarities)[::-1][:top_k], similarities[np.argsort(similarities)[::-1][:top_k]]
