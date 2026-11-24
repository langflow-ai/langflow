"""A resumed background run validates the source saved in its checkpoint."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from importlib.resources import files
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from langflow.api.build import generate_flow_events
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service, session_scope
from lfx.events.event_manager import create_default_event_manager
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.interface import components
from lfx.schema.schema import InputValueRequest
from lfx.utils.flow_validation import CustomComponentValidationError

pytestmark = pytest.mark.no_blockbuster


async def test_resume_rejects_custom_checkpoint_even_when_saved_flow_is_trusted(active_user, monkeypatch, tmp_path):
    entries = dict(json.loads(files("lfx").joinpath("_assets/component_index.json").read_text())["entries"])
    template = deepcopy(entries["input_output"]["ChatInput"])
    cache = components.ComponentCache()
    cache.all_types_dict = {"input_output": {"ChatInput": template}}
    cache.all_types_ready = True
    monkeypatch.setattr(components, "component_cache", cache)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", True)
    monkeypatch.setattr(settings, "custom_component_admin_only", True)

    node_id = "ChatInput-resume"
    trusted = {
        "nodes": [{"id": node_id, "data": {"id": node_id, "type": "ChatInput", "node": template}}],
        "edges": [],
    }
    async with session_scope() as session:
        flow = Flow(name="resume policy", user_id=active_user.id, data=deepcopy(trusted))
        session.add(flow)
        await session.flush()
        flow_id = flow.id

    marker = tmp_path / "checkpoint-source-executed"
    stored = deepcopy(trusted)
    code = stored["nodes"][0]["data"]["node"]["template"]["code"]
    declaration = "class ChatInput(ChatComponent):"
    assert declaration in code["value"]
    code["value"] = code["value"].replace(
        declaration,
        f"{declaration}\n    _POLICY_PROBE = __import__('pathlib').Path({str(marker)!r}).write_text('executed')",
        1,
    )
    job_id = uuid4()
    checkpoint = GraphCheckpoint(
        run_id=str(job_id),
        job_id=str(job_id),
        flow_id=str(flow_id),
        user_id=str(active_user.id),
        flow_payload=stored,
    )
    store = InMemoryCheckpointStore()
    await store.save(checkpoint)
    monkeypatch.setattr("lfx.services.deps.get_checkpoint_service", lambda: store)
    queue = asyncio.Queue()
    error = None
    try:
        await generate_flow_events(
            flow_id=flow_id,
            provider_policy_flow=flow,
            background_tasks=BackgroundTasks(),
            event_manager=create_default_event_manager(queue),
            inputs=InputValueRequest(session=str(flow_id)),
            data=None,
            files=None,
            stop_component_id=None,
            start_component_id=None,
            log_builds=False,
            current_user=active_user,
            job_id=job_id,
            resume={"request_id": f"{node_id}:{job_id}", "decision": {"action_id": "continue"}},
            track_job_status=False,
            expose_error_details=True,
        )
    except Exception as exc:
        error = exc

    assert not marker.exists(), "Resuming executed component source from the unchecked checkpoint"
    assert isinstance(error, CustomComponentValidationError), repr(error)
    assert (await store.load_by_run_id(str(job_id))).flow_payload == stored
    async with session_scope() as session:
        assert (await session.get(Flow, flow_id)).data == trusted
