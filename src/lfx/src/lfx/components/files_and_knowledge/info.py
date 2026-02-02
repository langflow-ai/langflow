"""Knowledge Info component for inspecting knowledge base structure and statistics."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langflow.services.database.models.user.crud import get_user_by_id

from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.custom import Component
from lfx.io import DropdownInput, IntInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.services.deps import get_settings_service, session_scope
from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component

# Error message to raise if we're in Astra cloud environment and the component is not supported.
astra_error_msg = "Knowledge info is not supported in Astra cloud environment."


def _get_knowledge_bases_root_path() -> Path:
    """Get the knowledge bases root path from settings with caching."""
    if not hasattr(_get_knowledge_bases_root_path, "_cached_path"):
        settings = get_settings_service().settings
        knowledge_directory = settings.knowledge_bases_dir
        if not knowledge_directory:
            msg = "Knowledge bases directory is not set in the settings."
            raise ValueError(msg)
        _get_knowledge_bases_root_path._cached_path = Path(knowledge_directory).expanduser()
    return _get_knowledge_bases_root_path._cached_path


class KnowledgeInfoComponent(Component):
    """Inspect knowledge base structure, metadata fields, and statistics."""

    display_name = "Knowledge Info"
    description = "Get structure and statistics about a knowledge base."
    icon = "info"
    name = "KnowledgeInfo"

    inputs = [
        DropdownInput(
            name="knowledge_base",
            display_name="Knowledge",
            info="Select the knowledge to inspect.",
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
            info="Returns information and statistics about the knowledge base.",
            tool_mode=True,
        ),
    ]

    async def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
        """Update build configuration with available knowledge bases."""
        raise_error_if_astra_cloud_disable_component(astra_error_msg)
        if field_name == "knowledge_base":
            build_config["knowledge_base"]["options"] = await get_knowledge_bases(
                _get_knowledge_bases_root_path(),
                user_id=self.user_id,
            )
            if build_config["knowledge_base"]["value"] not in build_config["knowledge_base"]["options"]:
                build_config["knowledge_base"]["value"] = None
        return build_config

    def _get_kb_metadata(self, kb_path: Path) -> dict[str, Any]:
        """Load knowledge base metadata from embedding_metadata.json."""
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

        # Remove sensitive data (api_key)
        metadata.pop("api_key", None)
        return metadata

    def _analyze_field(self, values: list, field_name: str) -> dict[str, Any]:
        """Analyze a single metadata field and return statistics."""
        # Filter out None values
        non_null_values = [v for v in values if v is not None]

        if not non_null_values:
            return {"count": 0, "null_count": len(values), "type": "unknown"}

        # Determine type
        sample_value = non_null_values[0]
        field_type = type(sample_value).__name__

        analysis: dict[str, Any] = {
            "count": len(non_null_values),
            "null_count": len(values) - len(non_null_values),
            "type": field_type,
        }

        # For numeric fields, add min/max/avg
        if isinstance(sample_value, (int, float)):
            numeric_values = [v for v in non_null_values if isinstance(v, (int, float))]
            if numeric_values:
                analysis["min"] = min(numeric_values)
                analysis["max"] = max(numeric_values)
                analysis["avg"] = sum(numeric_values) / len(numeric_values)

        # For all fields, count unique values
        try:
            # Convert to string for counting (handles unhashable types)
            str_values = [str(v) for v in non_null_values]
            counter = Counter(str_values)
            analysis["unique_count"] = len(counter)

            # Get most common values (up to max_unique_values)
            most_common = counter.most_common(self.max_unique_values)
            analysis["top_values"] = [{"value": val, "count": cnt} for val, cnt in most_common]
        except Exception as e:
            logger.warning(f"Could not analyze unique values for field {field_name}: {e}")

        return analysis

    async def get_info(self) -> Data:
        """Get comprehensive information about the knowledge base.

        Returns:
            Data object containing:
            - total_documents: Total number of documents
            - collection_name: Name of the collection
            - embedding_model: Model used for embeddings
            - embedding_provider: Provider of the embedding model
            - created_at: When the KB was created
            - metadata_fields: List of available metadata fields
            - describe: Statistics for each metadata field
            - sample: Sample documents from the KB
        """
        raise_error_if_astra_cloud_disable_component(astra_error_msg)

        # Get the current user
        async with session_scope() as db:
            if not self.user_id:
                msg = "User ID is required for fetching Knowledge Base info."
                raise ValueError(msg)
            current_user = await get_user_by_id(db, self.user_id)
            if not current_user:
                msg = f"User with ID {self.user_id} not found."
                raise ValueError(msg)
            kb_user = current_user.username

        kb_path = _get_knowledge_bases_root_path() / kb_user / self.knowledge_base

        # Get KB metadata (embedding info)
        kb_metadata = self._get_kb_metadata(kb_path)

        # Load Chroma collection (without embedding function - we don't need it for info)
        chroma = Chroma(
            persist_directory=str(kb_path),
            collection_name=self.knowledge_base,
        )

        # Get collection info
        collection = chroma._collection  # noqa: SLF001

        # Get all documents to analyze
        logger.info(f"Fetching all documents from knowledge base '{self.knowledge_base}' for analysis")
        all_data = collection.get(include=["metadatas", "documents"])

        total_documents = len(all_data.get("ids", []))
        metadatas = all_data.get("metadatas", [])
        documents = all_data.get("documents", [])

        # Identify all metadata fields
        all_fields: set[str] = set()
        for meta in metadatas:
            if meta:
                all_fields.update(meta.keys())

        # Remove internal fields from the list (but still analyze them)
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
            "collection_name": self.knowledge_base,
            "total_documents": total_documents,
            "embedding_provider": kb_metadata.get("embedding_provider"),
            "embedding_model": kb_metadata.get("embedding_model"),
            "created_at": kb_metadata.get("created_at"),
            "metadata_fields": display_fields,
            "internal_fields": internal_fields,
            "describe": describe,
            "sample": sample,
        }

        self.status = f"Knowledge base '{self.knowledge_base}': {total_documents} documents, {len(display_fields)} metadata fields"

        return Data(data=info_data)
