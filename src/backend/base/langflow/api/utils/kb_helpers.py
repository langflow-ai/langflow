import asyncio
import contextlib
import gc
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
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

_KNOWLEDGE_BASES_DIR: Path | None = None


def _get_knowledge_bases_dir() -> Path:
    """Lazy load the knowledge bases directory from settings."""
    global _KNOWLEDGE_BASES_DIR  # noqa: PLW0603
    if _KNOWLEDGE_BASES_DIR is None:
        settings = get_settings_service().settings
        knowledge_directory = settings.knowledge_bases_dir
        if not knowledge_directory:
            msg = "Knowledge bases directory is not set in the settings."
            raise ValueError(msg)
        _KNOWLEDGE_BASES_DIR = Path(knowledge_directory).expanduser()
    return _KNOWLEDGE_BASES_DIR


def get_kb_root_path() -> Path:
    """Get the knowledge bases root path."""
    return _get_knowledge_bases_dir()


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


def detect_embedding_provider(kb_path: Path) -> str:
    """Detect the embedding provider from config files and directory structure."""
    # Provider patterns to check for
    provider_patterns = {
        "OpenAI": ["openai", "text-embedding-ada", "text-embedding-3"],
        "Azure OpenAI": ["azure"],
        "HuggingFace": ["sentence-transformers", "huggingface", "bert-"],
        "Cohere": ["cohere", "embed-english", "embed-multilingual"],
        "Google": ["palm", "gecko", "google"],
        "Ollama": ["ollama"],
        "Chroma": ["chroma"],
    }

    # Check JSON config files for provider information
    for config_file in kb_path.glob("*.json"):
        try:
            with config_file.open("r", encoding="utf-8") as f:
                config_data = json.load(f)
                if not isinstance(config_data, dict):
                    continue

                config_str = json.dumps(config_data).lower()

                # Check for explicit provider fields first
                provider_fields = ["embedding_provider", "provider", "embedding_model_provider"]
                for field in provider_fields:
                    if field in config_data:
                        provider_value = str(config_data[field]).lower()
                        # If it matches a pattern, return the standardized name
                        for provider, patterns in provider_patterns.items():
                            if any(pattern in provider_value for pattern in patterns):
                                return provider
                        # If it is an explicit field but no pattern match, return it title-cased
                        if provider_value and provider_value != "unknown":
                            return provider_value.title()

                # Check for model name patterns
                for provider, patterns in provider_patterns.items():
                    if any(pattern in config_str for pattern in patterns):
                        return provider

        except (OSError, json.JSONDecodeError) as _:
            logger.exception("Error reading config file '%s'", config_file)
            continue

    # Fallback to directory structure
    if (kb_path / "chroma").exists():
        return "Chroma"
    if (kb_path / "vectors.npy").exists():
        return "Local"

    return "Unknown"


def detect_embedding_model(kb_path: Path) -> str:
    """Detect the embedding model from config files."""
    # First check the embedding metadata file (most accurate)
    metadata_file = kb_path / "embedding_metadata.json"
    if metadata_file.exists():
        try:
            with metadata_file.open("r", encoding="utf-8") as f:
                metadata = json.load(f)
                if isinstance(metadata, dict) and "embedding_model" in metadata:
                    # Check for embedding model field
                    model_value = str(metadata.get("embedding_model", "unknown"))
                    if model_value and model_value.lower() != "unknown":
                        return model_value
        except (OSError, json.JSONDecodeError) as _:
            logger.exception("Error reading embedding metadata file '%s'", metadata_file)

    # Check other JSON config files for model information
    for config_file in kb_path.glob("*.json"):
        # Skip the embedding metadata file since we already checked it
        if config_file.name == "embedding_metadata.json":
            continue

        try:
            with config_file.open("r", encoding="utf-8") as f:
                config_data = json.load(f)
                if not isinstance(config_data, dict):
                    continue

                # Check for explicit model fields first and return the actual model name
                model_fields = ["embedding_model", "model", "embedding_model_name", "model_name"]
                for field in model_fields:
                    if field in config_data:
                        model_value = str(config_data[field])
                        if model_value and model_value.lower() != "unknown":
                            return model_value

                # Check for OpenAI specific model names
                if "openai" in json.dumps(config_data).lower():
                    openai_models = ["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"]
                    config_str = json.dumps(config_data).lower()
                    for model in openai_models:
                        if model in config_str:
                            return model

                # Check for HuggingFace model names (usually in model field)
                if "model" in config_data:
                    model_name = str(config_data["model"])
                    # Common HuggingFace embedding models
                    hf_patterns = ["sentence-transformers", "all-MiniLM", "all-mpnet", "multi-qa"]
                    if any(pattern in model_name for pattern in hf_patterns):
                        return model_name

        except (OSError, json.JSONDecodeError) as _:
            logger.exception("Error reading config file '%s'", config_file)
            continue

    return "Unknown"


def get_text_columns(df: pd.DataFrame, schema_data: list | None = None) -> list[str]:
    """Get the text columns to analyze for word/character counts."""
    # First try schema-defined text columns
    if schema_data:
        text_columns = [
            col["column_name"]
            for col in schema_data
            if col.get("vectorize", False) and col.get("data_type") == "string"
        ]
        if text_columns:
            return [col for col in text_columns if col in df.columns]

    # Fallback to common text column names
    common_names = ["text", "content", "document", "chunk"]
    text_columns = [col for col in df.columns if col.lower() in common_names]
    if text_columns:
        return text_columns

    # Last resort: all string columns
    return [col for col in df.columns if df[col].dtype == "object"]


def calculate_text_metrics(df: pd.DataFrame, text_columns: list[str]) -> tuple[int, int]:
    """Calculate total words and characters from text columns."""
    total_words = 0
    total_characters = 0

    for col in text_columns:
        if col not in df.columns:
            continue

        text_series = df[col].astype(str).fillna("")
        total_characters += int(text_series.str.len().sum())
        total_words += int(text_series.str.split().str.len().sum())

    return total_words, total_characters


def get_kb_metadata(kb_path: Path, *, fast: bool = False) -> dict:
    """Extract metadata from a knowledge base directory.

    If fast=True, returns data from embedding_metadata.json.
    If fast=False or keys are missing, performs detection and updates the file.
    This method NEVER opens exploring Chroma to avoid SQLite conflicts.
    """
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

    # 1. Load existing
    metadata = {}
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text())
        except (OSError, json.JSONDecodeError):
            logger.warning(f"Failed to parse metadata file for {kb_path.name}, resetting to defaults.")

    # 2. Check if we need a deep update (backfill)
    # Triggered if: fast=False OR file missing OR keys missing OR legacy Unknowns
    missing_keys = not all(k in metadata for k in defaults)
    has_unknowns = metadata.get("embedding_provider") == "Unknown" or metadata.get("embedding_model") == "Unknown"

    # Early return for fast path if schema is already compliant
    if fast and not missing_keys:
        return metadata

    backfill_needed = not metadata_file.exists() or missing_keys or (not fast and has_unknowns)

    # 3. Handle detection / Reconcile defaults
    if backfill_needed:
        for key, default_val in defaults.items():
            if key not in metadata or (key == "id" and not metadata[key]):
                metadata[key] = default_val

        # Detection logic (Slow path)
        try:
            metadata["size"] = get_directory_size(kb_path)
            if metadata.get("embedding_provider") == "Unknown":
                metadata["embedding_provider"] = detect_embedding_provider(kb_path)
            if metadata.get("embedding_model") == "Unknown":
                metadata["embedding_model"] = detect_embedding_model(kb_path)

            # Persist the alignment
            metadata_file.write_text(json.dumps(metadata, indent=2))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Metadata backfill failed for {kb_path}: {e}")

    return metadata


def _update_text_metrics(kb_path: Path, metadata: dict, chroma: Chroma | None = None) -> None:
    """Internal helper to calculate chunks, words, and characters.

    If 'chroma' is provided, it uses the existing connection to avoid SQLite locking.
    """
    try:
        if chroma is None:
            # Only open a new connection if none exists.
            # Warning: This can cause conflicts if another connection is open in the same thread.
            chroma = Chroma(persist_directory=str(kb_path), collection_name=kb_path.name)

        collection = chroma._collection  # noqa: SLF001
        metadata["chunks"] = collection.count()

        if metadata["chunks"] > 0:
            results = collection.get(include=["documents", "metadatas"])
            source_chunks = pd.DataFrame({"document": results["documents"], "metadata": results["metadatas"]})

            schema_file = kb_path / "schema.json"
            schema_data = None
            if schema_file.exists():
                with schema_file.open("r", encoding="utf-8") as f:
                    schema_data = json.load(f)

            text_columns = get_text_columns(source_chunks, schema_data)
            if text_columns:
                words, characters = calculate_text_metrics(source_chunks, text_columns)
                metadata["words"] = words
                metadata["characters"] = characters
                metadata["avg_chunk_size"] = (
                    round(characters / metadata["chunks"], 1) if metadata["chunks"] > 0 else 0.0
                )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Metrics update failed for {kb_path.name}: {e}")


async def _build_embeddings(provider: str, model: str, current_user):
    """Build embeddings based on provider using EmbeddingModelComponent."""
    # Get available embedding model options for the user
    options = get_embedding_model_options(user_id=current_user.id)

    # Find the specific model option for the provider and model
    selected_option = next((o for o in options if o["provider"] == provider and o["name"] == model), None)

    if not selected_option:
        # If not found in user-specific options, try one more time without user-specific filtering
        # to see if it exists but is just not configured yet
        all_options = get_embedding_model_options()
        selected_option = next((o for o in all_options if o["provider"] == provider and o["name"] == model), None)

        if not selected_option:
            msg = f"Embedding model '{model}' for provider '{provider}' not found."
            raise ValueError(msg)

    # Instantiate the component with the correct model configuration and user ID
    embedding_model = EmbeddingModelComponent(model=[selected_option], _user_id=current_user.id)

    # Build the embeddings object. This returns an EmbeddingsWithModels wrapper.
    embeddings_with_models = embedding_model.build_embeddings()

    # Return the primary LangChain Embeddings instance
    return embeddings_with_models.embeddings


async def _cleanup_chroma_chunks_by_job(
    job_id: uuid.UUID,
    kb_path: Path,
    kb_name: str,
):
    """Clean up ChromaDB chunks associated with a specific job ID."""
    try:
        chroma = Chroma(
            persist_directory=str(kb_path),
            collection_name=kb_name,
        )
        await chroma.adelete(where={"job_id": str(job_id)})
        await logger.ainfo(f"Cleaned up chunks for job {job_id} in knowledge base '{kb_name}'")
    except Exception as cleanup_error:  # noqa: BLE001
        await logger.aerror(f"Failed to clean up chunks for job {job_id}: {cleanup_error}")
    finally:
        chroma = None
        gc.collect()


async def _perform_ingestion(
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
    try:
        processed_files = []
        total_chunks_created = 0

        splitter_kwargs: dict = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
        if separator:
            # Support \n as a literal escape sequence entered by users
            resolved_separator = separator.replace("\\n", "\n")
            splitter_kwargs["separators"] = [resolved_separator]
        text_splitter = RecursiveCharacterTextSplitter(**splitter_kwargs)

        # Build embeddings based on provider
        embeddings = await _build_embeddings(embedding_provider, embedding_model, current_user)

        # Create or update vector store
        chroma = Chroma(
            persist_directory=str(kb_path),
            embedding_function=embeddings,
            collection_name=kb_name,
        )

        batch_size = 200
        job_id_str = str(task_job_id)
        for file_name, file_content in files_data:
            try:
                await logger.ainfo(f"Starting ingestion of {file_name} for {kb_name}")
                text_content = file_content.decode("utf-8", errors="ignore")
                if not text_content.strip():
                    continue

                chunks = text_splitter.split_text(text_content)
                file_chunks_count = len(chunks)

                for i in range(0, file_chunks_count, batch_size):
                    # Check for cancellation before expensive operations
                    current_job = await job_service.get_job_by_job_id(task_job_id)
                    if current_job and current_job.status == JobStatus.CANCELLED:
                        await logger.awarning(
                            f"Job {task_job_id} was cancelled, stopping ingestion early. Cleaning up chunks..."
                        )
                        await _cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
                        chroma = None
                        return {"message": "Job cancelled"}

                    batch_chunks = chunks[i : i + batch_size]
                    batch_docs = [
                        Document(
                            page_content=chunk,
                            metadata={
                                "source": source_name or file_name,
                                "file_name": file_name,
                                "chunk_index": i + j,
                                "total_chunks": file_chunks_count,
                                "ingested_at": datetime.now(timezone.utc).isoformat(),
                                "job_id": job_id_str,
                            },
                        )
                        for j, chunk in enumerate(batch_chunks)
                    ]

                    # Retry mechanism for document addition to handle SQLite locks
                    max_retries = 5
                    for attempt in range(max_retries):
                        try:
                            await chroma.aadd_documents(batch_docs)
                            break
                        except Exception:
                            if attempt == max_retries - 1:
                                raise
                            wait_time = (attempt + 1) * 2
                            await logger.awarning(f"Write attempt {attempt + 1} failed, retrying in {wait_time}s")
                            await asyncio.sleep(wait_time)

                    await asyncio.sleep(0.01)

                total_chunks_created += file_chunks_count
                processed_files.append(file_name)

            except Exception as file_error:
                await logger.aerror(f"Error processing file {file_name}: {file_error}")
                raise

        # Finalize metadata
        metadata = get_kb_metadata(kb_path, fast=True)
        _update_text_metrics(kb_path, metadata, chroma=chroma)
        metadata["size"] = get_directory_size(kb_path)
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

    except Exception as e:
        # Check if job was cancelled during execution
        current_job = await job_service.get_job_by_job_id(task_job_id)
        if current_job and current_job.status == JobStatus.CANCELLED:
            await logger.ainfo(f"Ingestion job {task_job_id} finished after cancellation.")
        else:
            await logger.aerror(f"Error in background ingestion: {e!s}. Initiating rollback...")
            await _cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
        raise
    finally:
        chroma = None
        gc.collect()


def _teardown_kb_storage(kb_path: Path, kb_name: str) -> None:
    """Internal helper to explicitly flush and invalidate Chroma clients before deletion."""
    try:
        # Only attempt if the directory contains vector store markers
        has_data = any((kb_path / m).exists() for m in ["chroma", "chroma.sqlite3", "index"])
        if has_data:
            chroma = Chroma(persist_directory=str(kb_path), collection_name=kb_name)
            # Try to delete the collection via API to clean up internal management state
            with contextlib.suppress(Exception):
                chroma.delete_collection()

            # Ensure the object is eligible for GC
            chroma = None
            gc.collect()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Storage teardown failed for {kb_path.name} (ignoring): {e}")
