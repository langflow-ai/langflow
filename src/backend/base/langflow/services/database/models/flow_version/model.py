from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, computed_field, field_serializer
from pydantic import Field as PydanticField
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.sql.naming import conv
from sqlmodel import JSON, Field, SQLModel

# Final name of the ``version_number >= 1`` CHECK. It is wrapped in ``conv()`` below so Alembic's
# ``ck_%(table_name)s_%(constraint_name)s`` convention (installed on SQLModel.metadata by
# alembic/env.py) renders the same name whether the table is created by
# ``SQLModel.metadata.create_all`` or by the migration's ``op.create_table``.
VERSION_NUMBER_CHECK_NAME = "ck_flow_version_version_number_positive"


class FlowVersion(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_version"
    __mapper_args__ = {"confirm_deleted_rows": False}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(
        sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    user_id: UUID | None = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True, nullable=True),
    )
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    # NULL marks a checkpoint the system wrote to anchor the flow's history.
    # Those are not versions anyone saved, so they take no number, never appear
    # in the version list, and never count toward the version limit.
    version_number: int | None = Field(default=None, nullable=True, ge=1)
    description: str | None = Field(default=None, nullable=True, max_length=500)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True),
    )
    # The history revision whose graph ``data`` holds, when this version anchors
    # replay. NULL for versions saved before the flow had history.
    operation_revision: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    # SHA-256 of ``data``'s canonical graph form. The only whole-graph hash the
    # history stores; replay checks it whenever it reaches this version.
    graph_hash: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    # The original of a flow whose graph was repaired. It can be viewed and
    # exported but not restored, and the version limit never prunes it.
    view_only: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=false()),
    )

    # The UniqueConstraint on (flow_id, version_number) creates an implicit composite
    # btree index that also covers ORDER BY version_number DESC queries filtered by
    # flow_id. No additional index is needed for the list/prune queries.
    __table_args__ = (
        UniqueConstraint("flow_id", "version_number", name="unique_flow_version_number"),
        CheckConstraint("version_number >= 1", name=conv(VERSION_NUMBER_CHECK_NAME)),
        Index("ix_flow_version_flow_id_operation_revision", "flow_id", "operation_revision"),
    )


class FlowVersionRead(BaseModel):
    """Schema for listing flow versions — excludes data for performance."""

    id: UUID
    flow_id: UUID
    user_id: UUID | None
    version_number: int = PydanticField(ge=1)
    description: str | None
    created_at: datetime
    username: str | None = PydanticField(
        default=None,
        description="Display name of whoever authored this version, resolved from user_id.",
    )
    operation_revision: int | None = PydanticField(
        default=None,
        description="History revision this version's graph belongs to; None for versions saved before history.",
    )
    view_only: bool = PydanticField(
        default=False,
        description="The original of a repaired flow: viewable and exportable, not restorable.",
    )
    is_deployed: bool | None = PydanticField(
        default=None,
        description=(
            "True when this version is attached to at least one deployment. "
            "Omitted unless deployment_provider_id is provided as a query parameter."
        ),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def version_tag(self) -> str:
        return f"v{self.version_number}"

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> str:
        value = value.replace(microsecond=0)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class FlowVersionReadWithData(FlowVersionRead):
    """Schema for a single flow version — includes full data."""

    data: dict | None


class FlowVersionCreate(BaseModel):
    """Schema for creating a flow version.

    ``data`` lets a caller archive a graph the server never had — the state on
    somebody's canvas as they abandon it. Without it the only snapshot possible
    is of what is already stored, which is exactly the state that is *not* at
    risk of being lost.
    """

    description: str | None = Field(default=None, max_length=500)
    data: dict | None = Field(default=None)


class FlowVersionListResponse(BaseModel):
    """Wrapper for the list endpoint — includes flow versions and the configured max."""

    entries: list[FlowVersionRead]
    max_entries: int = PydanticField(ge=1)
