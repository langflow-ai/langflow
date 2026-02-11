from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, UniqueConstraint, func

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def utc_now():
    return datetime.now(timezone.utc)


# Memory Models
class MemoryBase(SQLModel):
    name: str = Field(description="Name of the memory", index=True)
    description: str | None = Field(default=None, description="Description of the memory")
    kb_name: str = Field(description="Knowledge base directory name on disk")
    embedding_model: str = Field(description="Embedding model name, e.g. text-embedding-3-small")
    embedding_provider: str = Field(description="Embedding provider: OpenAI, HuggingFace, Cohere")
    is_active: bool = Field(default=False, description="When active, new messages are auto-vectorized")
    status: str = Field(default="idle", description="Status: idle / generating / updating / failed")
    error_message: str | None = Field(default=None, description="Error details when failed")
    total_messages_processed: int = Field(default=0, description="Total messages vectorized")
    total_chunks: int = Field(default=0, description="Total chunks in the KB")
    sessions_count: int = Field(default=0, description="Distinct sessions captured")
    batch_size: int = Field(default=1, description="Messages to accumulate before auto-capture triggers")
    preprocessing_enabled: bool = Field(default=False, description="Toggle LLM preprocessing before vectorization")
    preprocessing_model: str | None = Field(default=None, description="JSON-serialized LLM config for preprocessing")
    preprocessing_prompt: str | None = Field(default=None, description="Custom prompt for LLM preprocessing")
    pending_messages_count: int = Field(default=0, description="Messages waiting for batch threshold")


class Memory(MemoryBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "memory"
    __table_args__ = (UniqueConstraint("user_id", "flow_id", "name", name="unique_memory_name_per_user_flow"),)

    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the memory",
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the memory",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last update time of the memory",
    )
    last_generated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the memory was last generated/updated",
    )
    user_id: UUID = Field(description="User ID associated with this memory", foreign_key="user.id")
    flow_id: UUID = Field(description="Flow ID associated with this memory", foreign_key="flow.id", index=True)
    user: "User" = Relationship(back_populates="memories")
    processed_messages: list["MemoryProcessedMessage"] = Relationship(
        back_populates="memory",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )


class MemoryProcessedMessage(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "memoryprocessedmessage"
    __table_args__ = (
        UniqueConstraint("memory_id", "message_id", name="unique_memory_message"),
    )

    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID",
    )
    memory_id: UUID = Field(description="Memory ID", foreign_key="memory.id", index=True)
    message_id: UUID = Field(description="Reference to message.id")
    processed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="When the message was processed",
    )
    memory: Memory = Relationship(back_populates="processed_messages")


class MemoryCreate(SQLModel):
    name: str
    description: str | None = None
    flow_id: UUID
    embedding_model: str
    embedding_provider: str
    is_active: bool = False
    batch_size: int = 1
    preprocessing_enabled: bool = False
    preprocessing_model: str | None = None
    preprocessing_prompt: str | None = None


class MemoryRead(SQLModel):
    id: UUID
    name: str
    description: str | None = None
    kb_name: str
    embedding_model: str
    embedding_provider: str
    is_active: bool = False
    status: str
    error_message: str | None = None
    total_messages_processed: int = 0
    total_chunks: int = 0
    sessions_count: int = 0
    batch_size: int = 1
    preprocessing_enabled: bool = False
    preprocessing_model: str | None = None
    preprocessing_prompt: str | None = None
    pending_messages_count: int = 0
    user_id: UUID
    flow_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_generated_at: datetime | None = None


class MemoryUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    batch_size: int | None = None
    preprocessing_enabled: bool | None = None
    preprocessing_model: str | None = None
    preprocessing_prompt: str | None = None
