# Feature 13: Knowledge Info Component & Exact Match Search

## Summary

Adds two capabilities to the Files & Knowledge category:

1. **Knowledge Info Component** (`KnowledgeInfoComponent`): A new component that inspects a knowledge base's structure and statistics, returning metadata such as total document count, embedding model/provider, metadata field analysis (unique values, min/max/avg for numerics), and sample documents.

2. **Exact Match Search**: Extends the existing `KnowledgeRetrievalComponent` with a "Search Mode" tab selector that allows switching between "Similarity" (vector-based) and "Exact Match" (text substring) search. Exact match search uses Chroma's `$contains` filter on document content, with an optional "Also Search Metadata" toggle that performs a case-insensitive search across all metadata field values.

## Dependencies

- `langchain_chroma` (Chroma vector store)
- `langchain_core.documents.Document` (for exact match result construction)
- `langflow.services.database.models.user.crud.get_user_by_id` (user lookup for KB path resolution)
- `lfx.base.knowledge_bases.knowledge_base_utils.get_knowledge_bases` (KB listing utility)
- `lfx.services.deps.get_settings_service, session_scope` (settings and DB session)
- `lfx.io.TabInput` (new input type used for search mode selector)

## File Diffs

### `src/lfx/src/lfx/components/files_and_knowledge/info.py` (new)

```diff
diff --git a/src/lfx/src/lfx/components/files_and_knowledge/info.py b/src/lfx/src/lfx/components/files_and_knowledge/info.py
new file mode 100644
index 0000000000..5973435844
--- /dev/null
+++ b/src/lfx/src/lfx/components/files_and_knowledge/info.py
@@ -0,0 +1,245 @@
+"""Knowledge Info component for inspecting knowledge base structure and statistics."""
+
+from __future__ import annotations
+
+import json
+from collections import Counter
+from pathlib import Path
+from typing import Any
+
+from langchain_chroma import Chroma
+from langflow.services.database.models.user.crud import get_user_by_id
+
+from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
+from lfx.custom import Component
+from lfx.io import DropdownInput, IntInput, Output
+from lfx.log.logger import logger
+from lfx.schema.data import Data
+from lfx.services.deps import get_settings_service, session_scope
+from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component
+
+# Error message to raise if we're in Astra cloud environment and the component is not supported.
+astra_error_msg = "Knowledge info is not supported in Astra cloud environment."
+
+
+def _get_knowledge_bases_root_path() -> Path:
+    """Get the knowledge bases root path from settings with caching."""
+    if not hasattr(_get_knowledge_bases_root_path, "_cached_path"):
+        settings = get_settings_service().settings
+        knowledge_directory = settings.knowledge_bases_dir
+        if not knowledge_directory:
+            msg = "Knowledge bases directory is not set in the settings."
+            raise ValueError(msg)
+        _get_knowledge_bases_root_path._cached_path = Path(knowledge_directory).expanduser()
+    return _get_knowledge_bases_root_path._cached_path
+
+
+class KnowledgeInfoComponent(Component):
+    """Inspect knowledge base structure, metadata fields, and statistics."""
+
+    display_name = "Knowledge Info"
+    description = "Get structure and statistics about a knowledge base."
+    icon = "info"
+    name = "KnowledgeInfo"
+
+    inputs = [
+        DropdownInput(
+            name="knowledge_base",
+            display_name="Knowledge",
+            info="Select the knowledge to inspect.",
+            required=True,
+            options=[],
+            refresh_button=True,
+            real_time_refresh=True,
+        ),
+        IntInput(
+            name="sample_size",
+            display_name="Sample Size",
+            info="Number of sample documents to include in the output.",
+            value=5,
+            tool_mode=True,
+            advanced=True,
+        ),
+        IntInput(
+            name="max_unique_values",
+            display_name="Max Unique Values to Show",
+            info="Maximum number of unique values to show per field in describe.",
+            value=10,
+            advanced=True,
+        ),
+    ]
+
+    outputs = [
+        Output(
+            name="info",
+            display_name="Info",
+            method="get_info",
+            info="Returns information and statistics about the knowledge base.",
+            tool_mode=True,
+        ),
+    ]
+
+    async def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
+        """Update build configuration with available knowledge bases."""
+        raise_error_if_astra_cloud_disable_component(astra_error_msg)
+        if field_name == "knowledge_base":
+            build_config["knowledge_base"]["options"] = await get_knowledge_bases(
+                _get_knowledge_bases_root_path(),
+                user_id=self.user_id,
+            )
+            if build_config["knowledge_base"]["value"] not in build_config["knowledge_base"]["options"]:
+                build_config["knowledge_base"]["value"] = None
+        return build_config
+
+    def _get_kb_metadata(self, kb_path: Path) -> dict[str, Any]:
+        """Load knowledge base metadata from embedding_metadata.json."""
+        metadata: dict[str, Any] = {}
+        metadata_file = kb_path / "embedding_metadata.json"
+        if not metadata_file.exists():
+            logger.warning(f"Embedding metadata file not found at {metadata_file}")
+            return metadata
+
+        try:
+            with metadata_file.open("r", encoding="utf-8") as f:
+                metadata = json.load(f)
+        except json.JSONDecodeError:
+            logger.error(f"Error decoding JSON from {metadata_file}")
+            return {}
+
+        # Remove sensitive data (api_key)
+        metadata.pop("api_key", None)
+        return metadata
+
+    def _analyze_field(self, values: list, field_name: str) -> dict[str, Any]:
+        """Analyze a single metadata field and return statistics."""
+        # Filter out None values
+        non_null_values = [v for v in values if v is not None]
+
+        if not non_null_values:
+            return {"count": 0, "null_count": len(values), "type": "unknown"}
+
+        # Determine type
+        sample_value = non_null_values[0]
+        field_type = type(sample_value).__name__
+
+        analysis: dict[str, Any] = {
+            "count": len(non_null_values),
+            "null_count": len(values) - len(non_null_values),
+            "type": field_type,
+        }
+
+        # For numeric fields, add min/max/avg
+        if isinstance(sample_value, (int, float)):
+            numeric_values = [v for v in non_null_values if isinstance(v, (int, float))]
+            if numeric_values:
+                analysis["min"] = min(numeric_values)
+                analysis["max"] = max(numeric_values)
+                analysis["avg"] = sum(numeric_values) / len(numeric_values)
+
+        # For all fields, count unique values
+        try:
+            # Convert to string for counting (handles unhashable types)
+            str_values = [str(v) for v in non_null_values]
+            counter = Counter(str_values)
+            analysis["unique_count"] = len(counter)
+
+            # Get most common values (up to max_unique_values)
+            most_common = counter.most_common(self.max_unique_values)
+            analysis["top_values"] = [{"value": val, "count": cnt} for val, cnt in most_common]
+        except Exception as e:
+            logger.warning(f"Could not analyze unique values for field {field_name}: {e}")
+
+        return analysis
+
+    async def get_info(self) -> Data:
+        """Get comprehensive information about the knowledge base.
+
+        Returns:
+            Data object containing:
+            - total_documents: Total number of documents
+            - collection_name: Name of the collection
+            - embedding_model: Model used for embeddings
+            - embedding_provider: Provider of the embedding model
+            - created_at: When the KB was created
+            - metadata_fields: List of available metadata fields
+            - describe: Statistics for each metadata field
+            - sample: Sample documents from the KB
+        """
+        raise_error_if_astra_cloud_disable_component(astra_error_msg)
+
+        # Get the current user
+        async with session_scope() as db:
+            if not self.user_id:
+                msg = "User ID is required for fetching Knowledge Base info."
+                raise ValueError(msg)
+            current_user = await get_user_by_id(db, self.user_id)
+            if not current_user:
+                msg = f"User with ID {self.user_id} not found."
+                raise ValueError(msg)
+            kb_user = current_user.username
+
+        kb_path = _get_knowledge_bases_root_path() / kb_user / self.knowledge_base
+
+        # Get KB metadata (embedding info)
+        kb_metadata = self._get_kb_metadata(kb_path)
+
+        # Load Chroma collection (without embedding function - we don't need it for info)
+        chroma = Chroma(
+            persist_directory=str(kb_path),
+            collection_name=self.knowledge_base,
+        )
+
+        # Get collection info
+        collection = chroma._collection  # noqa: SLF001
+
+        # Get all documents to analyze
+        logger.info(f"Fetching all documents from knowledge base '{self.knowledge_base}' for analysis")
+        all_data = collection.get(include=["metadatas", "documents"])
+
+        total_documents = len(all_data.get("ids", []))
+        metadatas = all_data.get("metadatas", [])
+        documents = all_data.get("documents", [])
+
+        # Identify all metadata fields
+        all_fields: set[str] = set()
+        for meta in metadatas:
+            if meta:
+                all_fields.update(meta.keys())
+
+        # Remove internal fields from the list (but still analyze them)
+        display_fields = sorted([f for f in all_fields if not f.startswith("_")])
+        internal_fields = sorted([f for f in all_fields if f.startswith("_")])
+
+        # Analyze each field
+        describe: dict[str, Any] = {}
+        for field in all_fields:
+            values = [meta.get(field) if meta else None for meta in metadatas]
+            describe[field] = self._analyze_field(values, field)
+
+        # Get sample documents
+        sample_size = min(self.sample_size, total_documents)
+        sample: list[dict[str, Any]] = []
+        for i in range(sample_size):
+            sample_doc: dict[str, Any] = {
+                "content": documents[i] if documents and i < len(documents) else None,
+            }
+            if metadatas and i < len(metadatas) and metadatas[i]:
+                sample_doc["metadata"] = metadatas[i]
+            sample.append(sample_doc)
+
+        # Build the info response
+        info_data: dict[str, Any] = {
+            "collection_name": self.knowledge_base,
+            "total_documents": total_documents,
+            "embedding_provider": kb_metadata.get("embedding_provider"),
+            "embedding_model": kb_metadata.get("embedding_model"),
+            "created_at": kb_metadata.get("created_at"),
+            "metadata_fields": display_fields,
+            "internal_fields": internal_fields,
+            "describe": describe,
+            "sample": sample,
+        }
+
+        self.status = f"Knowledge base '{self.knowledge_base}': {total_documents} documents, {len(display_fields)} metadata fields"
+
+        return Data(data=info_data)
```

### `src/lfx/src/lfx/components/files_and_knowledge/__init__.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/components/files_and_knowledge/__init__.py b/src/lfx/src/lfx/components/files_and_knowledge/__init__.py
index fa3df7a988..99588d9aae 100644
--- a/src/lfx/src/lfx/components/files_and_knowledge/__init__.py
+++ b/src/lfx/src/lfx/components/files_and_knowledge/__init__.py
@@ -7,6 +7,7 @@ from lfx.components._importing import import_mod
 if TYPE_CHECKING:
     from lfx.components.files_and_knowledge.directory import DirectoryComponent
     from lfx.components.files_and_knowledge.file import FileComponent
+    from lfx.components.files_and_knowledge.info import KnowledgeInfoComponent
     from lfx.components.files_and_knowledge.ingestion import KnowledgeIngestionComponent
     from lfx.components.files_and_knowledge.retrieval import KnowledgeRetrievalComponent
     from lfx.components.files_and_knowledge.save_file import SaveToFileComponent
@@ -15,6 +16,7 @@ if TYPE_CHECKING:
 _dynamic_imports = {
     "DirectoryComponent": "directory",
     "FileComponent": "file",
+    "KnowledgeInfoComponent": "info",
     "KnowledgeIngestionComponent": "ingestion",
     "KnowledgeRetrievalComponent": "retrieval",
     "SaveToFileComponent": "save_file",
@@ -23,6 +25,7 @@ _dynamic_imports = {
 __all__ = [
     "DirectoryComponent",
     "FileComponent",
+    "KnowledgeInfoComponent",
     "KnowledgeIngestionComponent",
     "KnowledgeRetrievalComponent",
     "SaveToFileComponent",
```

### `src/lfx/src/lfx/components/files_and_knowledge/retrieval.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/components/files_and_knowledge/retrieval.py b/src/lfx/src/lfx/components/files_and_knowledge/retrieval.py
index 6b18fe9097..c24168eec8 100644
--- a/src/lfx/src/lfx/components/files_and_knowledge/retrieval.py
+++ b/src/lfx/src/lfx/components/files_and_knowledge/retrieval.py
@@ -10,30 +10,28 @@ from pydantic import SecretStr

 from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
 from lfx.custom import Component
-from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
+from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput, TabInput
 from lfx.log.logger import logger
 from lfx.schema.data import Data
 from lfx.schema.dataframe import DataFrame
 from lfx.services.deps import get_settings_service, session_scope
 from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component

-_KNOWLEDGE_BASES_ROOT_PATH: Path | None = None
-
 # Error message to raise if we're in Astra cloud environment and the component is not supported.
 astra_error_msg = "Knowledge retrieval is not supported in Astra cloud environment."


 def _get_knowledge_bases_root_path() -> Path:
-    """Lazy load the knowledge bases root path from settings."""
-    global _KNOWLEDGE_BASES_ROOT_PATH  # noqa: PLW0603
-    if _KNOWLEDGE_BASES_ROOT_PATH is None:
+    """Get the knowledge bases root path from settings with caching."""
+    # Use function attribute for caching instead of global variable
+    if not hasattr(_get_knowledge_bases_root_path, "_cached_path"):
         settings = get_settings_service().settings
         knowledge_directory = settings.knowledge_bases_dir
         if not knowledge_directory:
             msg = "Knowledge bases directory is not set in the settings."
             raise ValueError(msg)
-        _KNOWLEDGE_BASES_ROOT_PATH = Path(knowledge_directory).expanduser()
-    return _KNOWLEDGE_BASES_ROOT_PATH
+        _get_knowledge_bases_root_path._cached_path = Path(knowledge_directory).expanduser()
+    return _get_knowledge_bases_root_path._cached_path


 class KnowledgeRetrievalComponent(Component):
@@ -43,6 +41,14 @@ class KnowledgeRetrievalComponent(Component):
     name = "KnowledgeRetrieval"

     inputs = [
+        TabInput(
+            name="search_mode",
+            display_name="Search Mode",
+            info="Choose between similarity (vector) search or exact match (text) search.",
+            options=["Similarity", "Exact Match"],
+            value="Similarity",
+            tool_mode=True,
+        ),
         DropdownInput(
             name="knowledge_base",
             display_name="Knowledge",
@@ -52,19 +58,19 @@ class KnowledgeRetrievalComponent(Component):
             refresh_button=True,
             real_time_refresh=True,
         ),
-        SecretStrInput(
-            name="api_key",
-            display_name="Embedding Provider API Key",
-            info="API key for the embedding provider to generate embeddings.",
-            advanced=True,
-            required=False,
-        ),
         MessageTextInput(
             name="search_query",
             display_name="Search Query",
-            info="Optional search query to filter knowledge base data.",
+            info="Search query to filter knowledge base data.",
             tool_mode=True,
         ),
+        BoolInput(
+            name="search_metadata",
+            display_name="Also Search Metadata",
+            info="When using Exact Match, also search in metadata fields (not just content).",
+            value=False,
+            advanced=True,
+        ),
         IntInput(
             name="top_k",
             display_name="Top K Results",
@@ -87,6 +93,13 @@ class KnowledgeRetrievalComponent(Component):
             value=False,
             advanced=True,
         ),
+        SecretStrInput(
+            name="api_key",
+            display_name="Embedding Provider API Key",
+            info="API key for the embedding provider to generate embeddings. Only required for Similarity search.",
+            advanced=True,
+            required=False,
+        ),
     ]

     outputs = [
@@ -186,6 +199,73 @@ class KnowledgeRetrievalComponent(Component):
         msg = f"Embedding provider '{provider}' is not supported for retrieval."
         raise NotImplementedError(msg)

+    def _exact_match_search(self, chroma: Chroma, query: str) -> list[tuple]:
+        """Perform exact match search on content and optionally metadata.
+
+        Args:
+            chroma: The Chroma vector store instance.
+            query: The search query string.
+
+        Returns:
+            List of (Document, score) tuples matching the query.
+        """
+        collection = chroma._collection  # noqa: SLF001
+
+        # Use Chroma's where_document for content search
+        # $contains does a substring match on the document content
+        logger.info(f"Performing exact match search with query: {query}")
+
+        try:
+            # Search in document content
+            content_results = collection.get(
+                where_document={"$contains": query},
+                include=["documents", "metadatas"],
+                limit=self.top_k,
+            )
+
+            # Build results list from content matches
+            results = []
+            for i, doc_content in enumerate(content_results.get("documents", [])):
+                from langchain_core.documents import Document
+
+                metadata = content_results["metadatas"][i] if content_results.get("metadatas") else {}
+                doc = Document(page_content=doc_content or "", metadata=metadata or {})
+                results.append((doc, 0))  # Score 0 for exact match (no similarity score)
+
+            # If search_metadata is enabled, also search in metadata fields
+            if self.search_metadata:
+                logger.info("Also searching in metadata fields")
+                # Get all documents to search metadata (Chroma doesn't support $contains on metadata)
+                all_docs = collection.get(include=["documents", "metadatas"])
+
+                existing_ids = {r[0].metadata.get("_id") for r in results if r[0].metadata.get("_id")}
+
+                for i, metadata in enumerate(all_docs.get("metadatas", [])):
+                    if not metadata:
+                        continue
+                    # Skip if already in results
+                    if metadata.get("_id") in existing_ids:
+                        continue
+                    # Check if query appears in any metadata value
+                    for value in metadata.values():
+                        if value and query.lower() in str(value).lower():
+                            from langchain_core.documents import Document
+
+                            doc_content = all_docs["documents"][i] if all_docs.get("documents") else ""
+                            doc = Document(page_content=doc_content or "", metadata=metadata)
+                            results.append((doc, 0))
+                            existing_ids.add(metadata.get("_id"))
+                            break
+
+                # Limit to top_k
+                results = results[: self.top_k]
+
+            return results
+
+        except Exception as e:
+            logger.error(f"Error during exact match search: {e}")
+            return []
+
     async def retrieve_data(self) -> DataFrame:
         """Retrieve data from the selected knowledge base by reading the Chroma collection.

@@ -211,8 +291,13 @@ class KnowledgeRetrievalComponent(Component):
             msg = f"Metadata not found for knowledge base: {self.knowledge_base}. Ensure it has been indexed."
             raise ValueError(msg)

-        # Build the embedder for the knowledge base
-        embedding_function = self._build_embeddings(metadata)
+        # Determine if we need embeddings (only for similarity search)
+        use_similarity = self.search_mode == "Similarity"
+
+        # Build the embedder only if needed for similarity search
+        embedding_function = None
+        if use_similarity:
+            embedding_function = self._build_embeddings(metadata)

         # Load vector store
         chroma = Chroma(
@@ -221,22 +306,34 @@ class KnowledgeRetrievalComponent(Component):
             collection_name=self.knowledge_base,
         )

-        # If a search query is provided, perform a similarity search
+        results: list[tuple] = []
+
         if self.search_query:
-            # Use the search query to perform a similarity search
-            logger.info(f"Performing similarity search with query: {self.search_query}")
-            results = chroma.similarity_search_with_score(
-                query=self.search_query or "",
-                k=self.top_k,
-            )
+            if use_similarity:
+                # Use the search query to perform a similarity search
+                logger.info(f"Performing similarity search with query: {self.search_query}")
+                results = chroma.similarity_search_with_score(
+                    query=self.search_query,
+                    k=self.top_k,
+                )
+            else:
+                # Exact match search
+                results = self._exact_match_search(chroma, self.search_query)
         else:
-            results = chroma.similarity_search(
-                query=self.search_query or "",
-                k=self.top_k,
-            )
+            # No query - just return top_k documents
+            if use_similarity:
+                docs = chroma.similarity_search(query="", k=self.top_k)
+                results = [(doc, 0) for doc in docs]
+            else:
+                # For exact match without query, just get documents
+                collection = chroma._collection  # noqa: SLF001
+                all_docs = collection.get(include=["documents", "metadatas"], limit=self.top_k)
+                from langchain_core.documents import Document

-            # For each result, make it a tuple to match the expected output format
-            results = [(doc, 0) for doc in results]  # Assign a dummy score of 0
+                for i, doc_content in enumerate(all_docs.get("documents", [])):
+                    meta = all_docs["metadatas"][i] if all_docs.get("metadatas") else {}
+                    doc = Document(page_content=doc_content or "", metadata=meta or {})
+                    results.append((doc, 0))

         # If include_embeddings is enabled, get embeddings for the results
         id_to_embedding = {}
@@ -250,9 +347,9 @@ class KnowledgeRetrievalComponent(Component):
                 embeddings_result = collection.get(where={"_id": {"$in": doc_ids}}, include=["metadatas", "embeddings"])

                 # Create a mapping from document ID to embedding
-                for i, metadata in enumerate(embeddings_result.get("metadatas", [])):
-                    if metadata and "_id" in metadata:
-                        id_to_embedding[metadata["_id"]] = embeddings_result["embeddings"][i]
+                for i, meta in enumerate(embeddings_result.get("metadatas", [])):
+                    if meta and "_id" in meta:
+                        id_to_embedding[meta["_id"]] = embeddings_result["embeddings"][i]

         # Build output data based on include_metadata setting
         data_list = []
@@ -260,7 +357,7 @@ class KnowledgeRetrievalComponent(Component):
             kwargs = {
                 "content": doc[0].page_content,
             }
-            if self.search_query:
+            if self.search_query and use_similarity:
                 kwargs["_score"] = -1 * doc[1]
             if self.include_metadata:
                 # Include all metadata, embeddings, and content
```

## Implementation Notes

1. **Knowledge Info Component**: Opens the Chroma collection without an embedding function (since it only needs metadata and document content, not vector operations). Fetches all documents with `collection.get(include=["metadatas", "documents"])` to perform field analysis.

2. **Field Analysis**: For each metadata field, the `_analyze_field` method computes:
   - Count of non-null values and null count
   - Type inference from the first non-null value
   - Min/max/avg for numeric fields
   - Unique value count and top N most common values (configurable via `max_unique_values`)

3. **Exact Match Search**: Uses Chroma's native `where_document={"$contains": query}` for content matching (case-sensitive substring match at the Chroma level). Metadata search is done client-side with `query.lower() in str(value).lower()` since Chroma does not support `$contains` on metadata fields.

4. **Caching Refactor**: Both `info.py` and `retrieval.py` replace the global `_KNOWLEDGE_BASES_ROOT_PATH` variable with a function-attribute-based cache pattern (`_get_knowledge_bases_root_path._cached_path`), avoiding global variable mutation.

5. **Input Reordering**: The `api_key` input is moved to the bottom (advanced) and its description updated to note it is only required for similarity search. A new `search_metadata` BoolInput is added for exact match mode.

6. **Score Handling**: Similarity scores (`_score`) are only included in output when using similarity search mode. Exact match results always have score 0 since there is no vector distance metric.
