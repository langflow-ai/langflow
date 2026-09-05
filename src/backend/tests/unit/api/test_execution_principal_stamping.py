"""INT-6: every graph-building seam stamps a per-family execution principal.

A graph that reaches a component unstamped carries ``ExecutionPrincipal.unknown()``
and the portable deny floor refuses every connection, so these are fail-closed
regression tests: a new build site that forgets to stamp is a silent outage for
connection-backed components, not a security hole.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api import warm_graph
from langflow.api.utils.execution_principal import (
    CONNECTION_RESOLUTION_BY_FAMILY,
    EXECUTION_FAMILIES,
    FAMILY_A2A,
    FAMILY_DEPLOYMENTS,
    FAMILY_INTERACTIVE_CHAT,
    FAMILY_LEGACY_MCP,
    FAMILY_MCP_PROJECTS,
    FAMILY_V1_RUN,
    FAMILY_WEBHOOK,
    FAMILY_WORKFLOW_HITL_V2,
    execution_principal_for,
    execution_principal_for_job,
    stamp_execution_principal,
)
from langflow.api.utils.flow_utils import build_and_cache_graph_from_data, build_graph_from_data
from langflow.services.authorization.public_access import public_execution_user
from lfx.services.authorization.base import PUBLIC_ANONYMOUS_ACTOR_ID, ExecutionPrincipal

pytestmark = pytest.mark.no_blockbuster

_MINIMAL_FLOW = {"nodes": [], "edges": []}


def _user(user_id=None):
    return SimpleNamespace(id=user_id or uuid4())


def test_every_matrix_family_has_a_rule() -> None:
    assert set(CONNECTION_RESOLUTION_BY_FAMILY) == EXECUTION_FAMILIES


def test_unknown_family_is_a_programming_error_not_a_silent_default() -> None:
    with pytest.raises(ValueError, match="unknown execution family"):
        execution_principal_for("totally_new_route", user=_user())


def test_an_interactive_family_runs_as_the_actor() -> None:
    actor = _user()
    owner = uuid4()

    principal = execution_principal_for(FAMILY_INTERACTIVE_CHAT, user=actor, flow_owner_id=owner)

    assert principal.kind == "actor"
    assert principal.user_id == str(actor.id)
    assert principal.interactive is True
    assert principal.allow_explicit_shares is True


def test_an_owner_family_runs_as_the_resource_owner_not_the_caller() -> None:
    caller = _user()
    owner = uuid4()

    for family in (FAMILY_WEBHOOK, FAMILY_DEPLOYMENTS):
        principal = execution_principal_for(family, user=caller, flow_owner_id=owner)

        assert principal.user_id == str(owner)
        assert principal.actor_id == str(caller.id)
        assert principal.interactive is False
        assert principal.allow_explicit_shares is False


def test_a_job_owner_family_runs_as_the_job_owner_not_the_flow_owner() -> None:
    """The identity a resumed HITL run keeps is the JOB's owner.

    A background run can be submitted against a flow the caller only holds a share
    on, so ``flow.user_id`` and ``job.user_id`` genuinely differ. Reading the flow
    owner here would let the share holder's resumed run resolve the flow owner's
    opted-in connections -- the implicit identity borrowing this ticket exists to
    prevent.
    """
    job_owner = _user()
    flow_owner = uuid4()

    principal = execution_principal_for(
        FAMILY_WORKFLOW_HITL_V2,
        user=job_owner,
        flow_owner_id=flow_owner,
    )

    assert principal.kind == "job_owner"
    assert principal.user_id == str(job_owner.id)
    assert principal.actor_id == str(job_owner.id)
    assert principal.user_id != str(flow_owner)
    assert principal.interactive is False
    assert principal.allow_explicit_shares is False


def test_an_explicit_job_owner_outranks_the_effective_user() -> None:
    """Worker paths that hold only a job row pass the owner id directly."""
    job_owner = uuid4()

    principal = execution_principal_for(
        FAMILY_WORKFLOW_HITL_V2,
        user=_user(),
        flow_owner_id=uuid4(),
        job_owner_id=job_owner,
    )

    assert principal.user_id == str(job_owner)


def test_owner_only_families_refuse_explicit_shares() -> None:
    for family in (FAMILY_LEGACY_MCP, FAMILY_MCP_PROJECTS):
        assert execution_principal_for(family, user=_user()).allow_explicit_shares is False


def test_the_anonymous_actor_collapses_whatever_family_is_named() -> None:
    """A public admission cannot be widened by naming an interactive family.

    ``mcp_utils`` swaps in the public execution user for an unauthenticated MCP
    project call while still passing ``mcp_projects``; the helper, not the caller,
    decides that this is an anonymous run.
    """
    owner = uuid4()

    for family in (FAMILY_INTERACTIVE_CHAT, FAMILY_V1_RUN, FAMILY_MCP_PROJECTS, FAMILY_A2A):
        principal = execution_principal_for(family, user=public_execution_user(), flow_owner_id=owner)

        assert principal.kind == "anonymous_public"
        assert principal.user_id is None
        assert principal.actor_id == str(PUBLIC_ANONYMOUS_ACTOR_ID)
        assert principal.interactive is False
        assert principal.allow_explicit_shares is False


def test_a_graph_free_job_principal_is_available_for_worker_paths() -> None:
    """Knowledge-base ingestion sources are not Components and have no graph."""
    owner = uuid4()

    principal = execution_principal_for_job(user_id=owner)

    assert principal.kind == "job_owner"
    assert principal.user_id == str(owner)
    assert principal.interactive is False
    assert principal.family == FAMILY_WORKFLOW_HITL_V2


async def test_build_graph_from_data_stamps_the_supplied_principal() -> None:
    principal = execution_principal_for(FAMILY_INTERACTIVE_CHAT, user=_user())

    graph = await build_graph_from_data(
        uuid4(),
        _MINIMAL_FLOW,
        flow_name="flow",
        user_id=str(uuid4()),
        execution_principal=principal,
    )

    assert graph.execution_principal == principal


async def test_build_graph_from_data_without_a_principal_fails_closed() -> None:
    graph = await build_graph_from_data(uuid4(), _MINIMAL_FLOW, flow_name="flow", user_id=str(uuid4()))

    assert graph.execution_principal.kind == "unknown"


async def test_the_playground_cache_seam_stamps_too() -> None:
    """``build_and_cache_graph_from_data`` is the primary Playground build path."""

    class _ChatServiceStub:
        def __init__(self) -> None:
            self.cached: dict[str, object] = {}

        async def set_cache(self, key, value) -> None:
            self.cached[key] = value

    principal = execution_principal_for(FAMILY_INTERACTIVE_CHAT, user=_user())
    chat_service = _ChatServiceStub()
    flow_id = uuid4()

    graph = await build_and_cache_graph_from_data(
        flow_id,
        chat_service,
        _MINIMAL_FLOW,
        execution_principal=principal,
    )

    assert graph.execution_principal == principal
    assert chat_service.cached[str(flow_id)] is graph


class _WarmTemplate:
    """The subset of the warm-template surface ``warm_deepcopy`` touches."""

    def __init__(self) -> None:
        self.vertices: list = []
        self.user_id = None
        self.session_id = None
        self.has_session_id_vertices: list[str] = []
        self.execution_principal = ExecutionPrincipal.unknown()

    def get_vertex(self, _vertex_id: str):
        return None

    def copy_for_run(self, *, user_id, before_instantiate=None):
        from copy import deepcopy

        copied = deepcopy(self)
        copied.user_id = user_id
        if before_instantiate is not None:
            before_instantiate(copied)
        return copied


async def test_a_warm_copy_keeps_its_family_after_the_lfx_run_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ordering hazard this ticket fixes, pinned.

    ``warm_deepcopy`` calls ``apply_run_defaults``, which used to stamp the lfx
    headless operator on every graph it touched -- the one principal allowed to
    resolve environment-backed connections.
    """
    from langflow.services import deps
    from langflow.services.warm_registry import service as registry_service

    template = _WarmTemplate()
    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _settings: True)
    monkeypatch.setattr(deps, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace()))
    registry = SimpleNamespace(get=lambda _flow_id: (template, "v1"))
    monkeypatch.setattr(registry_service, "get_warm_registry", lambda: registry)

    principal = execution_principal_for(FAMILY_WEBHOOK, user=_user(), flow_owner_id=uuid4())
    graph = await warm_graph.warm_deepcopy(
        "flow-id",
        expected_version="v1",
        user_id=str(uuid4()),
        session_id="session-id",
        execution_principal=principal,
    )

    assert graph is not None
    assert graph.execution_principal == principal


async def test_a_warm_copy_without_a_principal_still_gets_the_headless_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lfx's own callers keep the behavior they had."""
    from langflow.services import deps
    from langflow.services.warm_registry import service as registry_service

    template = _WarmTemplate()
    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _settings: True)
    monkeypatch.setattr(deps, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace()))
    registry = SimpleNamespace(get=lambda _flow_id: (template, "v1"))
    monkeypatch.setattr(registry_service, "get_warm_registry", lambda: registry)

    graph = await warm_graph.warm_deepcopy(
        "flow-id", expected_version="v1", user_id=str(uuid4()), session_id="session-id"
    )

    assert graph is not None
    assert graph.execution_principal.kind == "headless_operator"


async def test_a_sub_flow_inherits_the_parent_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    """``helpers.flow.run_flow`` runs a child graph; it must not stay on unknown().

    Only the provider-policy scope and the graph run itself are stubbed: the
    identity assignment under test is the real code path a Run Flow / Sub Flow /
    flow-as-tool component reaches.
    """
    import contextlib

    from langflow.helpers import flow as flow_helpers

    parent_principal = execution_principal_for(FAMILY_INTERACTIVE_CHAT, user=_user())
    child = await build_graph_from_data(uuid4(), _MINIMAL_FLOW, flow_name="child", user_id=str(uuid4()))
    assert child.execution_principal.kind == "unknown"

    @contextlib.asynccontextmanager
    async def _fake_scope(**_kwargs):
        yield SimpleNamespace(id=uuid4(), name="child")

    async def _fake_arun(*_args, **_kwargs):
        return []

    monkeypatch.setattr(flow_helpers, "scoped_model_provider_policy_for_target_flow", _fake_scope)
    monkeypatch.setattr(child, "arun", _fake_arun)

    await flow_helpers.run_flow(
        inputs=[],
        graph=child,
        user_id=str(uuid4()),
        execution_principal=parent_principal,
    )

    assert child.execution_principal == parent_principal


async def test_the_lfx_sub_flow_component_forwards_its_graph_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lfx half of the same seam: ``CustomComponent.run_flow`` passes it on.

    Asserted on the forwarded value rather than on the source text, so a broken
    forward fails and a reformat does not.
    """
    from lfx.custom.custom_component import custom_component as custom_component_module

    forwarded: dict = {}

    async def _record_run_flow(**kwargs):
        forwarded.update(kwargs)
        return []

    monkeypatch.setattr(custom_component_module, "run_flow", _record_run_flow)

    principal = execution_principal_for(FAMILY_INTERACTIVE_CHAT, user=_user())
    component = custom_component_module.CustomComponent()
    # ``graph`` is a read-only property over the component's vertex.
    component._vertex = SimpleNamespace(graph=SimpleNamespace(run_id="run-1", execution_principal=principal))
    component._user_id = uuid4()

    await component.run_flow(inputs={"input_value": "hi"}, flow_id=str(uuid4()))

    assert forwarded["execution_principal"] == principal


async def test_the_run_flow_component_forwards_its_graph_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The palette 'Run Flow' node is the common sub-flow path and forwards too."""
    from lfx.base.tools import run_flow as run_flow_module

    forwarded: dict = {}

    async def _record_run_flow(**kwargs):
        forwarded.update(kwargs)
        return []

    monkeypatch.setattr(run_flow_module, "run_flow", _record_run_flow)

    principal = execution_principal_for(FAMILY_INTERACTIVE_CHAT, user=_user())
    component = run_flow_module.RunFlowBaseComponent()
    child_graph = object()
    monkeypatch.setattr(component, "get_graph", lambda **_kwargs: _awaitable(child_graph))
    monkeypatch.setattr(component, "_build_flow_tweak_data", dict)
    monkeypatch.setattr(component, "_build_inputs", lambda _tweaks: {})
    component._vertex = SimpleNamespace(graph=SimpleNamespace(execution_principal=principal))
    component.flow_name_selected = None
    component.flow_id_selected = None
    component.session_id = "session"
    component._cached_flow_updated_at = None

    await component._run_flow_with_cached_graph(user_id=str(uuid4()))

    assert forwarded["execution_principal"] == principal
    assert forwarded["graph"] is child_graph


async def _awaitable(value):
    return value


async def _principal_from_a_build(monkeypatch: pytest.MonkeyPatch, **kwargs) -> ExecutionPrincipal:
    """Drive the real ``generate_flow_events`` and return the principal it stamped.

    Only the graph build and the service lookups are stubbed, so the identity
    decision under test is the production one; the principal is read off the
    ``build_graph_from_db`` call the build loop actually makes.
    """
    import asyncio
    import contextlib
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import BackgroundTasks
    from langflow.api import build as build_module
    from lfx.events.event_manager import create_default_event_manager

    graph = MagicMock()
    graph.source_flow_id = None
    graph.run_id = None
    graph.vertices = []
    graph.vertices_to_run = set()
    graph.sort_vertices.return_value = []
    graph.set_run_id.side_effect = lambda value: setattr(graph, "run_id", value)
    graph.end_all_traces = AsyncMock()

    @contextlib.asynccontextmanager
    async def _fake_session_scope():
        yield MagicMock()

    build_from_db = AsyncMock(return_value=graph)
    chat_service = MagicMock()
    chat_service.set_cache = AsyncMock()
    monkeypatch.setattr(build_module, "get_chat_service", lambda: chat_service)
    monkeypatch.setattr(build_module, "get_telemetry_service", lambda: MagicMock())
    monkeypatch.setattr(build_module, "session_scope", _fake_session_scope)
    monkeypatch.setattr(build_module, "build_graph_from_db", build_from_db)

    await build_module.generate_flow_events(
        background_tasks=BackgroundTasks(),
        event_manager=create_default_event_manager(asyncio.Queue()),
        inputs=None,
        data=None,
        files=None,
        stop_component_id=None,
        start_component_id=None,
        log_builds=False,
        flow_name="flow",
        track_job_status=False,
        expose_error_details=False,
        **kwargs,
    )

    build_from_db.assert_awaited_once()
    return build_from_db.await_args.kwargs["execution_principal"]


async def test_the_build_loop_stamps_a_resume_with_the_job_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """End of the wire for the job-owner rule: a shared flow's HITL resume.

    ``BackgroundExecutionService.resume_job`` re-enqueues under a stub for
    ``job.user_id``, so ``current_user`` here is the job owner while
    ``source_flow_owner_id`` is whoever owns the shared flow. The stamped
    principal must follow the job.
    """
    job_owner = uuid4()
    flow_owner = uuid4()

    principal = await _principal_from_a_build(
        monkeypatch,
        flow_id=uuid4(),
        current_user=_user(job_owner),
        source_flow_owner_id=flow_owner,
        execution_family=FAMILY_WORKFLOW_HITL_V2,
    )

    assert principal.kind == "job_owner"
    assert principal.user_id == str(job_owner)
    assert principal.user_id != str(flow_owner)


async def test_the_build_loop_still_stamps_a_webhook_with_the_flow_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """The owner families are unchanged: a webhook keeps running as the publisher."""
    caller = uuid4()
    flow_owner = uuid4()

    principal = await _principal_from_a_build(
        monkeypatch,
        flow_id=uuid4(),
        current_user=_user(caller),
        source_flow_owner_id=flow_owner,
        execution_family=FAMILY_WEBHOOK,
    )

    assert principal.kind == "flow_owner"
    assert principal.user_id == str(flow_owner)
    assert principal.actor_id == str(caller)


def test_stamping_is_a_no_op_on_a_missing_graph() -> None:
    assert stamp_execution_principal(None, execution_principal_for(FAMILY_V1_RUN, user=_user())) is None
