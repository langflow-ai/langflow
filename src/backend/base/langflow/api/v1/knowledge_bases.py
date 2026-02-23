import asyncio
import gc
import json
import shutil
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Annotated, Any

import chromadb
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.log import logger
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
from langflow.api.utils.kb_helpers import (
    _cleanup_chroma_chunks_by_job,
    _perform_ingestion,
    _teardown_kb_storage,
    get_directory_size,
    get_kb_metadata,
    get_kb_root_path,
)
from langflow.api.v1.schemas import TaskResponse
from langflow.services.database.models.jobs.model import JobStatus, JobType
from langflow.services.deps import get_job_service, get_settings_service, get_task_service
from langflow.services.jobs.service import JobService
from langflow.services.task.service import TaskService

router = APIRouter(tags=["Knowledge Bases"], prefix="/knowledge_bases", include_in_schema=False)


# Helper methods moved to utils/kb_helpers.py


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


# Helper methods moved to utils/kb_helpers.py


@router.post("", status_code=HTTPStatus.CREATED)
@router.post("/", status_code=HTTPStatus.CREATED)
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseInfo:
    """Create a new knowledge base with embedding configuration."""
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

        # Initialize Chroma storage and collection immediately
        # This ensures files exist for read operations and avoids 'readonly' errors later
        try:
            client = chromadb.PersistentClient(path=str(kb_path))
            client.create_collection(name=kb_name)
            # Explicitly delete reference to help release handle
            client = None
            gc.collect()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Initial Chroma setup for {kb_name} failed: {e}")

        # Save full embedding metadata to prevent immediate backfill
        embedding_metadata = {
            "id": str(kb_id),
            "embedding_provider": request.embedding_provider,
            "embedding_model": request.embedding_model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chunks": 0,
            "words": 0,
            "characters": 0,
            "avg_chunk_size": 0.0,
            "size": 0,
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

        # Read embedding metadata (Pass fast=False to ensure legacy KBs are migrated/detected)
        metadata = get_kb_metadata(kb_path, fast=False)
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
            job_service=job_service,
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
                # Use deep update (fast=False) to ensure legacy KBs are migrated on first view
                metadata = get_kb_metadata(kb_dir, fast=False)

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

        # Guard: If no physical chroma data exists, return empty response immediately
        # This prevents 'readonly database' errors when trying to initialize Chroma on an empty directory
        has_data = any((kb_path / m).exists() for m in ["chroma", "chroma.sqlite3", "index"])
        if not has_data:
            return PaginatedChunkResponse(
                chunks=[],
                total=0,
                page=page,
                limit=limit,
                total_pages=0,
            )

        # Create vector store
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
    finally:
        chroma = None
        gc.collect()


@router.delete("/{kb_name}", status_code=HTTPStatus.OK)
async def delete_knowledge_base(kb_name: str, current_user: CurrentActiveUser) -> dict[str, str]:
    """Delete a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name
        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Explicitly teardown KB storage to flush Chroma handles before directory deletion
        _teardown_kb_storage(kb_path, kb_name)

        # Delete the entire knowledge base directory
        shutil.rmtree(kb_path)
        # Final GC collect after removal to ensure zombie handles are flushed
        gc.collect()

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
                # Explicitly teardown KB storage to flush Chroma handles before directory deletion
                _teardown_kb_storage(kb_path, kb_name)

                # Delete the entire knowledge base directory
                shutil.rmtree(kb_path)
                # Final GC collect after removal to ensure zombie handles are flushed
                gc.collect()
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


# Helper methods moved to utils/kb_helpers.py


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
        # Update status immediately so background task can see it
        await job_service.update_job_status(job.job_id, JobStatus.CANCELLED)

        # Clean up any partially ingested chunks from this job
        await _cleanup_chroma_chunks_by_job(job.job_id, kb_path, kb_name)
        gc.collect()

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
