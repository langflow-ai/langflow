"""Eval Suite contracts and fail-closed assessment, independent of the hosting database."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lfx.projects.artifacts import SourcedReport
from lfx.projects.bindings import FlowBinding, contract_outputs, flow_revision

EVAL_INPUT_VARIABLE = "HARNESS_EVAL_INPUT"


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=200)
    input: str = Field(min_length=1, max_length=16000)
    reference: str = Field(default="", max_length=16000)
    minimum_score: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    require_sourced_artifact: bool = False
    require_supported_claims: bool = False
    expected_policy: Literal["compliant", "violation"] | None = None
    max_latency_ms: int | None = Field(default=None, gt=0, le=3_600_000)
    max_cost_usd: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class EvalSuiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: UUID | None = None
    candidate_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    scorer: FlowBinding | None = None
    cases: list[EvalCase] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def unique_cases(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            msg = "Evaluation case IDs must be unique."
            raise ValueError(msg)
        return self

    def require_runnable(self) -> None:
        if not self.workflow_id or not self.candidate_digest or not self.scorer or not self.cases:
            msg = "Choose a mounted candidate, review a scorer, and add at least one case."
            raise ValueError(msg)

    @property
    def revision(self) -> str:
        # Candidate identity is separate: identical cases/scorers across candidates
        # must have the same comparison key. Server-assigned snapshots are included.
        content = self.model_dump(mode="json", exclude={"candidate_digest"})
        return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class EvalVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=8000)
    claim_support: Literal["supported", "unsupported", "not_evaluated"] = "not_evaluated"
    policy: Literal["compliant", "violation", "not_evaluated"] = "not_evaluated"


class EvalCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    workflow_job_id: UUID | None = None
    scorer_job_id: UUID | None = None
    passed: bool = False
    failures: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    cost_usd: float | None = None
    verdict: EvalVerdict | None = None
    output: dict | None = None


def scorer_outputs(data: dict) -> list[dict]:
    sources = [node["id"] for node in data.get("nodes", []) if node.get("data", {}).get("type") == "EvaluationInput"]
    if len(sources) != 1:
        msg = "A scorer needs one Evaluation Input connected to an Evaluation Result output."
        raise ValueError(msg)
    reachable = set(sources)
    for _ in data.get("nodes", []):
        reachable.update(edge["target"] for edge in data.get("edges", []) if edge.get("source") in reachable)
    results = {node["id"] for node in data.get("nodes", []) if node.get("data", {}).get("type") == "EvaluationResult"}
    return [choice for choice in contract_outputs(data, {"Data", "JSON"}) if choice["node_id"] in reachable & results]


def validate_scorer(data: dict, binding: FlowBinding) -> None:
    if flow_revision(data) != binding.revision or not any(
        item["node_id"] == binding.node_id and item["output_name"] == binding.output_name
        for item in scorer_outputs(data)
    ):
        msg = "The scorer changed or its output is incompatible. Review the scorer again."
        raise ValueError(msg)


def output_data(output: dict, output_name: str) -> dict:
    """Unwrap only the documented Data/component output envelopes, never search arbitrary nested content."""
    content = output.get("content")
    if isinstance(content, dict) and output_name in content:
        content = content[output_name]
    if isinstance(content, dict) and content.get("type") in {"data", "object"}:
        content = content.get("message")
    if isinstance(content, dict) and isinstance(content.get("data"), dict):
        content = content["data"]
    if not isinstance(content, dict):
        msg = "The selected output did not return a Data record."
        raise TypeError(msg)
    return content


def assess_case(case: EvalCase, result: EvalCaseResult) -> EvalCaseResult:
    failures = list(result.failures)
    verdict = result.verdict
    if verdict is None:
        failures.append("scorer_result_missing")
    else:
        if verdict.score < case.minimum_score:
            failures.append("score_below_threshold")
        if case.require_supported_claims and verdict.claim_support != "supported":
            failures.append("claims_not_supported")
        if case.expected_policy is not None and verdict.policy != case.expected_policy:
            failures.append("policy_outcome_mismatch")
    if case.max_latency_ms is not None and (result.latency_ms is None or result.latency_ms > case.max_latency_ms):
        failures.append("latency_budget_exceeded_or_unavailable")
    if case.max_cost_usd is not None and (result.cost_usd is None or result.cost_usd > case.max_cost_usd):
        failures.append("cost_budget_exceeded_or_unavailable")
    if case.require_sourced_artifact:
        reports = []
        for output in (result.output or {}).get("outputs", {}).values():
            try:
                data = output_data(output, "artifact")
                report = SourcedReport.model_validate(data.get("artifact"))
                report.require_resolved_citations()
                if report.execution.run_id != result.workflow_job_id or str(report.execution.flow_id) != str(
                    (result.output or {}).get("flow_id")
                ):
                    continue
                reports.append(report)
            except (ValueError, TypeError):
                continue
        if not reports:
            failures.append("sourced_artifact_missing_or_invalid")
    return result.model_copy(update={"passed": not failures, "failures": list(dict.fromkeys(failures))})


def scorer_baseline() -> dict:
    from lfx.components.models_and_agents.evaluation_input import EvaluationInputComponent
    from lfx.components.models_and_agents.evaluation_result import EvaluationResultComponent
    from lfx.graph.flow_builder import add_component, add_connection, empty_flow

    flow = empty_flow("Evaluation scorer", "Judge the actual response and evidence against the case reference.")
    for component in (EvaluationInputComponent(), EvaluationResultComponent()):
        add_component(flow, component.name, {component.name: component.to_frontend_node()["data"]["node"]})
    source, target = flow["data"]["nodes"]
    source["position"], target["position"] = {"x": 100, "y": 160}, {"x": 620, "y": 160}
    add_connection(flow, source["id"], "case", target["id"], "case")
    return flow
