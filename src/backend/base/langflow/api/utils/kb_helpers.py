import asyncio
import contextlib
import gc
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
import chromadb.errors
import pandas as pd
from chromadb.api.shared_system_client import SharedSystemClient
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.base.data.utils import extract_text_from_bytes
from lfx.base.knowledge_bases.backends import BackendType, create_backend
from lfx.base.knowledge_bases.backends.base import (
    METADATA_KEY_CHUNK_INDEX,
    METADATA_KEY_FILE_NAME,
    METADATA_KEY_INGESTED_AT,
    METADATA_KEY_JOB_ID,
    METADATA_KEY_SOURCE,
    METADATA_KEY_SOURCE_METADATA,
    METADATA_KEY_SOURCE_TYPE,
    METADATA_KEY_TOTAL_CHUNKS,
    BaseVectorStoreBackend,
)
from lfx.base.knowledge_bases.ingestion_sources import (
    FileUploadSource,
    IngestionItemResult,
    IngestionSummary,
    KBIngestionSource,
)
from lfx.base.knowledge_bases.ingestion_sources.base import IngestionItemStatus, IngestionRunStatus
from lfx.base.vectorstores.chroma_security import chroma_langchain_collection_kwargs
from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent
from lfx.log import logger

from langflow.api.utils import CurrentActiveUser
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseStatus
from langflow.services.deps import get_settings_service
from langflow.services.jobs.service import JobService
from langflow.utils.kb_constants import (
    DELETE_BACKOFF_SECONDS,
    EXPONENTIAL_BACKOFF_MULTIPLIER,
    INGESTION_BATCH_SIZE,
    MAX_DELETE_RETRIES,
    MAX_RETRY_ATTEMPTS,
)

# Default ingestion source type written to every chunk created via the
# direct file-upload path. Phase 1 will introduce additional source types
# (folder, connectors, URL, template) through the ingestion-source registry.
DEFAULT_INGESTION_SOURCE_TYPE = "file_upload"

# Marker file dropped inside a KB directory whose row has been deleted from
# the DB but whose on-disk contents could not be removed (most commonly
# because Chroma still holds an exclusive SQLite lock on Windows).  Listing
# code paths skip directories containing this file so the deleted KB does
# not reappear in the UI before the next server restart cleans up the dir.
KB_DELETED_SENTINEL = ".kb_deleted"


class IngestionCancelledError(Exception):
    """Custom error for when an ingestion job is cancelled."""


def chunk_text_for_ingestion(
    text: str,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    separator: str | None = None,
) -> list[str]:
    r"""Split text into chunks using ``RecursiveCharacterTextSplitter``.

    Single source of truth for chunking config used by every ingestion path —
    KB file ingestion and Memory Base raw / preprocessed message ingestion.
    Centralizing this keeps chunk-size / overlap behavior identical so a
    chunk that fits in one path won't suddenly overflow in another.

    ``separator``: when provided, escaped newlines (``"\\n"``) are unescaped
    and the value is passed as a single-element ``separators`` list, matching
    the behavior of ``KBIngestionHelper.perform_ingestion``.

    Returns ``[]`` for empty / whitespace-only input.
    """
    if not text or not text.strip():
        return []
    splitter_kwargs: dict = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
    if separator:
        splitter_kwargs["separators"] = [separator.replace("\\n", "\n")]
    splitter = RecursiveCharacterTextSplitter(**splitter_kwargs)
    return splitter.split_text(text)


class KBStorageHelper:
    """Helper class for Knowledge Base storage and path management."""

    @staticmethod
    def get_root_path() -> Path:
        """Lazy load and return the knowledge bases root directory.

        Not cached: reading from the settings service is cheap, and a
        process-wide ``@lru_cache`` would lock in a mis-configured
        value until restart even when the operator fixes it. Making
        the read live also keeps the behaviour consistent with other
        settings-dependent helpers in the codebase.
        """
        settings = get_settings_service().settings
        knowledge_directory = settings.knowledge_bases_dir
        if not knowledge_directory:
            msg = "Knowledge bases directory is not set in the settings."
            raise ValueError(msg)
        return Path(knowledge_directory).expanduser()

    @staticmethod
    def get_directory_size(path: Path) -> int:
        """Calculate the total size of all files in a directory."""
        total_size = 0
        try:
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except (OSError, PermissionError):
            pass
        return total_size

    @staticmethod
    def get_fresh_chroma_client(kb_path: Path) -> chromadb.PersistentClient:
        """Get a fresh Chroma client with a unique session ID to avoid 'readonly' errors."""
        path_key = str(kb_path)
        try:
            if path_key in SharedSystemClient._identifier_to_system:  # noqa: SLF001
                del SharedSystemClient._identifier_to_system[path_key]  # noqa: SLF001
        except KeyError as e:
            logger.debug(f"Failed to clear existing Chroma registry entry for {path_key}: {e}")

        return chromadb.PersistentClient(
            path=path_key,
            settings=Settings(
                is_persistent=True,
                persist_directory=path_key,
                chroma_otel_service_name=str(uuid.uuid4()),
            ),
        )

    @staticmethod
    def release_chroma_resources(kb_path: Path) -> None:
        """Release ChromaDB resources by clearing the registry entry and forcing GC."""
        path_key = str(kb_path)
        try:
            if path_key in SharedSystemClient._identifier_to_system:  # noqa: SLF001
                del SharedSystemClient._identifier_to_system[path_key]  # noqa: SLF001
        except KeyError:
            pass
        gc.collect()

    @staticmethod
    def delete_storage(kb_path: Path, kb_name: str) -> bool:
        """Teardown ChromaDB connections and delete KB directory with retry logic.

        Handles ChromaDB SQLite file locks that can prevent deletion, particularly
        on Windows where mandatory file locks block deletion of open files.
        Uses retry with exponential backoff and a sentinel-file fallback when
        physical removal is impossible.

        The sentinel-file fallback (``.kb_deleted``) is preferred over the
        previous rename-based fallback because Windows can refuse to rename a
        directory whose contents are still locked open, in which case the
        directory remained at its original name and the disk-scan listing
        path re-discovered it as a valid KB.  Writing a marker file inside
        the dir works in cases where rename does not, and the listing layer
        treats it identically to a missing dir.

        Returns:
            True if the KB is no longer visible to listing code (either
            because the dir was removed, or because a sentinel was written
            after a failed rmtree).  False only when both physical removal
            and the sentinel write fail.
        """
        if not kb_path.exists():
            return True

        # Teardown ChromaDB collection to release handles
        try:
            has_data = any((kb_path / m).exists() for m in ["chroma", "chroma.sqlite3", "index"])
            if has_data:
                client = KBStorageHelper.get_fresh_chroma_client(kb_path)
                chroma = Chroma(client=client, collection_name=kb_name, **chroma_langchain_collection_kwargs())
                with contextlib.suppress(Exception):
                    chroma.delete_collection()
                chroma = None
                client = None
        except (OSError, ValueError, TypeError, chromadb.errors.ChromaError) as e:
            logger.debug("Collection teardown failed for %s: %s", kb_path.name, e)

        gc.collect()

        for attempt in range(MAX_DELETE_RETRIES):
            try:
                if attempt > 0:
                    time.sleep(DELETE_BACKOFF_SECONDS * (2**attempt))

                _remove_sqlite_lock_files(kb_path)
                _truncate_sqlite_files(kb_path)
                gc.collect()

                shutil.rmtree(kb_path, ignore_errors=False)

                if not kb_path.exists():
                    logger.info("Deleted knowledge base %s on attempt %d", kb_name, attempt + 1)
                    return True

            except OSError as e:
                if attempt < MAX_DELETE_RETRIES - 1:
                    logger.debug("KB deletion attempt %d failed for %s: %s", attempt + 1, kb_name, e)
                else:
                    logger.warning(
                        "KB deletion failed for %s after %d attempts: %s",
                        kb_name,
                        MAX_DELETE_RETRIES,
                        e,
                    )

        # Fallback: drop a sentinel inside the dir so the listing code paths
        # treat it as deleted even though the bytes are still on disk.  Done
        # AFTER the final rmtree attempt so anything that did get cleaned out
        # of the dir does not also remove the sentinel we just wrote.
        if kb_path.exists() and kb_path.is_dir():
            try:
                (kb_path / KB_DELETED_SENTINEL).touch(exist_ok=True)
            except OSError as e:
                logger.warning("Could not write %s sentinel for %s: %s", KB_DELETED_SENTINEL, kb_name, e)
                return False
            logger.info("Wrote %s sentinel for %s; dir remains on disk pending restart", KB_DELETED_SENTINEL, kb_name)
            return True

        return False

    @staticmethod
    def is_kb_dir_deleted(kb_path: Path) -> bool:
        """Return True if the KB directory carries the deletion sentinel.

        Used by listing endpoints and the disk-scan fallback in
        :func:`get_knowledge_bases` so a KB whose row was deleted but whose
        bytes could not be removed (locked-file case) does not reappear in
        the UI.
        """
        try:
            return kb_path.is_dir() and (kb_path / KB_DELETED_SENTINEL).is_file()
        except OSError:
            # Permission errors / disappearing dir under our feet -> treat as
            # not-deleted; the caller will fall through to its own checks.
            return False

    @staticmethod
    def clear_deletion_sentinel(kb_path: Path) -> None:
        """Remove a leftover ``.kb_deleted`` marker before reusing the path.

        Called from the create / first-ingest paths so a recreate-with-the-
        same-name immediately after a failed delete does not silently vanish
        from listings.  Safe to call when the marker is absent.
        """
        marker = kb_path / KB_DELETED_SENTINEL
        try:
            marker.unlink(missing_ok=True)
        except OSError as e:
            logger.debug("Could not clear %s sentinel under %s: %s", KB_DELETED_SENTINEL, kb_path, e)


def _remove_sqlite_lock_files(kb_path: Path) -> None:
    """Remove SQLite auxiliary files (WAL, SHM, journal) that hold locks."""
    for pattern in ["*.sqlite3-wal", "*.sqlite3-shm", "*.sqlite3-journal"]:
        for lock_file in kb_path.glob(pattern):
            try:
                lock_file.unlink()
            except OSError as e:
                logger.debug("Could not remove lock file %s: %s", lock_file.name, e)


def _truncate_sqlite_files(kb_path: Path) -> None:
    """Truncate SQLite database files to release locks."""
    for sqlite_file in kb_path.glob("*.sqlite3"):
        try:
            with sqlite_file.open("r+b") as f:
                f.truncate(0)
        except OSError as e:
            logger.debug("Could not truncate %s: %s", sqlite_file.name, e)


class KBAnalysisHelper:
    """Helper class for Knowledge Base metadata, metrics, and configuration detection."""

    @staticmethod
    def get_metadata(kb_path: Path, *, fast: bool = False) -> dict:
        """Extract metadata from a knowledge base directory."""
        metadata_file = kb_path / "embedding_metadata.json"
        defaults = {
            "chunks": 0,
            "words": 0,
            "characters": 0,
            "avg_chunk_size": 0.0,
            "embedding_provider": "Unknown",
            "embedding_model": "Unknown",
            "id": str(uuid.uuid4()),
            "size": 0,
            "source_types": [],
            "chunk_size": None,
            "chunk_overlap": None,
            "separator": None,
            "backend_type": BackendType.CHROMA.value,
            "backend_config": {},
        }

        metadata = {}
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
            except (OSError, json.JSONDecodeError):
                logger.warning(f"Failed to parse metadata file for {kb_path.name}, resetting to defaults.")

        missing_keys = not all(k in metadata for k in defaults)
        has_unknowns = metadata.get("embedding_provider") == "Unknown" or metadata.get("embedding_model") == "Unknown"
        # Detect stale zero-chunk metadata: the file claims 0 chunks but
        # Chroma data exists on disk, meaning data was ingested without updating
        # the metrics (e.g. via the KnowledgeIngestionComponent before the fix).
        has_chroma_data = any((kb_path / m).exists() for m in ["chroma", "chroma.sqlite3", "index"])
        stale_chunks = metadata.get("chunks", 0) == 0 and has_chroma_data
        directory_size: int | None = None

        if fast and not missing_keys and not stale_chunks:
            return metadata

        backfill_needed = not metadata_file.exists() or missing_keys or (not fast and has_unknowns)

        if backfill_needed:
            for key, default_val in defaults.items():
                if key not in metadata or (key == "id" and not metadata[key]):
                    metadata[key] = default_val
            if not isinstance(metadata.get("backend_config"), dict):
                metadata["backend_config"] = {}

            try:
                if directory_size is None:
                    directory_size = KBStorageHelper.get_directory_size(kb_path)
                metadata["size"] = directory_size
                if metadata.get("embedding_provider") == "Unknown":
                    metadata["embedding_provider"] = KBAnalysisHelper._detect_embedding_provider(kb_path)
                if metadata.get("embedding_model") == "Unknown":
                    metadata["embedding_model"] = KBAnalysisHelper._detect_embedding_model(kb_path)

                metadata_file.write_text(json.dumps(metadata, indent=2))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
                logger.debug(f"Metadata backfill failed for {kb_path}: {e}")

        # Recount metrics from Chroma if metadata claims 0 chunks but data exists
        if stale_chunks:
            try:
                KBAnalysisHelper.update_text_metrics(kb_path, metadata)
                if directory_size is None:
                    directory_size = KBStorageHelper.get_directory_size(kb_path)
                metadata["size"] = directory_size
                metadata_file.write_text(json.dumps(metadata, indent=2))
            except (OSError, ValueError, TypeError, json.JSONDecodeError, chromadb.errors.ChromaError) as e:
                logger.debug(f"Stale metrics recount failed for {kb_path}: {e}")

        return metadata

    @staticmethod
    async def update_text_metrics_via_backend(metadata: dict, backend) -> None:
        """Backend-agnostic metrics refresh.

        Drives ``chunks`` / ``words`` / ``characters`` / ``avg_chunk_size``
        from the backend's ``count`` + ``iter_documents`` abstraction so
        every vector-store target (Chroma / Mongo / Astra / Postgres) is
        covered. Silently tolerates iterator failures — metrics are
        cosmetic, and raising here would wrongly fail an ingestion whose
        writes already succeeded.
        """
        try:
            total_chunks = await backend.count()
        except Exception as exc:  # noqa: BLE001 — backend-level issues are best-effort
            logger.debug(f"Backend count() failed during metrics refresh: {exc}")
            total_chunks = 0
        metadata["chunks"] = total_chunks

        if total_chunks <= 0:
            return

        total_words = 0
        total_characters = 0
        try:
            async for batch in backend.iter_documents(batch_size=5000):
                if not batch:
                    continue
                source_chunks = pd.DataFrame({"document": [doc.content for doc in batch]})
                words, characters = KBAnalysisHelper._calculate_text_metrics(source_chunks, ["document"])
                total_words += words
                total_characters += characters
        except Exception as exc:  # noqa: BLE001 — see note above
            logger.debug(f"Backend iter_documents failed during metrics refresh: {exc}")
            return

        metadata["words"] = total_words
        metadata["characters"] = total_characters
        metadata["avg_chunk_size"] = round(total_characters / total_chunks, 1) if total_chunks > 0 else 0.0

    @staticmethod
    def update_text_metrics(kb_path: Path, metadata: dict, chroma: Chroma | None = None) -> None:
        """Update text metrics (chunks, words, characters) for a knowledge base."""
        created_locally = chroma is None
        client = None
        try:
            if created_locally:
                client = KBStorageHelper.get_fresh_chroma_client(kb_path)
                chroma = Chroma(client=client, collection_name=kb_path.name, **chroma_langchain_collection_kwargs())

            if chroma is None:
                return
            collection = chroma._collection  # noqa: SLF001
            metadata["chunks"] = collection.count()

            if metadata["chunks"] > 0:
                total_words = 0
                total_characters = 0
                # Use a robust batch size to avoid SQLite limits and memory pressure
                batch_size = 5000

                for offset in range(0, metadata["chunks"], batch_size):
                    results = collection.get(
                        include=["documents"],
                        limit=batch_size,
                        offset=offset,
                    )
                    if not results["documents"]:
                        break

                    # Chroma collections always return the text content within the 'documents' field
                    source_chunks = pd.DataFrame({"document": results["documents"]})
                    words, characters = KBAnalysisHelper._calculate_text_metrics(source_chunks, ["document"])
                    total_words += words
                    total_characters += characters

                metadata["words"] = total_words
                metadata["characters"] = total_characters
                metadata["avg_chunk_size"] = (
                    round(total_characters / metadata["chunks"], 1) if metadata["chunks"] > 0 else 0.0
                )
        except (OSError, ValueError, TypeError, json.JSONDecodeError, chromadb.errors.ChromaError) as e:
            logger.debug(f"Metrics update failed for {kb_path.name}: {e}")
        finally:
            if created_locally:
                client = None
                chroma = None
                KBStorageHelper.release_chroma_resources(kb_path)

    @staticmethod
    def _detect_embedding_provider(kb_path: Path) -> str:
        """Internal helper to detect the embedding provider."""
        provider_patterns = {
            "OpenAI": ["openai", "text-embedding-ada", "text-embedding-3"],
            "Azure OpenAI": ["azure"],
            "HuggingFace": ["sentence-transformers", "huggingface", "bert-"],
            "Cohere": ["cohere", "embed-english", "embed-multilingual"],
            "Google": ["palm", "gecko", "google"],
            "Ollama": ["ollama"],
            "Chroma": ["chroma"],
        }

        for config_file in kb_path.glob("*.json"):
            try:
                with config_file.open("r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    if not isinstance(config_data, dict):
                        continue

                    config_str = json.dumps(config_data).lower()
                    provider_fields = ["embedding_provider", "provider", "embedding_model_provider"]
                    for field in provider_fields:
                        if field in config_data:
                            provider_value = str(config_data[field]).lower()
                            for provider, patterns in provider_patterns.items():
                                if any(pattern in provider_value for pattern in patterns):
                                    return provider
                            if provider_value and provider_value != "unknown":
                                return provider_value.title()

                    for provider, patterns in provider_patterns.items():
                        if any(pattern in config_str for pattern in patterns):
                            return provider

            except (OSError, json.JSONDecodeError):
                logger.exception("Error reading config file '%s'", config_file)
                continue

        if (kb_path / "chroma").exists():
            return "Chroma"
        if (kb_path / "vectors.npy").exists():
            return "Local"

        return "Unknown"

    @staticmethod
    def _detect_embedding_model(kb_path: Path) -> str:
        """Internal helper to detect the embedding model."""
        metadata_file = kb_path / "embedding_metadata.json"
        if metadata_file.exists():
            try:
                with metadata_file.open("r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    if isinstance(metadata, dict) and "embedding_model" in metadata:
                        model_value = str(metadata.get("embedding_model", "unknown"))
                        if model_value and model_value.lower() != "unknown":
                            return model_value
            except (OSError, json.JSONDecodeError):
                logger.exception("Error reading embedding metadata file '%s'", metadata_file)

        for config_file in kb_path.glob("*.json"):
            if config_file.name == "embedding_metadata.json":
                continue

            try:
                with config_file.open("r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    if not isinstance(config_data, dict):
                        continue

                    model_fields = ["embedding_model", "model", "embedding_model_name", "model_name"]
                    for field in model_fields:
                        if field in config_data:
                            model_value = str(config_data[field])
                            if model_value and model_value.lower() != "unknown":
                                return model_value

                    if "openai" in json.dumps(config_data).lower():
                        openai_models = ["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"]
                        config_str = json.dumps(config_data).lower()
                        for model in openai_models:
                            if model in config_str:
                                return model

                    if "model" in config_data:
                        model_name = str(config_data["model"])
                        hf_patterns = ["sentence-transformers", "all-MiniLM", "all-mpnet", "multi-qa"]
                        if any(pattern in model_name for pattern in hf_patterns):
                            return model_name

            except (OSError, json.JSONDecodeError):
                logger.exception("Error reading config file '%s'", config_file)
                continue

        return "Unknown"

    @staticmethod
    def _calculate_text_metrics(df: pd.DataFrame, text_columns: list[str]) -> tuple[int, int]:
        """Internal helper to calculate total words and characters."""
        total_words = 0
        total_characters = 0

        for col in text_columns:
            if col not in df.columns:
                continue

            text_series = df[col].astype(str).fillna("")
            total_characters += int(text_series.str.len().sum())
            total_words += int(text_series.str.split().str.len().sum())

        return total_words, total_characters


class KBIngestionHelper:
    """Helper class for Knowledge Base ingestion processes."""

    @staticmethod
    async def perform_ingestion(
        kb_name: str,
        kb_path: Path,
        files_data: list[tuple[str, bytes]] | None,
        chunk_size: int,
        chunk_overlap: int,
        separator: str,
        source_name: str,
        current_user: CurrentActiveUser,
        model_selection: dict | list[dict],
        task_job_id: uuid.UUID,
        job_service: JobService,
        source_type: str = DEFAULT_INGESTION_SOURCE_TYPE,
        source_metadata: dict | None = None,
        source: KBIngestionSource | None = None,
        per_file_metadata: dict[str, dict] | None = None,
    ) -> dict[str, object]:
        """Orchestrate the ingestion of content into a knowledge base.

        Accepts either a preloaded ``files_data`` list (the long-standing
        file-upload path) or a ``source`` — any ``KBIngestionSource``
        implementation. When both are provided, ``source`` wins; when
        neither is, raises ``ValueError``.

        ``model_selection`` is the canonical embedding-config payload
        (matching ``KnowledgeBaseRecord.model_selection``); provider /
        model name are derived via the ``get_embedding_provider`` /
        ``get_embedding_model`` helpers when this function needs them
        for ``build_embeddings``.

        Every chunk carries ``source_type`` + ``source_metadata`` so
        Phase 2 visibility tooling can group, filter, and drill into
        chunks by origin.

        Persistence side-effects: on entry, inserts a PENDING row in
        ``ingestion_run`` and transitions it to RUNNING; on exit,
        finalizes the row with succeeded / failed / skipped counters,
        per-item details, and one of SUCCEEDED / PARTIAL / FAILED /
        CANCELLED.
        """
        # Lazy import: the service reaches into langflow DB plumbing we
        # can't expose at module scope without widening lfx's surface.
        from langflow.api.utils import ingestion_run_service, knowledge_base_service
        from langflow.api.utils.knowledge_base_service import (
            get_embedding_model,
            get_embedding_provider,
        )

        embedding_provider = get_embedding_provider(model_selection)
        embedding_model = get_embedding_model(model_selection)

        if source is None:
            if not files_data:
                msg = "perform_ingestion requires either 'source' or non-empty 'files_data'."
                raise ValueError(msg)
            source_config: dict[str, Any] = {"files": files_data, "source_name": source_name}
            if per_file_metadata:
                source_config["per_file_metadata"] = per_file_metadata
            source = FileUploadSource(
                user_id=current_user.id,
                source_config=source_config,
            )

        try:
            await source.validate_config()
        except ValueError as exc:
            await logger.aerror("Ingestion source validation failed: %s", exc)
            raise

        summary = IngestionSummary(
            kb_name=kb_name,
            source_type=source.source_type.value,
            user_id=current_user.id,
            job_id=task_job_id,
            source_config=source.describe().get("config") or {},
            user_metadata=dict(source_metadata or {}),
        )
        # Link the run to the ``knowledge_base`` row when one exists.
        # During the Phase 1.5 rollout some KBs still only exist in
        # JSON files; in that case ``kb_id`` stays None and the run
        # row keeps pointing at ``kb_name`` for N-1 compatibility.
        kb_record = await knowledge_base_service.get_by_user_and_name(current_user.id, kb_name)
        kb_record_id = kb_record.id if kb_record is not None else None
        run_id = await ingestion_run_service.create_run(
            kb_name=kb_name,
            user_metadata=dict(source_metadata or {}),
            source=source,
            job_id=task_job_id,
            user_id=current_user.id,
            kb_id=kb_record_id,
        )
        await ingestion_run_service.mark_running(run_id)
        # Reflect the in-flight ingestion on the KB row so the UI can
        # surface accurate status + failure_reason without re-deriving
        # them from job state alone.
        if kb_record_id is not None:
            try:
                await knowledge_base_service.update_status(
                    kb_record_id,
                    status=KnowledgeBaseStatus.INGESTING,
                    failure_reason=None,
                )
            except Exception as exc:  # noqa: BLE001
                await logger.awarning("KB status update to INGESTING lagged for %s: %s", kb_name, exc)

        # ``create_backend`` can return any ``BaseVectorStoreBackend``
        # subclass. Typing the local as the narrower ``ChromaBackend``
        # would hide type errors when this code path routes to
        # MongoDB/Astra/Postgres.
        backend: BaseVectorStoreBackend | None = None
        final_status = IngestionRunStatus.SUCCEEDED
        final_error: str | None = None
        encoded_metadata_tag = json.dumps(source_metadata) if source_metadata else ""
        source_extension_tags: set[str] = set()
        try:
            embeddings = await KBIngestionHelper.build_embeddings(embedding_provider, embedding_model, current_user)
            backend_type_value = (
                kb_record.backend_type if kb_record and kb_record.backend_type else BackendType.CHROMA.value
            )
            backend_config = (kb_record.backend_config or {}) if kb_record is not None else {}
            backend = create_backend(
                backend_type_value,
                kb_name=kb_name,
                kb_path=kb_path,
                backend_config=backend_config,
                embedding_function=embeddings,
                # Forward the user id so Mongo/Astra/Postgres backends can
                # pull their connection URI / tokens from Langflow's
                # variable_service instead of forcing the server to export
                # matching env vars.
                user_id=getattr(current_user, "id", None),
            )

            job_id_str = str(task_job_id)

            async for item in source.list_items():
                if await KBIngestionHelper.is_job_cancelled(job_service, task_job_id):
                    raise IngestionCancelledError

                await logger.ainfo("Starting ingestion of %s for %s", item.display_name, kb_name)

                try:
                    content_obj = await source.fetch_content(item)
                except (OSError, ValueError) as fetch_exc:
                    summary.record_item(
                        IngestionItemResult(
                            item_id=item.item_id,
                            display_name=item.display_name,
                            status=IngestionItemStatus.FAILED,
                            error_message=f"fetch failed: {fetch_exc}",
                        ),
                        size_bytes=item.size_bytes or 0,
                    )
                    await logger.awarning("Failed to fetch %s: %s", item.display_name, fetch_exc)
                    continue

                size_bytes = len(content_obj.raw_bytes)
                text = extract_text_from_bytes(content_obj.file_name, content_obj.raw_bytes)
                if not text.strip():
                    summary.record_item(
                        IngestionItemResult(
                            item_id=item.item_id,
                            display_name=item.display_name,
                            status=IngestionItemStatus.SKIPPED,
                            error_message="no extractable text",
                        ),
                        size_bytes=size_bytes,
                    )
                    continue

                # Collapse run-level + per-item metadata into one blob so
                # Phase 2 can render either view. Per-item wins on key
                # collision: callers that set both run-level and per-file
                # tags expect the file-specific value to override the
                # batch default (e.g. ``confidential=true`` on one file
                # in an otherwise public batch).
                combined_metadata: dict = dict(source_metadata or {})
                if item.source_metadata:
                    combined_metadata.update(item.source_metadata)
                item_metadata_tag = json.dumps(combined_metadata) if combined_metadata else encoded_metadata_tag

                chunks = chunk_text_for_ingestion(
                    text,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    separator=separator,
                )
                docs = [
                    Document(
                        page_content=c,
                        metadata={
                            METADATA_KEY_SOURCE: source_name or content_obj.file_name,
                            METADATA_KEY_FILE_NAME: content_obj.file_name,
                            METADATA_KEY_CHUNK_INDEX: i,
                            METADATA_KEY_TOTAL_CHUNKS: len(chunks),
                            METADATA_KEY_INGESTED_AT: datetime.now(timezone.utc).isoformat(),
                            METADATA_KEY_JOB_ID: job_id_str,
                            METADATA_KEY_SOURCE_TYPE: source.source_type.value or source_type,
                            METADATA_KEY_SOURCE_METADATA: item_metadata_tag,
                        },
                    )
                    for i, c in enumerate(chunks)
                ]

                # Writes that exhaust the retry budget still propagate to
                # the outer handler so the whole run can roll back
                # uncommitted chunks. Only per-item fetch/extraction
                # failures are caught and continue (above).
                item_chunks_written = await KBIngestionHelper.write_documents_to_backend(
                    documents=docs,
                    backend=backend,
                    task_job_id=task_job_id,
                    job_service=job_service,
                )
                if item_chunks_written < len(docs):
                    # Job was cancelled mid-item — bail out and let the
                    # outer handler roll the run back.
                    raise IngestionCancelledError

                summary.record_item(
                    IngestionItemResult(
                        item_id=item.item_id,
                        display_name=item.display_name,
                        status=IngestionItemStatus.SUCCEEDED,
                        chunks_created=item_chunks_written,
                    ),
                    size_bytes=size_bytes,
                )
                # Track extension for the legacy ``source_types`` list
                # in the KB's ``embedding_metadata.json``.
                if "." in content_obj.file_name:
                    source_extension_tags.add(content_obj.file_name.rsplit(".", 1)[-1].lower())

            # Status order matters: a run with zero successes and any
            # failure is FAILED; a run with mixed outcomes (some failed
            # OR some skipped) is PARTIAL; otherwise SUCCEEDED. Skipped
            # items (e.g. empty file, no extractable text) used to fall
            # through to SUCCEEDED, which made notifications and the
            # runs list misreport an ingestion that produced 0 chunks.
            if summary.failed > 0 and summary.succeeded == 0:
                final_status = IngestionRunStatus.FAILED
            elif summary.failed > 0 or summary.skipped > 0:
                final_status = IngestionRunStatus.PARTIAL
            else:
                final_status = IngestionRunStatus.SUCCEEDED

            metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
            # Backend-agnostic metrics refresh — ``raw_langchain_store`` was
            # Chroma-only and broke Mongo/Astra/Postgres with AttributeError
            # (which then falsely marked the run failed and rolled back the
            # chunks we'd just written).
            await KBAnalysisHelper.update_text_metrics_via_backend(metadata, backend)
            metadata["size"] = KBStorageHelper.get_directory_size(kb_path)
            metadata["chunk_size"] = chunk_size
            metadata["chunk_overlap"] = chunk_overlap
            metadata["separator"] = separator or None
            metadata_path = kb_path / "embedding_metadata.json"
            existing_source_types = metadata.get("source_types", [])
            metadata["source_types"] = sorted(set(existing_source_types) | source_extension_tags)
            metadata_path.write_text(json.dumps(metadata, indent=2))

            # Mirror the refreshed stats onto the DB row. Done after
            # the JSON write so if the DB update fails, older service
            # versions still see a consistent filesystem view.
            if kb_record_id is not None:
                try:
                    await knowledge_base_service.update_stats(
                        kb_record_id,
                        chunks=metadata.get("chunks", 0),
                        words=metadata.get("words", 0),
                        characters=metadata.get("characters", 0),
                        size_bytes=metadata.get("size", 0),
                        source_types=metadata.get("source_types", []),
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        separator=separator or None,
                    )
                except Exception as exc:  # noqa: BLE001
                    await logger.awarning("KB DB stat update lagged for %s: %s", kb_name, exc)
                # Clear any previous failure marker once the run finishes
                # writing chunks; ``final_status`` (PARTIAL/SUCCEEDED) is
                # not "failed", so the KB row should reflect READY.
                try:
                    await knowledge_base_service.update_status(
                        kb_record_id,
                        status=KnowledgeBaseStatus.READY,
                        failure_reason=None,
                    )
                except Exception as exc:  # noqa: BLE001
                    await logger.awarning("KB status update to READY lagged for %s: %s", kb_name, exc)

            await logger.ainfo(
                "Completed ingestion for %s (succeeded=%d failed=%d skipped=%d)",
                kb_name,
                summary.succeeded,
                summary.failed,
                summary.skipped,
            )

            return {
                "message": f"Successfully ingested {summary.succeeded} item(s)",
                "files_processed": summary.succeeded,
                "chunks_created": summary.chunks_created,
                "ingestion_run_id": str(run_id),
                "failed": summary.failed,
                "skipped": summary.skipped,
            }

        except IngestionCancelledError:
            final_status = IngestionRunStatus.CANCELLED
            final_error = "ingestion cancelled by user"
            await logger.awarning("Ingestion job %s was cancelled; rolling back partial data.", task_job_id)
            await KBIngestionHelper.cleanup_chroma_chunks_by_job(
                task_job_id,
                kb_path,
                kb_name,
                backend_type=kb_record.backend_type if kb_record is not None else None,
                backend_config=kb_record.backend_config if kb_record is not None else None,
                user_id=getattr(current_user, "id", None),
            )
            if kb_record_id is not None:
                try:
                    await knowledge_base_service.update_status(
                        kb_record_id,
                        status=KnowledgeBaseStatus.FAILED,
                        failure_reason=final_error,
                    )
                except Exception as status_exc:  # noqa: BLE001
                    await logger.awarning("KB status update to FAILED (cancel) lagged for %s: %s", kb_name, status_exc)
            return {"message": "Job cancelled", "ingestion_run_id": str(run_id)}
        except Exception as exc:
            final_status = IngestionRunStatus.FAILED
            final_error = str(exc) or exc.__class__.__name__
            # ``aexception`` includes the traceback so the underlying
            # backend error (e.g. OpenSearch auth / connection failure)
            # is preserved in the server logs even when the UI surface
            # is limited to a single-line ``failure_reason``.
            await logger.aexception("Error in background ingestion for %s: %s. Initiating rollback.", kb_name, exc)
            await KBIngestionHelper.cleanup_chroma_chunks_by_job(
                task_job_id,
                kb_path,
                kb_name,
                backend_type=kb_record.backend_type if kb_record is not None else None,
                backend_config=kb_record.backend_config if kb_record is not None else None,
                user_id=getattr(current_user, "id", None),
            )
            if kb_record_id is not None:
                try:
                    await knowledge_base_service.update_status(
                        kb_record_id,
                        status=KnowledgeBaseStatus.FAILED,
                        failure_reason=final_error,
                    )
                except Exception as status_exc:  # noqa: BLE001
                    await logger.awarning("KB status update to FAILED lagged for %s: %s", kb_name, status_exc)
            raise
        finally:
            if backend is not None:
                await backend.teardown()
            await ingestion_run_service.finalize_run(
                run_id,
                summary=summary,
                status=final_status,
                error_message=final_error,
            )

    @staticmethod
    async def cleanup_chroma_chunks_by_job(
        job_id: uuid.UUID,
        kb_path: Path,
        kb_name: str,
        backend_type: str | None = None,
        backend_config: dict | None = None,
        user_id=None,
    ) -> None:
        """Delete every chunk written by ``job_id`` from this KB.

        Used by the ingestion rollback path on error or cancellation. The
        backend-level filter keyed on ``METADATA_KEY_JOB_ID`` is what makes
        rollbacks safe even when multiple concurrent jobs write to the same
        collection.

        Name kept for backward compatibility — the cleanup now runs through
        whichever backend the KB is configured with, not just Chroma.
        Defaults to Chroma so existing callers still work.
        """
        effective_type = backend_type or BackendType.CHROMA.value
        backend = create_backend(
            effective_type,
            kb_name=kb_name,
            kb_path=kb_path,
            backend_config=backend_config or {},
            user_id=user_id,
        )
        try:
            await backend.delete_by({METADATA_KEY_JOB_ID: str(job_id)})
            await logger.ainfo(f"Cleaned up chunks for job {job_id} in knowledge base '{kb_name}'")
        except (OSError, ValueError, TypeError, chromadb.errors.ChromaError) as cleanup_error:
            await logger.aerror(f"Failed to clean up chunks for job {job_id}: {cleanup_error}")
        finally:
            await backend.teardown()

    @staticmethod
    async def write_documents_to_chroma(
        *,
        documents: list[Document],
        chroma: Chroma,
        task_job_id: uuid.UUID,
        job_service: JobService,
    ) -> int:
        """Write pre-built Documents into an open Chroma collection.

        This is the shared primitive used by both file-based KB ingestion
        (``perform_ingestion``) and message-based Memory Base ingestion.

        Documents must already be chunked and have their metadata populated
        by the caller — this method only handles the batched write, cancellation
        checking, and retry logic.

        Args:
            documents: LangChain Document objects ready for embedding.
            chroma: An already-constructed ``Chroma`` instance pointing at the
                target collection.
            task_job_id: Job ID used to poll for cancellation.
            job_service: Service for checking job status.

        Returns:
            Number of documents successfully written.  If the job is cancelled
            mid-batch this will be less than ``len(documents)``.

        Raises:
            Exception: Re-raises any non-cancellation write failure after the
                retry budget is exhausted.
        """
        written = 0
        for i in range(0, len(documents), INGESTION_BATCH_SIZE):
            if await KBIngestionHelper.is_job_cancelled(job_service, task_job_id):
                return written

            batch = documents[i : i + INGESTION_BATCH_SIZE]
            for attempt in range(MAX_RETRY_ATTEMPTS):
                if await KBIngestionHelper.is_job_cancelled(job_service, task_job_id):
                    return written
                try:
                    await chroma.aadd_documents(batch)
                    break
                except Exception as e:
                    if attempt == MAX_RETRY_ATTEMPTS - 1:
                        raise
                    wait = (attempt + 1) * EXPONENTIAL_BACKOFF_MULTIPLIER
                    await logger.awarning("Write failed, retrying in %ds: %s", wait, e)
                    await asyncio.sleep(wait)

            written += len(batch)
            await asyncio.sleep(0.01)

        return written

    @staticmethod
    async def write_documents_to_backend(
        *,
        documents: list[Document],
        backend: BaseVectorStoreBackend,
        task_job_id: uuid.UUID,
        job_service: JobService,
    ) -> int:
        """Write pre-built Documents through a ``BaseVectorStoreBackend``.

        Backend-agnostic counterpart to :meth:`write_documents_to_chroma`.
        Used by the multi-backend KB ingestion path so Mongo/Astra/
        Postgres/OpenSearch ingestions share the same batching,
        cancellation-checking, and exponential-backoff retry logic that
        Memory Base's Chroma path gets from
        :meth:`write_documents_to_chroma`.

        Documents must already be chunked with metadata populated.

        Returns:
            Number of documents successfully written. Less than
            ``len(documents)`` when the job is cancelled mid-write.

        Raises:
            Exception: Re-raises any non-cancellation write failure
                after the retry budget is exhausted.
        """
        written = 0
        for i in range(0, len(documents), INGESTION_BATCH_SIZE):
            if await KBIngestionHelper.is_job_cancelled(job_service, task_job_id):
                return written

            batch = documents[i : i + INGESTION_BATCH_SIZE]
            for attempt in range(MAX_RETRY_ATTEMPTS):
                if await KBIngestionHelper.is_job_cancelled(job_service, task_job_id):
                    return written
                try:
                    await backend.add_documents(batch)
                    break
                except Exception as exc:
                    if attempt == MAX_RETRY_ATTEMPTS - 1:
                        raise
                    wait = (attempt + 1) * EXPONENTIAL_BACKOFF_MULTIPLIER
                    await logger.awarning("Write failed, retrying in %ds: %s", wait, exc)
                    await asyncio.sleep(wait)

            written += len(batch)
            await asyncio.sleep(0.01)

        return written

    @staticmethod
    async def is_job_cancelled(job_service: JobService, job_id: uuid.UUID) -> bool:
        """Internal helper to check if a job has been cancelled."""
        job = await job_service.get_job_by_job_id(job_id)
        return job is not None and job.status == JobStatus.CANCELLED

    @staticmethod
    async def build_embeddings(provider: str, model: str, current_user):
        """Build a LangChain embeddings instance for a stored KB.

        The provider/model pair is the source of truth recorded in the KB's
        ``embedding_metadata.json`` at creation time. We resolve the embedding
        class and parameter mapping straight from the static registry rather
        than the user-filtered catalog, so retrieval keeps working when:

        - the call originates from a context where the credential lookup
          inside ``get_embedding_model_options`` silently returns an empty
          set of enabled providers (e.g. a thread-bridged async hop), or
        - the user has since disabled the model in their settings.

        The runtime credential is still resolved by ``get_embeddings`` via
        ``get_api_key_for_provider``, so a missing API key still raises a
        clear, user-actionable error at instantiation time.
        """
        from lfx.base.models.unified_models.class_registry import (
            EMBEDDING_PARAM_MAPPINGS,
            EMBEDDING_PROVIDER_CLASS_MAPPING,
        )

        embedding_class = EMBEDDING_PROVIDER_CLASS_MAPPING.get(provider)
        param_mapping = EMBEDDING_PARAM_MAPPINGS.get(provider)
        if not embedding_class or not param_mapping:
            supported = ", ".join(sorted(EMBEDDING_PROVIDER_CLASS_MAPPING))
            msg = (
                f"Embedding model '{model}' for provider '{provider}' could not be "
                f"resolved: provider '{provider}' is not registered. Supported "
                f"providers: {supported}."
            )
            raise ValueError(msg)

        selected_option = {
            "name": model,
            "provider": provider,
            "category": provider,
            "icon": provider,
            "metadata": {
                "embedding_class": embedding_class,
                "param_mapping": param_mapping,
                "model_type": "embeddings",
            },
        }

        # Pass ``ollama_base_url=None`` explicitly so the component does NOT fall
        # back to the input default (``http://localhost:11434``). When the
        # component is built programmatically without this field,
        # ``getattr(self, "ollama_base_url", None)`` returns that localhost
        # default, which is truthy and short-circuits the ``OLLAMA_BASE_URL``
        # global-variable / env resolution inside ``get_embeddings`` — so a KB
        # configured against a remote Ollama server would silently try
        # localhost and fail with "Failed to connect to Ollama". Forcing the
        # value to ``None`` lets ``get_embeddings`` resolve the user's
        # configured base URL (falling back to localhost only when nothing is
        # configured). See https://github.com/langflow-ai/langflow/issues/13883.
        embedding_model = EmbeddingModelComponent(
            model=[selected_option],
            ollama_base_url=None,
            _user_id=current_user.id,
        )
        return embedding_model.build_embeddings()
