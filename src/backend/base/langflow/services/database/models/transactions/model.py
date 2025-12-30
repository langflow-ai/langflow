import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import field_serializer, field_validator
from sqlmodel import JSON, Column, Field, SQLModel

from langflow.serialization.serialization import get_max_items_length, get_max_text_length, serialize

# Cache for regex pattern matches to avoid repeated searches
_pattern_cache: dict[str, bool] = {}

# Keys that should have their values masked for security
SENSITIVE_KEYS_PATTERN = re.compile(
    r"(api[_-]?key|password|secret|token|credential|auth|bearer|private[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)

# Keys to completely exclude from logs
EXCLUDED_KEYS = frozenset({"code"})

# Minimum length for partial masking (show first 4 and last 4 chars)
MIN_LENGTH_FOR_PARTIAL_MASK = 12


def _mask_sensitive_value(value: str) -> str:
    """Mask a sensitive string value, showing only first 4 and last 4 chars."""
    if len(value) <= MIN_LENGTH_FOR_PARTIAL_MASK:
        return "***REDACTED***"
    return f"{value[:4]}...{value[-4:]}"


def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize a dictionary, masking sensitive values."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in EXCLUDED_KEYS:
            continue

        # Check cache first to avoid repeated regex searches
        is_sensitive = _pattern_cache.get(key)
        if is_sensitive is None:
            is_sensitive = bool(SENSITIVE_KEYS_PATTERN.search(key))
            _pattern_cache[key] = is_sensitive

        if is_sensitive:
            if isinstance(value, str) and value:
                result[key] = _mask_sensitive_value(value)
            else:
                result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = _sanitize_list(value)
        else:
            result[key] = value
    return result


def _sanitize_list(data: list[Any]) -> list[Any]:
    """Recursively sanitize a list."""
    result: list[Any] = []
    for item in data:
        if isinstance(item, dict):
            result.append(_sanitize_dict(item))
        elif isinstance(item, list):
            result.append(_sanitize_list(item))
        else:
            result.append(item)
    return result


def sanitize_data(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sanitize data by masking sensitive values and excluding certain keys."""
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    return _sanitize_dict(data)


class TransactionBase(SQLModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    vertex_id: str = Field(nullable=False)
    target_id: str | None = Field(default=None)
    inputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    outputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(nullable=False)
    error: str | None = Field(default=None)
    flow_id: UUID = Field()

    # Needed for Column(JSON)
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        # Sanitize inputs and outputs to remove sensitive data before storing
        if "inputs" in data and isinstance(data["inputs"], dict):
            data["inputs"] = sanitize_data(data["inputs"])
        if "outputs" in data and isinstance(data["outputs"], dict):
            data["outputs"] = sanitize_data(data["outputs"])
        super().__init__(**data)

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = UUID(value)
        return value

    @field_serializer("inputs")
    def serialize_inputs(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Serialize inputs, sanitizing sensitive data and enforcing size limits."""
        sanitized = sanitize_data(data)
        return serialize(sanitized, max_length=get_max_text_length(), max_items=get_max_items_length())

    @field_serializer("outputs")
    def serialize_outputs(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Serialize outputs, sanitizing sensitive data and enforcing size limits."""
        sanitized = sanitize_data(data)
        return serialize(sanitized, max_length=get_max_text_length(), max_items=get_max_items_length())


class TransactionTable(TransactionBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "transaction"
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)


class TransactionReadResponse(TransactionBase):
    id: UUID = Field(alias="transaction_id")
    flow_id: UUID


class TransactionLogsResponse(SQLModel):
    """Transaction response model for logs view - excludes error and flow_id fields."""

    model_config = {"populate_by_name": True, "from_attributes": True}

    id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    vertex_id: str = Field(nullable=False)
    target_id: str | None = Field(default=None)
    inputs: dict[str, Any] | None = Field(default=None)
    outputs: dict[str, Any] | None = Field(default=None)
    status: str = Field(nullable=False)

    @field_serializer("inputs")
    def serialize_inputs(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Serialize inputs, sanitizing sensitive data and enforcing size limits."""
        sanitized = sanitize_data(data)
        return serialize(sanitized, max_length=get_max_text_length(), max_items=get_max_items_length())

    @field_serializer("outputs")
    def serialize_outputs(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Serialize outputs, sanitizing sensitive data and enforcing size limits."""
        sanitized = sanitize_data(data)
        return serialize(sanitized, max_length=get_max_text_length(), max_items=get_max_items_length())
