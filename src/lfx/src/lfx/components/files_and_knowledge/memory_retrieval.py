"""Memory Retrieval component — semantic search over past conversations stored in a flow memory."""

from pathlib import Path
from uuid import UUID

from langchain_chroma import Chroma

from lfx.components.files_and_knowledge.embedding_utils import build_embeddings
from lfx.custom import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.services.deps import get_settings_service, session_scope


class MemoryRetrievalComponent(Component):
    display_name = "Memory Retrieval"
    description = "Retrieve relevant context from a flow's long-term memory."
    icon = "Brain"
    name = "MemoryRetrieval"

    inputs = [
        DropdownInput(
            name="memory",
            display_name="Memory",
            info="Select which memory to search.",
            required=True,
            options=[],
            refresh_button=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="The question or topic to search for in past conversations.",
            tool_mode=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K Results",
            info="Number of most relevant conversation chunks to return.",
            value=5,
            advanced=True,
        ),
        BoolInput(
            name="include_metadata",
            display_name="Include Metadata",
            info="Include sender, session ID, and timestamp in results.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="retrieve_memory",
            display_name="Results",
            method="retrieve_memory",
            info="Returns matching conversation chunks from the selected memory.",
        ),
    ]

    _memory_map: dict = {}

    @staticmethod
    def _get_kb_root() -> Path:
        settings = get_settings_service().settings
        knowledge_directory = settings.knowledge_bases_dir
        if not knowledge_directory:
            msg = "Knowledge bases directory is not set in the settings."
            raise ValueError(msg)
        return Path(knowledge_directory).expanduser()

    @staticmethod
    async def _fetch_memories(user_id: UUID | str) -> list[dict]:
        from langflow.services.database.models.memory.model import Memory
        from sqlmodel import select as sql_select

        if isinstance(user_id, str):
            user_id = UUID(user_id)

        async with session_scope() as session:
            stmt = sql_select(Memory).where(Memory.user_id == user_id)
            result = await session.exec(stmt)
            memories = result.all()
            return [
                {
                    "name": m.name,
                    "kb_name": m.kb_name,
                    "embedding_model": m.embedding_model,
                    "embedding_provider": m.embedding_provider,
                }
                for m in memories
            ]

    async def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
        if field_name == "memory":
            memories = await self._fetch_memories(self.user_id)
            options = []
            self._memory_map = {}
            for mem in memories:
                display = mem["name"]
                options.append(display)
                self._memory_map[display] = mem
            build_config["memory"]["options"] = options

            if build_config["memory"]["value"] not in options:
                build_config["memory"]["value"] = None

        return build_config

    async def retrieve_memory(self) -> DataFrame:
        """Search the selected memory's vector store and return matching conversation chunks."""
        if not self.memory:
            msg = "No memory selected. Please select a memory from the dropdown."
            raise ValueError(msg)

        # Look up memory metadata from cache or re-fetch
        mem_info = self._memory_map.get(self.memory)
        if not mem_info:
            memories = await self._fetch_memories(self.user_id)
            for mem in memories:
                if mem["name"] == self.memory or mem["kb_name"] == self.memory:
                    mem_info = mem
                    break
            if not mem_info:
                msg = f"Memory '{self.memory}' not found. It may have been deleted."
                raise ValueError(msg)

        kb_name = mem_info["kb_name"]
        embedding_model = mem_info["embedding_model"]
        embedding_provider = mem_info["embedding_provider"]

        # Resolve paths
        from langflow.services.database.models.user.crud import get_user_by_id

        async with session_scope() as db:
            current_user = await get_user_by_id(db, self.user_id)
            if not current_user:
                msg = f"User with ID {self.user_id} not found."
                raise ValueError(msg)
            username = current_user.username

        kb_path = self._get_kb_root() / username / kb_name

        if not kb_path.exists():
            msg = f"Memory knowledge base directory not found at {kb_path}. Try regenerating the memory."
            raise ValueError(msg)

        # Build embeddings using the unified model provider
        from lfx.base.models.unified_models import get_api_key_for_provider

        api_key = get_api_key_for_provider(self.user_id, embedding_provider) or ""
        embedding_function = build_embeddings(embedding_model, api_key, provider=embedding_provider)

        # Open Chroma vector store
        chroma = Chroma(
            persist_directory=str(kb_path),
            embedding_function=embedding_function,
            collection_name=kb_name,
        )

        # Perform similarity search
        results: list[tuple] = []
        if self.search_query:
            results = chroma.similarity_search_with_score(
                query=self.search_query,
                k=self.top_k,
            )
        else:
            # No query — return top chunks
            collection = chroma._collection  # noqa: SLF001
            raw = collection.get(
                include=["documents", "metadatas"],
                limit=self.top_k,
            )
            from langchain_core.documents import Document

            for i, doc_content in enumerate(raw.get("documents", [])):
                meta = raw["metadatas"][i] if raw.get("metadatas") else {}
                doc = Document(page_content=doc_content or "", metadata=meta or {})
                results.append((doc, 0))

        # Build output
        data_list = []
        for doc, score in results:
            kwargs = {"content": doc.page_content}
            if self.search_query:
                kwargs["_score"] = -1 * score
            if self.include_metadata:
                kwargs.update(doc.metadata)
            data_list.append(Data(**kwargs))

        return DataFrame(data=data_list)
