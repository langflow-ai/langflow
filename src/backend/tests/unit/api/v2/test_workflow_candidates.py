"""Real Workflows API, durable jobs and graph reconstruction for mounted candidates."""

import json
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import ToolMessage
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import (
    get_background_execution_service,
    get_job_service,
    get_settings_service,
    session_scope,
)
from lfx.projects.runtime_artifacts import read_candidate
from lfx.services.settings.groups.runtime import HarnessCandidateMount

from tests.unit.api.v1.test_harness_skill_packs import skill_harness  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import save_config, stored_flow
from tests.unit.api.v2.test_workflow_skills import provider, wait_status, workflow_harness  # noqa: F401


async def mount(client, headers, project, root, monkeypatch, tmp_path, *, customizations=False):
    response = await client.get(f"/api/v1/projects/{project}/harness-artifact", headers=headers)
    assert response.status_code == 200, response.text
    candidate = read_candidate(response.content)
    if customizations:
        candidate = with_customizations(candidate, root)
    path = tmp_path / f"{candidate.digest}.lfpkg"
    path.write_bytes(candidate.archive())
    monkeypatch.setattr(
        get_settings_service().settings,
        "harness_candidate_mounts",
        {UUID(root): HarnessCandidateMount(path=path, digest=candidate.digest)},
    )
    monkeypatch.setenv("OPENAI_API_KEY", "candidate-test-key")
    return candidate


def with_customizations(candidate, root):
    from lfx.base.agents.hooks import HookBinding
    from lfx.projects.baselines import build_slot_baseline
    from lfx.projects.bindings import FlowBinding, compose_instructions, flow_revision, instruction_outputs
    from lfx.projects.context import ContextBinding, context_outputs
    from lfx.projects.hooks import hook_outputs
    from lfx.projects.runtime_artifacts import build_candidate

    definitions = dict(candidate.definitions)
    entry = definitions[root]
    for slot, choices, cls, input_name in (
        ("instructions", instruction_outputs, FlowBinding, "system_prompt"),
        ("hook", hook_outputs, HookBinding, "hook_bindings"),
        ("context", context_outputs, ContextBinding, "context_binding"),
    ):
        baseline = build_slot_baseline(f"builtin:{slot}", "Candidate instructions: cite original evidence.")
        baseline["id"] = str(uuid4())
        output = choices(baseline["data"])[0]
        binding = cls(
            flow_id=baseline["id"],
            node_id=output["node_id"],
            output_name=output["output_name"],
            revision=flow_revision(baseline["data"]),
            **({"on_event": "before_llm_call"} if slot == "hook" else {}),
        )
        if slot == "instructions":
            entry["data"] = compose_instructions(
                entry["data"], project_id=str(uuid4()), agent_id="Agent-1", target=baseline, binding=binding
            )
        else:
            template = next(n for n in entry["data"]["nodes"] if n["id"] == "Agent-1")["data"]["node"]["template"]
            template[input_name]["value"] = json.dumps(
                [binding.model_dump()] if slot == "hook" else binding.model_dump()
            )
        definitions[baseline["id"]] = baseline
    revisions = {item["id"]: item["source_revision"] for item in candidate.manifest["flows"]}
    revisions[root] = flow_revision(entry["data"])
    return build_candidate(
        root, list(definitions.values()), source_revisions=revisions, packages=candidate.manifest["runtime"]["packages"]
    )


@pytest.mark.parametrize(("mode", "protocol"), [("sync", "langflow"), ("stream", "langflow"), ("stream", "agui")])
async def test_mounted_candidate_ignores_draft_and_preserves_scope(
    client,
    logged_in_headers,
    created_api_key,
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
    mode,
    protocol,
):
    project, root, *_ = workflow_harness
    model = provider(monkeypatch, await stored_flow(root))
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    async with session_scope() as session:
        for identity in candidate.definitions:
            row = await session.get(Flow, UUID(identity))
            row.data = {"nodes": [], "edges": []}
            session.add(row)
        await session.commit()
    for _ in range(2):
        response = await client.post(
            "/api/v2/workflows",
            headers={"x-api-key": created_api_key.api_key},
            json={
                "flow_id": root,
                "input_value": "Research",
                "session_id": str(uuid4()),
                "mode": mode,
                "stream_protocol": protocol,
            },
        )
        assert response.status_code == 200, response.text
        assert "Research complete" in response.text, response.text
        results = [m for m in model.seen[-1] if isinstance(m, ToolMessage) and m.name == model.tool_name]
        assert [m.status for m in results] == ["error", "success", "error"]
        if mode == "stream":
            assert response.headers["x-langflow-candidate-digest"] == candidate.digest
        if mode == "sync":
            assert response.json()["candidate_digest"] == candidate.digest
            job = await get_job_service().get_job_by_job_id(UUID(response.json()["job_id"]))
            assert job.job_metadata["candidate_digest"] == candidate.digest


@pytest.mark.parametrize(
    ("decision", "restart"), [("approve", "services"), ("reject", "services"), ("approve", "process")]
)
async def test_candidate_retained_through_approval_and_service_restart(
    client,
    logged_in_headers,
    created_api_key,
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
    decision,
    restart,
):
    from langflow.api.v2.workflow import _default_frame_source_factory
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.checkpoint.store import JobScopedCheckpointStore
    from langflow.services.jobs.service import JobService
    from langflow.services.schema import ServiceType
    from lfx.services.manager import get_service_manager

    project, root, _, _, config, _ = workflow_harness
    await save_config(client, logged_in_headers, project, {**config, "tool_policy": "ask"})
    model = provider(monkeypatch, await stored_flow(root), probe_scope=False)
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path, customizations=True)
    headers = {"x-api-key": created_api_key.api_key}
    response = await client.post(
        "/api/v2/workflows",
        headers=headers,
        json={
            "flow_id": root,
            "input_value": "Research",
            "mode": "background",
            "session_id": str(uuid4()),
        },
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    await wait_status(client, headers, job_id, {"suspended"})
    job = await get_job_service().get_job_by_job_id(UUID(job_id))
    assert job.job_metadata["candidate_digest"] == candidate.digest
    request_id = job.job_metadata["pending_request_id"]
    checkpoint = json.loads(await get_job_service().load_checkpoint(UUID(job_id), "graph"))
    assert checkpoint["candidate_digest"] == candidate.digest

    # Change both the draft and the next-run selection; the paused run must use neither.
    async with session_scope() as session:
        row = await session.get(Flow, UUID(root))
        changed = deepcopy(row.data)
        agent = next(n for n in changed["nodes"] if n["id"] == "Agent-1")
        agent["data"]["node"]["template"]["system_prompt"]["value"] = "NEW DRAFT"
        row.data = changed
        session.add(row)
        await session.commit()
    newer = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    assert newer.digest != candidate.digest
    (tmp_path / f"{candidate.digest}.lfpkg").unlink()
    await get_background_execution_service().stop()
    if restart == "process":
        import asyncio
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
            "CANDIDATE_TEST_JOB": job_id,
            "CANDIDATE_TEST_REQUEST": request_id,
            "CANDIDATE_TEST_DIGEST": candidate.digest,
            "CANDIDATE_TEST_SKILL": model.skill_key,
            "CANDIDATE_TEST_API_KEY": created_api_key.api_key,
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "tests.unit.api.v2._candidate_restart_probe",
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
        assert b"CANDIDATE_PROCESS_RESTART_OK" in output
        return
    jobs = JobService()
    service = BackgroundExecutionService(get_settings_service(), frame_source_factory=_default_frame_source_factory)
    manager = get_service_manager()
    monkeypatch.setitem(manager.services, ServiceType.JOB_SERVICE, jobs)
    monkeypatch.setitem(manager.services, "checkpoint_service", JobScopedCheckpointStore(jobs))
    monkeypatch.setitem(manager.services, ServiceType.BACKGROUND_EXECUTION_SERVICE, service)
    try:
        await service.sweep_orphans_on_startup()
        stale = await client.post(
            f"/api/v2/workflows/{job_id}/resume",
            headers=headers,
            json={
                "request_id": "stale",
                "decision": {"action_id": decision},
            },
        )
        assert stale.status_code == 409
        resumed = await client.post(
            f"/api/v2/workflows/{job_id}/resume",
            headers=headers,
            json={
                "request_id": request_id,
                "decision": {"action_id": decision},
            },
        )
        assert resumed.status_code == 200, resumed.text
        result = await wait_status(client, headers, job_id, {"completed"})
        assert "Research complete" in json.dumps(result)
        results = [m for m in model.seen[-1] if isinstance(m, ToolMessage) and m.name == model.tool_name]
        assert len(results) == 1
        assert ("SOURCE RESULT" in results[0].content) == (decision == "approve")
        assert "NEW DRAFT" not in str(model.seen[-1])
        assert "Candidate instructions: cite original evidence." in str(model.seen[-1])
        duplicate = await client.post(
            f"/api/v2/workflows/{job_id}/resume",
            headers=headers,
            json={
                "request_id": request_id,
                "decision": {"action_id": decision},
            },
        )
        assert duplicate.status_code == 409
        replay = await client.get(f"/api/v2/workflows/{job_id}/events", headers=headers)
        assert replay.status_code == 200, replay.text
        assert "Research complete" in replay.text
    finally:
        await service.stop()


async def test_candidate_preflight_and_overrides_fail_before_provider(
    client,
    logged_in_headers,
    created_api_key,
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
):
    project, root, _, _, config, _ = workflow_harness
    model = provider(monkeypatch, await stored_flow(root))
    await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    headers = {"x-api-key": created_api_key.api_key}
    body = {"flow_id": root, "input_value": "Research", "mode": "sync"}
    for overrides in ({"tweaks": {"Agent-1": {"system_prompt": "different"}}}, {"data": {}}):
        response = await client.post("/api/v2/workflows", headers=headers, json={**body, **overrides})
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "HARNESS_CANDIDATE_OVERRIDES_UNSUPPORTED"
    selected = get_settings_service().settings.harness_candidate_mounts[UUID(root)]
    monkeypatch.setattr(selected, "digest", "0" * 64)
    response = await client.post("/api/v2/workflows", headers=headers, json=body)
    assert response.status_code == 409
    await save_config(client, logged_in_headers, project, {**config, "tool_policy": "ask"})
    await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    for mode in ("sync", "stream"):
        response = await client.post("/api/v2/workflows", headers=headers, json={**body, "mode": mode})
        assert response.status_code == 409
        assert "background" in response.text
    assert model.seen == []


async def test_candidate_pause_isolation_unavailable_bytes_and_stop(
    client,
    logged_in_headers,
    created_api_key,
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
):
    from langflow.services.deployment_artifacts.harness_runtime import CANDIDATE_KIND

    from tests.unit.api.v2.test_workflow_end_user_isolation import HEADER, _serving_on

    project, root, _, _, config, _ = workflow_harness
    await save_config(client, logged_in_headers, project, {**config, "tool_policy": "ask"})
    model = provider(monkeypatch, await stored_flow(root), probe_scope=False)
    await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    _serving_on(monkeypatch)
    headers = {"x-api-key": created_api_key.api_key, HEADER: "research-alice"}
    other = {**headers, HEADER: "research-bob"}
    response = await client.post(
        "/api/v2/workflows",
        headers=headers,
        json={
            "flow_id": root,
            "input_value": "Research",
            "mode": "background",
            "session_id": "research-isolation",
        },
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    await wait_status(client, headers, job_id, {"suspended"})
    jobs = get_job_service()
    job = await jobs.get_job_by_job_id(UUID(job_id))
    decision = {"request_id": job.job_metadata["pending_request_id"], "decision": {"action_id": "approve"}}
    for method, path, kwargs in (
        ("get", "/api/v2/workflows", {"params": {"job_id": job_id}}),
        ("get", f"/api/v2/workflows/{job_id}/events", {}),
        ("post", f"/api/v2/workflows/{job_id}/resume", {"json": decision}),
        ("post", "/api/v2/workflows/stop", {"json": {"job_id": job_id}}),
    ):
        refused = await getattr(client, method)(path, headers=other, **kwargs)
        assert refused.status_code == 404, refused.text
    provider_calls = len(model.seen)
    blob = await jobs.load_checkpoint(UUID(job_id), CANDIDATE_KIND)
    await jobs.delete_checkpoint(UUID(job_id), CANDIDATE_KIND)
    refused = await client.post(f"/api/v2/workflows/{job_id}/resume", headers=headers, json=decision)
    assert refused.status_code == 409, refused.text
    await jobs.save_checkpoint(UUID(job_id), CANDIDATE_KIND, "tampered")
    refused = await client.post(f"/api/v2/workflows/{job_id}/resume", headers=headers, json=decision)
    assert refused.status_code == 409, refused.text
    assert (await jobs.get_job_by_job_id(UUID(job_id))).status.value == "suspended"
    assert len(model.seen) == provider_calls
    await jobs.save_checkpoint(UUID(job_id), CANDIDATE_KIND, blob)
    selected = get_settings_service().settings.harness_candidate_mounts[UUID(root)]
    monkeypatch.setattr(selected, "enabled", False)
    refused = await client.post(f"/api/v2/workflows/{job_id}/resume", headers=headers, json=decision)
    assert refused.status_code == 409
    stopped = await client.post("/api/v2/workflows/stop", headers=headers, json={"job_id": job_id})
    assert stopped.status_code == 200, stopped.text
    await wait_status(client, headers, job_id, {"cancelled"})
    replay = await client.get(f"/api/v2/workflows/{job_id}/events", headers=headers)
    assert "cancel" in replay.text.lower()
    refused = await client.post(f"/api/v2/workflows/{job_id}/resume", headers=headers, json=decision)
    assert refused.status_code == 409


@pytest.mark.parametrize(("missing", "protocol"), [(False, "langflow"), (True, "agui")])
async def test_queued_candidate_recovers_without_mount_or_emits_terminal_error(
    client,
    logged_in_headers,
    created_api_key,
    workflow_harness,  # noqa: F811
    monkeypatch,
    tmp_path,
    missing,
    protocol,
):
    import asyncio

    from langflow.api.v2.workflow import _default_frame_source_factory
    from langflow.services.background_execution.executor import InProcessExecutor
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deployment_artifacts.harness_runtime import CANDIDATE_KIND
    from langflow.services.schema import ServiceType
    from lfx.services.manager import get_service_manager

    project, root, *_ = workflow_harness
    model = provider(monkeypatch, await stored_flow(root))
    candidate = await mount(client, logged_in_headers, project, root, monkeypatch, tmp_path)
    manager = get_service_manager()
    await get_background_execution_service().stop()
    original = BackgroundExecutionService(get_settings_service(), frame_source_factory=_default_frame_source_factory)
    original._executor = InProcessExecutor(max_concurrency=1)
    monkeypatch.setitem(manager.services, ServiceType.BACKGROUND_EXECUTION_SERVICE, original)
    await original.start()
    occupied = asyncio.Event()

    async def occupy_worker():
        occupied.set()
        await asyncio.Event().wait()

    await original._executor.submit("occupied", occupy_worker)
    await occupied.wait()
    headers = {"x-api-key": created_api_key.api_key}
    request = {
        "flow_id": root,
        "input_value": "Research",
        "mode": "background",
        "stream_protocol": protocol,
        "idempotency_key": str(uuid4()),
        "session_id": str(uuid4()),
    }
    response = await client.post("/api/v2/workflows", headers=headers, json=request)
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    duplicate = await client.post("/api/v2/workflows", headers=headers, json=request)
    assert duplicate.json()["job_id"] == job_id
    assert duplicate.json()["candidate_digest"] == candidate.digest
    conflict = await client.post("/api/v2/workflows", headers=headers, json={**request, "session_id": str(uuid4())})
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert job_id not in conflict.text
    await original.stop()
    (tmp_path / f"{candidate.digest}.lfpkg").unlink()
    monkeypatch.setattr(get_settings_service().settings, "harness_candidate_mounts", {})
    async with session_scope() as session:
        row = await session.get(Flow, UUID(root))
        row.data = {"nodes": [], "edges": []}
        session.add(row)
        await session.commit()
    if missing:
        await get_job_service().delete_checkpoint(UUID(job_id), CANDIDATE_KIND)
    recovered = BackgroundExecutionService(get_settings_service(), frame_source_factory=_default_frame_source_factory)
    monkeypatch.setitem(manager.services, ServiceType.BACKGROUND_EXECUTION_SERVICE, recovered)
    try:
        await recovered.start()
        await recovered.sweep_orphans_on_startup()
        async with asyncio.timeout(30):
            while True:
                job = await get_job_service().get_job_by_job_id(UUID(job_id))
                if job.status.value in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.1)
        assert job.status.value == ("failed" if missing else "completed")
        replay = await client.get(f"/api/v2/workflows/{job_id}/events", headers=headers)
        assert replay.status_code == 200, replay.text
        if missing:
            frames = [json.loads(line[6:]) for line in replay.text.splitlines() if line.startswith("data: ")]
            assert sum(frame.get("type") == "RUN_ERROR" for frame in frames) == 1
            assert "RUN_FINISHED" not in replay.text
            assert job.error is not None
            assert model.seen == []
        else:
            assert "Research complete" in replay.text
            assert "SOURCE RESULT" in str(model.seen[-1])
            response = await client.get("/api/v2/workflows", headers=headers, params={"job_id": job_id})
            assert response.json()["candidate_digest"] == candidate.digest
    finally:
        await recovered.stop()
