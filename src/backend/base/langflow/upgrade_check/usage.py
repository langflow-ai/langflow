"""Import-safe usage evidence shared by the checker and report consumers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from langflow.upgrade_check.source import SourceIdentity


class UsageCoverage(BaseModel):
    """The observed job-record period, without claiming a complete execution history."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    oldest_retained_at: str | None = None
    newest_retained_at: str | None = None
    observed_at: str
    complete: Literal[False] = False
    retention_days: int | None = Field(default=None, ge=0)

    @field_validator("oldest_retained_at", "newest_retained_at", "observed_at")
    @classmethod
    def timezone_is_known(cls, value: str | None) -> str | None:
        return _aware_timestamp(value)

    @model_validator(mode="after")
    def period_is_ordered(self) -> UsageCoverage:
        if (
            self.oldest_retained_at
            and self.newest_retained_at
            and _parse(self.oldest_retained_at) > _parse(self.newest_retained_at)
        ):
            msg = "the retained period must be ordered"
            raise ValueError(msg)
        return self


class JobUsage(BaseModel):
    """Execution evidence for one preserved Editor flow ID in one database."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    runs: int | None = Field(default=None, ge=0)
    errors: int | None = Field(default=None, ge=0)
    last_run_at: str | None = None
    history: Literal["retained_records", "no_retained_records", "unavailable"]
    coverage: UsageCoverage
    limitations: list[str] = Field(default_factory=list)
    source_identity: SourceIdentity | None = None

    @field_validator("last_run_at")
    @classmethod
    def timezone_is_known(cls, value: str | None) -> str | None:
        return _aware_timestamp(value)

    @model_validator(mode="after")
    def counts_match_evidence(self) -> JobUsage:
        if self.history == "unavailable":
            if self.runs is not None or self.errors is not None or self.last_run_at is not None:
                msg = "unavailable history must keep counts and last run unknown"
                raise ValueError(msg)
        elif self.runs is None or self.errors is None:
            msg = "available history requires known retained counts"
            raise ValueError(msg)
        elif self.errors > self.runs:
            msg = "errors cannot exceed retained runs"
            raise ValueError(msg)
        elif self.history == "no_retained_records" and (self.runs or self.errors or self.last_run_at):
            msg = "absent retained records cannot establish a run"
            raise ValueError(msg)
        elif self.last_run_at is not None and not self.runs:
            msg = "a last run requires execution evidence"
            raise ValueError(msg)
        return self


class FlowUsage(BaseModel):
    """Keep Editor and Serving evidence separate rather than double-counting runs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    editor: JobUsage
    serving: JobUsage


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _aware_timestamp(value: str | None) -> str | None:
    if value is not None and _parse(value).utcoffset() is None:
        msg = "usage timestamps must include a timezone"
        raise ValueError(msg)
    return value
