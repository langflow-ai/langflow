from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import JSON, Column, Index, text
from sqlmodel import Field, Relationship, SQLModel

from langflow.schema.serialize import UUIDstr

if TYPE_CHECKING:
    from langflow.services.database.models.api_key.model import ApiKey
    from langflow.services.database.models.auth.authz import AuthzRoleAssignment
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.file.model import File
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.variable.model import Variable


class UserOptin(BaseModel):
    github_starred: bool = Field(default=False)
    dialog_dismissed: bool = Field(default=False)
    discord_clicked: bool = Field(default=False)
    # Add more opt-in actions as needed


class User(SQLModel, table=True):  # type: ignore[call-arg]
    # Created by migration 1d28fd31a982. Declared here as well so autogenerate
    # (and the startup ``alembic check``) sees it: Postgres reflects expression
    # indexes, so an index missing from the model reads as a ``remove_index`` diff.
    __table_args__ = (Index("ix_user_username_lower", text("lower(username)"), unique=True),)

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True, unique=True)
    username: str = Field(index=True, unique=True)
    password: str = Field()
    profile_image: str | None = Field(default=None, nullable=True)
    is_active: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    create_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime | None = Field(default=None, nullable=True)
    api_keys: list["ApiKey"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "delete"},
    )
    store_api_key: str | None = Field(default=None, nullable=True)
    flows: list["Flow"] = Relationship(back_populates="user")
    # User is a secondary parent, so cascade="delete" (no "delete-orphan").
    # Orphan management is handled by the owning models
    # (DeploymentProviderAccount, Folder) which use "all, delete, delete-orphan".
    deployment_provider_accounts: list["DeploymentProviderAccount"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "delete"},
    )
    deployments: list["Deployment"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "delete"},
    )
    variables: list["Variable"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "delete"},
    )
    files: list["File"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "delete"},
    )
    folders: list["Folder"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "delete"},
    )
    # No back_populates: AuthzRoleAssignment has two FKs to user.id, so each
    # relationship disambiguates its own join column explicitly rather than
    # relying on inference. SQLite never enforces ON DELETE CASCADE/SET NULL
    # (see AuthzRoleAssignment's own docstring), so without ORM-level cascade
    # here a deleted user's assignment rows — or rows they merely granted —
    # survive as unresolvable "unknown user" references in Access Control.
    role_assignments: list["AuthzRoleAssignment"] = Relationship(
        sa_relationship_kwargs={
            "cascade": "delete",
            "foreign_keys": "AuthzRoleAssignment.user_id",
        },
    )
    # Deleting whoever granted a role must not delete the grant itself — only
    # clear who granted it, matching the FK's own SET NULL semantics. Default
    # relationship cascade ("save-update, merge", no "delete") is exactly
    # that: on session.delete(user), SQLAlchemy nulls assigned_by on any
    # related rows rather than deleting them.
    role_assignments_granted: list["AuthzRoleAssignment"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "AuthzRoleAssignment.assigned_by",
        },
    )
    optins: dict[str, Any] | None = Field(
        sa_column=Column(JSON, default=lambda: UserOptin().model_dump(), nullable=True)
    )


class UserCreate(SQLModel):
    username: str = Field()
    password: str = Field()
    optins: dict[str, Any] | None = Field(
        default={"github_starred": False, "dialog_dismissed": False, "discord_clicked": False}
    )


class UserRead(SQLModel):
    id: UUID = Field(default_factory=uuid4)
    username: str = Field()
    profile_image: str | None = Field()
    store_api_key: str | None = Field(nullable=True)
    is_active: bool = Field()
    is_superuser: bool = Field()
    create_at: datetime = Field()
    updated_at: datetime = Field()
    last_login_at: datetime | None = Field(nullable=True)
    optins: dict[str, Any] | None = Field(default=None)


class UserUpdate(SQLModel):
    username: str | None = None
    profile_image: str | None = None
    password: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    last_login_at: datetime | None = None
    optins: dict[str, Any] | None = None
