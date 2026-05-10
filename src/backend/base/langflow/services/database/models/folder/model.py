from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import field_serializer
from sqlalchemy import Text, UniqueConstraint
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.user.model import User

# Keep in sync with SENSITIVE_FIELDS in
# langflow.services.auth.mcp_encryption — these field names are encrypted at
# rest and must never leave the server, even as ciphertext, in API responses.
_AUTH_SECRET_FIELDS = ("oauth_client_secret", "api_key")
_MASK = "*******"  # noqa: S105  # placeholder; matches frontend round-trip in auth_helpers.py


def _mask_auth_settings(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return value
    masked = dict(value)
    for field in _AUTH_SECRET_FIELDS:
        if masked.get(field):
            masked[field] = _MASK
    return masked


class FolderBase(SQLModel):
    name: str = Field(index=True)
    description: str | None = Field(default=None, sa_column=Column(Text))
    auth_settings: dict | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Authentication settings for the folder/project",
    )


class Folder(FolderBase, table=True):  # type: ignore[call-arg]
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    parent_id: UUID | None = Field(default=None, foreign_key="folder.id")

    parent: Optional["Folder"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Folder.id"},
    )
    children: list["Folder"] = Relationship(back_populates="parent")
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    user: User = Relationship(back_populates="folders")
    flows: list[Flow] = Relationship(
        back_populates="folder", sa_relationship_kwargs={"cascade": "all, delete, delete-orphan"}
    )
    deployments: list[Deployment] = Relationship(
        back_populates="folder", sa_relationship_kwargs={"cascade": "all, delete, delete-orphan"}
    )

    __table_args__ = (UniqueConstraint("user_id", "name", name="unique_folder_name"),)


class FolderCreate(FolderBase):
    components_list: list[UUID] | None = None
    flows_list: list[UUID] | None = None


class FolderRead(FolderBase):
    id: UUID
    parent_id: UUID | None = Field()

    @field_serializer("auth_settings")
    def _serialize_auth_settings(self, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _mask_auth_settings(value)


class FolderReadWithFlows(FolderBase):
    id: UUID
    parent_id: UUID | None = Field()
    flows: list[FlowRead] = Field(default=[])

    @field_serializer("auth_settings")
    def _serialize_auth_settings(self, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _mask_auth_settings(value)


class FolderUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None
    components: list[UUID] = Field(default_factory=list)
    flows: list[UUID] = Field(default_factory=list)
    auth_settings: dict | None = None
