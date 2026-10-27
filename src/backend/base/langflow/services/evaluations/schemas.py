from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from langflow.services.database.models.evaluation.dataset import DATASET_NAME_MAX_LENGTH

ScorerType = Literal["exact_match", "contains", "similarity", "llm_judge"]
TEXT_MAX_CHARS = 100_000
RUBRIC_MAX_CHARS = 4000
# Room for a judge model selection plus the longest rubric.
SCORER_CONFIG_MAX_CHARS = 16000
TEXT_SCORER_CONFIG_KEYS = frozenset({"case_sensitive"})
MAX_SCORERS = 10
MAX_ITEMS_PER_REQUEST = 500


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=DATASET_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "Name must not be blank"
            raise ValueError(msg)
        return stripped


class DatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=DATASET_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            msg = "Name must not be blank"
            raise ValueError(msg)
        return stripped


class DatasetRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    revision: int
    item_count: int
    created_at: datetime
    updated_at: datetime


class DatasetItemWrite(BaseModel):
    input: str = Field(min_length=1, max_length=TEXT_MAX_CHARS)
    expected_output: str | None = Field(default=None, max_length=TEXT_MAX_CHARS)


class DatasetItemsCreate(BaseModel):
    items: list[DatasetItemWrite] = Field(min_length=1, max_length=MAX_ITEMS_PER_REQUEST)


class DatasetItemUpdate(BaseModel):
    input: str | None = Field(default=None, min_length=1, max_length=TEXT_MAX_CHARS)
    expected_output: str | None = Field(default=None, max_length=TEXT_MAX_CHARS)
    clear_expected_output: bool = False


class DatasetItemRead(BaseModel):
    id: UUID
    position: int
    input: str
    expected_output: str | None
    source: str
    created_at: datetime
    updated_at: datetime


class DatasetItemsDelete(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=MAX_ITEMS_PER_REQUEST)


class CsvPreview(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    total_rows: int


class SkippedRow(BaseModel):
    row: int
    reason: str


class CsvImportResult(BaseModel):
    imported: int
    skipped: list[SkippedRow]


class Page(BaseModel):
    total: int
    page: int
    size: int


class DatasetPage(Page):
    items: list[DatasetRead]


class DatasetItemPage(Page):
    items: list[DatasetItemRead]


class ScorerSpec(BaseModel):
    type: ScorerType
    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9 _.-]+$")
    weight: float = Field(default=1.0, gt=0, le=100)
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config(self) -> ScorerSpec:
        if len(json.dumps(self.config, default=str)) > SCORER_CONFIG_MAX_CHARS:
            msg = f"Scorer config must be at most {SCORER_CONFIG_MAX_CHARS} characters"
            raise ValueError(msg)
        if self.type != "llm_judge":
            unknown = set(self.config) - TEXT_SCORER_CONFIG_KEYS
            if unknown:
                msg = f"Unknown config for {self.type}: {', '.join(sorted(unknown))}"
                raise ValueError(msg)
            return self
        model = self.config.get("model")
        if not isinstance(model, list) or not model or not isinstance(model[0], dict):
            msg = "llm_judge requires config.model: a model selection"
            raise ValueError(msg)
        rubric = self.config.get("rubric")
        if rubric is not None and (not isinstance(rubric, str) or len(rubric) > RUBRIC_MAX_CHARS):
            msg = f"llm_judge config.rubric must be text of at most {RUBRIC_MAX_CHARS} characters"
            raise ValueError(msg)
        return self


def _validate_scorer_names(scorers: list[ScorerSpec]) -> list[ScorerSpec]:
    names = [scorer.name for scorer in scorers]
    if len(names) != len(set(names)):
        msg = "Scorer names must be unique"
        raise ValueError(msg)
    return scorers


class EvaluationCreate(BaseModel):
    flow_id: UUID
    dataset_id: UUID
    name: str | None = Field(default=None, max_length=255)
    output_vertex_id: str | None = Field(default=None, max_length=255)
    scorers: list[ScorerSpec] = Field(min_length=1, max_length=MAX_SCORERS)
    pass_threshold: float = Field(default=0.5, ge=0, le=1)
    flow_version_id: UUID | None = None
    """With ``?run=true``: the history version to run (default: the latest draft). Not stored."""

    @field_validator("scorers")
    @classmethod
    def unique_names(cls, value: list[ScorerSpec]) -> list[ScorerSpec]:
        return _validate_scorer_names(value)


class EvaluationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    dataset_id: UUID | None = None
    output_vertex_id: str | None = Field(default=None, max_length=255)
    scorers: list[ScorerSpec] | None = Field(default=None, min_length=1, max_length=MAX_SCORERS)
    pass_threshold: float | None = Field(default=None, ge=0, le=1)

    @field_validator("scorers")
    @classmethod
    def unique_names(cls, value: list[ScorerSpec] | None) -> list[ScorerSpec] | None:
        return None if value is None else _validate_scorer_names(value)


class EvaluationRead(BaseModel):
    id: UUID
    name: str
    project_id: UUID | None
    flow_id: UUID | None
    flow_name: str | None
    dataset_id: UUID | None
    dataset_name: str | None
    output_vertex_id: str | None
    scorers: list[dict[str, Any]]
    pass_threshold: float
    last_run: EvaluationRunRead | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationPage(Page):
    items: list[EvaluationRead]


class RunStart(BaseModel):
    flow_version_id: UUID | None = None


class EvaluationRunRead(BaseModel):
    id: UUID
    evaluation_id: UUID
    status: str
    flow_id: UUID | None
    flow_name: str
    flow_version_id: UUID | None
    flow_version_number: int | None
    flow_version_source: str
    dataset_id: UUID | None
    dataset_name: str
    dataset_revision: int
    config: dict[str, Any]
    total_items: int
    completed_items: int
    failed_items: int
    passed_items: int
    summary: dict[str, Any] | None
    estimate: dict[str, Any] | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class EvaluationRunPage(Page):
    items: list[EvaluationRunRead]


class EvaluationResultRead(BaseModel):
    id: UUID
    position: int
    input: str
    expected_output: str | None
    actual_output: str | None
    output_truncated: bool
    error: str | None
    scores: dict[str, Any]
    passed: bool | None
    duration_ms: int
    tokens_flow: int | None
    tokens_judge: int | None
    cost_flow: float | None
    cost_judge: float | None
    trace_id: str | None
    preview: bool = False
    """True when the texts are clipped previews (the results list); the single-result read has them in full."""


class EvaluationResultPage(Page):
    items: list[EvaluationResultRead]


class FlowCheckIssue(BaseModel):
    code: str
    message: str
    components: list[str] = Field(default_factory=list)


class FlowCheckReport(BaseModel):
    blocking: list[FlowCheckIssue]
    warnings: list[FlowCheckIssue]
    output_vertices: list[dict[str, str]]


class EstimateRequest(BaseModel):
    flow_id: UUID
    dataset_id: UUID
    scorers: list[ScorerSpec] = Field(default_factory=list, max_length=MAX_SCORERS)


class EstimateRead(BaseModel):
    items: int
    basis: Literal["history", "model"]
    llm_calls: int
    judge_calls: int
    flow_tokens_low: int
    flow_tokens_high: int
    judge_tokens_low: int
    judge_tokens_high: int
    tokens_low: int
    tokens_high: int
    cost_low: float | None
    cost_high: float | None
    unpriced_models: list[str] = Field(default_factory=list)
    has_agent: bool = False


EvaluationRead.model_rebuild()
