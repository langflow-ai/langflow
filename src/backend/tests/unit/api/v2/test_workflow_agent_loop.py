"""A harness whose AgenticLoop slot is bound runs that loop flow through the public Workflows API.

Only the provider model is replaced. The loop flow, the Hook, Permission, Context and Compaction flows, the
skill pack and its tool pack are saved and reviewed through the project API and run for real.
"""

import json
from copy import deepcopy

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.components.input_output import ChatOutput
from lfx.components.models_and_agents import AgentContextComponent, AgentStepComponent, ExecuteToolComponent
from lfx.graph import Graph
from lfx.projects.baselines import compaction_baseline, context_baseline, hook_baseline, permission_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.compaction import compaction_outputs
from lfx.projects.context import context_outputs
from lfx.projects.hooks import hook_outputs
from lfx.projects.loop import loop_outputs
from lfx.projects.permissions import permission_outputs
from pydantic import Field

from tests.unit.api.v1.conftest import allow_edited_component_code  # noqa: F401
from tests.unit.api.v1.test_harness_skill_packs import skill_harness, skills_of  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import create_flow, save_config, stored_flow
from tests.unit.api.v2.test_workflow_skills import WorkflowSkillModel, wait_status, workflow_harness  # noqa: F401

REVIEWED_CONTEXT = "Use the reviewed sources."
HOOKED = "HOOKED RESULT"


class LoopSkillModel(WorkflowSkillModel):
    """The skill model with a script that counts its own calls, because Compaction drops the tool results.

    It also answers the Compaction flow's summary request and does not record it as an Agent call.
    """

    turns: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        if "Messages to summarize:" in str(messages[0].content):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Earlier work was reviewed."))])
        self.seen.append(deepcopy(messages))
        sequence = [("activate_skill", {"skill": self.skill_key}), (self.tool_name, self.tool_args)]
        if self.turns < len(sequence):
            name, args = sequence[self.turns]
            message = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{self.turns}"}])
        else:
            message = AIMessage(content="Research complete")
        self.turns += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def loop_flow_data() -> dict:
    """Agent Context -> While Loop <-> Agent Step / Execute Tool, with Last Message on a Chat Output."""
    context = AgentContextComponent(_id="AgentContext-ac001")
    loop = WhileLoopComponent(_id="WhileLoop-wl001")
    loop.set(input_value=context.build_messages, max_iterations=8)
    step = AgentStepComponent(_id="AgentStep-as001")
    step.set(messages=loop.loop_output)
    execute = ExecuteToolComponent(_id="ExecuteTool-et001")
    execute.set(messages=step.get_tool_calls)
    loop.set(loop=execute.execute_tools)
    chat_output = ChatOutput(_id="ChatOutput-co001")
    chat_output.set(input_value=loop.last_message_output)
    return Graph(context, chat_output).dump()["data"]


def bound(flow_id, data, output, **extra):
    return {
        "flow_id": flow_id,
        "node_id": output["node_id"],
        "output_name": output["output_name"],
        "revision": flow_revision(data),
        **extra,
    }


@pytest.fixture
async def loop_harness(client, logged_in_headers, active_user, workflow_harness):  # noqa: F811
    """Save the loop flow and one flow for each control into the harness project and bind them."""
    project, agent, pack, _, config, definition = workflow_harness

    async def build(permission_policy="tool_defaults"):
        loop = loop_flow_data()
        loop_id = await create_flow(active_user, folder_id=project, data=loop, name="Loop")
        hook = hook_baseline()["data"]
        template = hook["nodes"][-1]["data"]["node"]["template"]
        template["action"]["value"] = "modify"
        # The Hook runs before every tool call, so its arguments keep the skill key for activate_skill.
        template["modified_payload"]["value"] = json.dumps(
            {
                "args": {
                    "skill": f"{pack}:{definition['name']}",
                    "flow_tweak_data": {"ChatInput-echo~input_value": HOOKED},
                }
            }
        )
        hook_id = await create_flow(active_user, folder_id=project, data=hook, name="Tool hook")
        permission = permission_baseline({"tool_policy": permission_policy})["data"]
        permission_id = await create_flow(active_user, folder_id=project, data=permission, name="Permissions")
        context = context_baseline()["data"]
        terminal = context["nodes"][-1]["data"]["node"]["template"]
        terminal["code"]["value"] = terminal["code"]["value"].replace(
            "return messages_to_table(prepared)",
            f'prepared[0] = prepared[0].model_copy(update={{"content": "{REVIEWED_CONTEXT} " + prepared[0].text}})\n'
            "        return messages_to_table(prepared)",
        )
        context_id = await create_flow(active_user, folder_id=project, data=context, name="Context")
        compaction = compaction_baseline({"compaction_keep_messages": 1})["data"]
        compaction_id = await create_flow(active_user, folder_id=project, data=compaction, name="Compaction")
        bindings = {
            "agentic_loop": bound(loop_id, loop, loop_outputs(loop)[0]),
            "hooks": [
                bound(
                    hook_id, hook, hook_outputs(hook)[0], on_event="before_tool_call", mode="control", on_failure="stop"
                )
            ],
            "tool_policy": bound(permission_id, permission, permission_outputs(permission)[0]),
            "context_strategy": bound(context_id, context, context_outputs(context)[0]),
            "compaction": bound(compaction_id, compaction, compaction_outputs(compaction)[0], trigger_tokens=1),
        }
        await save_config(client, logged_in_headers, project, {**config, "flow_bindings": bindings})
        return agent, loop_id

    return build


async def run_harness(client, created_api_key, agent, monkeypatch):
    flow = await stored_flow(agent)
    pack = skills_of(flow).packs[0]
    model = LoopSkillModel(skill_key=f"{pack.reference.project_id}:{pack.skills[0].name}", probe_scope=False)
    for target in ("lfx.base.models.unified_models.get_llm", "lfx.components.models_and_agents.agent.get_llm"):
        monkeypatch.setattr(target, lambda **_kwargs: model)
    headers = {"x-api-key": created_api_key.api_key}
    # A Permission flow can pause for a decision, so the API runs the harness in background mode.
    started = await client.post(
        "/api/v2/workflows",
        headers=headers,
        json={"flow_id": agent, "input_value": "Research this question", "mode": "background"},
    )
    assert started.status_code == 200, started.text
    return model, await wait_status(client, headers, started.json()["job_id"], {"completed"})


@pytest.mark.usefixtures("allow_edited_component_code")
async def test_a_harness_runs_its_bound_loop_flow_under_every_control(
    client, created_api_key, loop_harness, monkeypatch
):
    agent, loop_id = await loop_harness()
    node = next(n for n in (await stored_flow(agent)).data["nodes"] if n["id"] == "Agent-1")["data"]
    assert json.loads(node["node"]["template"]["loop_binding"]["value"])["flow_id"] == loop_id

    model, done = await run_harness(client, created_api_key, agent, monkeypatch)

    assert done["output"]["text"] == "Research complete"
    assert model.turns == 3
    assert all(REVIEWED_CONTEXT in str(call) for call in model.seen)  # Context rewrote every request
    assert "Use original sources." not in str(model.seen[0])
    assert any("Use original sources." in str(call) for call in model.seen[1:])  # the activated Skill's instructions
    results = [m for call in model.seen for m in call if isinstance(m, ToolMessage) and m.name == model.tool_name]
    assert [HOOKED in m.content and "SOURCE RESULT" not in m.content for m in results] == [True]  # the Hook's arguments
    assert "Earlier work was reviewed." in str(model.seen[-1])  # Compaction replaced the older messages


@pytest.mark.usefixtures("allow_edited_component_code")
async def test_a_permission_flow_that_rejects_stops_the_loops_tool(client, created_api_key, loop_harness, monkeypatch):
    agent, _ = await loop_harness("deny")

    model, done = await run_harness(client, created_api_key, agent, monkeypatch)

    assert done["output"]["text"] == "Research complete"
    results = [m for call in model.seen for m in call if isinstance(m, ToolMessage) and m.name == model.tool_name]
    assert results
    assert {m.status for m in results} == {"error"}
    assert not any(HOOKED in str(m.content) for m in results)


class PlainModel(BaseChatModel):
    """Answers `answer N` and records what each call saw."""

    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "plain-loop-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=f"answer {len(self.seen)}"))])


async def two_turns(client, created_api_key, agent, monkeypatch, session):
    model = PlainModel()
    for target in ("lfx.base.models.unified_models.get_llm", "lfx.components.models_and_agents.agent.get_llm"):
        monkeypatch.setattr(target, lambda **_kwargs: model)
    headers = {"x-api-key": created_api_key.api_key}
    for text in ("first question", "second question"):
        started = await client.post(
            "/api/v2/workflows",
            headers=headers,
            json={"flow_id": agent, "input_value": text, "mode": "background", "session_id": session},
        )
        assert started.status_code == 200, started.text
        await wait_status(client, headers, started.json()["job_id"], {"completed"})
    return [[(m.type, str(m.content)) for m in call] for call in model.seen]


@pytest.mark.usefixtures("allow_edited_component_code")
async def test_the_loops_model_sees_the_same_two_turn_session_as_the_packaged_agents_model(
    client,
    logged_in_headers,
    created_api_key,
    active_user,
    workflow_harness,  # noqa: F811
    monkeypatch,
):
    project, agent, _, _, config, _ = workflow_harness
    packaged = await two_turns(client, created_api_key, agent, monkeypatch, "packaged-session")
    loop = loop_flow_data()
    loop_id = await create_flow(active_user, folder_id=project, data=loop, name="Loop")
    binding = bound(loop_id, loop, loop_outputs(loop)[0])
    await save_config(client, logged_in_headers, project, {**config, "flow_bindings": {"agentic_loop": binding}})

    looped = await two_turns(client, created_api_key, agent, monkeypatch, "loop-session")

    assert [kind for kind, _ in packaged[1]] == ["system", "human", "ai", "human"]
    assert looped == packaged
