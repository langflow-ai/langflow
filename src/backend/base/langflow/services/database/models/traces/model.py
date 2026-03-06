from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from pydantic import Field as PydanticField
from pydantic.alias_generators import to_camel
from sqlmodel import JSON, Column, Field, Relationship, SQLModel, Text

from langflow.serialization.serialization import serialize


class SpanKind(str, Enum):
    """OpenTelemetry SpanKind values.

    Describes the relationship between the span, its parents, and its children
    in a distributed trace.

    - INTERNAL: Default. Represents an internal operation within an application.
    - CLIENT: Represents a request made to some remote service.
    - SERVER: Represents a request received from a remote client.
    - PRODUCER: Represents the initiation of an asynchronous request.
    - CONSUMER: Represents the processing of an asynchronous message.
    """

    INTERNAL = "INTERNAL"
    CLIENT = "CLIENT"
    SERVER = "SERVER"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


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
    """OpenTelemetry status codes.

    - UNSET: Default status, span has not ended yet
    - OK: Span completed successfully
    - ERROR: Span completed with an error
    """

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class TraceBase(SQLModel):
    """Base model for traces."""

    name: str = Field(nullable=False, description="Name of the trace (usually flow name)")
    status: SpanStatus = Field(default=SpanStatus.UNSET, description="Overall trace status")
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the trace started",
    )
    end_time: datetime | None = Field(default=None, description="When the trace ended")
    total_latency_ms: int = Field(default=0, description="Total execution time in milliseconds")
    total_tokens: int = Field(default=0, description="Total tokens used across all LLM calls")
    flow_id: UUID = Field(
        foreign_key="flow.id",
        ondelete="CASCADE",
        index=True,
        description="ID of the flow this trace belongs to",
    )
    session_id: str | None = Field(
        default=None,
        nullable=True,
        index=True,
        description="Session ID for grouping traces",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if value is None:
            msg = "flow_id is required and cannot be None"
            raise ValueError(msg)
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


class SpanReadResponse(BaseModel):
    """Response model for a single span, with nested children.

    Serializes to camelCase JSON to match the frontend API contract.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    name: str
    type: SpanType
    status: SpanStatus
    start_time: datetime | None
    end_time: datetime | None
    latency_ms: int
    inputs: dict[str, Any] | None
    outputs: dict[str, Any] | None
    error: str | None
    model_name: str | None
    token_usage: dict[str, Any] | None
    children: list["SpanReadResponse"] = PydanticField(default_factory=list)


class TraceRead(BaseModel):
    """Response model for a single trace with its hierarchical span tree.

    Serializes to camelCase JSON to match the frontend API contract.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    name: str
    status: SpanStatus
    start_time: datetime | None
    end_time: datetime | None
    total_latency_ms: int
    total_tokens: int
    flow_id: UUID
    session_id: str
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    spans: list[SpanReadResponse] = PydanticField(default_factory=list)


class TraceSummaryRead(BaseModel):
    """Lightweight trace model for list endpoint.

    Serializes to camelCase JSON to match the frontend API contract.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    name: str
    status: SpanStatus
    start_time: datetime | None
    total_latency_ms: int
    total_tokens: int
    flow_id: UUID
    session_id: str
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None


class TraceListResponse(BaseModel):
    """Paginated list response for traces."""

    traces: list[TraceSummaryRead]
    total: int
    pages: int


class TraceCreate(SQLModel):
    """Create model for traces."""

    name: str
    flow_id: UUID
    session_id: str | None = None


class SpanBase(SQLModel):
    """Base model for spans (individual execution steps)."""

    name: str = Field(nullable=False, description="Name of the span following OTel convention: '{operation} {model}'")
    span_type: SpanType = Field(default=SpanType.CHAIN, description="Type of operation")
    status: SpanStatus = Field(default=SpanStatus.UNSET, description="Execution status")
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the span started",
    )
    end_time: datetime | None = Field(default=None, description="When the span ended")
    latency_ms: int = Field(default=0, description="Execution time in milliseconds")
    inputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    outputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = Field(default=None, sa_column=Column(Text), description="Error message if failed")
    span_kind: SpanKind = Field(
        default=SpanKind.INTERNAL,
        description="OpenTelemetry SpanKind",
    )
    # OTel-compliant extensible attributes
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

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

    @field_serializer("attributes")
    def serialize_attributes(self, data):
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


class SpanCreate(SQLModel):
    """Create model for spans."""

    name: str
    span_type: SpanType = SpanType.CHAIN
    trace_id: UUID
    parent_span_id: UUID | None = None
    inputs: dict[str, Any] | None = None
    # OTel attributes
    attributes: dict[str, Any] | None = None


class SpanUpdate(SQLModel):
    """Update model for completing spans."""

    status: SpanStatus | None = None
    end_time: datetime | None = None
    latency_ms: int | None = None
    outputs: dict[str, Any] | None = None
    error: str | None = None
    # OTel attribute
    attributes: dict[str, Any] | None = None


# SpanReadResponse and TraceRead reference each other via forward refs; rebuild resolves them at import time.
SpanReadResponse.model_rebuild()
TraceRead.model_rebuild()
