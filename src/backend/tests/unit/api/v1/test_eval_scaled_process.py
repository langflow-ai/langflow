"""Frozen evaluations survive API/worker replacement over the shared database."""

# Pytest fixtures are imported from the existing evaluation scenario modules.
# ruff: noqa: F811

import asyncio
import os
import sys
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import pytest
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.services.schema import ServiceType
from lfx.services.manager import get_service_manager

from tests.unit.api.v1.test_eval_durability import submit, wait_run
from tests.unit.api.v1.test_eval_scaled import scaled_api  # noqa: F401
from tests.unit.api.v1.test_eval_suites import evaluation  # noqa: F401
from tests.unit.api.v1.test_harness_skill_packs import skill_harness  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import save_config, stored_flow
from tests.unit.api.v2.test_workflow_candidates import mount
from tests.unit.api.v2.test_workflow_skills import provider, workflow_harness  # noqa: F401

pytestmark = pytest.mark.parametrize("client", ["sqlite", "postgres"], indirect=True)


@pytest.fixture
async def worker_process(tmp_path):
    processes = []
    logs = []

    async def start(skill_key, *, block=False):
        log = (tmp_path / f"worker-{len(processes)}.log").open("wb")
        logs.append(log)
        env = {
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[4]),
            "LANGFLOW_DATABASE_URL": get_db_service().database_url,
            "LANGFLOW_CONFIG_DIR": str(tmp_path / f"worker-{len(processes)}"),
            "LANGFLOW_SECRET_KEY": get_settings_service().auth_settings.SECRET_KEY.get_secret_value(),
            "LANGFLOW_BACKGROUND_BACKEND": "scaled",
            "LANGFLOW_BACKGROUND_LEASE_TTL_S": "2",
            "LANGFLOW_BACKGROUND_HEARTBEAT_INTERVAL_S": "0.2",
            "LANGFLOW_BACKGROUND_WATCHDOG_INTERVAL_S": "0.2",
            "LANGFLOW_HARNESS_CANDIDATE_MOUNTS": "{}",
            "LANGFLOW_DEVELOPER_API_ENABLED": "true",
            "LANGFLOW_UPDATE_STARTER_PROJECTS": "false",
            "EVAL_TEST_SKILL": skill_key,
            "EVAL_WORKER_TURNS_FILE": str(tmp_path / "provider-turns.txt"),
            "EVAL_WORKER_BLOCK": "true" if block else "false",
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "tests.unit.api.v1._eval_worker_probe", env=env, stdout=log, stderr=log
        )
        processes.append(process)
        return process

    try:
        yield start
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), timeout=10)
        for log in logs:
            log.close()
            # Captured by pytest; exposed only on failure.
            print(Path(log.name).read_text()[-5000:])  # noqa: T201


async def test_frozen_evaluation_resumes_on_new_api_and_worker(
    client,
    logged_in_headers,
    created_api_key,
    evaluation,
    workflow_harness,
    scaled_api,
    worker_process,
    monkeypatch,
    tmp_path,
):
    suite, root, scorer, config, _, _ = evaluation
    project, _, _, _, harness_config, _ = workflow_harness
    await save_config(client, logged_in_headers, project, {**harness_config, "tool_policy": "ask"})
    model = provider(monkeypatch, await stored_flow(root), probe_scope=False)
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    config["candidate_digest"] = candidate.digest
    config["cases"].append({**config["cases"][0], "id": "follow-up", "name": "Follow-up research"})
    await save_config(client, logged_in_headers, suite, config)
    run = await submit(client, logged_in_headers, suite)
    process = await worker_process(model.skill_key)
    paused = await wait_run(client, logged_in_headers, suite, run["id"], {"suspended"})
    first = paused["pending_approval"]
    headers = {"x-api-key": created_api_key.api_key}
    response = await client.post(
        f"/api/v2/workflows/{first['job_id']}/resume",
        headers=headers,
        json={"request_id": first["request"]["request_id"], "decision": {"action_id": "approve"}},
    )
    assert response.status_code == 200, response.text
    paused = await wait_run(client, logged_in_headers, suite, run["id"], {"suspended"}, completed_cases=1)
    process.kill()
    await process.wait()
    for service in scaled_api:
        await service.stop()

    # The replacement process has no source mount and must use the retained bytes.
    async with session_scope() as session:
        for flow_id in (root, scorer):
            row = await session.get(Flow, UUID(flow_id))
            row.data = {"nodes": [], "edges": []}
            session.add(row)
    changed = deepcopy(config)
    changed["cases"][0]["reference"] = "DO NOT USE THIS NEW RUBRIC"
    await save_config(client, logged_in_headers, suite, changed)
    (tmp_path / f"{candidate.digest}.lfpkg").unlink()
    monkeypatch.setattr(get_settings_service().settings, "harness_candidate_mounts", {})
    replacement = BackgroundExecutionService(get_settings_service())
    scaled_api.append(replacement)
    monkeypatch.setitem(get_service_manager().services, ServiceType.BACKGROUND_EXECUTION_SERVICE, replacement)
    await replacement.sweep_orphans_on_startup()
    await worker_process(model.skill_key)
    pending = paused["pending_approval"]
    decision = {"request_id": pending["request"]["request_id"], "decision": {"action_id": "approve"}}
    response = await client.post(f"/api/v2/workflows/{pending['job_id']}/resume", headers=headers, json=decision)
    assert response.status_code == 200, response.text
    assert (
        await client.post(f"/api/v2/workflows/{pending['job_id']}/resume", headers=headers, json=decision)
    ).status_code == 409
    finished = await wait_run(client, logged_in_headers, suite, run["id"], {"completed"})
    assert finished["passed"], finished
    assert finished["result"]["cases"][0] == paused["result"]["cases"][0]
    assert finished["result"]["cases"][1]["workflow_job_id"] == pending["job_id"]
    assert finished["candidate_digest"] == candidate.digest
    assert finished["scorer_digest"] == paused["scorer_digest"]
    assert len((tmp_path / "provider-turns.txt").read_text().splitlines()) == 6
    assert model.seen == []  # All model calls happened outside the API process.


async def test_killed_worker_fails_evaluation_without_replaying_provider(
    client,
    logged_in_headers,
    evaluation,
    scaled_api,  # noqa: ARG001
    worker_process,
    tmp_path,
):
    suite, _, _, _, _, model = evaluation
    run = await submit(client, logged_in_headers, suite)
    process = await worker_process(model.skill_key, block=True)
    turns = tmp_path / "provider-turns.txt"
    async with asyncio.timeout(30):
        while not turns.exists():
            assert process.returncode is None, "Worker exited before provider execution"
            await asyncio.sleep(0.05)
    active = await wait_run(client, logged_in_headers, suite, run["id"], {"in_progress"})
    child_id = active["result"]["current"]["job_id"]
    process.kill()
    await process.wait()
    # A new real worker watchdog reconciles the stale lease. It must not retry
    # an in-flight provider/tool call whose effects may already have happened.
    await worker_process(model.skill_key)
    failed = await wait_run(client, logged_in_headers, suite, run["id"], {"failed"})
    assert failed["error"] == "workflow_interrupted"
    assert not failed["passed"]
    assert not failed["result"]["complete"]
    assert len(turns.read_text().splitlines()) == 1
    response = await client.get("/api/v2/workflows", params={"job_id": child_id}, headers=logged_in_headers)
    assert response.status_code == 500, response.text
    assert response.json()["detail"]["error_detail"] == {"type": "worker_lost"}
