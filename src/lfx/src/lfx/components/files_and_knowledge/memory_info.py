"""Memory Info component for inspecting memory structure and statistics."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_chroma import Chroma
from langflow.services.database.models.user.crud import get_user_by_id

from lfx.custom import Component
from lfx.io import DropdownInput, IntInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.services.deps import get_settings_service, session_scope


class MemoryInfoComponent(Component):
    """Inspect memory structure, metadata fields, and statistics."""

    display_name = "Memory Info"
    description = "Get structure and statistics about a flow memory."
    icon = "Brain"
    name = "MemoryInfo"

    inputs = [
        DropdownInput(
            name="memory",
            display_name="Memory",
            info="Select the memory to inspect.",
            required=True,
            options=[],
            refresh_button=True,
            real_time_refresh=True,
        ),
        IntInput(
            name="sample_size",
            display_name="Sample Size",
            info="Number of sample documents to include in the output.",
            value=5,
            tool_mode=True,
            advanced=True,
        ),
        IntInput(
            name="max_unique_values",
            display_name="Max Unique Values to Show",
            info="Maximum number of unique values to show per field in describe.",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="info",
            display_name="Info",
            method="get_info",
            info="Returns information and statistics about the memory.",
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

    def _analyze_field(self, values: list, field_name: str) -> dict[str, Any]:
        """Analyze a single metadata field and return statistics."""
        non_null_values = [v for v in values if v is not None]

        if not non_null_values:
            return {"count": 0, "null_count": len(values), "type": "unknown"}

        sample_value = non_null_values[0]
        field_type = type(sample_value).__name__

        analysis: dict[str, Any] = {
            "count": len(non_null_values),
            "null_count": len(values) - len(non_null_values),
            "type": field_type,
        }

        if isinstance(sample_value, (int, float)):
            numeric_values = [v for v in non_null_values if isinstance(v, (int, float))]
            if numeric_values:
                analysis["min"] = min(numeric_values)
                analysis["max"] = max(numeric_values)
                analysis["avg"] = sum(numeric_values) / len(numeric_values)

        try:
            str_values = [str(v) for v in non_null_values]
            counter = Counter(str_values)
            analysis["unique_count"] = len(counter)
            most_common = counter.most_common(self.max_unique_values)
            analysis["top_values"] = [{"value": val, "count": cnt} for val, cnt in most_common]
        except Exception as e:
            logger.warning(f"Could not analyze unique values for field {field_name}: {e}")

        return analysis

    async def get_info(self) -> Data:
        """Get comprehensive information about the memory."""
        if not self.memory:
            msg = "No memory selected."
            raise ValueError(msg)

        # Resolve memory metadata
        mem_info = self._memory_map.get(self.memory)
        if not mem_info:
            memories = await self._fetch_memories(self.user_id)
            for mem in memories:
                if mem["name"] == self.memory or mem["kb_name"] == self.memory:
                    mem_info = mem
                    break
            if not mem_info:
                msg = f"Memory '{self.memory}' not found."
                raise ValueError(msg)

        kb_name = mem_info["kb_name"]

        # Get username for path
        async with session_scope() as db:
            current_user = await get_user_by_id(db, self.user_id)
            if not current_user:
                msg = f"User with ID {self.user_id} not found."
                raise ValueError(msg)
            username = current_user.username

        kb_path = self._get_kb_root() / username / kb_name

        if not kb_path.exists():
            return Data(data={
                "memory_name": mem_info["name"],
                "kb_name": kb_name,
                "status": "KB directory not found",
                "total_documents": 0,
            })

        # Load Chroma collection (no embedding function needed for info)
        chroma = Chroma(
            persist_directory=str(kb_path),
            collection_name=kb_name,
        )

        collection = chroma._collection  # noqa: SLF001

        logger.info(f"Fetching all documents from memory '{self.memory}' for analysis")
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
        internal_fields = sorted([f for f in all_fields if f.startswith("_")])

        # Analyze each field
        describe: dict[str, Any] = {}
        for field in all_fields:
            values = [meta.get(field) if meta else None for meta in metadatas]
            describe[field] = self._analyze_field(values, field)

        # Get sample documents
        sample_size = min(self.sample_size, total_documents)
        sample: list[dict[str, Any]] = []
        for i in range(sample_size):
            sample_doc: dict[str, Any] = {
                "content": documents[i] if documents and i < len(documents) else None,
            }
            if metadatas and i < len(metadatas) and metadatas[i]:
                sample_doc["metadata"] = metadatas[i]
            sample.append(sample_doc)

        # Build the info response
        info_data: dict[str, Any] = {
            "memory_name": mem_info["name"],
            "kb_name": kb_name,
            "total_documents": total_documents,
            "embedding_provider": mem_info["embedding_provider"],
            "embedding_model": mem_info["embedding_model"],
            "status": mem_info["status"],
            "is_active": mem_info["is_active"],
            "total_messages_processed": mem_info["total_messages_processed"],
            "sessions_count": mem_info["sessions_count"],
            "created_at": mem_info["created_at"],
            "last_generated_at": mem_info["last_generated_at"],
            "metadata_fields": display_fields,
            "internal_fields": internal_fields,
            "describe": describe,
            "sample": sample,
        }

        self.status = f"Memory '{self.memory}': {total_documents} chunks, {mem_info['sessions_count']} sessions, {len(display_fields)} metadata fields"

        return Data(data=info_data)
