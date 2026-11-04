"""Only reviewed identities cross the repair API boundary."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SHA256_PATTERN = r"^[0-9a-f]{64}$"
MAX_SELECTED_FLOWS = 100


class RepairSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flow_id: UUID
    version_token: UUID | None
    data_sha256: str = Field(pattern=SHA256_PATTERN)


class RepairPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flow_ids: list[UUID] = Field(min_length=1, max_length=MAX_SELECTED_FLOWS)
    report_id: UUID | None = None

    @model_validator(mode="after")
    def reject_duplicate_selections(self) -> RepairPreviewRequest:
        if len(set(self.flow_ids)) != len(self.flow_ids):
            msg = "Select each flow only once"
            raise ValueError(msg)
        return self


class RepairApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flows: list[RepairSelection] = Field(min_length=1, max_length=MAX_SELECTED_FLOWS)
    target_sha256: str = Field(pattern=SHA256_PATTERN)
    report_id: UUID | None = None

    @model_validator(mode="after")
    def reject_duplicate_selections(self) -> RepairApplyRequest:
        if len({flow.flow_id for flow in self.flows}) != len(self.flows):
            msg = "Select each flow only once"
            raise ValueError(msg)
        return self


class RepairResult(BaseModel):
    flow_id: UUID
    status: Literal["ready", "updated", "unchanged", "manual", "conflict", "forbidden", "not_found", "failed"]
    version_token: UUID | None = None
    data_sha256: str | None = None
    updated_nodes: int = 0
    recovery_version_id: UUID | None = None
    reason_codes: list[str] = Field(default_factory=list)


class RepairBatchResult(BaseModel):
    target_sha256: str
    results: list[RepairResult]
