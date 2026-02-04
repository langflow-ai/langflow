from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from langflow.services.database.models.dataset.model import Dataset
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User


class EvaluationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScoringMethod(str, Enum):
    EXACT_MATCH = "exact_match"
    CONTAINS = "contains"
    SIMILARITY = "similarity"
    LLM_JUDGE = "llm_judge"


# Evaluation Models
class EvaluationBase(SQLModel):
    name: str | None = Field(default=None, description="Name of the evaluation")
    scoring_methods: list[str] = Field(
        default=["exact_match"],
        sa_column=Column(JSON),
        description="List of scoring methods to use",
    )


class Evaluation(EvaluationBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "evaluation"

    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the evaluation",
    )
    status: str = Field(default=EvaluationStatus.PENDING.value, description="Status of the evaluation")
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the evaluation",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last update time of the evaluation",
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the evaluation started running",
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the evaluation completed",
    )
    error_message: str | None = Field(default=None, description="Error message if evaluation failed")

    # Summary metrics
    total_items: int = Field(default=0, description="Total number of items to evaluate")
    completed_items: int = Field(default=0, description="Number of items completed")
    passed_items: int = Field(default=0, description="Number of items that passed")
    mean_score: float | None = Field(default=None, description="Mean score across all items")
    mean_duration_ms: float | None = Field(default=None, description="Mean duration in milliseconds")
    total_runtime_ms: int | None = Field(default=None, description="Total runtime in milliseconds")

    # Foreign keys
    user_id: UUID = Field(description="User ID who created this evaluation", foreign_key="user.id")
    dataset_id: UUID = Field(description="Dataset used for evaluation", foreign_key="dataset.id")
    flow_id: UUID = Field(description="Flow being evaluated", foreign_key="flow.id")

    # Relationships
    user: "User" = Relationship(back_populates="evaluations")
    dataset: "Dataset" = Relationship()
    flow: "Flow" = Relationship()
    results: list["EvaluationResult"] = Relationship(
        back_populates="evaluation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )


class EvaluationCreate(SQLModel):
    name: str | None = None
    dataset_id: UUID
    flow_id: UUID
    scoring_methods: list[str] = ["exact_match"]


class EvaluationRead(SQLModel):
    id: UUID
    name: str | None = None
    status: str
    scoring_methods: list[str]
    user_id: UUID
    dataset_id: UUID
    flow_id: UUID
    dataset_name: str | None = None
    flow_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    total_items: int = 0
    completed_items: int = 0
    passed_items: int = 0
    mean_score: float | None = None
    mean_duration_ms: float | None = None
    total_runtime_ms: int | None = None


class EvaluationReadWithResults(EvaluationRead):
    results: list["EvaluationResultRead"] = []


class EvaluationUpdate(SQLModel):
    name: str | None = None
    status: str | None = None


# EvaluationResult Models
class EvaluationResultBase(SQLModel):
    input: str = Field(description="Input value from dataset")
    expected_output: str = Field(description="Expected output from dataset")
    actual_output: str | None = Field(default=None, description="Actual output from flow")
    duration_ms: int | None = Field(default=None, description="Execution duration in milliseconds")
    scores: dict = Field(default={}, sa_column=Column(JSON), description="Scores for each scoring method")
    passed: bool = Field(default=False, description="Whether the result passed based on threshold")
    error: str | None = Field(default=None, description="Error message if execution failed")
    order: int = Field(default=0, description="Order of the item in the dataset")


class EvaluationResult(EvaluationResultBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "evaluationresult"

    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the evaluation result",
    )
    evaluation_id: UUID = Field(
        description="Evaluation this result belongs to",
        foreign_key="evaluation.id",
    )
    dataset_item_id: UUID | None = Field(
        default=None,
        description="Reference to the original dataset item",
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the result",
    )
    evaluation: Evaluation = Relationship(back_populates="results")


class EvaluationResultCreate(SQLModel):
    input: str
    expected_output: str
    actual_output: str | None = None
    duration_ms: int | None = None
    scores: dict = {}
    passed: bool = False
    error: str | None = None
    order: int = 0
    dataset_item_id: UUID | None = None


class EvaluationResultRead(SQLModel):
    id: UUID
    evaluation_id: UUID
    dataset_item_id: UUID | None = None
    input: str
    expected_output: str
    actual_output: str | None = None
    duration_ms: int | None = None
    scores: dict = {}
    passed: bool = False
    error: str | None = None
    order: int = 0
    created_at: datetime | None = None
