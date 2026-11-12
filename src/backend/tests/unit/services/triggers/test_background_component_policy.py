"""Trigger workers enforce component policy against the graph they will build."""

import json
from copy import deepcopy
from importlib.resources import files
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v2 import workflow
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers.dispatcher import build_submit_request
from lfx.interface import components

pytestmark = pytest.mark.no_blockbuster

_CUSTOM_SOURCE = """
from lfx.custom import Component
from lfx.io import Output
from lfx.schema import Message

class TriggerPolicyProbe(Component):
    display_name = "Trigger Policy Probe"
    outputs = [Output(name="message", display_name="Message", method="build")]

    def build(self) -> Message:
        return Message(text="custom component output")
"""


def _canvas(component_type, template):
    node_id = f"{component_type}-policy"
    return {
        "nodes": [{"id": node_id, "data": {"id": node_id, "type": component_type, "node": template}}],
        "edges": [],
    }


@pytest.fixture
async def component_context(owned_flow, trigger_owner, monkeypatch):
    entries = dict(json.loads(files("lfx").joinpath("_assets/component_index.json").read_text())["entries"])
    trusted = deepcopy(entries["input_output"]["ChatInput"])
    cache = components.ComponentCache()
    cache.all_types_dict = {"input_output": {"ChatInput": trusted}}
    cache.all_types_ready = True
    monkeypatch.setattr(components, "component_cache", cache)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", True)
    monkeypatch.setattr(settings, "custom_component_admin_only", True)
    custom = {
        "display_name": "Trigger Policy Probe",
        "template": {"code": {"value": _CUSTOM_SOURCE}},
        "outputs": [{"name": "message", "display_name": "Message", "method": "build"}],
    }
    builds = []

    async def record_build(**kwargs):
        builds.append(kwargs)
        yield b"test stopped at build boundary", "error"

    monkeypatch.setattr(workflow, "_stream_event_frames", record_build)
    return SimpleNamespace(
        flow_id=owned_flow,
        owner_id=trigger_owner,
        user=UserRead.model_construct(id=trigger_owner),
        settings=settings,
        custom=_canvas("TriggerPolicyProbe", custom),
        trusted=_canvas("ChatInput", trusted),
        builds=builds,
    )


async def _source(context, *, pinned=False, custom=True, is_superuser=False, user=None):
    selected = deepcopy(context.custom if custom else context.trusted)
    async with session_scope() as session:
        owner = await session.get(User, context.owner_id)
        owner.is_superuser = is_superuser
        session.add(owner)
        flow = await session.get(Flow, context.flow_id)
        # A pin must be checked independently of the current saved canvas.
        flow.data = deepcopy(context.trusted if custom else context.custom) if pinned else selected
        session.add(flow)
    trigger = Trigger(flow_id=context.flow_id, user_id=context.owner_id, name="Policy trigger", kind="schedule")
    event = TriggerEvent(trigger_id=trigger.id, dedupe_key="tick")
    request = build_submit_request(trigger=trigger, event=event, binding_data=selected if pinned else None)
    source = workflow._default_frame_source_factory(
        request=request,
        flow_id=context.flow_id,
        user=user or context.user,
        adapter=SimpleNamespace(terminal_error_type="error"),
    )
    return source, selected


@pytest.mark.parametrize("pinned", [False, True], ids=["current", "pinned"])
async def test_trigger_worker_blocks_nonadmin_custom_components(component_context, pinned):
    context = component_context
    source, _ = await _source(context, pinned=pinned)

    with pytest.raises(HTTPException) as exc_info:
        _ = [frame async for frame in source(job_id=uuid4())]

    assert exc_info.value.status_code == 400
    assert "custom components are not allowed" in str(exc_info.value.detail)
    assert context.builds == []


@pytest.mark.parametrize(("is_superuser", "admin_only"), [(True, True), (False, False)])
async def test_trigger_worker_preserves_authorized_custom_components(
    component_context, monkeypatch, is_superuser, admin_only
):
    context = component_context
    monkeypatch.setattr(context.settings, "custom_component_admin_only", admin_only)
    source, selected = await _source(context, is_superuser=is_superuser)

    assert [frame async for frame in source(job_id=uuid4())]

    assert len(context.builds) == 1
    build = context.builds[0]
    assert build["current_user"].is_superuser is is_superuser
    assert (build["parsed"].data or build["provider_policy_flow"].data) == selected


@pytest.mark.parametrize("is_superuser", [False, True])
async def test_trigger_worker_keeps_global_custom_component_restriction(component_context, monkeypatch, is_superuser):
    context = component_context
    monkeypatch.setattr(context.settings, "allow_custom_components", False)
    source, _ = await _source(context, is_superuser=is_superuser)

    with pytest.raises(HTTPException) as exc_info:
        _ = [frame async for frame in source(job_id=uuid4())]

    assert exc_info.value.status_code == 400
    assert "custom components are not allowed" in str(exc_info.value.detail)
    assert context.builds == []


@pytest.mark.parametrize("pinned", [False, True], ids=["current", "pinned"])
async def test_trigger_worker_builds_from_sanitized_builtin_canvas(component_context, pinned):
    context = component_context
    source, selected = await _source(context, pinned=pinned, custom=False)

    assert [frame async for frame in source(job_id=uuid4())]

    assert len(context.builds) == 1
    build = context.builds[0]
    assert build["current_user"].is_superuser is False
    assert build["parsed"].data == selected
    assert build["parsed"].data is not build["provider_policy_flow"].data
    async with session_scope() as session:
        stored = await session.get(Flow, context.flow_id)
        assert stored.data == (context.custom if pinned else selected)


async def test_trigger_worker_checks_policy_when_queued_job_starts(component_context, monkeypatch):
    context = component_context
    monkeypatch.setattr(context.settings, "custom_component_admin_only", False)
    source, _ = await _source(context)
    monkeypatch.setattr(context.settings, "custom_component_admin_only", True)

    with pytest.raises(HTTPException) as exc_info:
        _ = [frame async for frame in source(job_id=uuid4())]

    assert exc_info.value.status_code == 400
    assert context.builds == []


async def test_trigger_worker_rechecks_demoted_owner(component_context):
    context = component_context
    stale_admin = UserRead.model_construct(id=context.owner_id, is_superuser=True, is_active=True)
    source, _ = await _source(context, is_superuser=True, user=stale_admin)
    async with session_scope() as session:
        owner = await session.get(User, context.owner_id)
        owner.is_superuser = False
        session.add(owner)

    with pytest.raises(HTTPException) as exc_info:
        _ = [frame async for frame in source(job_id=uuid4())]

    assert exc_info.value.status_code == 400
    assert context.builds == []
