"""Saved flow tools retain original evidence through Agent checkpoints and report downloads."""

import re
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_job_service, session_scope
from lfx.components.data_source.record_source import RecordSourceComponent
from lfx.components.files_and_knowledge.sourced_report import SourcedReportComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.custom import Component
from lfx.graph.flow_builder import add_component, add_connection, configure_component, empty_flow
from lfx.graph.graph.base import Graph
from lfx.io import MessageTextInput, Output
from lfx.projects.artifacts import AgentRunResult, SourcedReport
from lfx.schema.message import Message
from pydantic import Field
from sqlmodel import select

from tests.unit.api.v1.test_project_config_write_through import (
    create_flow,
    create_project,
    save_config,
    stored_flow,
)


class OfflineSourceFixture(Component):
    """A deterministic lookup; the model supplies a key, never the evidence text."""

    display_name = "Offline Source Fixture"
    name = "OfflineSourceFixture"
    inputs = [MessageTextInput(name="query", display_name="Query")]
    outputs = [Output(name="text", display_name="Retrieved Text", method="lookup")]

    def lookup(self) -> Message:
        if self.query not in {"alpha", "beta"}:
            msg = "Unknown offline source"
            raise ValueError(msg)
        return Message(text=f"The offline {self.query} fixture records three observations. " * 2500)


class StoredEvidenceModel(BaseChatModel):
    tool_name: str = ""
    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "stored-offline-evidence-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        assert len(tools) == 1
        self.tool_name = tools[0].name
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        completed = [message for message in messages if isinstance(message, ToolMessage)]
        if len(completed) == 2:
            ids = list(dict.fromkeys(re.findall(r"source-[a-f0-9]{24}", str([m.content for m in completed]))))
            assert len(ids) == 2
            answer = AIMessage(
                content="## Offline findings\n\nBoth fixtures record three observations. "
                + " ".join(f"[@{source_id}]" for source_id in ids)
            )
        else:
            query = "alpha" if not completed else "beta"
            answer = AIMessage(
                content="Reading original evidence.",
                tool_calls=[
                    {
                        "name": self.tool_name,
                        "args": {"flow_tweak_data": {"ChatInput-query~input_value": query}},
                        "id": f"call-{query}",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=answer)])


def registry():
    result = {}
    for cls in (
        AgentComponent,
        SourcedReportComponent,
        ChatInput,
        ChatOutput,
        OfflineSourceFixture,
        RecordSourceComponent,
    ):
        node = cls().to_frontend_node()["data"]["node"]
        node["field_order"] = [item.name for item in cls.inputs]
        result[cls.name] = node
    return result


@pytest.mark.parametrize("gated", [False, True])
async def test_saved_agent_collects_flow_tool_evidence_and_downloads_report(
    client, logged_in_headers, active_user, gated
):
    project_id = await create_project(client, logged_in_headers, name="Offline evidence harness")
    components = registry()
    source_flow = empty_flow("offline-sources")
    add_component(source_flow, "ChatInput", components, component_id="ChatInput-query")
    configure_component(source_flow, "ChatInput-query", {"should_store_message": False})
    add_component(source_flow, "OfflineSourceFixture", components, component_id="OfflineSourceFixture-lookup")
    add_component(source_flow, "RecordSource", components, component_id="RecordSource-capture")
    configure_component(
        source_flow,
        "RecordSource-capture",
        {
            "uri": "fixture://offline-study",
            "title": "Offline study fixture",
        },
    )
    add_connection(source_flow, "ChatInput-query", "message", "OfflineSourceFixture-lookup", "query")
    add_connection(source_flow, "OfflineSourceFixture-lookup", "text", "RecordSource-capture", "content")
    source_id = await create_flow(active_user, folder_id=project_id, data=source_flow["data"], name="offline-sources")
    main = empty_flow("Evidence Agent")
    add_component(main, "Agent", components, component_id="Agent-research")
    configure_component(
        main,
        "Agent-research",
        {
            "tool_policy": "ask" if gated else "tool_defaults",
            "n_messages": 0,
            "add_current_date_tool": False,
            "add_calculator_tool": False,
        },
    )
    add_component(main, "SourcedReport", components, component_id="SourcedReport-save")
    add_component(main, "ChatOutput", components, component_id="ChatOutput-answer")
    add_connection(main, "Agent-research", "response", "ChatOutput-answer", "input_value")
    add_connection(main, "Agent-research", "response", "SourcedReport-save", "report")
    agent_id = await create_flow(active_user, folder_id=project_id, data=main["data"], name="Evidence Agent")
    await save_config(client, logged_in_headers, project_id, {"agent_flow_id": agent_id, "tools": [source_id]})
    job_id = uuid4()
    jobs = get_job_service()
    await jobs.create_job(job_id=job_id, flow_id=UUID(agent_id), user_id=active_user.id)

    async def build():
        graph = Graph.from_payload(
            deepcopy((await stored_flow(agent_id)).data), flow_id=agent_id, user_id=str(active_user.id)
        )
        graph.set_run_id(job_id)
        graph.session_id = f"evidence-test-{agent_id}"
        model = StoredEvidenceModel()
        graph.get_vertex("Agent-research").update_raw_params(
            {"model": model, "input_value": "Research the alpha and beta fixtures."}, overwrite=True
        )
        return graph, model

    async def execute_until_pause(graph):
        async for result in graph.async_start():
            assert getattr(result, "valid", True)
            if graph.pause_requested:
                # The production build driver also stops before downstream vertices.
                partial = graph.get_vertex("Agent-research").custom_component.get_output("response").value
                assert partial.properties.state == "partial"
                break

    graph, model = await build()
    await execute_until_pause(graph)
    if gated:
        for call_id in ("call-alpha", "call-beta"):
            assert graph.pause_requested
            request = graph.pause_info["data"]
            assert request["action_requests"][0]["tool_call_id"] == call_id
            assert await jobs.load_checkpoint(job_id, "agent")
            # New Graph, Agent, model, and saver; only database state survives.
            graph, model = await build()
            graph.human_input_decisions = {request["request_id"]: {"action_id": "approve"}}
            await execute_until_pause(graph)
    assert not graph.pause_requested
    output = graph.get_vertex("SourcedReport-save").custom_component.get_output("artifact").value.data
    report = SourcedReport.model_validate(output["artifact"])
    assert len(report.sources) == 2
    assert all(len(source.content.encode()) > 128_000 for source in report.sources)
    assert {use.tool_call_id for use in report.source_uses} == {"call-alpha", "call-beta"}
    assert all(use.tool_name == model.tool_name for use in report.source_uses)
    assert report.claim_support == "not_evaluated"
    assert "Reading original" not in report.markdown
    report.require_resolved_citations()

    # These are the completed Agent's actual persisted properties, not a new fixture row.
    async with session_scope() as session:
        rows = (await session.exec(select(MessageTable).where(MessageTable.flow_id == UUID(agent_id)))).all()
        completed = [row for row in rows if row.properties.get("agent_run_result")]
        assert completed
        run = AgentRunResult.model_validate(completed[-1].properties["agent_run_result"])
        assert run.evidence.sources == report.sources
        assert run.evidence.uses == report.source_uses
        assert run.answer == report.markdown
    for path in output["files"]:
        response = await client.get(f"api/v1/files/download/{path}", headers=logged_in_headers)
        assert response.status_code == 200, response.text
        if path.endswith(".json"):
            assert SourcedReport.model_validate_json(response.content) == report
        else:
            assert response.text == report.render_markdown()
