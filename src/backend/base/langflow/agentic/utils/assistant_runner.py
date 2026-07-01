"""Headless Langflow Assistant runner for MCP clients.

External MCP clients have no frontend to apply ``flow_update`` SSE
events, so any canvas change the assistant produces must be persisted
server-side before returning. The runner drives the SAME streaming
pipeline the UI uses — the non-streaming path skips intent
classification and the agent chats instead of building.
"""

from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException
from lfx.mcp.flow_builder_tools import get_working_flow

from langflow.agentic.api.router import _resolve_assistant_context
from langflow.agentic.api.schemas import AssistantRequest
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import LANGFLOW_ASSISTANT_FLOW
from langflow.api.v1.flows import _new_flow, _save_flow_to_fs
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.deps import get_storage_service

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

DEFAULT_FLOW_NAME = "Assistant Flow"


async def _ensure_flow(session: AsyncSession, user_id: UUID, flow_id: str | None) -> tuple[Flow, bool]:
    if flow_id:
        try:
            flow_uuid = UUID(flow_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid flow_id: not a valid UUID.") from exc
        flow = await session.get(Flow, flow_uuid)
        if flow is None or (flow.user_id is not None and str(flow.user_id) != str(user_id)):
            raise HTTPException(status_code=404, detail="Flow not found.")
        return flow, False

    folder = await get_or_create_default_folder(session, user_id)
    new_flow = FlowCreate(
        name=DEFAULT_FLOW_NAME,
        description="Created by the Langflow Assistant via MCP",
        data={"nodes": [], "edges": []},
        folder_id=folder.id,
        user_id=user_id,
    )
    storage_service = get_storage_service()
    created = await _new_flow(session=session, flow=new_flow, user_id=user_id, storage_service=storage_service)
    await session.commit()
    # _new_flow returns a FlowRead; re-fetch the ORM row so later edits persist.
    db_flow = await session.get(Flow, created.id)
    if db_flow is None:
        raise HTTPException(status_code=500, detail="Flow creation failed.")
    return db_flow, True


class _CanvasState:
    """Fallback event replay for headless runs when no working-flow snapshot exists.

    Handles ``set_flow`` / ``add_component`` / ``connect``. The authoritative
    source is the server-side working flow (it captures configure/remove/
    tool-mode/select-output too); this replay only runs when that snapshot is
    unavailable. ``changed`` flips on ANY ``flow_update`` so persistence is
    gated on "the agent mutated the canvas", not on the subset replayed here.
    """

    def __init__(self, initial_data: dict[str, Any] | None) -> None:
        self.data: dict[str, Any] = copy.deepcopy(initial_data) if initial_data else {}
        self.data.setdefault("nodes", [])
        self.data.setdefault("edges", [])
        self.name: str | None = None
        self.changed = False

    def apply(self, event: dict[str, Any]) -> None:
        # Any flow_update is a canvas mutation, including actions only the
        # authoritative working-flow snapshot captures (configure/remove/etc.).
        self.changed = True
        action = event.get("action")
        if action == "set_flow":
            payload = event.get("flow")
            if isinstance(payload, dict) and payload.get("data"):
                self.data = payload["data"]
                self.name = payload.get("name") or self.name
                self.changed = True
        elif action == "add_component" and isinstance(event.get("node"), dict):
            node = event["node"]
            self.data["nodes"] = [n for n in self.data["nodes"] if n.get("id") != node.get("id")]
            self.data["nodes"].append(node)
            self.changed = True
        elif action == "connect" and isinstance(event.get("edge"), dict):
            edge = event["edge"]
            self.data["edges"] = [e for e in self.data["edges"] if e.get("id") != edge.get("id")]
            self.data["edges"].append(edge)
            self.changed = True


def _apply_field_edit(flow_data: dict[str, Any], edit: dict[str, Any]) -> None:
    """Write a proposed field value into the working flow, by component id + field.

    Resolves the node by id (index-independent — nodes may have shifted since
    the proposal was emitted) and sets its template field value. No-op when the
    node or field cannot be resolved (e.g. the node was removed this turn).
    """
    component_id = edit.get("component_id")
    field = edit.get("field")
    if not component_id or not field:
        return
    for node in flow_data.get("nodes", []):
        nid = node.get("data", {}).get("id", node.get("id"))
        if nid != component_id:
            continue
        template = node.get("data", {}).get("node", {}).get("template", {})
        target = template.get(field)
        if isinstance(target, dict):
            target["value"] = edit.get("new_value")
        return


async def _consume_stream(
    stream, initial_data: dict[str, Any] | None
) -> tuple[_CanvasState, dict[str, Any] | None, str | None, str | None, list[dict[str, Any]]]:
    """Drain the SSE stream into (canvas_state, working_snapshot, result_text, error_text, field_edits).

    ``working_snapshot`` is captured at the ``complete`` event, where the
    working flow is still alive — the generator's ``finally`` only resets it
    after iteration ends. ``field_edits`` are the ``edit_field`` proposals the
    working flow never applied; the caller writes them in before persisting.
    """
    canvas = _CanvasState(initial_data)
    working_snapshot: dict[str, Any] | None = None
    result_text: str | None = None
    error_text: str | None = None
    field_edits: list[dict[str, Any]] = []
    async for chunk in stream:
        for line in str(chunk).splitlines():
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[len("data: ") :])
            except json.JSONDecodeError:
                continue
            event_type = event.get("event")
            if event_type == "flow_update":
                canvas.apply(event)
                if event.get("action") == "edit_field":
                    field_edits.append(event)
            elif event_type == "complete":
                data = event.get("data") or {}
                result_text = data.get("result")
                working = get_working_flow()
                if isinstance(working, dict) and working.get("data", {}).get("nodes"):
                    working_snapshot = copy.deepcopy(working)
            elif event_type == "error":
                error_text = event.get("message")
    return canvas, working_snapshot, result_text, error_text, field_edits


async def run_assistant_and_persist(
    *,
    session: AsyncSession,
    user_id: UUID,
    instruction: str,
    flow_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Run the assistant against a flow and persist any canvas changes.

    Returns a dict with: ``flow_id``, ``link``, ``result`` (assistant
    reply text), ``flow_changed``, ``session_id``, ``provider`` and
    ``model_name``.
    """
    flow, created_new = await _ensure_flow(session, user_id, flow_id)

    request = AssistantRequest(
        flow_id=str(flow.id),
        input_value=instruction,
        provider=provider,
        model_name=model_name,
        session_id=session_id,
        max_retries=None,
    )
    ctx = await _resolve_assistant_context(request, user_id, session)

    stream = execute_flow_with_validation_streaming(
        flow_filename=LANGFLOW_ASSISTANT_FLOW,
        input_value=instruction,
        global_variables=ctx.global_vars,
        max_retries=ctx.max_retries,
        user_id=str(user_id),
        session_id=ctx.session_id,
        provider=ctx.provider,
        model_name=ctx.model_name,
        api_key_var=ctx.api_key_name,
        apply_edits_immediately=True,
    )
    canvas, working_snapshot, result_text, error_text, field_edits = await _consume_stream(stream, flow.data)

    if canvas.changed:
        flow_data = working_snapshot["data"] if working_snapshot else canvas.data
        # Headless MCP has no UI to apply an edit_field review proposal, so apply
        # each to the working flow here or the text edit is dropped (Bug #13641).
        for edit in field_edits:
            _apply_field_edit(flow_data, edit)
        flow.data = flow_data
        if created_new and canvas.name:
            flow.name = canvas.name
        session.add(flow)
        await session.commit()
        await _save_flow_to_fs(flow, user_id, get_storage_service())

    return {
        "flow_id": str(flow.id),
        "link": f"/flow/{flow.id}",
        "result": result_text or error_text,
        "error": error_text,
        "flow_changed": canvas.changed,
        "session_id": ctx.session_id,
        "provider": ctx.provider,
        "model_name": ctx.model_name,
    }
