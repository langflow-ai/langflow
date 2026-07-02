from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from langflow.schema.serialize import UUIDstr


class ProjectPhase(str, Enum):
    CLARIFICATION = "CLARIFICATION"
    # Epic E merged the two diagram phases (DIAGRAM_GENERATION + DIAGRAM_REFINEMENT)
    # into one ARCHITECTURE stage: the same engine generates on entry and refines
    # thereafter (E.2), and its output grows from one diagram to an ADR + diagram
    # set (E.3). Existing rows were remapped onto ARCHITECTURE by migration
    # e1f0a2b3c4d5.
    ARCHITECTURE = "ARCHITECTURE"
    # Epic UI (Story U.0) inserts the prototype stage between architecture and
    # code generation: approving the architecture (`POST /diagram/approve`) now
    # lands here, and approving the prototype advances to CODE_GENERATION. The
    # per-project Open Design run lifecycle lives in ``PrototypeStatus``; this
    # phase only marks that the project is *in* the prototype stage.
    PROTOTYPE = "PROTOTYPE"
    # Epic U-PLAN inserts the verification-driven planning stage between prototype
    # and code generation: approving the prototype lands here. The PM tree itself
    # (nodes, contracts, ratify gate, links, ledger) lives in the standalone Lothal
    # PM service (repo realbytecode/lothal_project), reached by the backend via
    # ``lothal/pm_client.py`` and re-exposed at ``/projects/{id}/plan/*``; this phase
    # only marks that the project is *in* the planning stage.
    PLAN = "PLAN"
    CODE_GENERATION = "CODE_GENERATION"
    DONE = "DONE"


class MessageRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class PrototypeStatus(str, Enum):
    """Lifecycle of the project's Open Design prototype run (Epic UI, Story U.1).

    Independent of ``ProjectPhase``: a project sits in the (future) ``PROTOTYPE``
    phase while this status walks ``IDLE → GENERATING → READY → APPROVED``. The
    phase enum itself is added separately by Story U.0.
    """

    IDLE = "IDLE"
    GENERATING = "GENERATING"
    READY = "READY"
    APPROVED = "APPROVED"


class Project(SQLModel, table=True):  # type: ignore[call-arg]
    """A Lothal project: the top-level entity holding every artifact (MVP stores all in the DB)."""

    __tablename__ = "lothal_project"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    # DB-level CASCADE so deleting a user can't be blocked by (or orphan) their
    # lothal rows, no matter which code path issues the DELETE.
    user_id: UUIDstr = Field(
        sa_column=Column(Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    name: str = Field(index=True)
    phase: str = Field(default=ProjectPhase.CLARIFICATION)
    # Synthesised PRD; null until clarification completes. Primary LLM context source.
    prd_content: str | None = Field(default=None, sa_column=Column(Text))
    # Canonical xyflow diagram as a JSON string ({nodes, edges} incl. positions);
    # null until generated. Legacy artifact: D.13 converts any populated value into
    # ``diagram_d2`` so all projects render on the D2 canvas. The column is kept for
    # historical reference; dropping it is a later, separate migration (post-D.15).
    diagram_json: str | None = Field(default=None, sa_column=Column(Text))
    # D2 source text — the diagram artifact going forward (Epic D). Null until
    # generated; D2 owns layout, so no positions are stored. The LLM reads/writes it.
    diagram_d2: str | None = Field(default=None, sa_column=Column(Text))
    # Generic artifact file-map ``{path: content}`` shared by every stage (Epic E).
    # The Architecture stage writes ``adr.md`` + ``diagrams/*.d2`` here; it is the
    # future git commit tree verbatim. Null until a stage produces artifacts; old
    # projects keep rendering via ``diagram_d2`` and are not backfilled.
    artifacts: dict[str, str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    # --- Open Design prototype linkage (Epic UI, Story U.1) -------------------
    # Identifiers of the OD project/conversation Lothal drives as a headless
    # prototyping engine; null until the PROTOTYPE stage seeds an OD project.
    od_project_id: str | None = Field(default=None, sa_column=Column(Text))
    od_conversation_id: str | None = Field(default=None, sa_column=Column(Text))
    # Prototype run lifecycle (see ``PrototypeStatus``). NOT NULL, defaults to
    # IDLE — every project (incl. pre-prototype rows) has a well-defined status.
    prototype_status: str = Field(
        default=PrototypeStatus.IDLE,
        sa_column=Column(Text, nullable=False, server_default=PrototypeStatus.IDLE.value),
    )
    # When the user approved the prototype (the boundary at which finalised
    # artifacts are copied into ``lothal_prototype_artifact``); null until then.
    prototype_approved_at: datetime | None = Field(default=None, sa_column=Column(DateTime))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
    )

    messages: list["Message"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    code_files: list["CodeFile"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    prototype_artifacts: list["PrototypeArtifact"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class PMProjectLink(SQLModel, table=True):  # type: ignore[call-arg]
    """The persisted Langflow-project → PM-project mapping (Story P.4).

    The standalone PM service issues its own project ids and has no
    lookup-by-external-key, so the mapping lives here. One row per Langflow
    project, written on first use of the plan stage (``_ensure_pm_project`` in
    ``api/v1/lothal.py``); the primary key on ``lf_project_id`` is what makes
    concurrent first use race-safe (losers hit the conflict, re-read the winner,
    and delete their orphan PM project).
    """

    __tablename__ = "lothal_pm_project_link"

    # DB-level CASCADE, matching the other lothal child tables: deleting a
    # project drops its link row (the PM-side tree is left to the PM service).
    lf_project_id: UUIDstr = Field(
        sa_column=Column(Uuid(), ForeignKey("lothal_project.id", ondelete="CASCADE"), primary_key=True)
    )
    pm_project_id: UUIDstr = Field(sa_column=Column(Uuid(), nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Message(SQLModel, table=True):  # type: ignore[call-arg]
    """A single conversation turn. Used for session restore, audit, and clarification-chip replay."""

    __tablename__ = "lothal_message"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    # DB-level CASCADE backs the ORM cascade for deletes that bypass the ORM.
    project_id: UUIDstr = Field(
        sa_column=Column(Uuid(), ForeignKey("lothal_project.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    role: str = Field()
    content: str = Field(sa_column=Column(Text, nullable=False))
    # Clarification chips; [] for USER messages and non-clarification replies.
    suggestions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    phase: str = Field()
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Project | None = Relationship(back_populates="messages")

    def __init__(self, **data) -> None:
        # Table models skip pydantic validation, so a missing phase would
        # otherwise surface only as an IntegrityError at flush time — far from
        # the bug (the column is NOT NULL and has no meaningful static
        # default; it must mirror the project's phase at send time). Fail at
        # construction instead. Rows loaded from the DB bypass __init__.
        if data.get("phase") is None:
            msg = "Message.phase is required — pass the project's current phase."
            raise TypeError(msg)
        super().__init__(**data)


class CodeFile(SQLModel, table=True):  # type: ignore[call-arg]
    """One generated source file. Populated during CODE_GENERATION; assembled into a ZIP on download."""

    __tablename__ = "lothal_code_file"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    # DB-level CASCADE backs the ORM cascade for deletes that bypass the ORM.
    project_id: UUIDstr = Field(
        sa_column=Column(Uuid(), ForeignKey("lothal_project.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    path: str = Field()
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Project | None = Relationship(back_populates="code_files")


class PrototypeArtifact(SQLModel, table=True):  # type: ignore[call-arg]
    """One finalised Open Design prototype artifact Lothal retains (Epic UI, Story U.1).

    DB-as-source-of-truth MVP rule: on prototype approval the chosen OD artifacts
    are copied here (one row each) so the project's prototype survives independent
    of OD's own storage. ``od_path`` is the artifact's path inside the OD project;
    ``manifest`` is OD's ``ArtifactManifest`` (kind/renderer/exports/provenance);
    ``content`` holds the copied file text (or a URL for media served by OD).
    """

    __tablename__ = "lothal_prototype_artifact"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    # DB-level CASCADE backs the ORM cascade for deletes that bypass the ORM.
    project_id: UUIDstr = Field(
        sa_column=Column(Uuid(), ForeignKey("lothal_project.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    od_path: str = Field()
    kind: str = Field()
    title: str = Field()
    manifest: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    content: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Project | None = Relationship(back_populates="prototype_artifacts")
