"""Saved flow tools retain original evidence through Agent checkpoints and report downloads."""

import re
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_job_service, session_scope
from lfx.components.data_source.record_source import RecordSourceComponent
from lfx.components.files_and_knowledge.sourced_report import SourcedReportComponent
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.custom import Component
from lfx.graph.flow_builder import add_component, add_connection, configure_component, empty_flow
from lfx.graph.graph.base import Graph
from lfx.io import MessageTextInput, Output
from lfx.projects.artifacts import AgentRunResult, SourcedReport
from lfx.projects.tools import prepare_tool_template
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
@pytest.mark.parametrize(("use_pack", "nested"), [(False, False), (True, False), (True, True)])
async def test_saved_agent_collects_flow_tool_evidence_and_downloads_report(
    client, logged_in_headers, active_user, gated, use_pack, nested
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
    add_connection(source_flow, "OfflineSourceFixture-lookup", "text", "RecordSource-capture", "content")
    pack_id = (
        await create_project(client, logged_in_headers, name="Offline evidence tools", project_type="tool-pack")
        if use_pack
        else None
    )
    if nested:
        from tests.unit.api.v1.test_project_config_write_through import echo_flow_data

        child_id = await create_flow(active_user, folder_id=pack_id, name="Reviewed query", data=echo_flow_data())
        child = {"id": child_id, "name": "Reviewed query", "data": (await stored_flow(child_id)).data}
        adapter = prepare_tool_template(child)
        child_graph = Graph.from_payload(child["data"], instantiate_components=False)
        adapter["outputs"] = [output.model_dump() for output in RunFlowComponent()._format_flow_outputs(child_graph)]
        adapter["add_tool_output"] = False
        components["RunFlow"] = adapter
        add_component(source_flow, "RunFlow", components, component_id="RunFlow-query")
        add_connection(
            source_flow,
            "ChatInput-query",
            "message",
            "RunFlow-query",
            "ChatInput-echo~input_value",
            registry=components,
        )
        add_connection(
            source_flow,
            "RunFlow-query",
            "ChatOutput-echo~message",
            "OfflineSourceFixture-lookup",
            "query",
            registry=components,
        )
    else:
        add_connection(source_flow, "ChatInput-query", "message", "OfflineSourceFixture-lookup", "query")
    source_id = await create_flow(
        active_user, folder_id=pack_id or project_id, data=source_flow["data"], name="offline-sources"
    )
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
    config = {"agent_flow_id": agent_id, "tools": [source_id]}
    if use_pack:
        await save_config(client, logged_in_headers, pack_id, {"tools": [source_id]})
        manifest = (await client.get(f"/api/v1/projects/{pack_id}/tool-pack", headers=logged_in_headers)).json()
        config.update(tools=[], tool_packs=[manifest["reference"]])
    await save_config(client, logged_in_headers, project_id, config)
    job_id = uuid4()
    jobs = get_job_service()
    await jobs.create_job(job_id=job_id, flow_id=UUID(agent_id), user_id=active_user.id)

    async def build(checkpoint=None):
        graph = (
            Graph.resume_from_checkpoint(checkpoint)
            if checkpoint
            else Graph.from_payload(
                deepcopy((await stored_flow(agent_id)).data), flow_id=agent_id, user_id=str(active_user.id)
            )
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
            checkpoint = None
            if nested:
                from lfx.graph.checkpoint.builder import build_checkpoint
                from lfx.graph.checkpoint.schema import GraphCheckpoint

                from tests.unit.api.v1.test_transitive_tool_snapshots import change_child

                checkpoint = GraphCheckpoint.model_validate_json(build_checkpoint(graph).model_dump_json())
                if call_id == "call-alpha":
                    # The edited query would make the deterministic lookup reject
                    # the input if a resumed nested call read the current flow.
                    await change_child(child_id)
            # New Graph, Agent, model, and saver; only database state survives.
            graph, model = await build(checkpoint)
            if checkpoint:
                graph.get_vertex("Agent-research").built = False
            graph.human_input_decisions = {request["request_id"]: {"action_id": "approve"}}
            await execute_until_pause(graph)
    assert not graph.pause_requested
    output = graph.get_vertex("SourcedReport-save").custom_component.get_output("artifact").value.data
    report = SourcedReport.model_validate(output["artifact"])
    assert len(report.sources) == 2
    assert all(len(source.content.encode()) > 128_000 for source in report.sources)
    assert {use.tool_call_id for use in report.source_uses} == {"call-alpha", "call-beta"}
    assert all(use.tool_name == model.tool_name for use in report.source_uses)
    if use_pack:
        assert {use.tool_call_id for use in report.tool_dependencies} == {"call-alpha", "call-beta"}
        assert all(
            use.binding.reference.model_dump(mode="json") == manifest["reference"] for use in report.tool_dependencies
        )
        assert all(str(use.binding.tool.flow_id) == source_id for use in report.tool_dependencies)
        if nested:
            assert all(
                [str(item.flow.flow_id) for item in use.binding.dependency_versions] == [child_id]
                for use in report.tool_dependencies
            )
    else:
        assert report.tool_dependencies == ()
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
        assert run.evidence.tool_dependencies == report.tool_dependencies
        assert run.answer == report.markdown
    for path in output["files"]:
        response = await client.get(f"api/v1/files/download/{path}", headers=logged_in_headers)
        assert response.status_code == 200, response.text
        if path.endswith(".json"):
            assert SourcedReport.model_validate_json(response.content) == report
        else:
            assert response.text == report.render_markdown()

    if use_pack and not gated:
        # The model can call a prepared tool more than once while its author edits
        # the source. Each invocation must use the same reviewed definition.
        async with session_scope() as session:
            source = await session.get(Flow, UUID(source_id))
            changed = deepcopy(source.data)
            lookup = next(node for node in changed["nodes"] if node["id"] == "OfflineSourceFixture-lookup")
            code = lookup["data"]["node"]["template"]["code"]
            code["value"] = code["value"].replace("three observations", "unreviewed observations")
            source.data = changed
            session.add(source)
        tool = graph.get_vertex("Agent-research").custom_component.tools[0]
        result = await tool.ainvoke(
            {
                "type": "tool_call",
                "id": "call-after-edit",
                "name": tool.name,
                "args": {"flow_tweak_data": {"ChatInput-query~input_value": "alpha"}},
            }
        )
        assert result.status == "success"
        assert "three observations" in str(result.artifact)
        assert "unreviewed observations" not in str(result.artifact)
        # A new run must explicitly review the changed pack, even if a previous
        # Run Flow graph remains cached in the process.
        fresh, _ = await build()
        with pytest.raises(Exception, match="tool pack changed"):
            await execute_until_pause(fresh)
        manifest = (await client.get(f"/api/v1/projects/{pack_id}/tool-pack", headers=logged_in_headers)).json()
        await save_config(client, logged_in_headers, project_id, {**config, "tool_packs": [manifest["reference"]]})
        reviewed, _ = await build()
        await execute_until_pause(reviewed)
        revised_output = reviewed.get_vertex("SourcedReport-save").custom_component.get_output("artifact").value.data
        revised = SourcedReport.model_validate(revised_output["artifact"])
        assert all("unreviewed observations" in source.content for source in revised.sources)
        assert all(
            use.binding.reference.revision == manifest["reference"]["revision"] for use in revised.tool_dependencies
        )
        assert revised.tool_dependencies[0].binding.version_id != report.tool_dependencies[0].binding.version_id
