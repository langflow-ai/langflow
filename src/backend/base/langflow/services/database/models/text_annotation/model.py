"""Text annotation persistence models (Label-Studio-compatible).

Two tables back the text-annotation feature:

* ``text_annotation_project`` — one row per labeling project. ``task_type``
  selects the labeling mode (``ner`` span labeling or ``classification``);
  entity / category label sets are stored as JSON arrays of
  ``{"value": ..., "background": ...}`` dicts (mirrors the image-annotation
  project's label-set shape).
* ``text_annotation_task`` — one row per text sample (task, in Label Studio
  terms). The raw text lives in the row (no external storage needed) together
  with a Label-Studio-compatible annotation ``result`` JSON array:

  - NER:            ``{"id", "type": "labels", "from_name": "label",
                     "to_name": "text", "value": {"start", "end", "text",
                     "labels": [...]}}``
  - classification: ``{"id", "type": "choices", "from_name": "choice",
                     "to_name": "text", "value": {"choices": [...]}}``

  so exports can interoperate with Label Studio and convert to BERT training
  formats (CSV / CoNLL BIO) without a format change.

A separate completion table (LS's ``task_completion``) is intentionally
omitted: langflow resources are single-owner, so one result set per task is
enough (same simplification as the image-annotation feature).
"""

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import field_validator
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSONB on Postgres; JSON on SQLite. The migration uses the identical
# variant so the ORM and DDL produce matching columns.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")

TASK_TYPE_NER = "ner"
TASK_TYPE_CLASSIFICATION = "classification"
TaskType = Literal["ner", "classification"]


class TextAnnotationLabel(SQLModel):
    """One label definition inside a project's label set."""

    value: str
    background: str | None = None

    @field_validator("value")
    @classmethod
    def _strip_value(cls, v: str) -> str:
        v = v.strip()
        if not v:
            msg = "Label value must not be empty"
            raise ValueError(msg)
        return v


def _validate_unique_labels(labels: list[TextAnnotationLabel] | None) -> list[TextAnnotationLabel] | None:
    if labels is None:
        return labels
    seen: set[str] = set()
    for label in labels:
        if label.value in seen:
            msg = f"Duplicate label value: {label.value}"
            raise ValueError(msg)
        seen.add(label.value)
    return labels


# --------------------------------------------------------------------------- #
# Annotation result schemas (Label-Studio-compatible Labels / Choices result)
# --------------------------------------------------------------------------- #


class TextSpanValue(SQLModel):
    """``value`` payload of one NER span region (character offsets)."""

    model_config = {"extra": "allow"}

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str = ""
    labels: list[str] = Field(default_factory=list)


class TextChoicesValue(SQLModel):
    """``value`` payload of one text-classification choices region."""

    model_config = {"extra": "allow"}

    choices: list[str] = Field(default_factory=list)


class TextAnnotationRegion(SQLModel):
    """One region entry in the Label-Studio-style ``result`` array.

    ``type`` is ``labels`` (NER span) or ``choices`` (classification). Extra
    fields are preserved so a result produced by Label Studio can be stored
    and returned verbatim.
    """

    model_config = {"extra": "allow"}

    id: str
    type: str
    from_name: str = "label"
    to_name: str = "text"
    origin: str = "manual"
    # Span dicts carry start/end and validate as TextSpanValue; choice dicts
    # fall through to TextChoicesValue (union order matters).
    value: TextSpanValue | TextChoicesValue


class TextAnnotationResultUpdate(SQLModel):
    """PUT body for replacing one task's annotation result."""

    result: list[TextAnnotationRegion] = Field(default_factory=list)
    lead_time: float | None = None


class TextAnnotationResultRead(SQLModel):
    """Stored annotation result, returned raw to preserve LS extra fields."""

    result: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Project table + CRUD schemas
# --------------------------------------------------------------------------- #


class TextAnnotationProjectBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    name: str = Field(index=True, nullable=False)
    description: str | None = Field(default=None, sa_column=Column(Text))
    task_type: str = Field(default=TASK_TYPE_NER, nullable=False)
    # JSON arrays of {"value": str, "background": str|None} dicts.
    entity_labels: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JsonVariant, nullable=False),
    )
    category_labels: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JsonVariant, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


class TextAnnotationProject(TextAnnotationProjectBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "text_annotation_project"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_text_annotation_project_user_name"),)


class TextAnnotationProjectCreate(SQLModel):
    name: str
    description: str | None = None
    task_type: TaskType = TASK_TYPE_NER
    entity_labels: list[TextAnnotationLabel] = Field(default_factory=list)
    category_labels: list[TextAnnotationLabel] = Field(default_factory=list)

    _unique_entity_labels = field_validator("entity_labels")(_validate_unique_labels)
    _unique_category_labels = field_validator("category_labels")(_validate_unique_labels)


class TextAnnotationProjectRead(SQLModel):
    id: UUID
    name: str
    description: str | None = None
    task_type: str = TASK_TYPE_NER
    entity_labels: list[TextAnnotationLabel] = Field(default_factory=list)
    category_labels: list[TextAnnotationLabel] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    # Computed by the route; defaults keep model_validate happy.
    task_count: int = 0
    labeled_count: int = 0


class TextAnnotationProjectUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    task_type: TaskType | None = None
    entity_labels: list[TextAnnotationLabel] | None = None
    category_labels: list[TextAnnotationLabel] | None = None

    _unique_entity_labels = field_validator("entity_labels")(_validate_unique_labels)
    _unique_category_labels = field_validator("category_labels")(_validate_unique_labels)


# --------------------------------------------------------------------------- #
# Task table + CRUD schemas
# --------------------------------------------------------------------------- #


class TextAnnotationTaskBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("text_annotation_project.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    # Denormalized owner id: lets every query stay owner-scoped without a
    # join back to the project (and gives authz the owner context key).
    user_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    name: str = Field(nullable=False)
    text: str = Field(sa_column=Column(Text, nullable=False))
    # Import provenance: "paste" | "text_file" | "csv" | "database".
    source: str = Field(default="paste", nullable=False)
    # Label-Studio-compatible annotation result array.
    result: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JsonVariant, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


class TextAnnotationTask(TextAnnotationTaskBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "text_annotation_task"


class TextAnnotationTaskCreate(SQLModel):
    text: str
    name: str | None = None

    @field_validator("text")
    @classmethod
    def _text_not_empty(cls, v: str) -> str:
        if not v.strip():
            msg = "Task text must not be empty"
            raise ValueError(msg)
        return v


class TextAnnotationTasksBulkCreate(SQLModel):
    """POST body for adding one or more plain-text tasks."""

    tasks: list[TextAnnotationTaskCreate] = Field(min_length=1)
    source: str = "paste"


class TextAnnotationTaskRead(SQLModel):
    id: UUID
    project_id: UUID
    name: str
    text: str
    source: str = "paste"
    result: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    # Computed by the route from ``result``.
    is_labeled: bool = False


class TextAnnotationTaskUpdate(SQLModel):
    name: str | None = None
    text: str | None = None


class TextAnnotationProjectDetail(TextAnnotationProjectRead):
    """Project detail response: project fields plus its task list."""

    tasks: list[TextAnnotationTaskRead] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Import schemas (CSV upload is multipart; database import is JSON)
# --------------------------------------------------------------------------- #

IMPORT_ROW_LIMIT = 10000


class DatabaseImportPreviewRequest(SQLModel):
    connection_uri: str
    table_name: str
    sample_size: int = Field(default=5, ge=1, le=50)


class DatabaseImportPreviewResponse(SQLModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class DatabaseImportRequest(SQLModel):
    connection_uri: str
    table_name: str
    text_column: str
    name_column: str | None = None
    limit: int = Field(default=1000, ge=1, le=IMPORT_ROW_LIMIT)
    offset: int = Field(default=0, ge=0)


class TextAnnotationImportResponse(SQLModel):
    created: int = 0
    skipped: int = 0
