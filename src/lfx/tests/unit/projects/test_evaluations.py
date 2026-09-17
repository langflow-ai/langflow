from uuid import uuid4

import pytest
from lfx.projects.artifacts import ArtifactExecution, SourcedReport, SourceRecord
from lfx.projects.evaluations import EvalCase, EvalCaseResult, EvalSuiteConfig, EvalVerdict, assess_case
from pydantic import ValidationError


def test_claims_and_policy_require_positive_evidence_even_with_perfect_score():
    case = EvalCase(
        id="research", name="Research", input="Research", require_supported_claims=True, expected_policy="compliant"
    )
    for support, policy in [("unsupported", "violation"), ("not_evaluated", "not_evaluated")]:
        result = assess_case(
            case,
            EvalCaseResult(
                case_id=case.id, verdict=EvalVerdict(score=1.0, reason="Checked", claim_support=support, policy=policy)
            ),
        )
        assert not result.passed
        assert result.failures == ["claims_not_supported", "policy_outcome_mismatch"]


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1, "1"])
def test_invalid_scores_cannot_pass(score):
    with pytest.raises(ValidationError):
        EvalVerdict(score=score, reason="Checked")


def test_missing_verdict_and_measurements_fail():
    case = EvalCase(id="case", name="Case", input="Question", max_latency_ms=100, max_cost_usd=0.01)
    result = assess_case(case, EvalCaseResult(case_id="case"))
    assert set(result.failures) == {
        "scorer_result_missing",
        "latency_budget_exceeded_or_unavailable",
        "cost_budget_exceeded_or_unavailable",
    }
    assert not result.passed


def test_comparison_revision_changes_with_case_or_threshold_but_not_candidate():
    suite = EvalSuiteConfig(cases=[EvalCase(id="case", name="Case", input="Question")], candidate_digest="a" * 64)
    assert suite.revision == suite.model_copy(update={"candidate_digest": "b" * 64}).revision
    assert (
        suite.revision
        != suite.model_copy(update={"cases": [suite.cases[0].model_copy(update={"minimum_score": 0.5})]}).revision
    )


@pytest.mark.parametrize("wrong_identity", ["flow", "run", "citation"])
def test_sourced_report_cannot_borrow_another_execution_or_missing_evidence(wrong_identity):
    flow_id, run_id = uuid4(), uuid4()
    source = SourceRecord(uri="fixture://study", title="Study", content="Evidence")
    report = SourcedReport(
        title="Research",
        markdown=f"Claim [@{source.id if wrong_identity != 'citation' else 'missing'}]",
        sources=(source,),
        execution=ArtifactExecution(
            flow_id=uuid4() if wrong_identity == "flow" else flow_id,
            run_id=uuid4() if wrong_identity == "run" else run_id,
            node_id="report",
        ),
    )
    result = assess_case(
        EvalCase(id="case", name="Research", input="Research", require_sourced_artifact=True),
        EvalCaseResult(
            case_id="case",
            workflow_job_id=run_id,
            verdict=EvalVerdict(score=1, reason="Checked"),
            output={
                "flow_id": str(flow_id),
                "outputs": {
                    "report": {
                        "content": {
                            "artifact": {
                                "type": "object",
                                "message": {"artifact": report.model_dump(mode="json")},
                            }
                        }
                    }
                },
            },
        ),
    )
    assert result.failures == ["sourced_artifact_missing_or_invalid"]
