import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import field_serializer, field_validator
from sqlmodel import JSON, Column, Field, SQLModel

from langflow.serialization.serialization import get_max_items_length, get_max_text_length, serialize

# Keys that should have their values masked for security
# Pattern uses fullmatch-style matching to avoid false positives like "max_tokens"
# Each pattern should match the entire key or a specific suffix
SENSITIVE_KEY_NAMES = frozenset(
    {
        "api_key",
        "api-key",
        "apikey",
        "password",
        "passwd",
        "secret",
        "token",
        "auth_token",
        "access_token",
        "api_token",
        "bearer_token",
        "credential",
        "credentials",
        "auth",
        "authorization",
        "bearer",
        "private_key",
        "private-key",
        "access_key",
        "access-key",
        "openai_api_key",
        "anthropic_api_key",
    }
)

# Pattern for keys that end with sensitive suffixes
SENSITIVE_KEYS_PATTERN = re.compile(
    r".*[_-]?(api[_-]?key|password|secret|token|credential|auth|bearer|private[_-]?key|access[_-]?key)$",
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


def _is_sensitive_key(key: str) -> bool:
    """Check if a key name is sensitive and should be masked."""
    key_lower = key.lower()
    # Check exact match first (faster)
    if key_lower in SENSITIVE_KEY_NAMES:
        return True
    # Check pattern match for keys ending with sensitive suffixes
    return bool(SENSITIVE_KEYS_PATTERN.match(key_lower))


def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize a dictionary, masking sensitive values."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in EXCLUDED_KEYS:
            continue
        if _is_sensitive_key(key):
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
    inputs: dict | None = Field(default=None, sa_column=Column(JSON))
    outputs: dict | None = Field(default=None, sa_column=Column(JSON))
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
    def serialize_inputs(self, data) -> dict:
        """Serialize inputs, sanitizing sensitive data and enforcing size limits."""
        sanitized = sanitize_data(data)
        return serialize(sanitized, max_length=get_max_text_length(), max_items=get_max_items_length())

    @field_serializer("outputs")
    def serialize_outputs(self, data) -> dict:
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
    inputs: dict | None = Field(default=None)
    outputs: dict | None = Field(default=None)
    status: str = Field(nullable=False)

    @field_serializer("inputs")
    def serialize_inputs(self, data) -> dict:
        """Serialize inputs, sanitizing sensitive data and enforcing size limits."""
        sanitized = sanitize_data(data)
        return serialize(sanitized, max_length=get_max_text_length(), max_items=get_max_items_length())

    @field_serializer("outputs")
    def serialize_outputs(self, data) -> dict:
        """Serialize outputs, sanitizing sensitive data and enforcing size limits."""
        sanitized = sanitize_data(data)
        return serialize(sanitized, max_length=get_max_text_length(), max_items=get_max_items_length())
