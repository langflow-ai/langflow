"""The Langflow Assistant must be callable from external MCP clients.

User report (Discord, 2026-06-11): "i can't call the assistant by mcp."
Verified live (2026-06-12): the ``langflow-agentic`` MCP server exposes 18
tools (templates, components, flow inspection) but none invokes the
assistant; the assistant is HTTP-only.

These tests pin the new ``run_assistant`` MCP tool and its runner:
- the tool is registered on the FastMCP server;
- the runner creates a flow when none is given, persists canvas changes
  the assistant produced (headless clients have no frontend to apply
  ``flow_update`` events), and enforces flow ownership.

The runner must consume the SAME streaming pipeline the UI uses
(``execute_flow_with_validation_streaming``) — the non-streaming path
skips intent classification and the agent just chats instead of building
(observed live, 2026-06-12, via a real MCP stdio call with gpt-oss:20b).

Mock boundaries: the streaming generator (full LLM round-trip) and the
DB session, mirroring ``test_template_create.py``.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

RUNNER_MODULE = "langflow.agentic.utils.assistant_runner"

NEW_FLOW_DATA = {"nodes": [{"id": "ChatInput-abc"}], "edges": []}

EVENTS_WITH_FLOW = [
    {"event": "progress", "step": "generating_flow"},
    {"event": "flow_update", "action": "set_flow", "flow": {"name": "Simple Chat Flow", "data": NEW_FLOW_DATA}},
    {"event": "complete", "data": {"result": "Built a simple chat flow.", "success": True}},
]

EVENTS_TEXT_ONLY = [
    {"event": "progress", "step": "generating"},
    {"event": "complete", "data": {"result": "Langflow is a visual flow builder."}},
]

INCREMENTAL_NODE_A = {"id": "ChatInput-abc", "data": {"id": "ChatInput-abc", "type": "ChatInput"}}
INCREMENTAL_NODE_B = {"id": "ChatOutput-def", "data": {"id": "ChatOutput-def", "type": "ChatOutput"}}
INCREMENTAL_EDGE = {"id": "edge-1", "source": "ChatInput-abc", "target": "ChatOutput-def"}

EVENTS_INCREMENTAL = [
    {"event": "flow_update", "action": "add_component", "node": INCREMENTAL_NODE_A},
    {"event": "flow_update", "action": "add_component", "node": INCREMENTAL_NODE_B},
    {"event": "flow_update", "action": "connect", "edge": INCREMENTAL_EDGE},
    {"event": "complete", "data": {"result": "Added two components and connected them."}},
]


def _stream_of(events: list[dict]):
    def factory(*_args, **_kwargs):
        async def gen():
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"

        return gen()

    return factory


def _context_stub() -> SimpleNamespace:
    return SimpleNamespace(
        provider="Ollama",
        model_name="gpt-oss:20b",
        api_key_name="OLLAMA_BASE_URL",
        session_id="mcp-session",
        global_vars={"PROVIDER": "Ollama"},
        max_retries=2,
    )


class TestRunAssistantToolRegistration:
    @pytest.mark.asyncio
    async def test_should_expose_run_assistant_tool_on_the_agentic_mcp_server(self):
        from langflow.agentic.mcp.server import mcp

        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "run_assistant" in tool_names, f"The assistant must be callable via MCP; available tools: {tool_names}"


class TestRunAssistantAndPersist:
    @pytest.mark.asyncio
    async def test_should_create_a_new_flow_when_no_flow_id_is_given(self):
        from langflow.agentic.utils.assistant_runner import run_assistant_and_persist

        user_id = uuid4()
        created_flow = SimpleNamespace(id=uuid4(), name="Assistant Flow", data=None, user_id=user_id)
        session = AsyncMock()
        session.get = AsyncMock(return_value=created_flow)
        with (
            patch(f"{RUNNER_MODULE}._new_flow", new_callable=AsyncMock, return_value=created_flow) as new_flow,
            patch(f"{RUNNER_MODULE}._save_flow_to_fs", new_callable=AsyncMock),
            patch(
                f"{RUNNER_MODULE}.get_or_create_default_folder",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(id=uuid4()),
            ),
            patch(f"{RUNNER_MODULE}.get_storage_service", MagicMock()),
            patch(
                f"{RUNNER_MODULE}._resolve_assistant_context",
                new_callable=AsyncMock,
                return_value=_context_stub(),
            ),
            patch(
                f"{RUNNER_MODULE}.execute_flow_with_validation_streaming",
                side_effect=_stream_of(EVENTS_WITH_FLOW),
            ),
        ):
            result = await run_assistant_and_persist(
                session=session,
                user_id=user_id,
                instruction="Build a chat flow",
            )

        new_flow.assert_awaited_once()
        assert result["flow_id"] == str(created_flow.id)
        assert result["flow_changed"] is True
        assert created_flow.data == NEW_FLOW_DATA

    @pytest.mark.asyncio
    async def test_should_persist_canvas_changes_on_an_existing_flow(self):
        from langflow.agentic.utils.assistant_runner import run_assistant_and_persist

        user_id = uuid4()
        flow = SimpleNamespace(id=uuid4(), name="My Flow", data={"nodes": [], "edges": []}, user_id=user_id)
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)
        with (
            patch(
                f"{RUNNER_MODULE}._resolve_assistant_context",
                new_callable=AsyncMock,
                return_value=_context_stub(),
            ),
            patch(
                f"{RUNNER_MODULE}.execute_flow_with_validation_streaming",
                side_effect=_stream_of(EVENTS_WITH_FLOW),
            ),
            patch(f"{RUNNER_MODULE}._save_flow_to_fs", new_callable=AsyncMock),
            patch(f"{RUNNER_MODULE}.get_storage_service", MagicMock()),
        ):
            result = await run_assistant_and_persist(
                session=session,
                user_id=user_id,
                instruction="Add a chat output",
                flow_id=str(flow.id),
            )

        assert flow.data == NEW_FLOW_DATA
        session.commit.assert_awaited()
        assert result["flow_changed"] is True
        assert result["result"] == "Built a simple chat flow."

    @pytest.mark.asyncio
    async def test_should_not_touch_the_flow_when_assistant_only_answers_text(self):
        from langflow.agentic.utils.assistant_runner import run_assistant_and_persist

        user_id = uuid4()
        original_data = {"nodes": [], "edges": []}
        flow = SimpleNamespace(id=uuid4(), name="My Flow", data=original_data, user_id=user_id)
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)
        with (
            patch(
                f"{RUNNER_MODULE}._resolve_assistant_context",
                new_callable=AsyncMock,
                return_value=_context_stub(),
            ),
            patch(
                f"{RUNNER_MODULE}.execute_flow_with_validation_streaming",
                side_effect=_stream_of(EVENTS_TEXT_ONLY),
            ),
        ):
            result = await run_assistant_and_persist(
                session=session,
                user_id=user_id,
                instruction="What is Langflow?",
                flow_id=str(flow.id),
            )

        assert flow.data is original_data
        assert result["flow_changed"] is False
        assert result["result"] == "Langflow is a visual flow builder."

    @pytest.mark.asyncio
    async def test_should_persist_canvas_when_agent_emits_incremental_events(self):
        """Observed live (2026-06-12, LM Studio): incremental-only build was discarded."""
        from langflow.agentic.utils.assistant_runner import run_assistant_and_persist

        user_id = uuid4()
        flow = SimpleNamespace(id=uuid4(), name="My Flow", data={"nodes": [], "edges": []}, user_id=user_id)
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)
        with (
            patch(
                f"{RUNNER_MODULE}._resolve_assistant_context",
                new_callable=AsyncMock,
                return_value=_context_stub(),
            ),
            patch(
                f"{RUNNER_MODULE}.execute_flow_with_validation_streaming",
                side_effect=_stream_of(EVENTS_INCREMENTAL),
            ),
            patch(f"{RUNNER_MODULE}._save_flow_to_fs", new_callable=AsyncMock),
            patch(f"{RUNNER_MODULE}.get_storage_service", MagicMock()),
        ):
            result = await run_assistant_and_persist(
                session=session,
                user_id=user_id,
                instruction="Build a chat flow",
                flow_id=str(flow.id),
            )

        assert result["flow_changed"] is True
        assert [n["id"] for n in flow.data["nodes"]] == ["ChatInput-abc", "ChatOutput-def"]
        assert [e["id"] for e in flow.data["edges"]] == ["edge-1"]

    @pytest.mark.asyncio
    async def test_should_compose_incremental_events_on_top_of_existing_flow_data(self):
        from langflow.agentic.utils.assistant_runner import run_assistant_and_persist

        user_id = uuid4()
        existing_node = {"id": "Prompt-xyz", "data": {"id": "Prompt-xyz", "type": "Prompt Template"}}
        flow = SimpleNamespace(
            id=uuid4(), name="My Flow", data={"nodes": [existing_node], "edges": []}, user_id=user_id
        )
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)
        with (
            patch(
                f"{RUNNER_MODULE}._resolve_assistant_context",
                new_callable=AsyncMock,
                return_value=_context_stub(),
            ),
            patch(
                f"{RUNNER_MODULE}.execute_flow_with_validation_streaming",
                side_effect=_stream_of(EVENTS_INCREMENTAL[:1] + EVENTS_INCREMENTAL[-1:]),
            ),
            patch(f"{RUNNER_MODULE}._save_flow_to_fs", new_callable=AsyncMock),
            patch(f"{RUNNER_MODULE}.get_storage_service", MagicMock()),
        ):
            result = await run_assistant_and_persist(
                session=session,
                user_id=user_id,
                instruction="Add a chat input",
                flow_id=str(flow.id),
            )

        assert result["flow_changed"] is True
        assert [n["id"] for n in flow.data["nodes"]] == ["Prompt-xyz", "ChatInput-abc"]

    @pytest.mark.asyncio
    async def test_should_reject_a_flow_owned_by_another_user(self):
        from fastapi import HTTPException
        from langflow.agentic.utils.assistant_runner import run_assistant_and_persist

        flow = SimpleNamespace(id=uuid4(), name="Not yours", data=None, user_id=uuid4())
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)

        with pytest.raises(HTTPException) as exc_info:
            await run_assistant_and_persist(
                session=session,
                user_id=uuid4(),
                instruction="Edit this flow",
                flow_id=str(flow.id),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_should_drive_the_stream_with_apply_edits_immediately(self):
        # Wiring guard (Bug #13641): the runner must tell the streaming service it
        # is headless so the propose tools apply edits live and narrate them as
        # done instead of "(pending user approval)".
        from langflow.agentic.utils.assistant_runner import run_assistant_and_persist

        user_id = uuid4()
        flow = SimpleNamespace(id=uuid4(), name="My Flow", data={"nodes": [], "edges": []}, user_id=user_id)
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)

        captured_kwargs: dict = {}

        def _capturing_stream(*_args, **kwargs):
            captured_kwargs.update(kwargs)
            return _stream_of(EVENTS_TEXT_ONLY)()

        with (
            patch(f"{RUNNER_MODULE}._resolve_assistant_context", new_callable=AsyncMock, return_value=_context_stub()),
            patch(f"{RUNNER_MODULE}.execute_flow_with_validation_streaming", side_effect=_capturing_stream),
            patch(f"{RUNNER_MODULE}._save_flow_to_fs", new_callable=AsyncMock),
            patch(f"{RUNNER_MODULE}.get_storage_service", MagicMock()),
        ):
            await run_assistant_and_persist(
                session=session, user_id=user_id, instruction="Set the prompt to 'X'.", flow_id=str(flow.id)
            )

        assert captured_kwargs.get("apply_edits_immediately") is True, (
            f"headless runner must request immediate edit apply; got {captured_kwargs!r}"
        )


class TestRunAssistantAppliesProposedFieldEdits:
    """Bug #13641: headless MCP must persist proposed text edits.

    A proposed text edit (configure_component in propose-mode OR a direct
    ProposeFieldEdit call) emits an edit_field event but never writes the value
    into the working flow. Headless MCP has no UI to apply the proposal, so the
    runner must apply it before persisting or the change is silently dropped.
    """

    MARKER = "PIRATE-MARKER-9000"

    @staticmethod
    def _agent_data(system_prompt_value: str) -> dict:
        """Inner flow data (nodes/edges) — the shape stored in ``Flow.data``."""
        return {
            "nodes": [
                {
                    "id": "Agent-1",
                    "data": {
                        "id": "Agent-1",
                        "type": "Agent",
                        "node": {"template": {"system_prompt": {"value": system_prompt_value}}},
                    },
                }
            ],
            "edges": [],
        }

    def _edit_field_events(self) -> list[dict]:
        return [
            {
                "event": "flow_update",
                "action": "edit_field",
                "component_id": "Agent-1",
                "field": "system_prompt",
                "old_value": "You are a Langflow Agent.",
                "new_value": self.MARKER,
                "patch": [
                    {
                        "op": "replace",
                        "path": "/data/nodes/0/data/node/template/system_prompt/value",
                        "value": self.MARKER,
                    }
                ],
            },
            {"event": "complete", "data": {"result": "Proposed the system prompt change."}},
        ]

    @pytest.mark.asyncio
    async def test_should_persist_proposed_edit_when_working_flow_omits_it(self):
        from langflow.agentic.utils import assistant_runner

        user_id = uuid4()
        flow = SimpleNamespace(
            id=uuid4(), name="My Flow", data=self._agent_data("You are a Langflow Agent."), user_id=user_id
        )
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)

        # The working flow snapshot still holds the OLD prompt — the proposal was
        # never applied to it (the bug). The runner must apply the edit_field.
        working_without_edit = {"data": self._agent_data("You are a Langflow Agent.")}

        with (
            patch.object(
                assistant_runner, "_resolve_assistant_context", new_callable=AsyncMock, return_value=_context_stub()
            ),
            patch.object(
                assistant_runner,
                "execute_flow_with_validation_streaming",
                side_effect=_stream_of(self._edit_field_events()),
            ),
            patch.object(assistant_runner, "get_working_flow", return_value=working_without_edit),
            patch.object(assistant_runner, "_save_flow_to_fs", new_callable=AsyncMock),
            patch.object(assistant_runner, "get_storage_service", MagicMock()),
        ):
            result = await assistant_runner.run_assistant_and_persist(
                session=session,
                user_id=user_id,
                instruction=f"Set the Agent's system prompt to exactly '{self.MARKER}'.",
                flow_id=str(flow.id),
            )

        assert result["flow_changed"] is True
        persisted = flow.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"]
        assert persisted == self.MARKER, f"the proposed text edit must persist headlessly; got {persisted!r}"

    @pytest.mark.asyncio
    async def test_should_apply_proposed_edit_on_the_event_replay_fallback(self):
        # No working-flow snapshot (empty) → the runner falls back to canvas.data
        # built from the flow's initial data; the edit_field must still land.
        from langflow.agentic.utils import assistant_runner

        user_id = uuid4()
        flow = SimpleNamespace(
            id=uuid4(), name="My Flow", data=self._agent_data("You are a Langflow Agent."), user_id=user_id
        )
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)

        with (
            patch.object(
                assistant_runner, "_resolve_assistant_context", new_callable=AsyncMock, return_value=_context_stub()
            ),
            patch.object(
                assistant_runner,
                "execute_flow_with_validation_streaming",
                side_effect=_stream_of(self._edit_field_events()),
            ),
            patch.object(assistant_runner, "get_working_flow", return_value=None),
            patch.object(assistant_runner, "_save_flow_to_fs", new_callable=AsyncMock),
            patch.object(assistant_runner, "get_storage_service", MagicMock()),
        ):
            await assistant_runner.run_assistant_and_persist(
                session=session,
                user_id=user_id,
                instruction=f"Set the Agent's system prompt to exactly '{self.MARKER}'.",
                flow_id=str(flow.id),
            )

        persisted = flow.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"]
        assert persisted == self.MARKER, f"the proposed edit must land on the replay fallback too; got {persisted!r}"


class TestRunAssistantPersistsAuthoritativeWorkingFlow:
    """E1 (Eric): persist the authoritative working-flow snapshot so configure/remove/tool-mode survive."""

    AUTHORITATIVE_FLOW = {
        "data": {
            "nodes": [
                {
                    "id": "Agent-1",
                    "data": {
                        "id": "Agent-1",
                        "type": "Agent",
                        "node": {"template": {"system_prompt": {"value": "baker"}}},
                    },
                }
            ],
            "edges": [],
        }
    }

    @pytest.mark.asyncio
    async def test_should_persist_working_flow_snapshot_when_agent_configured_and_removed(self):
        from langflow.agentic.utils import assistant_runner

        user_id = uuid4()
        flow = SimpleNamespace(
            id=uuid4(),
            name="My Flow",
            data={"nodes": [{"id": "Agent-1"}, {"id": "Old-1"}], "edges": []},
            user_id=user_id,
        )
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)

        events = [
            {
                "event": "flow_update",
                "action": "configure",
                "component_id": "Agent-1",
                "params": {"system_prompt": "baker"},
            },
            {"event": "flow_update", "action": "remove_component", "component_id": "Old-1"},
            {"event": "complete", "data": {"result": "Configured the agent and removed a node."}},
        ]
        with (
            patch.object(
                assistant_runner, "_resolve_assistant_context", new_callable=AsyncMock, return_value=_context_stub()
            ),
            patch.object(assistant_runner, "execute_flow_with_validation_streaming", side_effect=_stream_of(events)),
            patch.object(assistant_runner, "get_working_flow", return_value=self.AUTHORITATIVE_FLOW),
            patch.object(assistant_runner, "_save_flow_to_fs", new_callable=AsyncMock),
            patch.object(assistant_runner, "get_storage_service", MagicMock()),
        ):
            result = await assistant_runner.run_assistant_and_persist(
                session=session, user_id=user_id, instruction="configure the agent", flow_id=str(flow.id)
            )

        assert result["flow_changed"] is True
        # The authoritative working flow wins: configure applied, Old-1 gone.
        assert [n["id"] for n in flow.data["nodes"]] == ["Agent-1"]
        agent = flow.data["nodes"][0]
        assert agent["data"]["node"]["template"]["system_prompt"]["value"] == "baker"

    @pytest.mark.asyncio
    async def test_should_fall_back_to_event_replay_when_working_flow_is_empty(self):
        from langflow.agentic.utils import assistant_runner

        user_id = uuid4()
        flow = SimpleNamespace(id=uuid4(), name="My Flow", data={"nodes": [], "edges": []}, user_id=user_id)
        session = AsyncMock()
        session.get = AsyncMock(return_value=flow)

        node = {"id": "ChatInput-x", "data": {"id": "ChatInput-x", "type": "ChatInput"}}
        events = [
            {"event": "flow_update", "action": "add_component", "node": node},
            {"event": "complete", "data": {"result": "Added it."}},
        ]
        with (
            patch.object(
                assistant_runner, "_resolve_assistant_context", new_callable=AsyncMock, return_value=_context_stub()
            ),
            patch.object(assistant_runner, "execute_flow_with_validation_streaming", side_effect=_stream_of(events)),
            patch.object(assistant_runner, "get_working_flow", return_value=None),
            patch.object(assistant_runner, "_save_flow_to_fs", new_callable=AsyncMock),
            patch.object(assistant_runner, "get_storage_service", MagicMock()),
        ):
            result = await assistant_runner.run_assistant_and_persist(
                session=session, user_id=user_id, instruction="add input", flow_id=str(flow.id)
            )

        assert result["flow_changed"] is True
        assert [n["id"] for n in flow.data["nodes"]] == ["ChatInput-x"]
