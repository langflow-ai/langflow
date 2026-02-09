import asyncio
import hashlib
import logging
import re
import shutil
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from langchain_chroma import Chroma
from langchain_core.documents import Document
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.memory.model import (
    Memory,
    MemoryCreate,
    MemoryProcessedMessage,
    MemoryRead,
    MemoryUpdate,
)
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_settings_service, session_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["Memories"])

# Track running memory tasks so they can be cancelled
_running_tasks: dict[UUID, asyncio.Task] = {}


def _get_knowledge_bases_dir() -> Path:
    """Get the knowledge bases root directory from settings."""
    settings = get_settings_service().settings
    knowledge_directory = settings.knowledge_bases_dir
    if not knowledge_directory:
        msg = "Knowledge bases directory is not set in the settings."
        raise ValueError(msg)
    return Path(knowledge_directory).expanduser()


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use as a directory name."""
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower().strip())
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    return sanitized[:50] if sanitized else "unnamed"


def _make_kb_name(flow_name: str, memory_id: UUID) -> str:
    """Create a KB directory name for a memory."""
    return f"memory-{_sanitize_name(flow_name)}-{str(memory_id)[:8]}"


def _to_read(m: Memory) -> MemoryRead:
    """Convert a Memory ORM object to a MemoryRead response."""
    return MemoryRead(
        id=m.id,
        name=m.name,
        description=m.description,
        kb_name=m.kb_name,
        embedding_model=m.embedding_model,
        embedding_provider=m.embedding_provider,
        is_active=m.is_active,
        status=m.status,
        error_message=m.error_message,
        total_messages_processed=m.total_messages_processed,
        total_chunks=m.total_chunks,
        sessions_count=m.sessions_count,
        user_id=m.user_id,
        flow_id=m.flow_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
        last_generated_at=m.last_generated_at,
    )


class AddMessagesRequest(BaseModel):
    message_ids: list[UUID]


class MemoryDocumentItem(BaseModel):
    content: str
    sender: str = ""
    session_id: str = ""
    timestamp: str = ""
    message_id: str = ""


class MemoryDocumentsResponse(BaseModel):
    documents: list[MemoryDocumentItem]
    total: int
    sessions: list[str]


# ─── CRUD ────────────────────────────────────────────────────────────────────


@router.post("/", response_model=MemoryRead, status_code=HTTPStatus.CREATED)
async def create_memory(
    *,
    session: DbSession,
    memory_data: MemoryCreate,
    current_user: CurrentActiveUser,
):
    """Create a new memory record and its KB directory on disk."""
    # Validate flow exists
    flow_stmt = select(Flow).where(Flow.id == memory_data.flow_id)
    flow_result = await session.exec(flow_stmt)
    flow = flow_result.first()
    if not flow:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Flow not found")

    # Build temporary id for kb_name
    from uuid import uuid4

    temp_id = uuid4()
    kb_name = _make_kb_name(flow.name, temp_id)

    db_memory = Memory(
        id=temp_id,
        name=memory_data.name,
        description=memory_data.description,
        kb_name=kb_name,
        embedding_model=memory_data.embedding_model,
        embedding_provider=memory_data.embedding_provider,
        is_active=memory_data.is_active,
        status="idle",
        user_id=current_user.id,
        flow_id=memory_data.flow_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    try:
        session.add(db_memory)
        await session.commit()
        await session.refresh(db_memory)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"A memory with the name '{memory_data.name}' already exists for this flow.",
        ) from e

    # Create the KB directory and save embedding metadata
    try:
        kb_root = _get_knowledge_bases_dir()
        kb_path = kb_root / current_user.username / kb_name
        kb_path.mkdir(parents=True, exist_ok=True)

        from lfx.base.models.unified_models import get_api_key_for_provider
        from lfx.components.files_and_knowledge.embedding_utils import save_embedding_metadata

        api_key = get_api_key_for_provider(current_user.id, memory_data.embedding_provider) or ""
        save_embedding_metadata(kb_path, memory_data.embedding_model, api_key)
    except Exception as e:
        logger.exception(f"Failed to create KB directory for memory {db_memory.id}: {e}")

    return _to_read(db_memory)


@router.get("/", response_model=list[MemoryRead], status_code=HTTPStatus.OK)
async def list_memories(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: UUID | None = None,
):
    """List memories, optionally filtered by flow_id."""
    statement = select(Memory).where(Memory.user_id == current_user.id)
    if flow_id:
        statement = statement.where(Memory.flow_id == flow_id)
    statement = statement.order_by(col(Memory.created_at).desc())

    result = await session.exec(statement)
    memories = result.all()

    return [_to_read(m) for m in memories]


@router.get("/{memory_id}", response_model=MemoryRead, status_code=HTTPStatus.OK)
async def get_memory(
    *,
    session: DbSession,
    memory_id: UUID,
    current_user: CurrentActiveUser,
):
    """Get a single memory with stats."""
    statement = select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    result = await session.exec(statement)
    memory = result.first()

    if not memory:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Memory not found")

    return _to_read(memory)


@router.put("/{memory_id}", response_model=MemoryRead, status_code=HTTPStatus.OK)
async def update_memory(
    *,
    session: DbSession,
    memory_id: UUID,
    memory_update: MemoryUpdate,
    current_user: CurrentActiveUser,
):
    """Update memory name/description/is_active."""
    statement = select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    result = await session.exec(statement)
    memory = result.first()

    if not memory:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Memory not found")

    if memory_update.name is not None:
        memory.name = memory_update.name
    if memory_update.description is not None:
        memory.description = memory_update.description
    if memory_update.is_active is not None:
        memory.is_active = memory_update.is_active
    memory.updated_at = datetime.now(timezone.utc)

    session.add(memory)
    await session.commit()
    await session.refresh(memory)

    return _to_read(memory)


@router.delete("/{memory_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_memory(
    *,
    session: DbSession,
    memory_id: UUID,
    current_user: CurrentActiveUser,
):
    """Delete a memory record and its KB directory on disk."""
    statement = select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    result = await session.exec(statement)
    memory = result.first()

    if not memory:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Memory not found")

    # Cancel any running task
    task = _running_tasks.pop(memory_id, None)
    if task and not task.done():
        task.cancel()

    # Delete KB directory
    try:
        kb_root = _get_knowledge_bases_dir()
        kb_path = kb_root / current_user.username / memory.kb_name
        if kb_path.exists():
            shutil.rmtree(kb_path)
    except Exception as e:
        logger.warning(f"Failed to delete KB directory for memory {memory_id}: {e}")

    await session.delete(memory)
    await session.commit()


# ─── Documents endpoint ──────────────────────────────────────────────────────


@router.get(
    "/{memory_id}/documents",
    response_model=MemoryDocumentsResponse,
    status_code=HTTPStatus.OK,
)
async def get_memory_documents(
    *,
    session: DbSession,
    memory_id: UUID,
    current_user: CurrentActiveUser,
    search: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    """Retrieve documents stored in the memory's Chroma KB."""
    statement = select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    result = await session.exec(statement)
    memory = result.first()

    if not memory:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Memory not found")

    try:
        kb_root = _get_knowledge_bases_dir()
        kb_path = kb_root / current_user.username / memory.kb_name

        if not kb_path.exists():
            return MemoryDocumentsResponse(documents=[], total=0, sessions=[])

        chroma = Chroma(
            persist_directory=str(kb_path),
            collection_name=memory.kb_name,
        )
        collection = chroma._collection  # noqa: SLF001

        if search and search.strip():
            # Text search in documents
            raw = collection.get(
                where_document={"$contains": search.strip()},
                include=["documents", "metadatas"],
                limit=limit,
                offset=offset,
            )
        else:
            raw = collection.get(
                include=["documents", "metadatas"],
                limit=limit,
                offset=offset,
            )

        docs_list = raw.get("documents") or []
        metas_list = raw.get("metadatas") or []
        total = collection.count()

        # Build document items
        documents: list[MemoryDocumentItem] = []
        all_sessions: set[str] = set()
        for doc_text, meta in zip(docs_list, metas_list):
            meta = meta or {}
            sid = meta.get("session_id", "")
            if sid:
                all_sessions.add(sid)
            documents.append(
                MemoryDocumentItem(
                    content=doc_text or "",
                    sender=meta.get("sender", ""),
                    session_id=sid,
                    timestamp=meta.get("timestamp", ""),
                    message_id=meta.get("message_id", ""),
                )
            )

        return MemoryDocumentsResponse(
            documents=documents,
            total=total,
            sessions=sorted(all_sessions),
        )

    except Exception as e:
        logger.exception(f"Error fetching documents for memory {memory_id}: {e}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Error fetching documents: {e!s}",
        ) from e


# ─── Vectorization endpoints ─────────────────────────────────────────────────


async def _vectorize_messages(
    memory_id: UUID,
    user_id: UUID,
    username: str,
    only_new: bool = False,
    message_ids: list[UUID] | None = None,
):
    """Background task: vectorize flow messages into the memory KB.

    Args:
        memory_id: The memory to update.
        user_id: Owner user.
        username: Owner username (for KB path).
        only_new: If True, skip already-processed messages.
        message_ids: If provided, only process these specific messages.
    """
    try:
        async with session_scope() as session:
            # Load memory
            stmt = select(Memory).where(Memory.id == memory_id)
            res = await session.exec(stmt)
            memory = res.first()
            if not memory:
                logger.warning(f"Memory {memory_id} not found")
                return

            status_label = "updating" if only_new else "generating"
            memory.status = status_label
            memory.error_message = None
            memory.updated_at = datetime.now(timezone.utc)
            session.add(memory)
            await session.commit()

            try:
                # Get flow messages
                msg_stmt = select(MessageTable).where(MessageTable.flow_id == memory.flow_id)
                if message_ids:
                    msg_stmt = msg_stmt.where(col(MessageTable.id).in_(message_ids))
                msg_stmt = msg_stmt.order_by(col(MessageTable.timestamp).asc())
                msg_result = await session.exec(msg_stmt)
                all_messages = msg_result.all()

                if not all_messages:
                    memory.status = "idle"
                    memory.updated_at = datetime.now(timezone.utc)
                    session.add(memory)
                    await session.commit()
                    return

                # Filter already-processed if only_new
                if only_new:
                    processed_stmt = (
                        select(MemoryProcessedMessage.message_id)
                        .where(MemoryProcessedMessage.memory_id == memory_id)
                    )
                    processed_result = await session.exec(processed_stmt)
                    processed_ids = set(processed_result.all())
                    messages_to_process = [m for m in all_messages if m.id not in processed_ids]
                else:
                    messages_to_process = list(all_messages)

                if not messages_to_process:
                    memory.status = "idle"
                    memory.updated_at = datetime.now(timezone.utc)
                    session.add(memory)
                    await session.commit()
                    return

                # Build documents
                documents: list[Document] = []
                session_ids_seen: set[str] = set()
                for msg in messages_to_process:
                    sender = msg.sender_name or msg.sender or "unknown"
                    text = msg.text or ""
                    content = f"{sender}: {text}"
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    sid = msg.session_id or ""
                    if sid:
                        session_ids_seen.add(sid)

                    doc = Document(
                        page_content=content,
                        metadata={
                            "message_id": str(msg.id),
                            "sender": sender,
                            "session_id": sid,
                            "timestamp": str(msg.timestamp) if msg.timestamp else "",
                            "_id": content_hash,
                        },
                    )
                    documents.append(doc)

                # Build embeddings
                kb_root = _get_knowledge_bases_dir()
                kb_path = kb_root / username / memory.kb_name

                # Get API key from the unified model provider system
                from lfx.base.models.unified_models import get_api_key_for_provider
                from lfx.components.files_and_knowledge.embedding_utils import build_embeddings

                api_key = get_api_key_for_provider(user_id, memory.embedding_provider) or ""
                embedding_function = build_embeddings(
                    memory.embedding_model, api_key, provider=memory.embedding_provider,
                )

                # Create/open Chroma vector store
                kb_path.mkdir(parents=True, exist_ok=True)
                chroma = Chroma(
                    persist_directory=str(kb_path),
                    embedding_function=embedding_function,
                    collection_name=memory.kb_name,
                )

                # Deduplicate against existing content hashes
                existing = chroma.get()
                existing_hashes = {
                    m.get("_id") for m in (existing.get("metadatas") or []) if m.get("_id")
                }
                # Also collect existing session ids for count
                for m in (existing.get("metadatas") or []):
                    sid = m.get("session_id", "")
                    if sid:
                        session_ids_seen.add(sid)

                new_docs = [d for d in documents if d.metadata.get("_id") not in existing_hashes]

                # Add documents in batches
                if new_docs:
                    batch_size = 5000
                    for i in range(0, len(new_docs), batch_size):
                        batch = new_docs[i : i + batch_size]
                        chroma.add_documents(batch)

                # Record processed messages
                for msg in messages_to_process:
                    existing_check = select(MemoryProcessedMessage).where(
                        MemoryProcessedMessage.memory_id == memory_id,
                        MemoryProcessedMessage.message_id == msg.id,
                    )
                    existing_result = await session.exec(existing_check)
                    if not existing_result.first():
                        pm = MemoryProcessedMessage(
                            memory_id=memory_id,
                            message_id=msg.id,
                        )
                        session.add(pm)

                # Update memory stats
                total_in_store = chroma._collection.count() if hasattr(chroma, "_collection") else len(new_docs)
                memory.total_messages_processed = len(memory.processed_messages) + len(messages_to_process)
                memory.total_chunks = total_in_store
                memory.sessions_count = len(session_ids_seen)
                memory.status = "idle"
                memory.last_generated_at = datetime.now(timezone.utc)
                memory.updated_at = datetime.now(timezone.utc)
                memory.error_message = None
                session.add(memory)
                await session.commit()

                logger.info(
                    f"Memory {memory_id}: processed {len(messages_to_process)} messages, "
                    f"added {len(new_docs)} new docs to KB"
                )

            except Exception as e:
                logger.exception(f"Error vectorizing memory {memory_id}: {e}")
                memory.status = "failed"
                memory.error_message = str(e)[:500]
                memory.updated_at = datetime.now(timezone.utc)
                session.add(memory)
                await session.commit()

    except Exception as e:
        logger.exception(f"Fatal error in memory vectorization task {memory_id}: {e}")


@router.post("/{memory_id}/generate", response_model=MemoryRead, status_code=HTTPStatus.OK)
async def generate_memory(
    *,
    session: DbSession,
    memory_id: UUID,
    current_user: CurrentActiveUser,
):
    """Vectorize ALL flow messages into the memory KB (full regeneration)."""
    statement = select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    result = await session.exec(statement)
    memory = result.first()

    if not memory:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Memory not found")

    if memory.status in ("generating", "updating"):
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Memory is already being processed")

    memory.status = "generating"
    memory.updated_at = datetime.now(timezone.utc)
    session.add(memory)
    await session.commit()
    await session.refresh(memory)

    # Launch background task
    task = asyncio.create_task(
        _vectorize_messages(
            memory_id=memory.id,
            user_id=current_user.id,
            username=current_user.username,
            only_new=False,
        )
    )
    _running_tasks[memory.id] = task

    return _to_read(memory)


@router.post("/{memory_id}/update", response_model=MemoryRead, status_code=HTTPStatus.OK)
async def update_memory_kb(
    *,
    session: DbSession,
    memory_id: UUID,
    current_user: CurrentActiveUser,
):
    """Vectorize only NEW messages into the memory KB (incremental update)."""
    statement = select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    result = await session.exec(statement)
    memory = result.first()

    if not memory:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Memory not found")

    if memory.status in ("generating", "updating"):
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Memory is already being processed")

    memory.status = "updating"
    memory.updated_at = datetime.now(timezone.utc)
    session.add(memory)
    await session.commit()
    await session.refresh(memory)

    # Launch background task
    task = asyncio.create_task(
        _vectorize_messages(
            memory_id=memory.id,
            user_id=current_user.id,
            username=current_user.username,
            only_new=True,
        )
    )
    _running_tasks[memory.id] = task

    return _to_read(memory)


@router.post("/{memory_id}/add-messages", response_model=MemoryRead, status_code=HTTPStatus.OK)
async def add_messages_to_memory(
    *,
    session: DbSession,
    memory_id: UUID,
    body: AddMessagesRequest,
    current_user: CurrentActiveUser,
):
    """Vectorize specific message IDs into the memory KB."""
    statement = select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    result = await session.exec(statement)
    memory = result.first()

    if not memory:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Memory not found")

    if memory.status in ("generating", "updating"):
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Memory is already being processed")

    memory.status = "updating"
    memory.updated_at = datetime.now(timezone.utc)
    session.add(memory)
    await session.commit()
    await session.refresh(memory)

    # Launch background task
    task = asyncio.create_task(
        _vectorize_messages(
            memory_id=memory.id,
            user_id=current_user.id,
            username=current_user.username,
            only_new=True,
            message_ids=body.message_ids,
        )
    )
    _running_tasks[memory.id] = task

    return _to_read(memory)


# ─── Auto-capture helper ─────────────────────────────────────────────────────


async def auto_capture_messages(messages: list, flow_id: UUID | str | None):
    """Called after messages are persisted. Vectorizes into any active memories for this flow.

    This is a fire-and-forget operation — errors are logged but never raised.
    """
    if not flow_id:
        return

    if isinstance(flow_id, str):
        try:
            flow_id = UUID(flow_id)
        except ValueError:
            return

    try:
        async with session_scope() as session:
            # Find active memories for this flow
            stmt = select(Memory).where(
                Memory.flow_id == flow_id,
                Memory.is_active == True,  # noqa: E712
                col(Memory.status).notin_(["generating", "updating"]),
            )
            result = await session.exec(stmt)
            active_memories = result.all()

            if not active_memories:
                return

            # Get message IDs
            msg_ids = []
            for msg in messages:
                msg_id = getattr(msg, "id", None)
                if msg_id:
                    if isinstance(msg_id, str):
                        msg_id = UUID(msg_id)
                    msg_ids.append(msg_id)

            if not msg_ids:
                return

            # Get user info for each memory and launch vectorization
            for memory in active_memories:
                # Get username for KB path
                from langflow.services.database.models.user.model import User

                user_stmt = select(User).where(User.id == memory.user_id)
                user_result = await session.exec(user_stmt)
                user = user_result.first()
                if not user:
                    continue

                task = asyncio.create_task(
                    _vectorize_messages(
                        memory_id=memory.id,
                        user_id=memory.user_id,
                        username=user.username,
                        only_new=True,
                        message_ids=msg_ids,
                    )
                )
                _running_tasks[memory.id] = task
                logger.info(f"Auto-capture: queued {len(msg_ids)} messages for memory {memory.id}")

    except Exception as e:
        logger.warning(f"Auto-capture failed for flow {flow_id}: {e}")
