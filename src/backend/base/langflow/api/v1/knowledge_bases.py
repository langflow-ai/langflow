import asyncio
import json
import shutil
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.base.models.unified_models import get_embedding_model_options
from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent
from lfx.log import logger
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.schemas import TaskResponse
from langflow.services.database.models.jobs.model import JobStatus, JobType
from langflow.services.deps import get_job_service, get_settings_service, get_task_service
from langflow.services.jobs.service import JobService
from langflow.services.task.service import TaskService

router = APIRouter(tags=["Knowledge Bases"], prefix="/knowledge_bases", include_in_schema=False)


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


class KnowledgeBaseInfo(BaseModel):
    id: str
    dir_name: str = ""
    name: str
    embedding_provider: str | None = "Unknown"
    embedding_model: str | None = "Unknown"
    size: int = 0
    words: int = 0
    characters: int = 0
    chunks: int = 0
    avg_chunk_size: float = 0.0
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    separator: str | None = None
    status: str = "empty"
    failure_reason: str | None = None
    last_job_id: str | None = None
    source_types: list[str] = []


class BulkDeleteRequest(BaseModel):
    kb_names: list[str]


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    embedding_provider: str
    embedding_model: str


class AddSourceRequest(BaseModel):
    source_name: str
    files: list[str]  # List of file paths or file IDs


class ChunkInfo(BaseModel):
    id: str
    content: str
    char_count: int
    metadata: dict | None = None


class PaginatedChunkResponse(BaseModel):
    chunks: list[ChunkInfo]
    total: int
    page: int
    limit: int
    total_pages: int


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
        "HuggingFace": ["sentence-transformers", "huggingface", "bert-"],
        "Cohere": ["cohere", "embed-english", "embed-multilingual"],
        "Google": ["palm", "gecko", "google"],
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
                        for provider, patterns in provider_patterns.items():
                            if any(pattern in provider_value for pattern in patterns):
                                return provider

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

    If fast=True, it will attempt to read from the embedding_metadata.json file.
    If essential fields are missing (backward compatibility), it will fall back
    to a full scan once and update the metadata file (backfill).
    """
    metadata: dict[str, Any] = {
        "chunks": 0,
        "words": 0,
        "characters": 0,
        "avg_chunk_size": 0.0,
        "embedding_provider": "Unknown",
        "embedding_model": "Unknown",
        "id": "",
        "size": 0,
        "source_types": [],
        "chunk_size": None,
        "chunk_overlap": None,
        "separator": None,
    }

    metadata_file = kb_path / "embedding_metadata.json"
    backfill_needed = False

    try:
        # 1. Try reading from existing metadata file
        if metadata_file.exists():
            try:
                with metadata_file.open("r", encoding="utf-8") as f:
                    embedding_metadata = json.load(f)
                    if isinstance(embedding_metadata, dict):
                        # Update all fields that exist in the JSON
                        for key in metadata:
                            if key in embedding_metadata:
                                metadata[key] = embedding_metadata[key]

                        # Check if we are missing any essential keys (for backward compatibility)
                        # ensure all metadata template keys are present in the actual file
                        if not all(key in embedding_metadata for key in metadata):
                            backfill_needed = True
            except (OSError, json.JSONDecodeError) as _:
                logger.exception("Error reading embedding metadata file '%s'", metadata_file)
                backfill_needed = True
        else:
            backfill_needed = True

        # 2. If we have all the data we need and fast=True, we can return early
        if fast and not backfill_needed:
            return metadata

        # 3. Slow path: Calculate missing data
        # Fallback to detection if provider/model are Unknown
        if metadata["embedding_provider"] == "Unknown":
            metadata["embedding_provider"] = detect_embedding_provider(kb_path)
            backfill_needed = True
        if metadata["embedding_model"] == "Unknown":
            metadata["embedding_model"] = detect_embedding_model(kb_path)
            backfill_needed = True

        # Calculate size if missing
        if metadata.get("size") == 0:
            metadata["size"] = get_directory_size(kb_path)
            backfill_needed = True

        # Read schema for text column information
        schema_data = None
        schema_file = kb_path / "schema.json"
        if schema_file.exists():
            try:
                with schema_file.open("r", encoding="utf-8") as f:
                    schema_data = json.load(f)
                    if not isinstance(schema_data, list):
                        schema_data = None
            except (ValueError, TypeError, OSError) as _:
                logger.exception("Error reading schema file '%s'", schema_file)

        # Create vector store and fetch count
        try:
            chroma = Chroma(
                persist_directory=str(kb_path),
                collection_name=kb_path.name,
            )
            # Access the raw collection and get count (this is fast)
            collection = chroma._collection  # noqa: SLF001
            metadata["chunks"] = collection.count()

            # Perform the heavy scan for text metrics if needed
            results = collection.get(include=["documents", "metadatas"])
            source_chunks = pd.DataFrame(
                {
                    "document": results["documents"],
                    "metadata": results["metadatas"],
                }
            )

            # Get text columns and calculate metrics
            text_columns = get_text_columns(source_chunks, schema_data)
            if text_columns:
                words, characters = calculate_text_metrics(source_chunks, text_columns)
                metadata["words"] = words
                metadata["characters"] = characters

                # Calculate average chunk size
                if int(metadata["chunks"]) > 0:
                    metadata["avg_chunk_size"] = round(int(characters) / int(metadata["chunks"]), 1)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Chroma-based metadata calculation failed for {kb_path.name}: {e}")

        # 4. Backfill: Update the metadata file for next time
        if backfill_needed:
            try:
                current_json = {}
                if metadata_file.exists():
                    current_json = json.loads(metadata_file.read_text())
                current_json.update(metadata)
                metadata_file.write_text(json.dumps(current_json, indent=2))
                logger.info(f"Backfilled metadata for knowledge base: {kb_path.name}")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not save backfilled metadata for {kb_path.name}: {e}")

    except (OSError, ValueError, TypeError) as exc:
        logger.exception("Error processing knowledge base directory '%s': %s: %s", kb_path, type(exc).__name__, exc)

    return metadata


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
) -> None:
    """Clean up ChromaDB chunks associated with a specific job ID.

    This is used for rollback during failed ingestion or when cancelling an ingestion job.

    Args:
        job_id: The job ID whose chunks should be removed
        kb_path: Path to the knowledge base directory
        kb_name: Name of the knowledge base (used as collection name)
    """
    try:
        chroma = Chroma(
            persist_directory=str(kb_path),
            collection_name=kb_name,
        )
        await chroma.adelete(where={"job_id": str(job_id)})
        await logger.ainfo(f"Cleaned up chunks for job {job_id} in knowledge base '{kb_name}'")
    except Exception as cleanup_error:  # noqa: BLE001
        await logger.aerror(f"Failed to clean up chunks for job {job_id}: {cleanup_error}")


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
) -> dict[str, object]:
    """Internal function to perform the actual ingestion logic with rollback capability."""
    chroma = None
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

        batch_size = 100
        job_id_str = str(task_job_id)

        for file_name, file_content in files_data:
            try:
                # Decode text content
                text_content = file_content.decode("utf-8", errors="ignore")

                if not text_content.strip():
                    await logger.awarning(f"File {file_name} is empty or not readable as text")
                    continue

                # Split into chunks
                chunks = text_splitter.split_text(text_content)
                file_chunks_count = len(chunks)
                await logger.ainfo(f"Processing {file_name}: splitting into {file_chunks_count} chunks")

                # Ingest this file's chunks in batches to prevent memory and API issues
                for i in range(0, file_chunks_count, batch_size):
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
                                "job_id": job_id_str,  # Tag each chunk with the unique job ID
                            },
                        )
                        for j, chunk in enumerate(batch_chunks)
                    ]

                    # Embed and add to Chroma using the native async method
                    await chroma.aadd_documents(batch_docs)

                    # Yield to the event loop to allow other tasks (like logging) to run
                    await asyncio.sleep(0.01)

                    if (i + batch_size) % 1000 == 0 or (i + batch_size) >= file_chunks_count:
                        msg = (
                            f"Progress for {file_name}: "
                            f"{min(i + batch_size, file_chunks_count)}/{file_chunks_count} chunks ingested"
                        )
                        await logger.ainfo(msg)

                total_chunks_created += file_chunks_count
                processed_files.append(file_name)

            except Exception as file_error:
                await logger.aerror(f"Error processing file {file_name}: {file_error}")
                # Re-raise to trigger the collection-level rollback
                raise

        if not processed_files:
            msg = "No files were successfully processed"
            raise ValueError(msg)

        # After successful ingestion, recalculate full metadata (cached for listing)
        try:
            full_metadata = get_kb_metadata(kb_path, fast=False)
            # Add directory size
            full_metadata["size"] = get_directory_size(kb_path)

            # Save to metadata file
            metadata_path = kb_path / "embedding_metadata.json"
            embedding_metadata = {}
            if metadata_path.exists():
                embedding_metadata = json.loads(metadata_path.read_text())

            # Collect unique file extensions from successfully processed files
            new_source_types = list({f.rsplit(".", 1)[-1].lower() for f in processed_files if "." in f})
            existing_source_types = embedding_metadata.get("source_types", [])
            full_metadata["source_types"] = list(set(existing_source_types + new_source_types))

            # Persist chunk settings used for this ingestion
            full_metadata["chunk_size"] = chunk_size
            full_metadata["chunk_overlap"] = chunk_overlap
            full_metadata["separator"] = separator

            # Merge updated fields
            embedding_metadata.update(full_metadata)
            metadata_path.write_text(json.dumps(embedding_metadata, indent=2))
            await logger.ainfo(f"Updated metadata for {kb_name} with {full_metadata['chunks']} total chunks")
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"Failed to update metadata cache for {kb_name}: {e}")

        msg = (
            f"Successfully ingested {len(processed_files)} file(s) with {total_chunks_created} chunks into '{kb_name}'"
        )
        return {
            "message": msg,
            "files_processed": len(processed_files),
            "chunks_created": total_chunks_created,
            "file_names": processed_files,
        }

    except Exception as e:
        await logger.aerror(f"Error in background ingestion: {e!s}. Initiating rollback...")
        # Rollback: Delete any chunks added during this specific job attempt
        await _cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
        raise
    finally:
        # Release Chroma's resources safely.
        # Avoid calling _server.stop() as it can leave the SQLite WAL in an
        # un-checkpointed state, making subsequent reads fail.
        if chroma is not None:
            try:
                # Reset the reference so the client can be garbage-collected
                chroma = None
            except Exception:  # noqa: BLE001
                # Silently log the failure to release resources
                logger.debug("Failed to release Chroma resources during ingestion cleanup", exc_info=True)


@router.post("", status_code=HTTPStatus.CREATED)
@router.post("/", status_code=HTTPStatus.CREATED)
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseInfo:
    """Create a new knowledge base with embedding configuration."""
    from datetime import datetime, timezone

    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_name = request.name.strip().replace(" ", "_")

        # Validate KB name
        min_kb_name_length = 3
        if not kb_name or len(kb_name) < min_kb_name_length:
            raise HTTPException(status_code=400, detail="Knowledge base name must be at least 3 characters")

        kb_path = kb_root_path / kb_user / kb_name

        # Check if KB already exists
        if kb_path.exists():
            raise HTTPException(status_code=409, detail=f"Knowledge base '{kb_name}' already exists")

        # Create KB directory
        kb_path.mkdir(parents=True, exist_ok=True)
        kb_id = uuid.uuid4()

        # Save embedding metadata
        embedding_metadata = {
            "embedding_provider": request.embedding_provider,
            "embedding_model": request.embedding_model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "id": str(kb_id),
        }

        metadata_path = kb_path / "embedding_metadata.json"
        metadata_path.write_text(json.dumps(embedding_metadata, indent=2))

        return KnowledgeBaseInfo(
            id=str(kb_id),
            dir_name=kb_name,
            name=kb_name.replace("_", " "),
            embedding_provider=request.embedding_provider,
            embedding_model=request.embedding_model,
            size=0,
            words=0,
            characters=0,
            chunks=0,
            avg_chunk_size=0.0,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up if something went wrong
        if kb_path.exists():
            shutil.rmtree(kb_path)
        raise HTTPException(status_code=500, detail=f"Error creating knowledge base: {e!s}") from e


@router.post("/preview-chunks", status_code=HTTPStatus.OK)
async def preview_chunks(
    _current_user: CurrentActiveUser,
    files: Annotated[list[UploadFile], File(description="Files to preview chunking for")],
    chunk_size: Annotated[int, Form()] = 1000,
    chunk_overlap: Annotated[int, Form()] = 200,
    separator: Annotated[str, Form()] = "\n",
    max_chunks: Annotated[int, Form()] = 5,
) -> dict[str, object]:
    """Preview how files will be chunked without storing anything.

    Uses the same RecursiveCharacterTextSplitter as the ingest endpoint
    so the preview accurately reflects what will be stored.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Build separators list: user separator first, then defaults
        separators = None
        if separator:
            # Unescape common escape sequences
            actual_separator = separator.replace("\\n", "\n").replace("\\t", "\t")
            separators = [actual_separator, "\n\n", "\n", " ", ""]

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )

        file_previews: list[dict[str, Any]] = []
        for uploaded_file in files:
            try:
                file_content = await uploaded_file.read()
                file_name = uploaded_file.filename or "unknown"
                text_content = file_content.decode("utf-8", errors="ignore")

                if not text_content.strip():
                    file_previews.append(
                        {
                            "file_name": file_name,
                            "total_chunks": 0,
                            "preview_chunks": [],
                        }
                    )
                    continue

                # Only process enough text for the requested preview chunks
                # to avoid splitting the entire file (which is slow for large files)
                preview_text_limit = max_chunks * chunk_size * 3
                preview_text = text_content[:preview_text_limit]
                chunks = text_splitter.split_text(preview_text)

                # Estimate total chunks from full text length
                effective_step = max(chunk_size - chunk_overlap, 1)
                estimated_total = max(
                    len(chunks),
                    int((len(text_content) - chunk_overlap) / effective_step),
                )

                # Track character positions for metadata
                preview_chunks = []
                position = 0
                for i, chunk in enumerate(chunks[:max_chunks]):
                    # Find the actual position of this chunk in the original text
                    chunk_start = text_content.find(chunk, position)
                    if chunk_start == -1:
                        chunk_start = position
                    chunk_end = chunk_start + len(chunk)

                    preview_chunks.append(
                        {
                            "content": chunk,
                            "index": i,
                            "char_count": len(chunk),
                            "start": chunk_start,
                            "end": chunk_end,
                        }
                    )
                    position = chunk_start + 1

                file_previews.append(
                    {
                        "file_name": file_name,
                        "total_chunks": estimated_total,
                        "preview_chunks": preview_chunks,
                    }
                )

            except Exception as file_error:  # noqa: BLE001
                logger.warning("Error previewing file %s: %s", uploaded_file.filename, file_error)
                file_previews.append(
                    {
                        "file_name": uploaded_file.filename or "unknown",
                        "total_chunks": 0,
                        "preview_chunks": [],
                    }
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error previewing chunks: {e!s}") from e
    else:
        return {"files": file_previews}


@router.post("/{kb_name}/ingest", status_code=HTTPStatus.OK)
async def ingest_files_to_knowledge_base(
    kb_name: str,
    current_user: CurrentActiveUser,
    files: Annotated[list[UploadFile], File(description="Files to ingest into the knowledge base")],
    source_name: Annotated[str, Form()] = "",
    chunk_size: Annotated[int, Form()] = 1000,
    chunk_overlap: Annotated[int, Form()] = 200,
    separator: Annotated[str, Form()] = "",
) -> dict[str, object] | TaskResponse:
    """Upload and ingest files directly into a knowledge base.

    This endpoint:
    1. Accepts file uploads
    2. Extracts text and chunks the content
    3. Creates embeddings using the KB's configured embedding model
    4. Stores the vectors in the knowledge base
    """
    try:
        settings = get_settings_service().settings
        max_file_size_upload = settings.max_file_size_upload

        files_data = []

        for uploaded_file in files:
            file_size = uploaded_file.size
            if file_size > max_file_size_upload * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail=f"File {uploaded_file.filename} exceeds the maximum upload size of {max_file_size_upload}MB",
                )
            content = await uploaded_file.read()
            files_data.append((uploaded_file.filename or "unknown", content))

        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Read embedding metadata
        metadata = get_kb_metadata(kb_path)
        if not metadata:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base missing embedding configuration. Please create a new KB or reconfigure it.",
            )

        embedding_provider = metadata.get("embedding_provider")
        embedding_model = metadata.get("embedding_model")

        # Handle backward compatibility: generate asset_id if not present
        asset_id_str = metadata.get("id")
        if not asset_id_str:
            # Generate new UUID for older KBs without asset_id
            asset_id = uuid.uuid4()
            # Persist the new ID to metadata
            metadata_path = kb_path / "embedding_metadata.json"
            if metadata_path.exists():
                try:
                    embedding_metadata = json.loads(metadata_path.read_text())
                    embedding_metadata["id"] = str(asset_id)
                    metadata_path.write_text(json.dumps(embedding_metadata, indent=2))
                except (OSError, json.JSONDecodeError) as e:
                    await logger.awarning(f"Could not update metadata with asset_id: {e}")
        else:
            asset_id = uuid.UUID(asset_id_str)

        if not embedding_provider or not embedding_model:
            raise HTTPException(status_code=400, detail="Invalid embedding configuration")

        # Get services and create job before async/sync split
        job_service = get_job_service()
        job_id = uuid.uuid4()

        # Create job record in database for both async and sync paths
        await job_service.create_job(
            job_id=job_id, flow_id=job_id, job_type=JobType.INGESTION, asset_id=asset_id, asset_type="knowledge_base"
        )

        # Always use async path: fire and forget the ingestion logic wrapped in status updates
        task_service = get_task_service()
        await task_service.fire_and_forget_task(
            job_service.execute_with_status,
            job_id=job_id,
            run_coro_func=_perform_ingestion,
            kb_name=kb_name,
            kb_path=kb_path,
            files_data=files_data,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator=separator,
            source_name=source_name,
            current_user=current_user,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            task_job_id=job_id,
        )
        return TaskResponse(id=str(job_id), href=f"/task/{job_id}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting files to knowledge base: {e!s}") from e


@router.get("", status_code=HTTPStatus.OK)
@router.get("/", status_code=HTTPStatus.OK)
async def list_knowledge_bases(
    current_user: CurrentActiveUser,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> list[KnowledgeBaseInfo]:
    """List all available knowledge bases."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user

        if not kb_path.exists():
            return []

        knowledge_bases = []
        kb_ids_to_fetch = []  # Collect KB IDs for batch fetching

        # First pass: Load all KBs into memory
        for kb_dir in kb_path.iterdir():
            if not kb_dir.is_dir() or kb_dir.name.startswith("."):
                continue
            try:
                # Get metadata from KB files (fast path)
                metadata = get_kb_metadata(kb_dir, fast=True)

                # Extract KB ID from metadata (stored as string, convert to UUID)
                kb_id_str = metadata.get("id")
                if kb_id_str:
                    try:
                        kb_id_uuid = uuid.UUID(kb_id_str)
                        kb_ids_to_fetch.append(kb_id_uuid)
                    except (ValueError, AttributeError):
                        # If ID is invalid, skip job status lookup for this KB
                        kb_id_str = None

                chunks_count = metadata["chunks"]
                status = "ready" if chunks_count > 0 else "empty"
                failure_reason = None
                kb_info = KnowledgeBaseInfo(
                    id=kb_id_str or kb_dir.name,  # Fallback to directory name if no ID
                    dir_name=kb_dir.name,
                    name=kb_dir.name.replace("_", " "),
                    embedding_provider=metadata["embedding_provider"],
                    embedding_model=metadata["embedding_model"],
                    size=metadata["size"],
                    words=metadata["words"],
                    characters=metadata["characters"],
                    chunks=chunks_count,
                    avg_chunk_size=metadata["avg_chunk_size"],
                    chunk_size=metadata.get("chunk_size"),
                    chunk_overlap=metadata.get("chunk_overlap"),
                    separator=metadata.get("separator"),
                    status=status,
                    failure_reason=failure_reason,
                    last_job_id=None,
                    source_types=metadata.get("source_types", []),
                )
                knowledge_bases.append(kb_info)

            except OSError as _:
                # Log the exception and skip directories that can't be read
                await logger.aexception("Error reading knowledge base directory '%s'", kb_dir)
                continue

        # Second pass: Batch fetch all job statuses in a single query
        if kb_ids_to_fetch:
            latest_jobs = await job_service.get_latest_jobs_by_asset_ids(kb_ids_to_fetch)

            # Map job statuses back to knowledge bases
            # Normalize to frontend-expected values: ready, ingesting, failed, empty
            job_status_map = {
                "queued": "ingesting",
                "in_progress": "ingesting",
                "failed": "failed",
                "cancelled": "failed",
                "timed_out": "failed",
            }
            for kb_info in knowledge_bases:
                try:
                    kb_uuid = uuid.UUID(kb_info.id)
                    if kb_uuid in latest_jobs:
                        job = latest_jobs[kb_uuid]
                        raw_status = job.status.value if hasattr(job.status, "value") else str(job.status)
                        mapped = job_status_map.get(raw_status)
                        if mapped:
                            kb_info.status = mapped
                        # For "completed", keep the file-marker / chunk-count status already set
                        kb_info.last_job_id = str(job.job_id)
                except (ValueError, AttributeError):
                    # If KB ID is not a valid UUID, skip job status update
                    pass

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing knowledge bases: {e!s}") from e
    else:
        return knowledge_bases


@router.get("/{kb_name}", status_code=HTTPStatus.OK)
async def get_knowledge_base(kb_name: str, current_user: CurrentActiveUser) -> KnowledgeBaseInfo:
    """Get detailed information about a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Get size of the directory
        size = get_directory_size(kb_path)

        # Get metadata from KB files
        metadata = get_kb_metadata(kb_path)

        chunks_count = metadata["chunks"]
        status = "ready" if chunks_count > 0 else "empty"
        return KnowledgeBaseInfo(
            id=kb_name,
            dir_name=kb_name,
            name=kb_name.replace("_", " "),
            embedding_provider=metadata["embedding_provider"],
            embedding_model=metadata["embedding_model"],
            size=size,
            words=metadata["words"],
            characters=metadata["characters"],
            chunks=chunks_count,
            avg_chunk_size=metadata["avg_chunk_size"],
            chunk_size=metadata.get("chunk_size"),
            chunk_overlap=metadata.get("chunk_overlap"),
            separator=metadata.get("separator"),
            status=status,
            source_types=metadata.get("source_types", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting knowledge base '{kb_name}': {e!s}") from e


@router.get("/{kb_name}/chunks", status_code=HTTPStatus.OK)
async def get_knowledge_base_chunks(
    kb_name: str,
    current_user: CurrentActiveUser,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str, Query(description="Filter chunks whose text contains this substring")] = "",
) -> PaginatedChunkResponse:
    """Get chunks from a specific knowledge base with pagination."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Create vector store
        # Optimization: We could use a cache here, but Chroma's persistent client
        # handles its own internal caching and re-opening is relatively fast.
        chroma = Chroma(
            persist_directory=str(kb_path),
            collection_name=kb_name,
        )

        # Access the raw collection
        collection = chroma._collection  # noqa: SLF001

        search_term = search.strip()

        if search_term:
            # When searching, fetch all matching docs then paginate in-memory
            where_doc = {"$contains": search_term}
            all_results = collection.get(
                include=["documents", "metadatas"],
                where_document=where_doc,
            )
            total_count = len(all_results["ids"])
            offset = (page - 1) * limit
            sliced_ids = all_results["ids"][offset : offset + limit]
            sliced_docs = all_results["documents"][offset : offset + limit]
            sliced_metas = all_results["metadatas"][offset : offset + limit]
        else:
            # No search - use Chroma's native pagination
            total_count = collection.count()
            offset = (page - 1) * limit
            results = collection.get(
                include=["documents", "metadatas"],
                limit=limit,
                offset=offset,
            )
            sliced_ids = results["ids"]
            sliced_docs = results["documents"]
            sliced_metas = results["metadatas"]

        chunks = []
        for doc_id, document, metadata in zip(sliced_ids, sliced_docs, sliced_metas, strict=False):
            content = document or ""
            chunks.append(
                ChunkInfo(
                    id=doc_id,
                    content=content,
                    char_count=len(content),
                    metadata=metadata,
                )
            )
        return PaginatedChunkResponse(
            chunks=chunks,
            total=total_count,
            page=page,
            limit=limit,
            total_pages=(total_count + limit - 1) // limit if total_count > 0 else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chunks for '{kb_name}': {e!s}") from e


@router.delete("/{kb_name}", status_code=HTTPStatus.OK)
async def delete_knowledge_base(kb_name: str, current_user: CurrentActiveUser) -> dict[str, str]:
    """Delete a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Delete the entire knowledge base directory
        shutil.rmtree(kb_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting knowledge base '{kb_name}': {e!s}") from e
    else:
        return {"message": f"Knowledge base '{kb_name}' deleted successfully"}


@router.delete("", status_code=HTTPStatus.OK)
@router.delete("/", status_code=HTTPStatus.OK)
async def delete_knowledge_bases_bulk(request: BulkDeleteRequest, current_user: CurrentActiveUser) -> dict[str, object]:
    """Delete multiple knowledge bases."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_user_path = kb_root_path / kb_user
        deleted_count = 0
        not_found_kbs = []

        for kb_name in request.kb_names:
            kb_path = kb_user_path / kb_name

            if not kb_path.exists() or not kb_path.is_dir():
                not_found_kbs.append(kb_name)
                continue

            try:
                # Delete the entire knowledge base directory
                shutil.rmtree(kb_path)
                deleted_count += 1
            except (OSError, PermissionError) as e:
                await logger.aexception("Error deleting knowledge base '%s': %s", kb_name, e)
                # Continue with other deletions even if one fails

        if not_found_kbs and deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Knowledge bases not found: {', '.join(not_found_kbs)}")

        result = {
            "message": f"Successfully deleted {deleted_count} knowledge base(s)",
            "deleted_count": deleted_count,
        }

        if not_found_kbs:
            result["not_found"] = ", ".join(not_found_kbs)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting knowledge bases: {e!s}") from e
    else:
        return result


@router.post("/{kb_name}/cancel", status_code=HTTPStatus.OK)
async def cancel_ingestion(
    kb_name: str,
    current_user: CurrentActiveUser,
    job_service: Annotated[JobService, Depends(get_job_service)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> dict[str, str]:
    """Cancel the ongoing ingestion task for a knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Get KB metadata to extract asset_id
        metadata = get_kb_metadata(kb_path, fast=True)
        asset_id_str = metadata.get("id")

        if not asset_id_str:
            raise HTTPException(status_code=400, detail="Knowledge base missing asset ID")

        try:
            asset_id = uuid.UUID(asset_id_str)
        except (ValueError, AttributeError) as e:
            raise HTTPException(status_code=400, detail="Invalid asset ID") from e

        # Fetch the latest ingestion job for this KB
        latest_jobs = await job_service.get_latest_jobs_by_asset_ids([asset_id])

        if asset_id not in latest_jobs:
            raise HTTPException(status_code=404, detail=f"No ingestion job found for the knowledge base {kb_name}")

        job = latest_jobs[asset_id]
        job_status = job.status.value if hasattr(job.status, "value") else str(job.status)

        # Check if job is already completed or failed
        if job_status in ["completed", "failed", "cancelled", "timed_out"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel job with status '{job_status}'")

        revoked = await task_service.revoke_task(job.job_id)
        await job_service.update_job_status(job.job_id, JobStatus.CANCELLED)

        # Clean up any partially ingested chunks from this job
        await _cleanup_chroma_chunks_by_job(job.job_id, kb_path, kb_name)

        if revoked:
            message = f"Ingestion job for {job.job_id} cancelled successfully."
        else:
            message = f"Job {job.job_id} is already cancelled."
    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling ingestion: {e!s}") from e
    else:
        return {"message": message}
