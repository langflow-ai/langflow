from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Text
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from langflow.schema.serialize import UUIDstr


class ProjectPhase(str, Enum):
    CLARIFICATION = "CLARIFICATION"
    DIAGRAM_GENERATION = "DIAGRAM_GENERATION"
    DIAGRAM_REFINEMENT = "DIAGRAM_REFINEMENT"
    CODE_GENERATION = "CODE_GENERATION"
    DONE = "DONE"


class MessageRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class Project(SQLModel, table=True):  # type: ignore[call-arg]
    """A Lothal project: the top-level entity holding every artifact (MVP stores all in the DB)."""

    __tablename__ = "lothal_project"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(index=True, foreign_key="user.id")
    name: str = Field(index=True)
    phase: str = Field(default=ProjectPhase.CLARIFICATION)
    # Synthesised PRD; null until clarification completes. Primary LLM context source.
    prd_content: str | None = Field(default=None, sa_column=Column(Text))
    # Canonical Mermaid sequence diagram; null until generated. LLM reads/writes this.
    diagram_mmd: str | None = Field(default=None, sa_column=Column(Text))
    # JSON string of xyflow node positions; canvas-only, never sent to the LLM.
    diagram_layout: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    messages: list["Message"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    code_files: list["CodeFile"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Message(SQLModel, table=True):  # type: ignore[call-arg]
    """A single conversation turn. Used for session restore, audit, and clarification-chip replay."""

    __tablename__ = "lothal_message"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    project_id: UUIDstr = Field(index=True, foreign_key="lothal_project.id")
    role: str = Field()
    content: str = Field(sa_column=Column(Text, nullable=False))
    # Clarification chips; [] for USER messages and non-clarification replies.
    suggestions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    phase: str = Field()
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Project | None = Relationship(back_populates="messages")


class CodeFile(SQLModel, table=True):  # type: ignore[call-arg]
    """One generated source file. Populated during CODE_GENERATION; assembled into a ZIP on download."""

    __tablename__ = "lothal_code_file"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    project_id: UUIDstr = Field(index=True, foreign_key="lothal_project.id")
    path: str = Field()
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Project | None = Relationship(back_populates="code_files")


class ProjectCreate(SQLModel):
    name: str


class ProjectRead(SQLModel):
    id: UUIDstr
    user_id: UUIDstr
    name: str
    phase: str
    prd_content: str | None
    diagram_mmd: str | None
    diagram_layout: str | None
    created_at: datetime
    updated_at: datetime


class ProjectUpdate(SQLModel):
    name: str | None = None
    phase: str | None = None
    prd_content: str | None = None
    diagram_mmd: str | None = None
    diagram_layout: str | None = None


class MessageCreate(SQLModel):
    role: str
    content: str
    phase: str
    suggestions: list[str] = Field(default_factory=list)


class MessageRead(SQLModel):
    id: UUIDstr
    project_id: UUIDstr
    role: str
    content: str
    suggestions: list[str]
    phase: str
    created_at: datetime


class CodeFileCreate(SQLModel):
    path: str
    content: str


class CodeFileRead(SQLModel):
    id: UUIDstr
    project_id: UUIDstr
    path: str
    content: str
    created_at: datetime
