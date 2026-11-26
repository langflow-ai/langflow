"""Exercise activation and scope enforcement through real LangChain agent graphs."""

from copy import deepcopy
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from lfx.components.models_and_agents.agent_helpers.permission_middleware import ToolApprovalMiddleware
from lfx.components.models_and_agents.agent_helpers.skill_middleware import HarnessSkillMiddleware
from lfx.projects.skills import HarnessSkills, skill_pack_manifest
from lfx.projects.tool_packs import ToolPackReference
from pydantic import Field


class SkillModel(BaseChatModel):
    calls: list = Field(default_factory=list)
    seen: list = Field(default_factory=list)
    bound: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "skill-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        self.bound.append([t.name for t in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        index = len(self.seen)
        self.seen.append(deepcopy(messages))
        calls = self.calls[index] if index < len(self.calls) else []
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="" if calls else "done", tool_calls=calls))]
        )


def call(name, args=None, index=0):
    return {"name": name, "args": args or {}, "id": f"call-{index}", "type": "tool_call"}


@pytest.fixture
def setup():
    pack_id = uuid4()
    reference = ToolPackReference(project_id=pack_id, revision="a" * 64)
    manifest = skill_pack_manifest(
        uuid4(),
        "Research",
        {
            "skills": [
                {
                    "name": "verify-sources",
                    "description": "Verify source claims",
                    "instructions": "PRIVATE SKILL BODY",
                    "tool_packs": [reference.model_dump(mode="json")],
                }
            ]
        },
    )
    effects = []

    @tool
    def lookup(value: str) -> str:
        """Look up a source."""
        effects.append(value)
        return value

    lookup.metadata = {"harness_tool_pack": {"reference": reference.model_dump(mode="json")}}
    key = f"{manifest.reference.project_id}:verify-sources"
    return manifest, reference, lookup, key, effects


async def test_skill_body_loads_on_activation_and_tools_are_enforced(setup):
    manifest, _, lookup, key, effects = setup
    model = SkillModel(
        calls=[
            [call("lookup", {"value": "before"}, 1)],
            [call("activate_skill", {"skill": key}, 2)],
            [call("lookup", {"value": "during"}, 3)],
            [call("finish_skill", index=4)],
            [call("lookup", {"value": "after"}, 5)],
        ]
    )
    graph = create_agent(
        model=model,
        tools=[lookup],
        system_prompt="BASE INSTRUCTIONS",
        middleware=[HarnessSkillMiddleware(HarnessSkills(packs=(manifest,)), [lookup])],
    )
    result = await graph.ainvoke({"messages": [HumanMessage(content="Research")]})
    assert effects == ["during"]
    assert "PRIVATE SKILL BODY" not in str(model.seen[0])
    assert "PRIVATE SKILL BODY" in str(model.seen[2])
    assert "BASE INSTRUCTIONS" in str(model.seen[2])
    assert "PRIVATE SKILL BODY" not in str(model.seen[4])
    assert "lookup" not in model.bound[0]
    assert "lookup" in model.bound[2]
    assert "lookup" not in model.bound[4]
    errors = [m for m in result["messages"] if isinstance(m, ToolMessage) and m.status == "error"]
    assert len(errors) == 2
    assert result["harness_active_skill"] is None


async def test_activation_cannot_authorize_a_parallel_call(setup):
    manifest, _, lookup, key, effects = setup
    model = SkillModel(calls=[[call("activate_skill", {"skill": key}, 1), call("lookup", {"value": "race"}, 2)]])
    graph = create_agent(
        model=model, tools=[lookup], middleware=[HarnessSkillMiddleware(HarnessSkills(packs=(manifest,)), [lookup])]
    )
    await graph.ainvoke({"messages": [HumanMessage(content="Research")]})
    assert effects == []


async def test_global_tools_remain_available_without_activation(setup):
    manifest, ref, lookup, _, effects = setup
    model = SkillModel(calls=[[call("lookup", {"value": "global"}, 1)]])
    graph = create_agent(
        model=model,
        tools=[lookup],
        middleware=[
            HarnessSkillMiddleware(HarnessSkills(packs=(manifest,), global_tool_pack_ids=(ref.project_id,)), [lookup])
        ],
    )
    await graph.ainvoke({"messages": [HumanMessage(content="Research")]})
    assert effects == ["global"]


async def test_active_skill_survives_approval_and_does_not_bypass_rejection(setup):
    from langgraph.types import Command

    manifest, _, lookup, key, effects = setup
    model = SkillModel(calls=[[call("activate_skill", {"skill": key}, 1)], [call("lookup", {"value": "private"}, 2)]])
    graph = create_agent(
        model=model,
        tools=[lookup],
        checkpointer=InMemorySaver(),
        middleware=[
            ToolApprovalMiddleware({"lookup": {"allowed_decisions": ["approve", "reject"]}}, policy="ask"),
            HarnessSkillMiddleware(HarnessSkills(packs=(manifest,)), [lookup]),
        ],
    )
    config = {"configurable": {"thread_id": "skill-approval"}}
    result = await graph.ainvoke({"messages": [HumanMessage(content="Research")]}, config)
    assert result["__interrupt__"]
    assert effects == []
    resumed = await graph.ainvoke(Command(resume={"decisions": [{"type": "reject"}]}), config)
    assert effects == []
    assert resumed["harness_active_skill"]["key"] == key
    assert "PRIVATE SKILL BODY" in str(model.seen[-1])


def test_pack_rejects_duplicate_names_and_modified_snapshot(setup):
    manifest, _, _, _, _ = setup
    with pytest.raises(ValueError, match="unique"):
        skill_pack_manifest(uuid4(), "Bad", {"skills": [manifest.skills[0], manifest.skills[0]]})
    changed = manifest.model_dump(mode="json")
    changed["skills"][0]["instructions"] = "Changed"
    with pytest.raises(ValueError, match="revision"):
        HarnessSkills.model_validate({"packs": [changed]})


async def test_agent_component_runs_and_records_reviewed_skills(setup):
    from types import SimpleNamespace

    from lfx.components.models_and_agents.agent import AgentComponent

    manifest, _, lookup, key, effects = setup
    lookup.metadata["harness_tool_pack"].update(
        tool={"flow_id": str(uuid4()), "name": "lookup", "revision": "b" * 64},
        version_id=str(uuid4()),
    )
    model = SkillModel(
        calls=[
            [call("activate_skill", {"skill": key}, 1)],
            [call("lookup", {"value": "component"}, 2)],
        ]
    )
    component = AgentComponent()
    component.set(
        model=model, tools=[lookup], max_iterations=5, skill_bindings=HarnessSkills(packs=(manifest,)).model_dump_json()
    )
    component._vertex = SimpleNamespace(graph=SimpleNamespace(run_id=str(uuid4()), session_id=str(uuid4())))
    graph = component.create_agent_runnable(allow_interrupts=False)
    result = await graph.ainvoke({"messages": [HumanMessage(content="Research")]}, {"recursion_limit": 70})
    assert effects == ["component"]
    assert result["harness_run_configurations"][0]["skills"]["packs"][0]["reference"] == manifest.reference.model_dump(
        mode="json"
    )


async def test_deny_all_tools_also_blocks_instruction_only_skill_activation():
    from lfx.components.models_and_agents.agent import AgentComponent

    manifest = skill_pack_manifest(
        uuid4(),
        "Writing",
        {"skills": [{"name": "write", "description": "Write prose", "instructions": "PRIVATE BODY"}]},
    )
    model = SkillModel(calls=[[call("activate_skill", {"skill": f"{manifest.reference.project_id}:write"}, 1)]])
    component = AgentComponent()
    component.set(
        model=model,
        tools=[],
        tool_policy="deny",
        max_iterations=3,
        skill_bindings=HarnessSkills(packs=(manifest,)).model_dump_json(),
    )
    graph = component.create_agent_runnable(allow_interrupts=False)
    result = await graph.ainvoke({"messages": [HumanMessage(content="Write")]})
    assert "PRIVATE BODY" not in str(model.seen)
    assert not result.get("harness_active_skill")
    assert result["harness_run_configurations"][0]["tool_retry_count"] == 2
    assert any(isinstance(message, ToolMessage) and message.status == "error" for message in result["messages"])
