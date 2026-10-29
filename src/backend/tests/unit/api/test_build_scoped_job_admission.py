"""Legacy build queues persist and revalidate restricted-key admission."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException
from langflow.api import build
from langflow.events.event_manager import create_default_event_manager
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth import SSOUserProfile
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_job_service, get_settings_service, session_scope
from lfx.graph.exceptions import GraphPausedException
from lfx.services.model_provider_policy import current_model_provider_policy_context

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture(autouse=True)
def credential_context():
    clear_current_auth_context()
    yield
    clear_current_auth_context()


class HeldQueue:
    def __init__(self):
        self.job_id = None
        self.task_coro = None
        self.event_manager = create_default_event_manager(asyncio.Queue())

    def create_queue(self, job_id):
        self.job_id = job_id
        return self.event_manager.queue, self.event_manager

    def start_job(self, job_id, task_coro):
        assert self.job_id == job_id
        self.task_coro = task_coro

    def close(self):
        if self.task_coro is not None:
            self.task_coro.close()


async def seed_restricted_build(active_user, monkeypatch):
    policy = {"restrictions": [{"resource_type": "flow", "actions": ["read", "execute"]}]}

    async def enforce(**kwargs):
        return any(kwargs["act"] in item["actions"] for item in policy["restrictions"])

    authorization = SimpleNamespace(supports_api_key_scopes=AsyncMock(return_value=True), enforce=enforce)
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.get_authorization_service", lambda: authorization
    )
    monkeypatch.setattr("langflow.services.authorization.guards.get_authorization_service", lambda: authorization)
    async with session_scope() as session:
        flow = Flow(id=uuid4(), name="Scoped legacy build", user_id=active_user.id, data={"nodes": [], "edges": []})
        key = ApiKey(name="Scoped legacy build", api_key="not-a-real-key", user_id=active_user.id, permissions=policy)
        session.add_all([flow, key])
        await session.flush()
        key_id = key.id
    set_current_auth_context(
        AuthCredentialContext(
            method="api_key",
            api_key_id=key_id,
            api_key_source="db",  # pragma: allowlist secret
            api_key_restricted=True,
            api_key_permissions=policy,
        )
    )
    return flow, key_id


async def start_build(user, flow, queue, **kwargs):
    return await build.start_flow_build(
        flow_id=kwargs.pop("flow_id", flow.id),
        background_tasks=BackgroundTasks(),
        inputs=None,
        data=None,
        files=None,
        stop_component_id=None,
        start_component_id=None,
        log_builds=False,
        current_user=user,
        provider_policy_flow=flow,
        queue_service=queue,
        **kwargs,
    )


async def test_restricted_metadata_exists_before_queue_start_and_uses_real_flow(active_user, monkeypatch):
    flow, key_id = await seed_restricted_build(active_user, monkeypatch)
    service = get_job_service()
    real_create = service.create_job
    admitted = []

    async def create_job(*args, **kwargs):
        row = await real_create(*args, **kwargs)
        admitted.append(row)
        return row

    monkeypatch.setattr(service, "create_job", create_job)
    generate = AsyncMock()
    monkeypatch.setattr(build, "generate_flow_events", generate)

    class AdmissionQueue(HeldQueue):
        def start_job(self, job_id, task_coro):
            assert admitted, "The job and restricted-key provenance must commit before queue submission"
            assert admitted[0].job_id == UUID(job_id)
            assert admitted[0].flow_id == flow.id
            origin = admitted[0].job_metadata["api_key_authorization"]
            assert origin["api_key_id"] == str(key_id)
            assert origin["targets"] == [{"resource_type": "flow", "resource_id": str(flow.id), "action": "execute"}]
            super().start_job(job_id, task_coro)

    queue = AdmissionQueue()
    try:
        job_id = await start_build(active_user, flow, queue, flow_id=uuid4())
        await queue.task_coro
        assert generate.await_args.kwargs["job_id"] == UUID(job_id)
        assert generate.await_args.kwargs.get("track_job_status", True)
        assert (await service.get_job_by_job_id(UUID(job_id))).status == JobStatus.COMPLETED
    finally:
        queue.close()


async def test_revoked_key_waiting_in_legacy_queue_is_denied_before_graph_build(active_user, monkeypatch):
    flow, key_id = await seed_restricted_build(active_user, monkeypatch)
    graph_build = AsyncMock(side_effect=AssertionError("Graph construction must not run"))
    monkeypatch.setattr(build, "build_graph_from_db", graph_build)
    queue = HeldQueue()
    try:
        job_id = await start_build(active_user, flow, queue)
        async with session_scope() as session:
            key = await session.get(ApiKey, key_id)
            key.is_active = False
            session.add(key)
        with pytest.raises(PermissionError):
            await queue.task_coro
        graph_build.assert_not_awaited()
        failed = await get_job_service().get_job_by_job_id(UUID(job_id))
        assert failed.status == JobStatus.FAILED
        assert failed.error["type"] == "authorization_denied"
    finally:
        queue.close()


async def test_waiting_build_refreshes_owner_privileges_before_provider_policy_scope(active_user, monkeypatch):
    flow, _ = await seed_restricted_build(active_user, monkeypatch)
    async with session_scope() as session:
        owner = await session.get(User, active_user.id)
        owner.is_superuser = True
        session.add(owner)
        submitted_user = UserRead.model_validate(owner, from_attributes=True)
    observed = []

    async def runtime(**kwargs):
        current_user = kwargs["current_user"]
        assert current_user.id == submitted_user.id
        assert current_user.is_superuser is False
        policy_context = current_model_provider_policy_context()
        assert policy_context.attributes["is_superuser"] is False
        observed.append(current_user)

    monkeypatch.setattr(build, "_generate_flow_events", runtime)
    queue = HeldQueue()
    try:
        await start_build(submitted_user, flow, queue)
        async with session_scope() as session:
            owner = await session.get(User, active_user.id)
            owner.is_superuser = False
            session.add(owner)
        await queue.task_coro
        assert len(observed) == 1
        assert submitted_user.is_superuser is True
    finally:
        queue.close()


async def test_build_rechecks_external_key_access_after_job_authorization(active_user, monkeypatch):
    flow, _ = await seed_restricted_build(active_user, monkeypatch)
    service = get_job_service()
    authorize = service.authorize_job_start

    async def add_external_profile_after_authorization(*args, **kwargs):
        context = await authorize(*args, **kwargs)
        auth_settings = get_settings_service().auth_settings
        async with session_scope() as session:
            session.add(
                SSOUserProfile(
                    user_id=active_user.id,
                    sso_provider=auth_settings.EXTERNAL_AUTH_PROVIDER,
                    sso_user_id=str(active_user.id),
                )
            )
        monkeypatch.setattr(auth_settings, "EXTERNAL_AUTH_ACCESS_CEILING_ENABLED", True)
        monkeypatch.setattr(auth_settings, "EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS", True)
        return context

    monkeypatch.setattr(service, "authorize_job_start", add_external_profile_after_authorization)
    generate = AsyncMock()
    monkeypatch.setattr(build, "generate_flow_events", generate)
    queue = HeldQueue()
    try:
        job_id = await start_build(active_user, flow, queue)
        with pytest.raises(HTTPException) as exc_info:
            await queue.task_coro
        assert exc_info.value.status_code == 403
        generate.assert_not_awaited()
        assert (await service.get_job_by_job_id(UUID(job_id))).status == JobStatus.FAILED
    finally:
        queue.close()


async def test_restricted_pause_keeps_job_nonterminal_and_preserves_provenance(active_user, monkeypatch):
    flow, key_id = await seed_restricted_build(active_user, monkeypatch)
    graph = MagicMock()
    graph.vertices = []
    graph.vertices_to_run = set()
    graph.sort_vertices.return_value = ["paused-vertex"]
    graph.session_id = str(flow.id)
    graph.set_run_id.side_effect = lambda value: setattr(graph, "run_id", value)
    graph.end_all_traces = AsyncMock()
    graph.check_and_handle_pause = AsyncMock(
        side_effect=GraphPausedException("checkpoint", "human_input", {"request_id": "approval"})
    )
    monkeypatch.setattr(build, "build_graph_from_db", AsyncMock(return_value=graph))
    monkeypatch.setattr(build, "get_chat_service", lambda: SimpleNamespace(set_cache=AsyncMock()))
    monkeypatch.setattr(build, "get_telemetry_service", MagicMock())
    monkeypatch.setattr("langflow.api.v2.hitl.persist_human_input_card", AsyncMock())
    queue = HeldQueue()
    try:
        job_id = await start_build(active_user, flow, queue)
        await queue.task_coro
        job = await get_job_service().get_job_by_job_id(UUID(job_id))
        assert job.status == JobStatus.SUSPENDED
        assert job.finished_timestamp is None
        assert job.job_metadata["api_key_authorization"]["api_key_id"] == str(key_id)
        events = []
        while not queue.event_manager.queue.empty():
            _event_id, payload, _timestamp = queue.event_manager.queue.get_nowait()
            if payload is not None:
                events.append(json.loads(payload))
        assert any(event["event"] == "human_input_required" for event in events)
        assert not any(event["event"] == "error" for event in events)
        assert await get_job_service().claim_suspended_for_resume(UUID(job_id))
    finally:
        queue.close()


async def test_restricted_admission_failure_prevents_queue_allocation(active_user, monkeypatch):
    flow, _ = await seed_restricted_build(active_user, monkeypatch)
    monkeypatch.setattr(get_job_service(), "create_job", AsyncMock(side_effect=RuntimeError("Database unavailable")))
    queue = MagicMock()
    with pytest.raises(HTTPException):
        await start_build(active_user, flow, queue)
    queue.create_queue.assert_not_called()
    queue.start_job.assert_not_called()


@pytest.mark.parametrize("failure_stage", ["allocation", "start"])
async def test_restricted_queue_failure_terminalizes_durable_job(active_user, monkeypatch, failure_stage):
    flow, _ = await seed_restricted_build(active_user, monkeypatch)
    service = get_job_service()
    real_create = service.create_job
    admitted = []

    async def create_job(*args, **kwargs):
        row = await real_create(*args, **kwargs)
        admitted.append(row.job_id)
        return row

    monkeypatch.setattr(service, "create_job", create_job)
    queue = MagicMock()
    if failure_stage == "allocation":
        queue.create_queue.side_effect = RuntimeError("Queue unavailable")
    else:
        events = create_default_event_manager(asyncio.Queue())
        queue.create_queue.return_value = (events.queue, events)
        queue.start_job.side_effect = RuntimeError("Queue unavailable")
    with pytest.raises(HTTPException):
        await start_build(active_user, flow, queue)
    assert len(admitted) == 1
    assert (await service.get_job_by_job_id(admitted[0])).status == JobStatus.FAILED
    if failure_stage == "allocation":
        queue.start_job.assert_not_called()
    else:
        queue.start_job.assert_called_once()


async def test_unrestricted_build_preserves_legacy_queue_call_shape(active_user, monkeypatch):
    queue = HeldQueue()
    service = MagicMock()
    monkeypatch.setattr(build, "get_job_service", lambda: service)
    generate = AsyncMock()
    monkeypatch.setattr(build, "generate_flow_events", generate)
    flow = Flow(id=uuid4(), name="Legacy build", user_id=active_user.id)
    try:
        await start_build(active_user, flow, queue)
        await queue.task_coro
        assert "job_id" not in generate.await_args.kwargs
        assert "track_job_status" not in generate.await_args.kwargs
        service.create_job.assert_not_called()
        service.execute_with_status.assert_not_called()
    finally:
        queue.close()


@pytest.mark.parametrize("restricted", [False, True])
async def test_legacy_tracking_failure_is_fatal_only_for_restricted_keys(active_user, monkeypatch, restricted):
    if restricted:
        flow, _ = await seed_restricted_build(active_user, monkeypatch)
    else:
        flow = Flow(id=uuid4(), name="Legacy build", user_id=active_user.id)
    graph = MagicMock()
    graph.vertices = []
    graph.vertices_to_run = set()
    graph.sort_vertices.return_value = []
    graph.set_run_id.side_effect = lambda value: setattr(graph, "run_id", value)
    graph.end_all_traces = AsyncMock()
    monkeypatch.setattr(build, "build_graph_from_db", AsyncMock(return_value=graph))
    monkeypatch.setattr(build, "get_chat_service", lambda: SimpleNamespace(set_cache=AsyncMock()))
    monkeypatch.setattr(build, "get_telemetry_service", MagicMock())
    service = SimpleNamespace(
        get_job_by_job_id=AsyncMock(return_value=None),
        create_job=AsyncMock(side_effect=RuntimeError("Tracking unavailable")),
    )
    monkeypatch.setattr(build, "get_job_service", lambda: service)
    callback = build.generate_flow_events(
        flow_id=flow.id,
        background_tasks=BackgroundTasks(),
        event_manager=create_default_event_manager(asyncio.Queue()),
        inputs=None,
        data=None,
        files=None,
        stop_component_id=None,
        start_component_id=None,
        log_builds=False,
        current_user=active_user,
        provider_policy_flow=flow,
    )
    if restricted:
        with pytest.raises(RuntimeError, match="Tracking unavailable"):
            await callback
        graph.flow_execution_span.assert_not_called()
    else:
        await callback
        graph.flow_execution_span.assert_called_once()
