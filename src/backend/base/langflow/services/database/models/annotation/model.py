"""Image annotation persistence models.

Two tables back the image-annotation feature:

* ``annotation_project`` — one row per labeling project. The label set is
  stored as a JSON array of ``{"value": ..., "background": ...}`` dicts
  (a deliberate simplification of Label Studio's XML ``label_config``; the
  shape mirrors LS's ``parsed_label_config`` labels list).
* ``annotation_image`` — one row per uploaded image (task, in Label Studio
  terms). The binary lives in the storage service; this row keeps the
  metadata plus the annotation ``result`` — a Label-Studio-compatible JSON
  array of region dicts (percentage coordinates + ``original_width`` /
  ``original_height`` + ``rectanglelabels``), so exports can interoperate
  with LS and convert to COCO without a format change.

A separate ``annotation`` table (LS's ``task_completion``) is intentionally
omitted: langflow resources are single-owner, so one result set per image
is enough. The API still exposes an ``/annotations`` sub-resource shape so
a future split does not break clients.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import field_validator
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSONB on Postgres; JSON on SQLite. The migration uses the identical
# variant so the ORM and DDL produce matching columns.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")


class AnnotationLabel(SQLModel):
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


def _validate_unique_labels(labels: list[AnnotationLabel] | None) -> list[AnnotationLabel] | None:
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
# Annotation region schemas (Label-Studio-compatible RectangleLabels result)
# --------------------------------------------------------------------------- #


class AnnotationRegionValue(SQLModel):
    """``value`` payload of one rectangle region (percentage coordinates)."""

    model_config = {"extra": "allow"}

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    width: float = Field(ge=0, le=100)
    height: float = Field(ge=0, le=100)
    rotation: float = 0
    rectanglelabels: list[str] = Field(default_factory=list)


class AnnotationRegion(SQLModel):
    """One region entry in the Label-Studio-style ``result`` array.

    Extra fields are preserved so a result produced by Label Studio can be
    stored and returned verbatim.
    """

    model_config = {"extra": "allow"}

    id: str
    type: str = "rectanglelabels"
    from_name: str = "label"
    to_name: str = "image"
    origin: str = "manual"
    original_width: int | None = None
    original_height: int | None = None
    image_rotation: int = 0
    value: AnnotationRegionValue


class AnnotationResultUpdate(SQLModel):
    """PUT body for replacing one image's annotation result."""

    result: list[AnnotationRegion] = Field(default_factory=list)
    lead_time: float | None = None


class AnnotationResultRead(SQLModel):
    """Stored annotation result, returned raw to preserve LS extra fields."""

    result: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Project table + CRUD schemas
# --------------------------------------------------------------------------- #


class AnnotationProjectBase(SQLModel):
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
    # JSON array of {"value": str, "background": str|None} dicts.
    labels: list[dict[str, Any]] = Field(
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


class AnnotationProject(AnnotationProjectBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "annotation_project"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_annotation_project_user_name"),)


class AnnotationProjectCreate(SQLModel):
    name: str
    description: str | None = None
    labels: list[AnnotationLabel] = Field(default_factory=list)

    _unique_labels = field_validator("labels")(_validate_unique_labels)


class AnnotationProjectRead(SQLModel):
    id: UUID
    name: str
    description: str | None = None
    labels: list[AnnotationLabel] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    # Computed by the route; defaults keep model_validate happy.
    image_count: int = 0
    labeled_count: int = 0


class AnnotationProjectUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    labels: list[AnnotationLabel] | None = None

    _unique_labels = field_validator("labels")(_validate_unique_labels)


class AnnotationImageBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("annotation_project.id", ondelete="CASCADE"),
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
    # Storage path relative to the storage root: ``{user_id}/{uuid}-{safe_name}``
    # (flat per-user namespace — the local storage service rejects nested names).
    path: str = Field(nullable=False)
    size: int = Field(default=0, nullable=False)
    # Natural pixel dimensions, backfilled by the client after first load.
    width: int | None = Field(default=None, nullable=True)
    height: int | None = Field(default=None, nullable=True)
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


class AnnotationImage(AnnotationImageBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "annotation_image"


class AnnotationImageRead(SQLModel):
    id: UUID
    project_id: UUID
    name: str
    size: int
    width: int | None = None
    height: int | None = None
    created_at: datetime
    updated_at: datetime
    # Computed by the route from ``result``.
    is_labeled: bool = False
    annotation_count: int = 0


class AnnotationImageUpdate(SQLModel):
    name: str | None = None
    width: int | None = None
    height: int | None = None


class AnnotationProjectDetail(AnnotationProjectRead):
    """Project detail response: project fields plus its image metadata list."""

    images: list[AnnotationImageRead] = Field(default_factory=list)
