# Feature 14: Knowledge Ingestion Batch Size Fix

## Summary

Fixes a crash when ingesting large document sets into the Chroma vector store. Chroma has an internal limit of ~5461 documents per `add_documents` call. This fix batches document additions in groups of 5000, logging progress for each batch.

Additionally, replaces the global variable `_KNOWLEDGE_BASES_ROOT_PATH` with a function-attribute caching pattern, and adds the `logger` import for structured logging.

## Dependencies

- `lfx.log.logger` (new import added)

## Files Changed

### `src/lfx/src/lfx/components/files_and_knowledge/ingestion.py`

```diff
diff --git a/src/lfx/src/lfx/components/files_and_knowledge/ingestion.py b/src/lfx/src/lfx/components/files_and_knowledge/ingestion.py
index 7e08796165..dd435253b4 100644
--- a/src/lfx/src/lfx/components/files_and_knowledge/ingestion.py
+++ b/src/lfx/src/lfx/components/files_and_knowledge/ingestion.py
@@ -31,6 +31,7 @@ from lfx.io import (
     StrInput,
     TableInput,
 )
+from lfx.log.logger import logger
 from lfx.schema.data import Data
 from lfx.schema.table import EditMode
 from lfx.services.deps import (
@@ -49,23 +50,21 @@ HUGGINGFACE_MODEL_NAMES = [
 ]
 COHERE_MODEL_NAMES = ["embed-english-v3.0", "embed-multilingual-v3.0"]

-_KNOWLEDGE_BASES_ROOT_PATH: Path | None = None
-
 # Error message to raise if we're in Astra cloud environment and the component is not supported.
 astra_error_msg = "Knowledge ingestion is not supported in Astra cloud environment."


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


 class KnowledgeIngestionComponent(Component):
@@ -406,10 +405,21 @@ class KnowledgeIngestionComponent(Component):
                 doc = data_obj.to_lc_document()
                 documents.append(doc)

-            # Add documents to vector store
+            # Add documents to vector store in batches (Chroma limit is ~5461)
             if documents:
-                chroma.add_documents(documents)
-                self.log(f"Added {len(documents)} documents to vector store '{self.knowledge_base}'")
+                batch_size = 5000
+                total_docs = len(documents)
+                total_batches = (total_docs + batch_size - 1) // batch_size
+                logger.info(f"Knowledge Ingestion: Adding {total_docs} documents in {total_batches} batches")
+                for i in range(0, total_docs, batch_size):
+                    batch_num = i // batch_size + 1
+                    batch = documents[i : i + batch_size]
+                    logger.info(
+                        f"Knowledge Ingestion: Processing batch {batch_num}/{total_batches} ({len(batch)} docs)"
+                    )
+                    chroma.add_documents(batch)
+                    logger.info(f"Knowledge Ingestion: Batch {batch_num}/{total_batches} completed")
+                logger.info(f"Knowledge Ingestion: All {total_docs} documents added to '{self.knowledge_base}'")

         except (OSError, ValueError, RuntimeError) as e:
             self.log(f"Error creating vector store: {e}")
```

## Implementation Notes

1. **Batch size of 5000**: Chosen to stay safely under Chroma's internal limit of ~5461 documents per call.
2. **Ceiling division**: `(total_docs + batch_size - 1) // batch_size` correctly calculates the total number of batches.
3. **Caching refactor**: The global variable `_KNOWLEDGE_BASES_ROOT_PATH` was replaced with `_get_knowledge_bases_root_path._cached_path` (function attribute). This avoids `global` statements and the associated linter warning (`PLW0603`).
4. **Logging**: Uses `logger.info` instead of `self.log` for batch progress, providing structured server-side logging.
