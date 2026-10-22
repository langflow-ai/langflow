"""Public request/response shapes for the data subject API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from langflow.services.database.models.data_subject_request.schemas import DataSubjectType

MAX_REFUSAL_NOTE_LENGTH = 1000
MAX_SCOPE_FLOWS = 500


class DataSubjectRef(BaseModel):
    """Identify a subject: a builder by ``user_id`` or ``username`` (the email under SSO), an end user by id."""

    subject_type: DataSubjectType
    user_id: UUID | None = None
    username: str | None = Field(default=None, min_length=1, max_length=255)
    end_user_id: str | None = Field(default=None, max_length=255)
    flow_ids: list[UUID] | None = Field(default=None, max_length=MAX_SCOPE_FLOWS)

    @model_validator(mode="after")
    def _one_identifier(self) -> DataSubjectRef:
        builder_ids = (self.user_id is not None) + (self.username is not None)
        if self.subject_type == DataSubjectType.BUILDER and (builder_ids != 1 or self.end_user_id):
            msg = "A builder is identified by exactly one of user_id or username"
            raise ValueError(msg)
        if self.subject_type == DataSubjectType.END_USER and (not self.end_user_id or builder_ids):
            msg = "An end user is identified by end_user_id only"
            raise ValueError(msg)
        if self.subject_type == DataSubjectType.BUILDER and self.flow_ids:
            msg = "flow_ids scopes end-user requests only"
            raise ValueError(msg)
        return self


class RefuseRequest(BaseModel):
    note: str | None = Field(default=None, max_length=MAX_REFUSAL_NOTE_LENGTH)


class DataSubjectRequestRead(BaseModel):
    id: UUID
    subject_type: str
    subject_user_id: UUID
    subject_label: str | None
    source: str
    status: str
    phase: str | None
    requested_by: UUID | None
    decided_by: UUID | None
    requested_at: datetime | None
    due_at: datetime
    decided_at: datetime | None
    finished_at: datetime | None
    counts: dict[str, Any] | None
    error: dict[str, Any] | None
    refusal_note: str | None
    overdue: bool = False


class DataSubjectRequestPage(BaseModel):
    total_count: int
    requests: list[DataSubjectRequestRead]


class DryRunSummary(BaseModel):
    subject_type: str
    counts: dict[str, int]
    deployments: list[str] = Field(default_factory=list)
    shared_flows: list[str] = Field(default_factory=list)
    blocked_by: Literal["deployed_flows", "last_administrator"] | None = None


class OwnDeletionRequestStatus(BaseModel):
    """What a builder sees about their own request; admin-only fields are left out."""

    id: UUID
    status: str
    requested_at: datetime | None
    decided_at: datetime | None


class ErasureAccepted(BaseModel):
    detail: str
    request_id: UUID


class EndUserMatch(BaseModel):
    """An end-user id Langflow has sessions for, to pick from when recording a request."""

    end_user_id: str
    messages: int
