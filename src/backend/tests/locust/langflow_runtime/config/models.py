"""Pydantic models for performance-suite movement profiles."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

STRESS_CATEGORIES = frozenset(
    {
        "protocol_calibration",
        "chat_db",
        "hitl",
        "queue",
        "kb_ingest",
        "kb_retrieve",
        "cpu_graph",
        "multiproc",
        "disk_io",
        "ram_storage",
        "outbound",
        "ensemble_flow",
        "ensemble_flow_hitl",
        "ensemble_suite",
    }
)

SUPPORTED_PROTOCOLS = frozenset(
    {
        "mcp",
        "workflows_sync",
        "workflows_stream",
        "workflows_background",
        "webhook",
    }
)

SUPPORTED_MODES = frozenset({"sync", "stream", "background", "webhook"})

SUPPORTED_SURFACES = SUPPORTED_PROTOCOLS

SCHEMA_VERSION = "1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ThinkTime(StrictModel):
    min_s: Annotated[float, Field(ge=0)]
    max_s: Annotated[float, Field(ge=0)]

    @model_validator(mode="after")
    def _max_gte_min(self) -> ThinkTime:
        if self.max_s < self.min_s:
            msg = "think_time.max_s must be >= think_time.min_s"
            raise ValueError(msg)
        return self


class UserMixEntry(StrictModel):
    user_class: str = Field(min_length=1)
    weight: Annotated[int, Field(ge=0)]
    count: int | None = Field(default=None, ge=0)


class WorkloadConfig(StrictModel):
    workload_model: Literal["closed", "paced_closed"]
    user_mix: list[UserMixEntry] = Field(min_length=1)
    think_time: ThinkTime | None = None
    arrival_rate_per_s: Annotated[float, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def _validate_workload(self) -> WorkloadConfig:
        if self.workload_model == "paced_closed" and self.arrival_rate_per_s is None:
            msg = "arrival_rate_per_s is required for paced_closed workload_model"
            raise ValueError(msg)
        if self.workload_model == "closed" and self.arrival_rate_per_s is not None:
            msg = "arrival_rate_per_s is only valid for paced_closed workload_model"
            raise ValueError(msg)
        return self


class WarmUpWindow(StrictModel):
    duration_s: Annotated[float, Field(gt=0)]
    users: Annotated[int, Field(ge=0)]


class MeasuredStep(StrictModel):
    duration_s: Annotated[float, Field(gt=0)]
    spawn_rate: Annotated[float, Field(gt=0)]
    users: Annotated[int, Field(ge=0)] | None = None
    arrival_rate_per_s: Annotated[float, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def _exactly_one_load_knob(self) -> MeasuredStep:
        has_users = self.users is not None
        has_rate = self.arrival_rate_per_s is not None
        if has_users == has_rate:
            msg = "measured step requires exactly one of users or arrival_rate_per_s"
            raise ValueError(msg)
        return self


class DrainWindow(StrictModel):
    deadline_s: Annotated[float, Field(gt=0)]


class WindowsConfig(StrictModel):
    warm_up: WarmUpWindow
    measured_steps: list[MeasuredStep] = Field(min_length=1)
    drain: DrainWindow
    sampling_interval_s: Annotated[float, Field(gt=0)]
    poll_interval_s: Annotated[float, Field(gt=0)]


class CorrectnessSampling(StrictModel):
    enabled: bool = True
    sample_every_n_requests: Annotated[int, Field(ge=1)] = 10
    verify_outputs: bool = True
    verify_lifecycle: bool = True


class SafetyLimits(StrictModel):
    provider_spend_usd: Annotated[float, Field(ge=0)]
    backlog_max: Annotated[int, Field(ge=0)]
    storage_growth_bytes: Annotated[int, Field(ge=0)]
    error_storm_rate: Annotated[float, Field(ge=0, le=1)]
    drain_timeout_s: Annotated[float, Field(gt=0)]
    cleanup_timeout_s: Annotated[float, Field(gt=0)]


class ValidityConfig(StrictModel):
    max_generator_cpu_pct: Annotated[float, Field(gt=0, le=100)]
    allowed_scheduling_lateness_s: Annotated[float, Field(ge=0)]
    cold_warm: Literal["cold", "warm", "either"]


class ResetRules(StrictModel):
    reset_message_store: bool = False
    reset_kb_corpus: bool = False
    reset_storage_artifacts: bool = False
    reset_webhook_subscriptions: bool = False
    reset_mcp_sessions: bool = False


class MovementProfile(StrictModel):
    schema_version: Literal["1"]
    id: str = Field(min_length=1)
    test_type: Literal["smoke", "load", "capacity"]
    purpose: str = Field(min_length=1)
    movement_kind: Literal["solo", "duet", "tutti"]
    stress_categories: list[str] = Field(min_length=1)
    protocols: list[str] = Field(min_length=1)
    modes: list[str] = Field(min_length=1)
    flow_selectors: list[str] = Field(min_length=1)
    dataset_selectors: list[str] = Field(default_factory=list)
    workload: WorkloadConfig
    windows: WindowsConfig
    correctness_sampling: CorrectnessSampling = Field(default_factory=CorrectnessSampling)
    safety_limits: SafetyLimits
    validity: ValidityConfig
    reset_rules: ResetRules = Field(default_factory=ResetRules)
    extends: str | None = None

    @field_validator("stress_categories")
    @classmethod
    def _validate_stress_categories(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - STRESS_CATEGORIES)
        if unknown:
            msg = f"unknown stress_categories: {', '.join(unknown)}"
            raise ValueError(msg)
        return value

    @field_validator("protocols")
    @classmethod
    def _validate_protocols(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - SUPPORTED_PROTOCOLS)
        if unknown:
            msg = f"unknown protocols (surfaces): {', '.join(unknown)}"
            raise ValueError(msg)
        return value

    @field_validator("modes")
    @classmethod
    def _validate_modes(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - SUPPORTED_MODES)
        if unknown:
            msg = f"unknown modes: {', '.join(unknown)}"
            raise ValueError(msg)
        return value
