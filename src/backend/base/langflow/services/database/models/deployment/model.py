from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from lfx.services.adapters.deployment.schema import DeploymentType
from pydantic import field_validator
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from langflow.schema.serialize import UUIDstr
from langflow.services.database.utils import validate_non_empty_string

if TYPE_CHECKING:
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.user.model import User


class Deployment(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "deployment"
    __table_args__ = (
        UniqueConstraint("deployment_provider_account_id", "name", name="uq_deployment_name_in_provider"),
        UniqueConstraint(
            "deployment_provider_account_id", "resource_key", name="uq_deployment_resource_key_in_provider"
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    resource_key: str = Field(index=True)
    user_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    # "project" is represented by a Folder row in the existing schema.
    project_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("folder.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    deployment_provider_account_id: UUIDstr = Field(
        sa_column=Column(
            sa.Uuid(), ForeignKey("deployment_provider_account.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    name: str = Field(index=True)
    description: str | None = Field(
        default=None,
        sa_column=Column(sa.Text(), nullable=True),
    )
    # ``DeploymentType`` is imported from LFX
    # (``lfx.services.adapters.deployment.schema``).  The DB-level
    # ``deployment_type_enum`` constraint is defined by a Langflow alembic
    # migration, **not** by LFX code.  This decoupling is intentional:
    #
    # LFX adds a new member  -> INSERT/UPDATE with the new value is rejected
    #                           by the DB until a Langflow migration adds it
    #                           to the enum type.  Langflow explicitly opts
    #                           in to new deployment types.
    #
    # LFX renames a value    -> Existing rows are unaffected (the DB stores
    #                           the old string).  Python deserialization via
    #                           ``DeploymentType(value)`` will raise
    #                           ``ValueError`` on read until the migration
    #                           and enum are reconciled.
    #
    # LFX removes a member   -> Same as rename: stored rows retain the
    #                           deleted string, but Python reads break.
    #                           The DB constraint still lists the old value,
    #                           so no data loss occurs.
    #
    # In all mutation scenarios the DB data remains intact; only the
    # application layer breaks until a coordinated migration is applied.
    #
    # To add a new value to ``deployment_type_enum``:
    #   1. Add the member to ``DeploymentType`` in LFX (or confirm it exists).
    #   2. Create a Langflow alembic migration that runs:
    #        op.execute("ALTER TYPE deployment_type_enum ADD VALUE '<new>'")
    #      For SQLite (dev/test) this is a no-op; the CHECK constraint is
    #      recreated automatically by ``batch_alter_table``.
    #   3. Deploy the migration before any code writes the new value.
    #
    # Removing or renaming a value is **strongly discouraged**.  Existing
    # rows reference the old string; renaming silently breaks every read
    # of those rows (``DeploymentType(value)`` raises ``ValueError``).
    # If absolutely necessary:
    #   1. Create a migration that (a) updates existing rows to the
    #      replacement value, then (b) recreates the enum type without
    #      the old value (PostgreSQL requires CREATE TYPE … / ALTER COLUMN
    #      … TYPE … USING …; SQLite uses ``batch_alter_table``).
    #   2. Update or remove the member in the Python enum.
    #   3. Coordinate with LFX — adapters and callers may still reference
    #      the old value.
    #
    # nullable=True at the DB level to satisfy the EXPAND-phase migration
    # validator; application-layer code treats this as required.
    deployment_type: DeploymentType = Field(
        sa_column=Column(
            SQLEnum(
                DeploymentType,
                name="deployment_type_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=True,
            index=True,
        ),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    user: "User" = Relationship(back_populates="deployments")
    deployment_provider_account: "DeploymentProviderAccount" = Relationship(back_populates="deployments")
    folder: "Folder" = Relationship(back_populates="deployments")

    @field_validator("name", "resource_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: object) -> str:
        return validate_non_empty_string(v, info)


class DeploymentRead(SQLModel):
    id: UUID
    resource_key: str
    user_id: UUID
    project_id: UUID
    deployment_provider_account_id: UUID
    name: str
    description: str | None = None
    deployment_type: DeploymentType
    created_at: datetime
    updated_at: datetime
