from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint, Text
from sqlmodel import Field, Relationship, SQLModel, Column

from langflow.services.database.models.flow.model import FlowRead

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User


class FolderBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))


class Folder(FolderBase, table=True):  # type: ignore
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    parent_id: Optional[UUID] = Field(default=None, foreign_key="folder.id")

    parent: Optional["Folder"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs=dict(remote_side="Folder.id"),
    )
    children: List["Folder"] = Relationship(back_populates="parent")
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    user: "User" = Relationship(back_populates="folders")
    flows: List["Flow"] = Relationship(
        back_populates="folder", sa_relationship_kwargs={"cascade": "all, delete, delete-orphan"}
    )

    __table_args__ = (UniqueConstraint("user_id", "name", name="unique_folder_name"),)


class FolderCreate(FolderBase):
    components_list: Optional[List[UUID]] = None
    flows_list: Optional[List[UUID]] = None


class FolderRead(FolderBase):
    id: UUID
    parent_id: Optional[UUID] = Field()


class FolderReadWithFlows(FolderBase):
    id: UUID
    parent_id: Optional[UUID] = Field()
    flows: List["FlowRead"] = Field(default=[])


class FolderUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    components: List[UUID] = Field(default_factory=list)
    flows: List[UUID] = Field(default_factory=list)
