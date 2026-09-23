"""Real workflow routing, skill scope, and nested tools on a database-free host."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from lfx.base.agents.hooks import HookBinding
from lfx.cli.harness_artifacts import mount_candidate
from lfx.cli.serve_app import FlowRegistry, create_multi_serve_app
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.graph import Graph
from lfx.graph.flow_builder import add_component, add_connection
from lfx.projects.baselines import build_slot_baseline
from lfx.projects.bindings import FlowBinding, compose_instructions, flow_revision, instruction_outputs
from lfx.projects.context import ContextBinding, context_outputs
from lfx.projects.hooks import hook_outputs
from lfx.projects.runtime_artifacts import build_candidate
from lfx.projects.skills import HarnessSkills, skill_pack_manifest
from lfx.projects.tool_packs import (
    FlowDependency,
    FlowDependencyVersion,
    ToolExport,
    ToolPackReference,
    ToolPackToolBinding,
)
from lfx.projects.tools import compose_tools, prepare_tool_template
from pydantic import Field


class CandidateModel(BaseChatModel):
    skill_key: str
    tool_name: str = ""
    tweak_key: str = "ChatInput-query~input_value"
    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "candidate-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        for tool in tools:
            if (tool.metadata or {}).get("harness_tool_pack"):
                self.tool_name = tool.name
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        step = sum(isinstance(m, ToolMessage) for m in messages)
        sequence = [
            (self.tool_name, {"flow_tweak_data": {self.tweak_key: "SOURCE RESULT"}}),
            ("activate_skill", {"skill": self.skill_key}),
            (self.tool_name, {"flow_tweak_data": {self.tweak_key: "SOURCE RESULT"}}),
            ("finish_skill", {}),
            (self.tool_name, {"flow_tweak_data": {self.tweak_key: "SOURCE RESULT"}}),
        ]
        if step < len(sequence):
            name, args = sequence[step]
            message = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{step}"}])
        else:
            message = AIMessage(
                content="Research complete: " + json.dumps([m.content for m in messages if isinstance(m, ToolMessage)])
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


def frontend(component):
    node = component().to_frontend_node()["data"]["node"]
    node["field_order"] = [item.name for item in component.inputs]
    return node


def research_candidate():
    leaf_id, tool_id, root_id = [str(uuid4()) for _ in range(3)]
    registry = {
        "RunFlow": frontend(RunFlowComponent),
        "ChatOutput": frontend(ChatOutput),
        "Agent": frontend(AgentComponent),
        "ChatInput": frontend(ChatInput),
    }
    leaf = {"id": leaf_id, "name": "Evidence", "data": {"nodes": [], "edges": []}}
    add_component(leaf, "ChatInput", registry, component_id="ChatInput-evidence")
    add_component(leaf, "ChatOutput", registry, component_id="ChatOutput-evidence")
    add_connection(leaf, "ChatInput-evidence", "message", "ChatOutput-evidence", "input_value")
    nested = {"id": tool_id, "name": "Lookup", "data": {"nodes": [], "edges": []}}
    nested_registry = {**registry, "RunFlow": prepare_tool_template(leaf)}
    nested_registry["RunFlow"]["outputs"] = [
        output.model_dump() for output in RunFlowComponent()._format_flow_outputs(Graph.from_payload(leaf["data"]))
    ]
    runner = add_component(nested, "RunFlow", nested_registry, component_id="RunFlow-nested")
    query = add_component(nested, "ChatInput", registry, component_id="ChatInput-query")
    nested["data"]["nodes"][-1]["data"]["node"]["template"]["input_value"]["value"] = "SOURCE RESULT"
    out = add_component(nested, "ChatOutput", registry, component_id="ChatOutput-tool")
    add_connection(nested, query["id"], "message", runner["id"], "ChatInput-evidence~input_value")
    add_connection(nested, runner["id"], "ChatOutput-evidence~message", out["id"], "input_value")
    pack = ToolPackReference(project_id=uuid4(), revision="a" * 64)
    skill = skill_pack_manifest(
        uuid4(),
        "Research",
        {
            "skills": [
                {
                    "name": "research",
                    "description": "Research",
                    "instructions": "Use original sources.",
                    "tool_packs": [pack.model_dump(mode="json")],
                }
            ]
        },
    )
    dependency = FlowDependency(flow_id=leaf_id, name="Evidence", revision=flow_revision(leaf["data"]))
    binding = ToolPackToolBinding(
        reference=pack,
        version_id=uuid4(),
        tool=ToolExport(
            flow_id=tool_id, name="Lookup", revision=flow_revision(nested["data"]), dependencies=(dependency,)
        ),
        dependency_versions=(FlowDependencyVersion(flow=dependency, version_id=uuid4()),),
    )
    root = {"id": root_id, "name": "Research", "data": {"nodes": [], "edges": []}}
    add_component(root, "ChatInput", registry, component_id="ChatInput-request")
    add_component(root, "Agent", registry, component_id="Agent-research")
    add_component(root, "ChatOutput", registry, component_id="ChatOutput-report")
    agent = root["data"]["nodes"][1]["data"]["node"]["template"]
    agent["model"]["value"] = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]
    agent["add_current_date_tool"]["value"] = False
    agent["skill_bindings"]["value"] = HarnessSkills(packs=(skill,)).model_dump_json()
    add_connection(root, "ChatInput-request", "message", "Agent-research", "input_value")
    root["data"] = compose_tools(
        root["data"],
        project_id=str(uuid4()),
        agent_id="Agent-research",
        targets=[{**nested, "tool_pack": binding.model_dump(mode="json")}],
    )
    add_connection(root, "Agent-research", "response", "ChatOutput-report", "input_value")
    customizations = []
    for slot, output_choices, binding_class, input_name in (
        ("hook", hook_outputs, HookBinding, "hook_bindings"),
        ("context", context_outputs, ContextBinding, "context_binding"),
        ("instructions", instruction_outputs, FlowBinding, "system_prompt"),
    ):
        baseline = build_slot_baseline(f"builtin:{slot}", "Candidate instructions: cite original evidence.")
        baseline["id"] = str(uuid4())
        choice = output_choices(baseline["data"])[0]
        binding = binding_class(
            flow_id=baseline["id"],
            node_id=choice["node_id"],
            output_name=choice["output_name"],
            revision=flow_revision(baseline["data"]),
            **({"on_event": "before_llm_call"} if slot == "hook" else {}),
        )
        if slot == "instructions":
            root["data"] = compose_instructions(
                root["data"], project_id=str(uuid4()), agent_id="Agent-research", target=baseline, binding=binding
            )
        else:
            template = next(node for node in root["data"]["nodes"] if node["id"] == "Agent-research")["data"]["node"][
                "template"
            ]
            template[input_name]["value"] = json.dumps(
                [binding.model_dump()] if slot == "hook" else binding.model_dump()
            )
        customizations.append(baseline)
    return build_candidate(root_id, [root, nested, leaf, *customizations]), f"{skill.reference.project_id}:research"


@pytest.mark.parametrize(("mode", "protocol"), [("sync", "langflow"), ("stream", "langflow"), ("stream", "agui")])
def test_candidate_workflows_are_database_free_and_dependencies_private(monkeypatch, mode, protocol):
    import importlib.util

    assert importlib.util.find_spec("langflow") is None
    candidate, skill = research_candidate()
    model = CandidateModel(skill_key=skill)
    monkeypatch.setattr("lfx.base.models.unified_models.get_llm", lambda **_kwargs: model)
    monkeypatch.setattr("lfx.components.models_and_agents.agent.get_llm", lambda **_kwargs: model)
    monkeypatch.setenv("LANGFLOW_API_KEY", "artifact-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "destination-test-key")
    registry = FlowRegistry()
    mount_candidate(registry, candidate.archive(), expected_digest=candidate.digest)
    root = candidate.manifest["entrypoints"][0]
    assert [meta.id for meta in registry.list_metas()] == [root]
    for identity in candidate.definitions:
        if identity != root:
            assert registry.get(identity) is None
    with TestClient(create_multi_serve_app(registry=registry)) as client:
        for _ in range(2):
            response = client.post(
                "/api/v2/workflows",
                headers={"x-api-key": "artifact-test-key"},
                json={
                    "flow_id": root,
                    "input_value": "Research",
                    "mode": mode,
                    "stream_protocol": protocol,
                },
            )
            assert response.status_code == 200, response.text
            assert "Research complete" in response.text, response.text
            results = [m for m in model.seen[-1] if isinstance(m, ToolMessage) and m.name == model.tool_name]
            assert [m.status for m in results] == ["error", "success", "error"], results
            assert "SOURCE RESULT" in results[1].content
            assert "Candidate instructions: cite original evidence." in str(model.seen[-1])


@pytest.mark.parametrize(("mode", "protocol"), [("sync", "langflow"), ("stream", "langflow"), ("stream", "agui")])
def test_exported_editor_candidate(monkeypatch, mode, protocol):
    """Invoked by the backend acceptance test in a separate LFX-only environment."""
    import importlib.util
    import os
    from pathlib import Path

    from lfx.projects.runtime_artifacts import read_candidate
    from lfx.projects.skills import parse_harness_skills

    artifact = os.environ.get("LFX_TEST_CANDIDATE")
    if not artifact:
        pytest.skip("Run backend candidate acceptance with LFX_CANDIDATE_TEST_PYTHON set to an LFX-only environment")
    assert importlib.util.find_spec("langflow") is None
    content = Path(artifact).read_bytes()
    candidate = read_candidate(content)
    root = candidate.manifest["entrypoints"][0]
    agent = next(node for node in candidate.definitions[root]["data"]["nodes"] if node["data"]["type"] == "Agent")
    skill = parse_harness_skills(agent["data"]["node"]["template"]["skill_bindings"]["value"]).packs[0]
    model = CandidateModel(
        skill_key=f"{skill.reference.project_id}:{skill.skills[0].name}", tweak_key="ChatInput-echo~input_value"
    )
    monkeypatch.setattr("lfx.base.models.unified_models.get_llm", lambda **_kwargs: model)
    monkeypatch.setattr("lfx.components.models_and_agents.agent.get_llm", lambda **_kwargs: model)
    monkeypatch.setenv("LANGFLOW_API_KEY", "artifact-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "destination-test-key")
    registry = FlowRegistry()
    mount_candidate(registry, content)
    assert len(registry.list_metas()) == 1
    with TestClient(create_multi_serve_app(registry=registry)) as client:
        response = client.post(
            "/api/v2/workflows",
            headers={"x-api-key": "artifact-test-key"},
            json={
                "flow_id": root,
                "input_value": "Research",
                "mode": mode,
                "stream_protocol": protocol,
            },
        )
    assert response.status_code == 200, response.text
    assert "Research complete" in response.text, response.text
    results = [m for m in model.seen[-1] if isinstance(m, ToolMessage) and m.name == model.tool_name]
    assert [m.status for m in results] == ["error", "success", "error"], results
    assert "SOURCE RESULT" in results[1].content


async def test_cli_loads_same_private_candidate_after_worker_restart(tmp_path, monkeypatch):
    from lfx.cli.commands import build_registry_from_paths
    from lfx.cli.flow_store import FilesystemFlowStore

    candidate, _ = research_candidate()
    monkeypatch.setenv("OPENAI_API_KEY", "destination-test-key")
    path = tmp_path / "research.lfpkg"
    path.write_bytes(candidate.archive())
    store = FilesystemFlowStore(tmp_path / "store")
    for _ in range(2):
        registry = await build_registry_from_paths([path], lambda _: None, check_variables=False, store=store)
        registry.warm_from_store()
        assert len(registry.list_metas()) == 1
        root = candidate.manifest["entrypoints"][0]
        graph, _ = registry.get(root)
        assert graph.runtime_candidate.digest == candidate.digest
        assert store.list_ids() == []


def test_workflows_rechecks_destination_before_starting_a_stream(monkeypatch):
    candidate, _ = research_candidate()
    monkeypatch.setenv("LANGFLOW_API_KEY", "artifact-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "destination-test-key")
    registry = FlowRegistry()
    mount_candidate(registry, candidate.archive())
    monkeypatch.delenv("OPENAI_API_KEY")
    with TestClient(create_multi_serve_app(registry=registry)) as client:
        response = client.post(
            "/api/v2/workflows",
            headers={"x-api-key": "artifact-test-key"},
            json={
                "flow_id": candidate.manifest["entrypoints"][0],
                "mode": "stream",
                "input_value": "Research",
            },
        )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "HARNESS_CANDIDATE_NOT_READY"
    assert "OPENAI_API_KEY" in response.text
