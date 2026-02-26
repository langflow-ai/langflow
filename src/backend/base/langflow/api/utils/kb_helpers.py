import asyncio
import contextlib
import gc
import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import chromadb
import chromadb.errors
import pandas as pd
from chromadb.api.shared_system_client import SharedSystemClient
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.base.models.unified_models import get_embedding_model_options
from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent
from lfx.log import logger

from langflow.api.utils import CurrentActiveUser
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_settings_service
from langflow.services.jobs.service import JobService
from langflow.utils.kb_constants import (
    EXPONENTIAL_BACKOFF_MULTIPLIER,
    INGESTION_BATCH_SIZE,
    MAX_RETRY_ATTEMPTS,
)


class IngestionCancelledError(Exception):
    """Custom error for when an ingestion job is cancelled."""


class KBStorageHelper:
    """Helper class for Knowledge Base storage and path management."""

    @staticmethod
    @lru_cache
    def get_root_path() -> Path:
        """Lazy load and return the knowledge bases root directory."""
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
    def teardown_storage(kb_path: Path, kb_name: str) -> None:
        """Explicitly flush and invalidate Chroma clients before directory deletion."""
        try:
            has_data = any((kb_path / m).exists() for m in ["chroma", "chroma.sqlite3", "index"])
            if has_data:
                client = KBStorageHelper.get_fresh_chroma_client(kb_path)
                chroma = Chroma(client=client, collection_name=kb_name)
                with contextlib.suppress(Exception):
                    chroma.delete_collection()
                chroma = None
                gc.collect()
        except (OSError, ValueError, TypeError, chromadb.errors.ChromaError) as e:
            logger.debug(f"Storage teardown failed for {kb_path.name} (ignoring): {e}")


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
        }

        metadata = {}
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
            except (OSError, json.JSONDecodeError):
                logger.warning(f"Failed to parse metadata file for {kb_path.name}, resetting to defaults.")

        missing_keys = not all(k in metadata for k in defaults)
        has_unknowns = metadata.get("embedding_provider") == "Unknown" or metadata.get("embedding_model") == "Unknown"

        if fast and not missing_keys:
            return metadata

        backfill_needed = not metadata_file.exists() or missing_keys or (not fast and has_unknowns)

        if backfill_needed:
            for key, default_val in defaults.items():
                if key not in metadata or (key == "id" and not metadata[key]):
                    metadata[key] = default_val

            try:
                metadata["size"] = KBStorageHelper.get_directory_size(kb_path)
                if metadata.get("embedding_provider") == "Unknown":
                    metadata["embedding_provider"] = KBAnalysisHelper._detect_embedding_provider(kb_path)
                if metadata.get("embedding_model") == "Unknown":
                    metadata["embedding_model"] = KBAnalysisHelper._detect_embedding_model(kb_path)

                metadata_file.write_text(json.dumps(metadata, indent=2))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
                logger.debug(f"Metadata backfill failed for {kb_path}: {e}")

        return metadata

    @staticmethod
    def update_text_metrics(kb_path: Path, metadata: dict, chroma: Chroma | None = None) -> None:
        """Update text metrics (chunks, words, characters) for a knowledge base."""
        try:
            if chroma is None:
                client = KBStorageHelper.get_fresh_chroma_client(kb_path)
                chroma = Chroma(client=client, collection_name=kb_path.name)

            collection = chroma._collection  # noqa: SLF001
            metadata["chunks"] = collection.count()

            if metadata["chunks"] > 0:
                results = collection.get(include=["documents", "metadatas"])
                source_chunks = pd.DataFrame({"document": results["documents"], "metadata": results["metadatas"]})

                # Chroma collections always return the text content within the 'documents' field
                words, characters = KBAnalysisHelper._calculate_text_metrics(source_chunks, ["document"])
                metadata["words"] = words
                metadata["characters"] = characters
                metadata["avg_chunk_size"] = (
                    round(characters / metadata["chunks"], 1) if metadata["chunks"] > 0 else 0.0
                )
        except (OSError, ValueError, TypeError, json.JSONDecodeError, chromadb.errors.ChromaError) as e:
            logger.debug(f"Metrics update failed for {kb_path.name}: {e}")

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
        files_data: list[tuple[str, bytes]],
        chunk_size: int,
        chunk_overlap: int,
        separator: str,
        source_name: str,
        current_user: CurrentActiveUser,
        embedding_provider: str,
        embedding_model: str,
        task_job_id: uuid.UUID,
        job_service: JobService,
    ) -> dict[str, object]:
        """Orchestrate the ingestion of files into a knowledge base."""
        try:
            processed_files = []
            total_chunks_created = 0

            splitter_kwargs: dict = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
            if separator:
                resolved_separator = separator.replace("\\n", "\n")
                splitter_kwargs["separators"] = [resolved_separator]
            text_splitter = RecursiveCharacterTextSplitter(**splitter_kwargs)

            embeddings = await KBIngestionHelper._build_embeddings(embedding_provider, embedding_model, current_user)

            client = KBStorageHelper.get_fresh_chroma_client(kb_path)
            chroma = Chroma(
                client=client,
                embedding_function=embeddings,
                collection_name=kb_name,
            )

            job_id_str = str(task_job_id)
            for file_name, file_content in files_data:
                await logger.ainfo("Starting ingestion of %s for %s", file_name, kb_name)
                content = file_content.decode("utf-8", errors="ignore")
                if not content.strip():
                    continue

                chunks = text_splitter.split_text(content)
                for i in range(0, len(chunks), INGESTION_BATCH_SIZE):
                    if await KBIngestionHelper._is_job_cancelled(job_service, task_job_id):
                        raise IngestionCancelledError

                    batch = chunks[i : i + INGESTION_BATCH_SIZE]
                    docs = [
                        Document(
                            page_content=c,
                            metadata={
                                "source": source_name or file_name,
                                "file_name": file_name,
                                "chunk_index": i + j,
                                "total_chunks": len(chunks),
                                "ingested_at": datetime.now(timezone.utc).isoformat(),
                                "job_id": job_id_str,
                            },
                        )
                        for j, c in enumerate(batch)
                    ]

                    for attempt in range(MAX_RETRY_ATTEMPTS):
                        if await KBIngestionHelper._is_job_cancelled(job_service, task_job_id):
                            raise IngestionCancelledError
                        try:
                            await chroma.aadd_documents(docs)
                            break
                        except Exception as e:
                            if attempt == MAX_RETRY_ATTEMPTS - 1:
                                raise
                            wait = (attempt + 1) * EXPONENTIAL_BACKOFF_MULTIPLIER
                            await logger.awarning("Write failed, retrying in %ds: %s", wait, e)
                            await asyncio.sleep(wait)

                    await asyncio.sleep(0.01)

                total_chunks_created += len(chunks)
                processed_files.append(file_name)

            metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
            KBAnalysisHelper.update_text_metrics(kb_path, metadata, chroma=chroma)
            metadata["size"] = KBStorageHelper.get_directory_size(kb_path)
            metadata["chunk_size"] = chunk_size
            metadata["chunk_overlap"] = chunk_overlap
            metadata["separator"] = separator or None
            metadata_path = kb_path / "embedding_metadata.json"
            new_source_types = list({f.rsplit(".", 1)[-1].lower() for f in processed_files if "." in f})
            existing_source_types = metadata.get("source_types", [])
            metadata["source_types"] = list(set(existing_source_types + new_source_types))
            metadata_path.write_text(json.dumps(metadata, indent=2))
            await logger.ainfo(f"Completed ingestion for {kb_name}")

            return {
                "message": f"Successfully ingested {len(processed_files)} file(s)",
                "files_processed": len(processed_files),
                "chunks_created": total_chunks_created,
            }

        except IngestionCancelledError:
            await logger.awarning(f"Ingestion job {task_job_id} was cancelled. Cleaning up partial data...")
            await KBIngestionHelper.cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
            return {"message": "Job cancelled"}
        except Exception as e:
            await logger.aerror(f"Error in background ingestion: {e!s}. Initiating rollback...")
            await KBIngestionHelper.cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
            raise
        finally:
            chroma = None
            gc.collect()

    @staticmethod
    async def cleanup_chroma_chunks_by_job(
        job_id: uuid.UUID,
        kb_path: Path,
        kb_name: str,
    ) -> None:
        """Clean up ChromaDB chunks associated with a specific job ID."""
        try:
            client = KBStorageHelper.get_fresh_chroma_client(kb_path)
            chroma = Chroma(
                client=client,
                collection_name=kb_name,
            )
            await chroma.adelete(where={"job_id": str(job_id)})
            await logger.ainfo(f"Cleaned up chunks for job {job_id} in knowledge base '{kb_name}'")
        except (OSError, ValueError, TypeError, chromadb.errors.ChromaError) as cleanup_error:
            await logger.aerror(f"Failed to clean up chunks for job {job_id}: {cleanup_error}")
        finally:
            chroma = None
            gc.collect()

    @staticmethod
    async def _is_job_cancelled(job_service: JobService, job_id: uuid.UUID) -> bool:
        """Internal helper to check if a job has been cancelled."""
        job = await job_service.get_job_by_job_id(job_id)
        return job is not None and job.status == JobStatus.CANCELLED

    @staticmethod
    async def _build_embeddings(provider: str, model: str, current_user):
        """Internal helper to build embeddings object."""
        options = get_embedding_model_options(user_id=current_user.id)
        selected_option = next((o for o in options if o["provider"] == provider and o["name"] == model), None)

        if not selected_option:
            all_options = get_embedding_model_options()
            selected_option = next((o for o in all_options if o["provider"] == provider and o["name"] == model), None)

            if not selected_option:
                msg = f"Embedding model '{model}' for provider '{provider}' not found."
                raise ValueError(msg)

        embedding_model = EmbeddingModelComponent(model=[selected_option], _user_id=current_user.id)
        embeddings_with_models = embedding_model.build_embeddings()
        return embeddings_with_models.embeddings
