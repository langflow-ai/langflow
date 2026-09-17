"""Eval APIs use the database queue with competing coordinators and workers."""

# Pytest fixtures are imported from the existing evaluation scenario modules.
# ruff: noqa: F811

import asyncio

import pytest
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.background_execution.worker import build_worker, run_worker_loop
from langflow.services.deps import get_background_execution_service, get_settings_service
from langflow.services.schema import ServiceType
from lfx.services.manager import get_service_manager

from tests.unit.api.v1.test_eval_durability import (
    submit,
    wait_run,
)
from tests.unit.api.v1.test_eval_durability import (
    test_cancel_suspended_evaluation_stops_child_and_cannot_resume as assert_cancel_suspended,
)
from tests.unit.api.v1.test_eval_durability import (
    test_scorer_can_pause_and_resume_with_the_original_recorded_response as assert_scorer_resume,
)
from tests.unit.api.v1.test_eval_suites import evaluation  # noqa: F401
from tests.unit.api.v1.test_harness_skill_packs import skill_harness  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import save_config, stored_flow
from tests.unit.api.v2.test_workflow_candidates import mount
from tests.unit.api.v2.test_workflow_skills import provider, workflow_harness  # noqa: F401

pytestmark = pytest.mark.parametrize("client", ["sqlite", "postgres"], indirect=True)


@pytest.fixture
async def scaled_api(client, monkeypatch):  # noqa: ARG001
    await get_background_execution_service().stop()
    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "background_backend", "scaled")
    services = [BackgroundExecutionService(settings), BackgroundExecutionService(settings)]
    monkeypatch.setitem(get_service_manager().services, ServiceType.BACKGROUND_EXECUTION_SERVICE, services[0])
    try:
        for service in services:
            await service.start()
        yield services
    finally:
        for service in services:
            await service.stop()


@pytest.fixture
async def scaled(scaled_api):
    stopping = asyncio.Event()
    workers = []
    try:
        for index in range(2):
            backend, runner, _ = await build_worker(owner=f"eval-test:{index}")
            workers.append(asyncio.create_task(run_worker_loop(backend, runner, stop_event=stopping, idle_block_ms=20)))
        yield scaled_api
    finally:
        stopping.set()
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


async def test_scaled_evaluation_runs_candidate_and_scorer_once(
    client,
    logged_in_headers,
    evaluation,
    scaled,  # noqa: ARG001
    monkeypatch,
):
    suite, root, _, _, candidate, _ = evaluation
    model = provider(monkeypatch, await stored_flow(root), probe_scope=False)
    run = await submit(client, logged_in_headers, suite)
    finished = await wait_run(client, logged_in_headers, suite, run["id"], {"completed"})
    assert finished["passed"], finished
    assert finished["candidate_digest"] == candidate.digest
    assert len(finished["result"]["cases"]) == 1
    assert await submit(client, logged_in_headers, suite, run_id=run["id"]) == finished
    assert len(model.seen) == 3  # Activate skill, use its tool, return the sourced answer.


@pytest.mark.parametrize("limit", ["evaluation", "host"])
async def test_scaled_evaluation_execution_ceiling_is_enforced(
    client,
    logged_in_headers,
    evaluation,
    scaled,  # noqa: ARG001
    monkeypatch,
    limit,
):
    suite, _, _, _, _, model = evaluation
    monkeypatch.setattr("langflow.services.evaluations.runner.MAX_RUN_SECONDS", 0.2 if limit == "evaluation" else 300)
    monkeypatch.setattr(get_settings_service().settings, "background_job_timeout", 0.2 if limit == "host" else None)

    async def blocked_provider(self, *args, **kwargs):  # noqa: ARG001
        await asyncio.Event().wait()

    monkeypatch.setattr(type(model), "_agenerate", blocked_provider)
    run = await submit(client, logged_in_headers, suite)
    finished = await wait_run(client, logged_in_headers, suite, run["id"], {"timed_out"})
    assert not finished["passed"]
    assert not finished["result"]["complete"]
    assert finished["error"] == "workflow_timed_out"


async def test_scaled_scorer_approval(client, logged_in_headers, created_api_key, evaluation, scaled):  # noqa: ARG001
    await assert_scorer_resume(client, logged_in_headers, created_api_key, evaluation)


async def test_scaled_cancel_is_private_and_stops_suspended_child(
    client,
    logged_in_headers,
    created_api_key,
    evaluation,
    workflow_harness,
    scaled,  # noqa: ARG001
    monkeypatch,
    tmp_path,
    user_two_api_key,
):
    await assert_cancel_suspended(
        client,
        logged_in_headers,
        created_api_key,
        evaluation,
        workflow_harness,
        monkeypatch,
        tmp_path,
        user_two_api_key,
    )


async def test_scaled_human_input_deadline_is_enforced(
    client,
    logged_in_headers,
    evaluation,
    workflow_harness,
    scaled,
    monkeypatch,
    tmp_path,
):
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "background_input_deadline_s", 0.2)
    monkeypatch.setattr(settings, "background_watchdog_interval_s", 0.05)
    for service in scaled:
        await service.stop()
        await service.start()
    suite, root, _, config, _, _ = evaluation
    project, _, _, _, harness_config, _ = workflow_harness
    await save_config(client, logged_in_headers, project, {**harness_config, "tool_policy": "ask"})
    provider(monkeypatch, await stored_flow(root), probe_scope=False)
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    await save_config(client, logged_in_headers, suite, {**config, "candidate_digest": candidate.digest})
    run = await submit(client, logged_in_headers, suite)
    finished = await wait_run(client, logged_in_headers, suite, run["id"], {"failed"})
    assert not finished["passed"]
    assert not finished["result"]["complete"]
    assert finished["error"] == "workflow_failed"
