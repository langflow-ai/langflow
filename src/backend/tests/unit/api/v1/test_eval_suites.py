"""Real candidate and scorer execution through the Workflows host, with provider replacement only."""

import asyncio
import json
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobType
from langflow.services.deps import get_job_service, get_settings_service, session_scope
from lfx.graph.flow_builder import add_component, add_connection
from lfx.projects.bindings import flow_revision
from lfx.projects.evaluations import scorer_baseline, scorer_outputs
from sqlmodel import select

from tests.unit.api.v1.evaluation_evidence_fixture import FixtureEvidence
from tests.unit.api.v1.evaluation_fixtures import FixtureJudge
from tests.unit.api.v1.test_harness_skill_packs import skill_harness  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import create_flow, create_project, save_config, stored_flow
from tests.unit.api.v2.test_workflow_candidates import mount
from tests.unit.api.v2.test_workflow_skills import provider, workflow_harness  # noqa: F401


@pytest.fixture
async def evaluation(client, logged_in_headers, active_user, workflow_harness, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(get_settings_service().settings, "developer_api_enabled", True)
    project, root, *_ = workflow_harness
    model = provider(monkeypatch, await stored_flow(root))
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    suite = await create_project(client, logged_in_headers, name="Evaluation suite", project_type="eval-suite")
    baseline = scorer_baseline()
    source, terminal = baseline["data"]["nodes"]
    judge = FixtureJudge()
    add_component(baseline, judge.name, {judge.name: judge.to_frontend_node()["data"]["node"]})
    judge_id = baseline["data"]["nodes"][-1]["id"]
    add_connection(baseline, source["id"], "case", judge_id, "case")
    add_connection(baseline, judge_id, "judgment", terminal["id"], "judgment")
    scorer = await create_flow(active_user, folder_id=suite, data=baseline["data"], name="Reviewed scorer")
    output = scorer_outputs(baseline["data"])[0]
    config = {
        "workflow_id": root,
        "candidate_digest": candidate.digest,
        "scorer": {
            "flow_id": scorer,
            "node_id": output["node_id"],
            "output_name": output["output_name"],
            "revision": flow_revision(baseline["data"]),
        },
        "cases": [
            {
                "id": "research",
                "name": "Research question",
                "input": "Research",
                "reference": "SOURCE RESULT",
                "require_supported_claims": True,
                "expected_policy": "compliant",
            }
        ],
    }
    saved = await save_config(client, logged_in_headers, suite, config)
    assert saved["project_config"]["scorer"]["version_id"]
    return suite, root, scorer, saved["project_config"], candidate, model


async def execute(client, headers, suite, *, run_id=None):
    config = await client.get(f"/api/v1/projects/{suite}/evaluations", headers=headers)
    assert config.status_code == 200, config.text
    response = await client.post(
        f"/api/v1/projects/{suite}/evaluations/runs",
        headers=headers,
        json={
            "run_id": str(run_id or uuid4()),
            "expected_revision": config.json()["revision"],
            "expected_candidate_digest": config.json()["config"]["candidate_digest"],
        },
    )

    if response.status_code != 202:
        return response
    identity = response.json()["id"]
    for _ in range(400):
        response = await client.get(f"/api/v1/projects/{suite}/evaluations/runs/{identity}", headers=headers)
        if response.json()["status"] not in {"queued", "in_progress"}:
            return response
        await asyncio.sleep(0.05)
    pytest.fail(f"Evaluation did not finish: {response.text}")


async def test_evaluation_keeps_candidate_scorer_and_results(client, logged_in_headers, evaluation):
    suite, root, scorer, config, candidate, model = evaluation
    # Both current drafts can change: execution must use candidate + reviewed snapshot.
    async with session_scope() as session:
        for flow_id in (root, scorer):
            row = await session.get(Flow, UUID(flow_id))
            row.data = {"nodes": [], "edges": []}
            session.add(row)
    run_id = uuid4()
    response = await execute(client, logged_in_headers, suite, run_id=run_id)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["passed"] is True, json.dumps(result, indent=2)
    assert result["candidate_digest"] == candidate.digest
    case = result["result"]["cases"][0]
    assert case["verdict"]["claim_support"] == "supported"
    assert "SOURCE RESULT" in json.dumps(case["output"])
    job = await get_job_service().get_job_by_job_id(run_id)
    assert await get_job_service().load_checkpoint(run_id, "harness-candidate")
    assert await get_job_service().load_checkpoint(run_id, "eval-scorer")
    assert job.job_metadata["suite"]["scorer"] == config["scorer"]
    calls = len(model.seen)
    again = await execute(client, logged_in_headers, suite, run_id=run_id)
    assert again.json() == result
    assert len(model.seen) == calls
    read = await client.get(f"/api/v1/projects/{suite}/evaluations/runs/{run_id}", headers=logged_in_headers)
    assert read.json() == result


async def test_budgets_and_missing_artifact_fail_closed(client, logged_in_headers, evaluation):
    suite, _, _, config, _, _ = evaluation
    changed = deepcopy(config)
    changed["cases"][0].update(max_latency_ms=1, max_cost_usd=1.0, require_sourced_artifact=True)
    await save_config(client, logged_in_headers, suite, changed)
    response = await execute(client, logged_in_headers, suite)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["passed"] is False
    assert set(result["result"]["cases"][0]["failures"]) >= {
        "latency_budget_exceeded_or_unavailable",
        "cost_budget_exceeded_or_unavailable",
        "sourced_artifact_missing_or_invalid",
    }


async def test_wrong_candidate_and_stale_suite_do_not_call_provider(client, logged_in_headers, evaluation):
    suite, _, _, config, _, model = evaluation
    wrong = {**config, "candidate_digest": "0" * 64}
    await save_config(client, logged_in_headers, suite, wrong)
    response = await execute(client, logged_in_headers, suite)
    assert response.status_code == 409, response.text
    assert model.seen == []
    stale = await client.post(
        f"/api/v1/projects/{suite}/evaluations/runs",
        headers=logged_in_headers,
        json={"run_id": str(uuid4()), "expected_revision": "0" * 64, "expected_candidate_digest": "0" * 64},
    )
    assert stale.status_code == 409
    assert model.seen == []


async def test_forged_scorer_version_and_invalid_cases_are_rejected(client, logged_in_headers, evaluation):
    suite, _, _, config, _, _ = evaluation
    bad = deepcopy(config)
    bad["scorer"].update(version_id=str(uuid4()), revision="0" * 64)
    response = await client.patch(f"/api/v1/projects/{suite}", headers=logged_in_headers, json={"project_config": bad})
    assert response.status_code == 422, response.text
    bad = deepcopy(config)
    bad["cases"] *= 2
    response = await client.patch(f"/api/v1/projects/{suite}", headers=logged_in_headers, json={"project_config": bad})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    ("outcome", "failure"),
    [
        ("unsupported", "claims_not_supported"),
        ("violation", "policy_outcome_mismatch"),
        ("malformed", "scorer_execution_failed"),
    ],
)
async def test_actual_scorer_cannot_pass_unsupported_claims_policy_or_invalid_results(
    client,
    logged_in_headers,
    evaluation,
    outcome,
    failure,
):
    suite, _, scorer, config, _, _ = evaluation
    async with session_scope() as session:
        row = await session.get(Flow, UUID(scorer))
        data = deepcopy(row.data)
        judge = next(node for node in data["nodes"] if node["data"]["type"] == "FixtureJudge")
        judge["data"]["node"]["template"]["outcome"]["value"] = outcome
        row.data = data
        session.add(row)
    config["scorer"]["revision"] = flow_revision(data)
    await save_config(client, logged_in_headers, suite, config)
    response = await execute(client, logged_in_headers, suite)
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result["passed"]
    assert failure in result["result"]["cases"][0]["failures"]


async def test_timeout_leaves_incomplete_record_and_retry_does_not_execute(
    client,
    logged_in_headers,
    evaluation,
    monkeypatch,
):
    suite, _, _, _, _, model = evaluation
    monkeypatch.setattr("langflow.services.evaluations.runner.MAX_RUN_SECONDS", 0)
    run_id = uuid4()
    response = await execute(client, logged_in_headers, suite, run_id=run_id)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "timed_out"
    assert not response.json()["passed"]
    assert not response.json()["result"]["complete"]
    assert (await execute(client, logged_in_headers, suite, run_id=run_id)).json() == response.json()
    assert model.seen == []


async def test_evaluation_and_scorer_are_private(client, logged_in_headers, evaluation, user_two_api_key):
    suite, _, _, _, _, model = evaluation
    context = (await client.get(f"/api/v1/projects/{suite}/evaluations", headers=logged_in_headers)).json()
    client.cookies.clear()
    other_headers = {"x-api-key": user_two_api_key}
    url = f"/api/v1/projects/{suite}/evaluations"
    for path in (url, f"{url}/runs", f"{url}/runs/{uuid4()}"):
        assert (await client.get(path, headers=other_headers)).status_code == 404
    response = await client.post(
        f"{url}/runs",
        headers=other_headers,
        json={
            "run_id": str(uuid4()),
            "expected_revision": context["revision"],
            "expected_candidate_digest": context["config"]["candidate_digest"],
        },
    )
    assert response.status_code == 404
    assert model.seen == []


async def test_sourced_artifact_is_checked_against_actual_workflow_execution(
    client,
    logged_in_headers,
    evaluation,
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
):
    from lfx.components.files_and_knowledge.sourced_report import SourcedReportComponent

    suite, root, _, config, _, _ = evaluation
    project = workflow_harness[0]
    data = deepcopy((await stored_flow(root)).data)
    flow = {"data": data}
    for cls in (FixtureEvidence, SourcedReportComponent):
        component = cls()
        add_component(flow, component.name, {component.name: component.to_frontend_node()["data"]["node"]})
    evidence, report = data["nodes"][-2:]
    chat = next(node for node in data["nodes"] if node["data"]["type"] == "ChatInput")
    add_connection(flow, chat["id"], "message", evidence["id"], "query")
    add_connection(flow, evidence["id"], "report", report["id"], "report")
    add_connection(flow, evidence["id"], "source", report["id"], "sources")
    async with session_scope() as session:
        row = await session.get(Flow, UUID(root))
        row.data = data
        session.add(row)
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    config["candidate_digest"] = candidate.digest
    config["cases"][0]["require_sourced_artifact"] = True
    await save_config(client, logged_in_headers, suite, config)
    response = await execute(client, logged_in_headers, suite)
    assert response.status_code == 200, response.text
    assert response.json()["passed"], response.text


async def test_concurrent_submission_cannot_execute_same_run_twice(client, logged_in_headers, evaluation):
    suite, root, _, _, _, _ = evaluation
    run_id = uuid4()
    responses = await asyncio.gather(
        execute(client, logged_in_headers, suite, run_id=run_id),
        execute(client, logged_in_headers, suite, run_id=run_id),
    )
    assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
    assert {response.json()["id"] for response in responses} == {str(run_id)}
    async with session_scope() as session:
        jobs = (await session.exec(select(Job).where(Job.flow_id == UUID(root), Job.type == JobType.WORKFLOW))).all()
        assert len(jobs) == 1
    read = await client.get(f"/api/v1/projects/{suite}/evaluations/runs/{run_id}", headers=logged_in_headers)
    assert read.json()["passed"]


async def test_generic_archive_cannot_copy_unreviewed_eval_bindings(client, logged_in_headers, evaluation):
    suite = evaluation[0]
    exported = await client.get(f"/api/v1/projects/download/{suite}", headers=logged_in_headers)
    assert exported.status_code == 422
    assert "Eval Suite export" in exported.text
    imported = await client.post(
        "/api/v1/projects/upload/",
        headers=logged_in_headers,
        files={
            "file": (
                "suite.json",
                json.dumps(
                    {
                        "folder_name": "Imported eval",
                        "folder_project_type": "eval-suite",
                        "folder_project_config": evaluation[3],
                        "flows": [],
                    }
                ),
                "application/json",
            )
        },
    )
    assert imported.status_code == 422, imported.text
    assert "Eval Suite import" in imported.text


async def test_scaled_profile_rejects_evaluation_before_provider_execution(
    client, logged_in_headers, evaluation, monkeypatch
):
    suite, _, _, _, _, model = evaluation
    monkeypatch.setattr(get_settings_service().settings, "job_queue_type", "redis")
    response = await execute(client, logged_in_headers, suite)
    assert response.status_code == 422, response.text
    assert "in-process Workflows backend" in response.text
    assert model.seen == []
