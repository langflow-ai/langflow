"""Validate report data without importing or running the isolated checker."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from langflow.upgrade_check.source import SourceIdentity
from langflow.upgrade_check.usage import FlowUsage

Count = Annotated[int, Field(ge=0)]
_MAX_OFFSET_HOUR = 23
_MAX_OFFSET_MINUTE = 59
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-](\d{2}):(\d{2}))$")


def aware_timestamp(value: str) -> str:
    match = _TIMESTAMP.fullmatch(value)
    if not match or (match[1] is not None and (int(match[1]) > _MAX_OFFSET_HOUR or int(match[2]) > _MAX_OFFSET_MINUTE)):
        msg = "timestamps must include a valid timezone"
        raise ValueError(msg)
    parsed = re.sub(r"\.(\d+)(?=Z|[+-])", lambda match: "." + match[1][:6].ljust(6, "0"), value)
    datetime.fromisoformat(parsed.replace("Z", "+00:00"))
    return value


class ReportPart(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)


class ReportSource(ReportPart):
    dialect: Literal["sqlite", "postgresql"]
    identity: SourceIdentity | None = None
    alembic_revision: str | None
    counts: dict[str, Count]

    @model_validator(mode="after")
    def consistent_identity(self) -> ReportSource:
        if self.identity is not None and self.identity.kind != self.dialect:
            msg = "the source identity must match the database dialect"
            raise ValueError(msg)
        return self


class ReportTarget(ReportPart):
    langflow: str = Field(min_length=1, max_length=128)
    lfx: str = Field(min_length=1, max_length=128)
    component_index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundles: list[str]
    custom_components: dict[str, JsonValue]


class ReportCounts(ReportPart):
    ok: Count
    warn: Count
    fail: Count


class ReportSummary(ReportPart):
    flows: ReportCounts
    nodes: dict[str, Count]


class ReportOwner(ReportPart):
    id: str | None
    username: str | None


class ReportProject(ReportPart):
    id: str
    name: str | None


class ReportNode(ReportPart):
    id: str
    group_path: list[str]
    type: str
    display_name: str
    status: str = Field(min_length=1)
    runs: str | None = None
    reasons: list[dict[str, str | None]] = Field(default_factory=list)
    dry_run: dict[str, JsonValue] | None = None
    replacement: list[str] | None = None
    bundle: str | None = None


class ReportFlow(ReportPart):
    id: str = Field(min_length=1, max_length=128)
    kind: Literal["flow", "component", "flow_version"]
    name: str | None
    owner: ReportOwner | None
    project: ReportProject | None
    last_edited_at: str | None
    status: Literal["ok", "warn", "fail"]
    nodes: list[ReportNode]
    ok_nodes: Count
    flow_id: str | None = None
    version_number: Count | None = None
    used_by: dict[str, list[str]] | None = None
    error: str | None = None
    usage: FlowUsage | None = None

    @field_validator("last_edited_at")
    @classmethod
    def validate_edit_time(cls, value: str | None) -> str | None:
        return aware_timestamp(value) if value is not None else None


class ReportError(ReportPart):
    kind: str
    status: Literal["ok", "warn", "fail"]
    message: str


class UpgradeReportDocument(ReportPart):
    format_version: Literal[1]
    generated_at: str
    source: ReportSource
    target: ReportTarget
    settings: dict[str, JsonValue]
    summary: ReportSummary
    flows: list[ReportFlow] = Field(max_length=50000)
    errors: list[ReportError]

    @field_validator("format_version", mode="before")
    @classmethod
    def exact_version(cls, value: object) -> object:
        if type(value) is not int:
            msg = "format_version must be an integer"
            raise ValueError(msg)
        return value

    @field_validator("generated_at")
    @classmethod
    def validate_generated_time(cls, value: str) -> str:
        return aware_timestamp(value)

    @model_validator(mode="after")
    def unique_rows(self) -> UpgradeReportDocument:
        identities = [(flow.kind, flow.id) for flow in self.flows]
        if len(set(identities)) != len(identities):
            msg = "flow rows must have unique kind and id pairs"
            raise ValueError(msg)
        for status in ("ok", "warn", "fail"):
            if sum(flow.status == status for flow in self.flows) > getattr(self.summary.flows, status):
                msg = "flow rows cannot exceed the reported status count"
                raise ValueError(msg)
        return self
