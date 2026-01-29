from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from pydantic import field_serializer, field_validator
from sqlmodel import JSON, Column, Field, Relationship, SQLModel, Text

from langflow.serialization.serialization import serialize


class SpanType(str, Enum):
    """Types of spans that can be recorded."""

    CHAIN = "chain"
    LLM = "llm"
    TOOL = "tool"
    RETRIEVER = "retriever"
    EMBEDDING = "embedding"
    PARSER = "parser"
    AGENT = "agent"


class SpanStatus(str, Enum):
    """Status of a span execution."""

    SUCCESS = "success"
    ERROR = "error"
    RUNNING = "running"


class TraceBase(SQLModel):
    """Base model for traces."""

    name: str = Field(nullable=False, description="Name of the trace (usually flow name)")
    status: SpanStatus = Field(default=SpanStatus.RUNNING, description="Overall trace status")
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the trace started",
    )
    end_time: datetime | None = Field(default=None, description="When the trace ended")
    total_latency_ms: int = Field(default=0, description="Total execution time in milliseconds")
    total_tokens: int = Field(default=0, description="Total tokens used across all LLM calls")
    total_cost: float = Field(default=0.0, description="Estimated total cost")
    flow_id: UUID = Field(index=True, description="ID of the flow this trace belongs to")
    session_id: str | None = Field(default=None, index=True, description="Session ID for grouping traces")

    class Config:
        arbitrary_types_allowed = True

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = UUID(value)
        return value


class TraceTable(TraceBase, table=True):  # type: ignore[call-arg]
    """Database table for storing execution traces."""

    __tablename__ = "trace"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    spans: list["SpanTable"] = Relationship(
        back_populates="trace",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class TraceRead(TraceBase):
    """Read model for traces with spans."""

    id: UUID
    spans: list["SpanRead"] = []


class TraceCreate(SQLModel):
    """Create model for traces."""

    name: str
    flow_id: UUID
    session_id: str | None = None


class SpanBase(SQLModel):
    """Base model for spans (individual execution steps)."""

    name: str = Field(nullable=False, description="Name of the span (component/operation name)")
    span_type: SpanType = Field(default=SpanType.CHAIN, description="Type of operation")
    status: SpanStatus = Field(default=SpanStatus.RUNNING, description="Execution status")
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the span started",
    )
    end_time: datetime | None = Field(default=None, description="When the span ended")
    latency_ms: int = Field(default=0, description="Execution time in milliseconds")
    inputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    outputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = Field(default=None, sa_column=Column(Text), description="Error message if failed")
    model_name: str | None = Field(default=None, description="Model name for LLM spans")
    prompt_tokens: int | None = Field(default=None, description="Number of prompt tokens")
    completion_tokens: int | None = Field(default=None, description="Number of completion tokens")
    total_tokens: int | None = Field(default=None, description="Total tokens used")
    cost: float | None = Field(default=None, description="Estimated cost for this span")

    class Config:
        arbitrary_types_allowed = True

    @field_serializer("inputs")
    def serialize_inputs(self, data) -> dict | None:
        if data is None:
            return None
        return serialize(data)

    @field_serializer("outputs")
    def serialize_outputs(self, data) -> dict | None:
        if data is None:
            return None
        return serialize(data)


class SpanTable(SpanBase, table=True):  # type: ignore[call-arg]
    """Database table for storing execution spans."""

    __tablename__ = "span"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    trace_id: UUID = Field(foreign_key="trace.id", index=True, description="Parent trace ID")
    parent_span_id: UUID | None = Field(
        default=None,
        foreign_key="span.id",
        index=True,
        description="Parent span ID for nested spans",
    )

    # Relationships
    trace: TraceTable = Relationship(back_populates="spans")
    parent: Optional["SpanTable"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "SpanTable.id"},
    )
    children: list["SpanTable"] = Relationship(back_populates="parent")


class SpanRead(SpanBase):
    """Read model for spans with nested children."""

    id: UUID
    trace_id: UUID
    parent_span_id: UUID | None = None
    children: list["SpanRead"] = []


class SpanCreate(SQLModel):
    """Create model for spans."""

    name: str
    span_type: SpanType = SpanType.CHAIN
    trace_id: UUID
    parent_span_id: UUID | None = None
    inputs: dict[str, Any] | None = None
    model_name: str | None = None


class SpanUpdate(SQLModel):
    """Update model for completing spans."""

    status: SpanStatus | None = None
    end_time: datetime | None = None
    latency_ms: int | None = None
    outputs: dict[str, Any] | None = None
    error: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost: float | None = None


# Update forward references
TraceRead.model_rebuild()
SpanRead.model_rebuild()
