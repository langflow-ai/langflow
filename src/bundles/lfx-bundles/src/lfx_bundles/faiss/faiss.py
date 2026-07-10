import re
from hashlib import sha256
from pathlib import Path

from langchain_community.vectorstores import FAISS
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, HandleInput, IntInput, StrInput
from lfx.schema.data import Data


class FaissVectorStoreComponent(LCVectorStoreComponent):
    """FAISS Vector Store with search capabilities."""

    display_name: str = "FAISS"
    description: str = "FAISS Vector Store with search capabilities"
    name = "FAISS"
    icon = "FAISS"

    # Strict portable allow-list for the index file prefix: letters, digits, dot,
    # underscore and hyphen only, and the name must contain at least one
    # non-dot character. This rejects empty, ".", "..", path separators
    # ("/", "\\") and drive-relative prefixes (e.g. "D:shared") that could escape
    # the per-user persist directory.
    _INDEX_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*$")

    inputs = [
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow_index",
        ),
        StrInput(
            name="persist_directory",
            display_name="Persist Directory",
            info="Path to save the FAISS index. It will be relative to where Langflow is running.",
        ),
        *LCVectorStoreComponent.inputs,
        BoolInput(
            name="allow_dangerous_deserialization",
            display_name="Allow Dangerous Deserialization",
            info="Set to True to allow loading pickle files. WARNING: Only enable this if you trust the source "
            "of the data. Malicious pickle files can execute arbitrary code on your system.",
            advanced=True,
            value=False,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=4,
        ),
    ]

    @staticmethod
    def _user_scope(user_id: object) -> str | None:
        if user_id is None:
            return None

        user_id_str = str(user_id).strip()
        if not user_id_str or user_id_str.lower() == "none":
            return None

        return sha256(user_id_str.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def resolve_path(path: str) -> str:
        """Resolve the path relative to the Langflow root.

        Args:
            path: The path to resolve
        Returns:
            str: The resolved path as a string
        """
        return str(Path(path).resolve())

    def get_index_name(self) -> str:
        """Returns the validated FAISS index file prefix."""
        index_name = str(self.index_name or "").strip()
        if not self._INDEX_NAME_PATTERN.match(index_name):
            msg = "FAISS index name must be a file name, not a path."
            raise ValueError(msg)
        return index_name

    def get_persist_directory(self) -> Path:
        """Returns the resolved, user-scoped persist directory path."""
        path = Path(self.resolve_path(self.persist_directory)) if self.persist_directory else Path()
        if user_scope := self._user_scope(self.user_id):
            return path / ".langflow_faiss" / "users" / user_scope
        return path

    @check_cached_vector_store
    def build_vector_store(self) -> FAISS:
        """Builds the FAISS object."""
        path = self.get_persist_directory()
        index_name = self.get_index_name()
        path.mkdir(parents=True, exist_ok=True)

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        faiss = FAISS.from_documents(documents=documents, embedding=self.embedding)
        faiss.save_local(str(path), index_name)
        return faiss

    def search_documents(self) -> list[Data]:
        """Search for documents in the FAISS vector store."""
        path = self.get_persist_directory()
        index_name = self.get_index_name()
        index_path = path / f"{index_name}.faiss"

        if not index_path.exists():
            vector_store = self.build_vector_store()
        else:
            vector_store = FAISS.load_local(
                folder_path=str(path),
                embeddings=self.embedding,
                index_name=index_name,
                allow_dangerous_deserialization=self.allow_dangerous_deserialization,
            )

        if not vector_store:
            msg = "Failed to load the FAISS index."
            raise ValueError(msg)

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )
            return docs_to_data(docs)
        return []
