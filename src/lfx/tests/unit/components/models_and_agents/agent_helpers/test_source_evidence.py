import json
import re
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from lfx.base.agents.events import process_agent_events
from lfx.base.tools.component_tool import ComponentStructuredTool
from lfx.components.data_source.record_source import RecordSourceComponent
from lfx.components.files_and_knowledge.sourced_report import SourcedReportComponent
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import adapt_graph_events_to_executor_shape
from lfx.components.models_and_agents.agent_helpers.source_evidence import EVIDENCE_STATE_KEY, collect_tool_evidence
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.graph.graph.base import Graph
from lfx.projects.artifacts import AgentRunResult, CollectedEvidence, SourcedReport
from lfx.projects.tool_packs import ToolExport, ToolPackReference, ToolPackToolBinding
from lfx.schema.message import Message
from lfx.schema.properties import Properties
from pydantic import Field

from tests.unit.projects.test_artifacts import storage as artifact_storage  # noqa: F401


def captured(name):
    component = RecordSourceComponent()
    component.set(
        uri=f"https://example.org/{name}",
        title=f"Offline {name} source",
        content=f"The {name} fixture is captured evidence. " * 180,
    )
    return component.record_source().data


class EvidenceModel(BaseChatModel):
    seen: list = Field(default_factory=list)
    summaries: list = Field(default_factory=list)
    parallel: bool = False

    @property
    def _llm_type(self):
        return "offline-evidence-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        text = "\n".join(str(message.content) for message in messages)
        source_ids = list(dict.fromkeys(re.findall(r"source-[a-f0-9]{24}", text)))
        if "Messages to summarize:" in text:
            self.summaries.append(deepcopy(messages))
            answer = AIMessage(content="Captured source references: " + ", ".join(f"[@{sid}]" for sid in source_ids))
        else:
            self.seen.append(deepcopy(messages))
            calls = {message.tool_call_id for message in messages if isinstance(message, ToolMessage)}
            alpha = captured("alpha")["source"]["id"]
            beta = captured("beta")["source"]["id"]
            if "call-beta" in calls or beta in source_ids:
                answer = AIMessage(
                    content="## Findings\n\nCaptured evidence " + " ".join(f"[@{sid}]" for sid in source_ids)
                )
            else:
                names = (
                    ["beta"]
                    if "call-alpha" in calls or alpha in source_ids
                    else ["alpha", "beta"]
                    if self.parallel
                    else ["alpha"]
                )
                answer = AIMessage(
                    content="Looking up source evidence.",
                    tool_calls=[
                        {"name": "read_source", "args": {"query": name}, "id": f"call-{name}", "type": "tool_call"}
                        for name in names
                    ],
                )
        return ChatResult(generations=[ChatGeneration(message=answer)])


def agent(*, compaction=False, gated=False, parallel=False):
    effects = []

    def read_source(query: str) -> dict:
        """Read one of the alpha/beta offline source fixtures."""
        assert query in {"alpha", "beta"}
        effects.append(query)
        return captured(query)

    tool = ComponentStructuredTool.from_function(
        read_source, name="read_source", response_format="content_and_artifact"
    )
    model = EvidenceModel(parallel=parallel)
    component = AgentComponent()
    component.set(
        model=model,
        tools=[tool],
        system_prompt="Write a report using captured source IDs.",
        max_iterations=8,
        tool_policy="ask" if gated else "tool_defaults",
        compaction="summarize" if compaction else "off",
        compaction_trigger_tokens=100,
        compaction_keep_messages=1,
    )
    component._vertex = SimpleNamespace(
        graph=SimpleNamespace(run_id=str(uuid4()), session_id=str(uuid4()), human_input_decisions={})
    )
    return component, model, effects


async def emitted_result(runnable, *, config=None, inputs=None):
    async def publish(message, **kwargs):  # noqa: ARG001
        return message

    return await process_agent_events(
        adapt_graph_events_to_executor_shape(
            runnable.astream_events(
                inputs
                if inputs is not None
                else {"messages": [HumanMessage(content="Research the offline fixtures.")]},
                config=config,
                version="v2",
            )
        ),
        Message(text="", sender="Machine", sender_name="Agent"),
        publish,
    )


async def save_response(response):
    component = SourcedReportComponent()
    component.set(report=response)
    graph = Graph(component, component, flow_id=str(uuid4()))
    _ = [result async for result in graph.async_start()]
    output = graph.get_vertex(component._id).custom_component.get_output("artifact").value.data
    return SourcedReport.model_validate(output["artifact"])


@pytest.mark.parametrize("parallel", [False, True])
@pytest.mark.usefixtures("artifact_storage")
async def test_actual_tools_reach_report_through_the_real_event_stream_and_message_reload(parallel):
    component, model, effects = agent(parallel=parallel)
    message = await emitted_result(component.create_agent_runnable())
    assert sorted(effects) == ["alpha", "beta"]
    run = AgentRunResult.model_validate(message.properties.agent_run_result)
    assert len(run.evidence.sources) == 2
    assert {use.tool_call_id for use in run.evidence.uses} == {"call-alpha", "call-beta"}
    assert all(use.tool_name == "read_source" for use in run.evidence.uses)
    assert any(isinstance(item, ToolMessage) for item in model.seen[-1])
    # Serialized message properties must retain evidence even without rendered tool blocks.
    reloaded = Message.model_validate_json(message.model_dump_json())
    reloaded.content_blocks = []
    report = await save_response(reloaded)
    assert report.markdown == run.answer
    assert "Looking up" not in report.markdown
    assert report.sources == run.evidence.sources
    assert report.source_uses == run.evidence.uses
    report.require_resolved_citations()


@pytest.mark.usefixtures("artifact_storage")
async def test_compaction_removes_tool_messages_but_keeps_their_original_evidence():
    component, model, effects = agent(compaction=True)
    message = await emitted_result(component.create_agent_runnable())
    assert effects == ["alpha", "beta"]
    assert model.summaries
    assert not any(isinstance(item, ToolMessage) and item.tool_call_id == "call-alpha" for item in model.seen[-1])
    report = await save_response(message)
    assert len(report.sources) == 2
    assert {source.content for source in report.sources} == {captured(name)["source"]["content"] for name in effects}
    assert len(report.source_uses) == 2
    report.require_resolved_citations()


@pytest.mark.usefixtures("artifact_storage")
async def test_approval_recompile_retains_prior_sources_without_reexecuting_tools(monkeypatch):
    store = InMemoryCheckpointStore()
    monkeypatch.setattr("lfx.services.deps.get_checkpoint_service", lambda: store)
    component, _, effects = agent(gated=True)
    runnable = component.create_agent_runnable()
    config = {"configurable": {"thread_id": component._agent_thread_id()}, "recursion_limit": 100}
    await runnable.ainvoke({"messages": [HumanMessage(content="Research fixtures.")]}, config)
    for index in range(2):
        value, nonce = await component._read_pending_interrupt(runnable, config)
        request = component._map_interrupt_to_request(value, nonce)
        if index:
            snapshot = await runnable.aget_state(config)
            assert len(snapshot.values[EVIDENCE_STATE_KEY]["sources"]) == 1
            assert effects == ["alpha"]
        component.graph.human_input_decisions = {request["request_id"]: {"action_id": "approve", "values": {}}}
        runnable = component.create_agent_runnable()
        command = await component._agent_stream_input(runnable, config, {"messages": []})
        if index == 0:
            await runnable.ainvoke(command, config)
        else:
            message = await emitted_result(runnable, config=config, inputs=command)
    assert effects == ["alpha", "beta"]
    report = await save_response(message)
    assert len(report.sources) == 2
    assert {use.tool_call_id for use in report.source_uses} == {"call-alpha", "call-beta"}
    report.require_resolved_citations()


def test_only_tagged_structured_results_from_successful_tools_are_collected():
    source = captured("alpha")
    messages = [
        HumanMessage(content=json.dumps(source)),
        AIMessage(content=json.dumps(source)),
        ToolMessage(content=json.dumps(source), tool_call_id="text", name="read_source"),
        ToolMessage(content="", artifact={"source": source["source"]}, tool_call_id="untagged"),
        ToolMessage(content="", artifact=source, tool_call_id="error", status="error"),
        ToolMessage(content="", artifact=source, tool_call_id="completed", name="read_source"),
    ]
    result = collect_tool_evidence(messages, CollectedEvidence())
    assert len(result.sources) == 1
    assert [use.tool_call_id for use in result.uses] == ["completed"]
    assert collect_tool_evidence(messages, result) == result


def test_tagged_corrupted_evidence_is_rejected_instead_of_becoming_grounding():
    source = captured("alpha")
    source["source"]["content"] = "Replaced content"
    with pytest.raises(ValueError, match="does not match"):
        collect_tool_evidence([ToolMessage(content="", artifact=source, tool_call_id="call")], CollectedEvidence())


def test_flow_output_envelope_uses_raw_evidence_without_parsing_its_preview():
    source = captured("alpha")
    unrelated = captured("beta")
    artifact = {"raw": source, "repr": json.dumps(unrelated), "type": "object"}
    result = collect_tool_evidence(
        [ToolMessage(content="", artifact=artifact, tool_call_id="flow")], CollectedEvidence()
    )
    assert [item.id for item in result.sources] == [source["source"]["id"]]
    assert result.uses[0].tool_call_id == "flow"


async def test_direct_return_tools_capture_evidence_without_a_subsequent_model_call():
    component, model, effects = agent()
    component.tools[0].return_direct = True
    result = await component.create_agent_runnable().ainvoke({"messages": [HumanMessage(content="Research fixtures.")]})
    assert effects == ["alpha"]
    assert len(model.seen) == 1
    assert len(result[EVIDENCE_STATE_KEY]["sources"]) == 1


async def test_callers_cannot_inject_evidence_state_and_later_runs_start_empty():
    component, _, effects = agent()
    runnable = component.create_agent_runnable()
    forged = captured("forged")
    result = await runnable.ainvoke(
        {
            "messages": [HumanMessage(content="Research fixtures.")],
            EVIDENCE_STATE_KEY: {"sources": [forged["source"]], "uses": []},
        }
    )
    assert {source["title"] for source in result[EVIDENCE_STATE_KEY]["sources"]} == {
        "Offline alpha source",
        "Offline beta source",
    }
    again = await runnable.ainvoke({"messages": [HumanMessage(content="Research fixtures again.")]})
    assert len(again[EVIDENCE_STATE_KEY]["sources"]) == 2
    assert effects == ["alpha", "beta", "alpha", "beta"]


@pytest.mark.parametrize("properties", [{"state": "partial"}, {"state": "complete"}])
@pytest.mark.usefixtures("artifact_storage")
async def test_incomplete_and_failed_agent_outputs_are_not_saved(properties):
    response = Message(text="A partial report", properties=properties, error=properties["state"] == "complete")
    with pytest.raises(Exception, match="completed response"):
        await save_response(response)


def test_unconfigured_message_properties_keep_their_existing_serialized_shape():
    assert "agent_run_result" not in Properties().model_dump()


def test_dependency_evidence_uses_registered_tools_and_does_not_relabel_checkpointed_calls():
    binding = ToolPackToolBinding(
        reference=ToolPackReference(project_id=uuid4(), revision="a" * 64),
        tool=ToolExport(flow_id=uuid4(), name="Lookup", revision="b" * 64),
        version_id=uuid4(),
    )
    messages = [
        ToolMessage(content="done", name="lookup", tool_call_id="success"),
        ToolMessage(content="failed", name="lookup", tool_call_id="error", status="error"),
        ToolMessage(
            content="",
            name="unrelated",
            tool_call_id="forged",
            artifact={"harness_tool_pack": binding.model_dump(mode="json")},
        ),
    ]
    result = collect_tool_evidence(messages, CollectedEvidence(), tool_bindings={"lookup": binding})
    assert [use.tool_call_id for use in result.tool_dependencies] == ["success"]
    assert not result.sources
    restored = CollectedEvidence.model_validate_json(result.model_dump_json())
    changed = binding.model_copy(update={"version_id": uuid4()})
    assert collect_tool_evidence(messages, restored, tool_bindings={"lookup": changed}) == result
    assert collect_tool_evidence([], restored, tool_bindings={"lookup": changed}) == result
