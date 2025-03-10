from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Text, UniqueConstraint
from sqlmodel import Column, Field, Relationship, SQLModel

from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.user.model import User


class ProjectBase(SQLModel):
    name: str = Field(index=True)
    description: str | None = Field(default=None, sa_column=Column(Text))


class Project(ProjectBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "folder"
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    parent_id: UUID | None = Field(default=None, foreign_key="folder.id")

    parent: Optional["Project"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Project.id"},
    )
    children: list["Project"] = Relationship(back_populates="parent")
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    user: User = Relationship(back_populates="folders")
    flows: list[Flow] = Relationship(
        back_populates="folder", sa_relationship_kwargs={"cascade": "all, delete, delete-orphan"}
    )

    __table_args__ = (UniqueConstraint("user_id", "name", name="unique_folder_name"),)


class ProjectCreate(ProjectBase):
    components_list: list[UUID] | None = None
    flows_list: list[UUID] | None = None


class ProjectRead(ProjectBase):
    id: UUID
    parent_id: UUID | None = Field()


class ProjectReadWithFlows(ProjectBase):
    id: UUID
    parent_id: UUID | None = Field()
    flows: list[FlowRead] = Field(default=[])


class ProjectUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None
    components: list[UUID] = Field(default_factory=list)
    flows: list[UUID] = Field(default_factory=list)
