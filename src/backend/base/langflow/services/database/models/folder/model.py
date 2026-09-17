import re
from typing import Optional
from uuid import UUID, uuid4

from pydantic import field_validator
from pydantic_core import PydanticCustomError
from sqlalchemy import Text, UniqueConstraint
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.user.model import User

# Emoji blocks: emoticons, pictographs, transport, flags and supplemental symbols, plus
# the misc-symbols and dingbats range. CJK, kana and Hangul are untouched.
_EMOJI_RE = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf]")


def reject_emoji(name: str | None) -> str | None:
    """Project names feed MCP server names and filenames, so emoji are refused outright."""
    if name is not None and _EMOJI_RE.search(name):
        # PydanticCustomError so the client sees the message without the "Value error, " prefix
        error_type, msg = "emoji_in_name", "Project names cannot contain emoji"
        raise PydanticCustomError(error_type, msg)
    return name


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
    workspace_id: UUID | None = Field(default=None, nullable=True, index=True)
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

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return reject_emoji(value)


class FolderRead(FolderBase):
    id: UUID
    parent_id: UUID | None = Field()


class FolderListRead(FolderRead):
    owner_username: str | None = None
    is_owner: bool


class FolderReadWithFlows(FolderBase):
    id: UUID
    parent_id: UUID | None = Field()
    flows: list[FlowRead] = Field(default=[])


class FolderUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None
    components: list[UUID] = Field(default_factory=list)
    flows: list[UUID] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return reject_emoji(value)

    auth_settings: dict | None = None
