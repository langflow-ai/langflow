from typing import List, Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow


class FolderBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)


class Folder(FolderBase, table=True):
    parent_id: Optional[int] = Field(default=None, foreign_key="folder.id")
    parent: Optional["Folder"] = Relationship(back_populates="children")
    children: List["Folder"] = Relationship(back_populates="parent")
    flows: List["Flow"] = Relationship(back_populates="folder")


class FolderCreate(FolderBase):
    parent_id: Optional[int] = None


class FolderRead(FolderBase):
    id: int
    parent_id: Optional[int] = Field()
    flows: List["Flow"] = Relationship(back_populates="folder")


class FolderUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
