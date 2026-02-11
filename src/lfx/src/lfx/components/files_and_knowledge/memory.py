"""Memory Retrieval component — semantic search and info for flow memories."""

from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_chroma import Chroma
from langflow.services.database.models.user.crud import get_user_by_id

from lfx.components.files_and_knowledge.embedding_utils import build_embeddings
from lfx.custom import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.services.deps import get_settings_service, session_scope


class MemoryComponent(Component):
    display_name = "Memory"
    description = "Retrieve relevant context from a flow's long-term memory."
    icon = "Brain"
    name = "Memory"
    tool_mode = True

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
        Output(
            name="get_memory_info",
            display_name="Info",
            method="get_memory_info",
            info="Returns structure and statistics about the selected memory.",
            tool_mode=True,
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
    async def _fetch_memories(user_id: UUID | str, flow_id: UUID | str | None = None) -> list[dict]:
        from langflow.services.database.models.memory.model import Memory
        from sqlmodel import select as sql_select

        if isinstance(user_id, str):
            user_id = UUID(user_id)
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        async with session_scope() as session:
            stmt = sql_select(Memory).where(Memory.user_id == user_id)
            if flow_id is not None:
                stmt = stmt.where(Memory.flow_id == flow_id)
            result = await session.exec(stmt)
            memories = result.all()
            return [
                {
                    "name": m.name,
                    "kb_name": m.kb_name,
                    "embedding_model": m.embedding_model,
                    "embedding_provider": m.embedding_provider,
                    "total_messages_processed": m.total_messages_processed,
                    "total_chunks": m.total_chunks,
                    "sessions_count": m.sessions_count,
                    "status": m.status,
                    "is_active": m.is_active,
                    "created_at": str(m.created_at) if m.created_at else None,
                    "last_generated_at": str(m.last_generated_at) if m.last_generated_at else None,
                }
                for m in memories
            ]

    def _get_flow_id(self) -> str | None:
        """Get the current flow ID from runtime or frontend node context."""
        return self._get_runtime_or_frontend_node_attr("flow_id")

    async def _resolve_memory(self) -> dict:
        """Resolve the selected memory name to its metadata dict."""
        if not self.memory:
            msg = "No memory selected. Please select a memory from the dropdown."
            raise ValueError(msg)

        mem_info = self._memory_map.get(self.memory)
        if not mem_info:
            memories = await self._fetch_memories(self.user_id, flow_id=self._get_flow_id())
            for mem in memories:
                if mem["name"] == self.memory or mem["kb_name"] == self.memory:
                    mem_info = mem
                    break
            if not mem_info:
                msg = f"Memory '{self.memory}' not found. It may have been deleted."
                raise ValueError(msg)
        return mem_info

    async def _resolve_kb_path(self, kb_name: str) -> tuple[Path, str]:
        """Resolve KB path and username."""
        async with session_scope() as db:
            current_user = await get_user_by_id(db, self.user_id)
            if not current_user:
                msg = f"User with ID {self.user_id} not found."
                raise ValueError(msg)
            username = current_user.username
        return self._get_kb_root() / username / kb_name, username

    async def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
        if field_name == "memory":
            memories = await self._fetch_memories(self.user_id, flow_id=self._get_flow_id())
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
        mem_info = await self._resolve_memory()
        kb_name = mem_info["kb_name"]
        kb_path, _ = await self._resolve_kb_path(kb_name)

        if not kb_path.exists():
            msg = f"Memory KB directory not found at {kb_path}. Try regenerating the memory."
            raise ValueError(msg)

        from lfx.base.models.unified_models import get_api_key_for_provider

        api_key = get_api_key_for_provider(self.user_id, mem_info["embedding_provider"]) or ""
        embedding_function = build_embeddings(mem_info["embedding_model"], api_key, provider=mem_info["embedding_provider"])

        chroma = Chroma(
            persist_directory=str(kb_path),
            embedding_function=embedding_function,
            collection_name=kb_name,
        )

        results: list[tuple] = []
        if self.search_query:
            results = chroma.similarity_search_with_score(
                query=self.search_query,
                k=self.top_k,
            )
        else:
            collection = chroma._collection  # noqa: SLF001
            raw = collection.get(include=["documents", "metadatas"], limit=self.top_k)
            from langchain_core.documents import Document

            for i, doc_content in enumerate(raw.get("documents", [])):
                meta = raw["metadatas"][i] if raw.get("metadatas") else {}
                doc = Document(page_content=doc_content or "", metadata=meta or {})
                results.append((doc, 0))

        data_list = []
        for doc, score in results:
            kwargs = {"content": doc.page_content}
            if self.search_query:
                kwargs["_score"] = -1 * score
            if self.include_metadata:
                kwargs.update(doc.metadata)
            data_list.append(Data(**kwargs))

        return DataFrame(data=data_list)

    async def get_memory_info(self) -> Data:
        """Get structure and statistics about the selected memory."""
        mem_info = await self._resolve_memory()
        kb_name = mem_info["kb_name"]
        kb_path, _ = await self._resolve_kb_path(kb_name)

        if not kb_path.exists():
            return Data(data={
                "memory_name": mem_info["name"],
                "kb_name": kb_name,
                "status": "KB directory not found",
                "total_documents": 0,
            })

        chroma = Chroma(persist_directory=str(kb_path), collection_name=kb_name)
        collection = chroma._collection  # noqa: SLF001
        all_data = collection.get(include=["metadatas", "documents"])

        total_documents = len(all_data.get("ids", []))
        metadatas = all_data.get("metadatas", [])
        documents = all_data.get("documents", [])

        # Identify metadata fields
        all_fields: set[str] = set()
        for meta in metadatas:
            if meta:
                all_fields.update(meta.keys())

        display_fields = sorted([f for f in all_fields if not f.startswith("_")])

        # Analyze each field
        describe: dict[str, Any] = {}
        for field in all_fields:
            values = [meta.get(field) if meta else None for meta in metadatas]
            non_null = [v for v in values if v is not None]
            if not non_null:
                describe[field] = {"count": 0, "unique": 0}
                continue
            str_values = [str(v) for v in non_null]
            counter = Counter(str_values)
            describe[field] = {
                "count": len(non_null),
                "unique": len(counter),
                "top_values": [{"value": val, "count": cnt} for val, cnt in counter.most_common(10)],
            }

        # Sample documents
        sample_size = min(5, total_documents)
        sample = []
        for i in range(sample_size):
            s: dict[str, Any] = {"content": documents[i] if documents and i < len(documents) else None}
            if metadatas and i < len(metadatas) and metadatas[i]:
                s["metadata"] = metadatas[i]
            sample.append(s)

        info_data: dict[str, Any] = {
            "memory_name": mem_info["name"],
            "kb_name": kb_name,
            "total_documents": total_documents,
            "embedding_provider": mem_info["embedding_provider"],
            "embedding_model": mem_info["embedding_model"],
            "status": mem_info.get("status", "unknown"),
            "is_active": mem_info.get("is_active", False),
            "total_messages_processed": mem_info.get("total_messages_processed", 0),
            "sessions_count": mem_info.get("sessions_count", 0),
            "created_at": mem_info.get("created_at"),
            "last_generated_at": mem_info.get("last_generated_at"),
            "metadata_fields": display_fields,
            "describe": describe,
            "sample": sample,
        }

        self.status = f"Memory '{self.memory}': {total_documents} chunks, {mem_info.get('sessions_count', 0)} sessions"

        return Data(data=info_data)
