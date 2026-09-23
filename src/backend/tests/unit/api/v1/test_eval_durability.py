"""Evaluation lifecycle through public APIs and real durable Workflows jobs."""

import asyncio
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_background_execution_service, get_settings_service, session_scope

from tests.unit.api.v1.test_eval_suites import evaluation  # noqa: F401
from tests.unit.api.v1.test_harness_skill_packs import skill_harness  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import save_config, stored_flow
from tests.unit.api.v2.test_workflow_candidates import mount
from tests.unit.api.v2.test_workflow_skills import provider, workflow_harness  # noqa: F401

pytestmark = pytest.mark.parametrize("client", ["sqlite", "postgres"], indirect=True)


async def submit(client, headers, suite, run_id=None):
    context = (await client.get(f"/api/v1/projects/{suite}/evaluations", headers=headers)).json()
    response = await client.post(
        f"/api/v1/projects/{suite}/evaluations/runs",
        headers=headers,
        json={
            "run_id": str(run_id or uuid4()),
            "expected_revision": context["revision"],
            "expected_candidate_digest": context["config"]["candidate_digest"],
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


async def wait_run(client, headers, suite, run_id, statuses, *, completed_cases=0):
    for _ in range(300):
        response = await client.get(f"/api/v1/projects/{suite}/evaluations/runs/{run_id}", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in statuses and len(payload["result"]["cases"]) >= completed_cases:
            return payload
        if payload["status"] in {"failed", "cancelled", "timed_out"}:
            pytest.fail(f"Unexpected terminal evaluation: {payload}")
        await asyncio.sleep(0.05)
    pytest.fail(f"Evaluation did not advance: {payload}")


@pytest.mark.parametrize("change", ["prune", "revoke_scorer", "revoke_dependency"])
async def test_accepted_evaluation_uses_retained_scorer_but_checks_current_access(
    client,
    logged_in_headers,
    created_api_key,
    active_user,
    user_two,
    evaluation,  # noqa: F811
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
    change,
):
    from langflow.services.database.models.flow_version.crud import create_flow_version_entry
    from langflow.services.database.models.flow_version.model import FlowVersion
    from lfx.components.flow_controls.run_flow import RunFlowComponent
    from lfx.graph.flow_builder import add_component

    from tests.unit.api.v1.test_project_config_write_through import create_flow, echo_flow_data

    suite, root, scorer, config, _, _ = evaluation
    project, _, _, _, harness_config, _ = workflow_harness
    await save_config(client, logged_in_headers, project, {**harness_config, "tool_policy": "ask"})
    provider(monkeypatch, await stored_flow(root), probe_scope=False)
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    # Even a declared dependency outside the selected output must remain authorized.
    dependency = await create_flow(active_user, folder_id=suite, data=echo_flow_data(), name="Scorer helper")
    nested = RunFlowComponent().to_frontend_node()["data"]["node"]
    nested["template"]["flow_id_selected"]["value"] = dependency
    async with session_scope() as session:
        row = await session.get(Flow, UUID(scorer))
        graph = {"data": deepcopy(row.data)}
        add_component(graph, "RunFlow", {"RunFlow": nested})
        row.data = graph["data"]
        session.add(row)
    context = (await client.get(f"/api/v1/projects/{suite}/evaluations", headers=logged_in_headers)).json()
    choice = next(item for item in context["scorers"] if item["flow_id"] == scorer)
    config["scorer"] = {key: value for key, value in choice.items() if key not in {"flow_name", "display_name"}}
    config["candidate_digest"] = candidate.digest
    config = (await save_config(client, logged_in_headers, suite, config))["project_config"]
    assert config["scorer"]["dependencies"][0]["flow_id"] == dependency
    run = await submit(client, logged_in_headers, suite)
    paused = await wait_run(client, logged_in_headers, suite, run["id"], {"suspended"})
    pending = paused["pending_approval"]
    assert pending["phase"] == "candidate"

    if change == "prune":
        monkeypatch.setattr(get_settings_service().settings, "max_flow_version_entries_per_flow", 1)
        async with session_scope() as session:
            for flow_id in (scorer, dependency):
                row = await session.get(Flow, UUID(flow_id))
                await create_flow_version_entry(session, row.id, row.user_id, {"nodes": [], "edges": []})
        async with session_scope() as session:
            for binding in [config["scorer"], *config["scorer"]["dependencies"]]:
                assert await session.get(FlowVersion, UUID(binding["version_id"])) is None
    else:
        async with session_scope() as session:
            row = await session.get(Flow, UUID(scorer if change == "revoke_scorer" else dependency))
            row.user_id = user_two.id
            session.add(row)
    response = await client.post(
        f"/api/v2/workflows/{pending['job_id']}/resume",
        headers={"x-api-key": created_api_key.api_key},
        json={"request_id": pending["request"]["request_id"], "decision": {"action_id": "approve"}},
    )
    assert response.status_code == 200, response.text
    finished = await wait_run(
        client, logged_in_headers, suite, run["id"], {"completed" if change == "prune" else "failed"}
    )
    assert finished["scorer_digest"] == paused["scorer_digest"]
    if change == "prune":
        assert finished["passed"], finished
        assert len(finished["result"]["cases"]) == 1
    else:
        assert not finished["passed"]
        assert not finished["result"]["complete"]
        assert not finished["result"]["cases"]


@pytest.mark.parametrize("restart", ["services", "process"])
async def test_evaluation_resumes_after_restart_with_original_candidate_and_scorer(
    client,
    logged_in_headers,
    created_api_key,
    evaluation,  # noqa: F811
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
    restart,
):
    from langflow.api.v2.workflow import _default_frame_source_factory
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.checkpoint.store import JobScopedCheckpointStore
    from langflow.services.jobs.service import JobService
    from langflow.services.schema import ServiceType
    from lfx.services.manager import get_service_manager

    suite, root, scorer, config, _, _ = evaluation
    project, _, _, _, harness_config, _ = workflow_harness
    await save_config(client, logged_in_headers, project, {**harness_config, "tool_policy": "ask"})
    model = provider(monkeypatch, await stored_flow(root), probe_scope=False)
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    config["candidate_digest"] = candidate.digest
    if restart == "process":
        config["cases"].append({**config["cases"][0], "id": "follow-up", "name": "Follow-up research"})
    await save_config(client, logged_in_headers, suite, config)
    run = await submit(client, logged_in_headers, suite)
    paused = await wait_run(client, logged_in_headers, suite, run["id"], {"suspended"})
    if restart == "process":
        first = paused["pending_approval"]
        response = await client.post(
            f"/api/v2/workflows/{first['job_id']}/resume",
            headers={"x-api-key": created_api_key.api_key},
            json={"request_id": first["request"]["request_id"], "decision": {"action_id": "approve"}},
        )
        assert response.status_code == 200, response.text
        paused = await wait_run(client, logged_in_headers, suite, run["id"], {"suspended"}, completed_cases=1)
        assert paused["result"]["cases"][0]["passed"]
    assert not paused["passed"]
    pending = paused["pending_approval"]
    assert pending["phase"] == "candidate"

    # The frozen target AND reviewed scorer must survive later authoring edits.
    async with session_scope() as session:
        for flow_id in (root, scorer):
            row = await session.get(Flow, UUID(flow_id))
            row.data = {"nodes": [], "edges": []}
            session.add(row)
    changed = deepcopy(config)
    changed["cases"][0]["reference"] = "NEW RUBRIC THAT MUST NOT BE USED"
    await save_config(client, logged_in_headers, suite, changed)
    retry = await client.post(
        f"/api/v1/projects/{suite}/evaluations/runs",
        headers=logged_in_headers,
        json={
            "run_id": run["id"],
            "expected_revision": run["suite_revision"],
            "expected_candidate_digest": candidate.digest,
        },
    )
    assert retry.status_code == 202, retry.text
    assert retry.json()["id"] == run["id"]
    (tmp_path / f"{candidate.digest}.lfpkg").unlink()
    await get_background_execution_service().stop()
    if restart == "process":
        import json
        import os
        import sys
        from pathlib import Path

        from langflow.services.deps import get_db_service

        env = {
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[4]),
            "LANGFLOW_DATABASE_URL": get_db_service().database_url,
            "LANGFLOW_SECRET_KEY": get_settings_service().auth_settings.SECRET_KEY.get_secret_value(),
            "LANGFLOW_HARNESS_CANDIDATE_MOUNTS": "{}",
            "LANGFLOW_DEVELOPER_API_ENABLED": "true",
            "EVAL_TEST_SUITE": suite,
            "EVAL_TEST_RUN": run["id"],
            "EVAL_TEST_PENDING": json.dumps(pending),
            "EVAL_TEST_SKILL": model.skill_key,
            "EVAL_TEST_API_KEY": created_api_key.api_key,
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "tests.unit.api.v1._eval_restart_probe",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=90)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise
        assert process.returncode == 0, output.decode()[-10000:]
        assert b"EVALUATION_PROCESS_RESTART_OK" in output
        finished = await wait_run(client, logged_in_headers, suite, run["id"], {"completed"})
        assert finished["result"]["cases"][0] == paused["result"]["cases"][0]
        assert finished["candidate_digest"] == candidate.digest
        assert finished["scorer_digest"] == paused["scorer_digest"]
        return
    jobs = JobService()
    service = BackgroundExecutionService(get_settings_service(), frame_source_factory=_default_frame_source_factory)
    manager = get_service_manager()
    monkeypatch.setitem(manager.services, ServiceType.JOB_SERVICE, jobs)
    monkeypatch.setitem(manager.services, "checkpoint_service", JobScopedCheckpointStore(jobs))
    monkeypatch.setitem(manager.services, ServiceType.BACKGROUND_EXECUTION_SERVICE, service)
    try:
        await service.sweep_orphans_on_startup()
        headers = {"x-api-key": created_api_key.api_key}
        decision = {"request_id": pending["request"]["request_id"], "decision": {"action_id": "approve"}}
        response = await client.post(f"/api/v2/workflows/{pending['job_id']}/resume", headers=headers, json=decision)
        assert response.status_code == 200, response.text
        finished = await wait_run(client, logged_in_headers, suite, run["id"], {"completed"})
        assert finished["passed"], finished
        assert finished["candidate_digest"] == candidate.digest
        assert finished["scorer_digest"] == paused["scorer_digest"]
        assert finished["result"]["cases"][0]["workflow_job_id"] == pending["job_id"]
        duplicate = await client.post(f"/api/v2/workflows/{pending['job_id']}/resume", headers=headers, json=decision)
        assert duplicate.status_code == 409
    finally:
        await service.stop()


async def test_cancel_suspended_evaluation_stops_child_and_cannot_resume(
    client,
    logged_in_headers,
    created_api_key,
    evaluation,  # noqa: F811
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
    user_two_api_key,
):
    suite, root, _, config, _, _ = evaluation
    project, _, _, _, harness_config, _ = workflow_harness
    await save_config(client, logged_in_headers, project, {**harness_config, "tool_policy": "ask"})
    model = provider(monkeypatch, await stored_flow(root), probe_scope=False)
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    await save_config(client, logged_in_headers, suite, {**config, "candidate_digest": candidate.digest})
    run = await submit(client, logged_in_headers, suite)
    paused = await wait_run(client, logged_in_headers, suite, run["id"], {"suspended"})
    pending = paused["pending_approval"]
    calls = len(model.seen)
    client.cookies.clear()
    foreign = {"x-api-key": user_two_api_key}
    url = f"/api/v1/projects/{suite}/evaluations/runs/{run['id']}"
    assert (await client.get(url, headers=foreign)).status_code == 404
    assert (await client.post(f"{url}/cancel", headers=foreign)).status_code == 404
    assert (
        await client.post(
            f"/api/v2/workflows/{pending['job_id']}/resume",
            headers=foreign,
            json={"request_id": pending["request"]["request_id"], "decision": {"action_id": "approve"}},
        )
    ).status_code == 404
    response = await client.post(
        f"/api/v1/projects/{suite}/evaluations/runs/{run['id']}/cancel", headers=logged_in_headers
    )
    assert response.status_code == 202, response.text
    cancelled = await wait_run(client, logged_in_headers, suite, run["id"], {"cancelled"})
    assert not cancelled["passed"]
    assert not cancelled["result"]["complete"]
    assert cancelled["pending_approval"] is None
    response = await client.post(
        f"/api/v2/workflows/{pending['job_id']}/resume",
        headers={"x-api-key": created_api_key.api_key},
        json={"request_id": pending["request"]["request_id"], "decision": {"action_id": "approve"}},
    )
    assert response.status_code == 409
    again = await submit(client, logged_in_headers, suite, run_id=run["id"])
    assert again == cancelled
    assert len(model.seen) == calls


async def test_interrupted_workflow_is_not_replayed_after_recovery(
    client,
    logged_in_headers,
    evaluation,  # noqa: F811
    monkeypatch,
):
    from langflow.api.v2.workflow import _default_frame_source_factory
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.schema import ServiceType
    from lfx.services.manager import get_service_manager

    suite, _, _, _, _, model = evaluation
    entered = asyncio.Event()
    attempts = []

    async def blocked_provider(self, *args, **kwargs):  # noqa: ARG001
        attempts.append(1)
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(type(model), "_agenerate", blocked_provider)
    run = await submit(client, logged_in_headers, suite)
    await asyncio.wait_for(entered.wait(), timeout=15)
    await get_background_execution_service().stop()
    service = BackgroundExecutionService(get_settings_service(), frame_source_factory=_default_frame_source_factory)
    monkeypatch.setitem(get_service_manager().services, ServiceType.BACKGROUND_EXECUTION_SERVICE, service)
    try:
        await service.sweep_orphans_on_startup()
        failed = await wait_run(client, logged_in_headers, suite, run["id"], {"failed"})
        assert failed["error"] == "workflow_interrupted"
        assert not failed["passed"]
        assert not failed["result"]["complete"]
        assert (await submit(client, logged_in_headers, suite, run["id"])) == failed
        assert len(attempts) == 1
    finally:
        await service.stop()


async def test_recovering_queued_evaluation_does_not_execute_it_twice(
    client,
    logged_in_headers,
    evaluation,  # noqa: F811
    monkeypatch,
):
    from langflow.api.v2.workflow import _default_frame_source_factory
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.schema import ServiceType
    from lfx.services.manager import get_service_manager

    suite, root, _, _, _, _ = evaluation
    model = provider(monkeypatch, await stored_flow(root), probe_scope=False)
    await get_background_execution_service().stop()
    monkeypatch.setattr(get_settings_service().settings, "background_max_concurrency", 1)
    owner = BackgroundExecutionService(get_settings_service(), frame_source_factory=_default_frame_source_factory)
    peer = BackgroundExecutionService(get_settings_service())
    monkeypatch.setitem(get_service_manager().services, ServiceType.BACKGROUND_EXECUTION_SERVICE, owner)
    entered, release = asyncio.Event(), asyncio.Event()
    original = type(model)._agenerate
    attempts = []

    async def gated_provider(self, *args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            entered.set()
            await release.wait()
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(type(model), "_agenerate", gated_provider)
    try:
        first = await submit(client, logged_in_headers, suite)
        await asyncio.wait_for(entered.wait(), timeout=15)
        second = await submit(client, logged_in_headers, suite)
        queued = await wait_run(client, logged_in_headers, suite, second["id"], {"in_progress"})
        assert queued["result"]["current"]["phase"] == "candidate"
        # A second application starts while the first still has this job in its local queue.
        await peer.sweep_orphans_on_startup()
        from tests.unit.api.v2.test_workflow_skills import wait_status

        await wait_status(client, logged_in_headers, queued["result"]["current"]["job_id"], {"completed"})
        release.set()
        assert (await wait_run(client, logged_in_headers, suite, second["id"], {"completed"}))["passed"]
        assert (await wait_run(client, logged_in_headers, suite, first["id"], {"completed"}))["passed"]
        # Each scripted research run needs three model turns: activate, tool, final answer.
        assert len(attempts) == 6
    finally:
        release.set()
        await peer.stop()
        await owner.stop()


async def test_scorer_can_pause_and_resume_with_the_original_recorded_response(
    client,
    logged_in_headers,
    created_api_key,
    evaluation,  # noqa: F811
):
    from lfx.components.flow_controls.human_input import HumanInput
    from lfx.graph.flow_builder import add_component, add_connection
    from lfx.projects.bindings import flow_revision

    suite, _, scorer, config, _, model = evaluation
    data = deepcopy((await stored_flow(scorer)).data)
    judge = next(node for node in data["nodes"] if node["data"]["type"] == "FixtureJudge")
    gate = HumanInput()
    gate.set(prompt="Review the evaluation before scoring.")
    flow = {"data": data}
    add_component(flow, gate.name, {gate.name: gate.to_frontend_node()["data"]["node"]})
    add_connection(flow, data["nodes"][-1]["id"], "branch_approve", judge["id"], "approval")
    async with session_scope() as session:
        row = await session.get(Flow, UUID(scorer))
        row.data = data
        session.add(row)
    config["scorer"]["revision"] = flow_revision(data)
    await save_config(client, logged_in_headers, suite, config)
    run = await submit(client, logged_in_headers, suite)
    paused = await wait_run(client, logged_in_headers, suite, run["id"], {"suspended"})
    pending = paused["pending_approval"]
    assert pending["phase"] == "scorer"
    calls = len(model.seen)
    response = await client.post(
        f"/api/v2/workflows/{pending['job_id']}/resume",
        headers={"x-api-key": created_api_key.api_key},
        json={"request_id": pending["request"]["request_id"], "decision": {"action_id": "approve"}},
    )
    assert response.status_code == 200, response.text
    finished = await wait_run(client, logged_in_headers, suite, run["id"], {"completed"})
    assert finished["passed"], finished
    assert finished["result"]["cases"][0]["scorer_job_id"] == pending["job_id"]
    assert len(model.seen) == calls
